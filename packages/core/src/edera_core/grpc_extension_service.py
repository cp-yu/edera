from __future__ import annotations

import json
from pathlib import Path

import grpc

from edera_core.bootstrap import discover_available_extensions
from edera_core.config.loader import _load_runtime_base_config
from edera_core.extension_manager import ExtensionManager
from edera_core.manifest import parse_manifest
from edera_core.service_common import json_response
from edera_core.storage.repository import get_installed_extension, list_installed_extensions


class _ExtensionService:
    def __init__(self, daemon) -> None:
        self.daemon = daemon
        self.pb2 = daemon.pb2

    async def ListAvailable(self, _request, context):
        await _identity(context)
        items = [
            {
                "name": manifest.name,
                "version": manifest.version,
                "description": manifest.description,
                "depends": list(manifest.depends),
            }
            for manifest in discover_available_extensions(_extensions_dirs(self.daemon))
        ]
        return json_response(self.pb2, {"extensions": items})

    async def ListInstalled(self, _request, context):
        await _identity(context)
        async with self.daemon.controller._factory()() as session:
            rows = [
                {
                    "name": row.name,
                    "version": row.version,
                    "enabled": row.enabled,
                    "installed_by": row.installed_by,
                    "created_at": row.created_at,
                }
                for row in await list_installed_extensions(session)
            ]
        return json_response(self.pb2, {"extensions": rows})

    async def Show(self, request, context):
        await _identity(context)
        async with self.daemon.controller._factory()() as session:
            row = await get_installed_extension(session, request.name)
        if row is not None:
            return json_response(self.pb2, {"manifest": row.manifest_data, "import_records": row.import_record_data})
        for root in _extensions_dirs(self.daemon):
            manifest_path = root / request.name / "manifest.yaml"
            if manifest_path.exists():
                manifest = parse_manifest(manifest_path)
                return json_response(
                    self.pb2,
                    {
                        "manifest": {
                            "name": manifest.name,
                            "version": manifest.version,
                            "description": manifest.description,
                            "depends": list(manifest.depends),
                            "handlers": [handler.__dict__ for handler in manifest.handlers],
                            "entity_types": [entity_type.__dict__ for entity_type in manifest.entity_types],
                            "imports": {"entities": list(manifest.entity_imports)},
                        },
                        "import_records": [],
                    },
                )
        await context.abort(grpc.StatusCode.NOT_FOUND, f"extension {request.name} not found")

    async def Install(self, request, context):
        await _identity(context)
        try:
            result = await _manager(self.daemon).install(request.name, installed_by="grpc")
        except FileNotFoundError as exc:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(exc))
        except ValueError as exc:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, str(exc))
        await _refresh(self.daemon)
        return json_response(self.pb2, result)

    async def Uninstall(self, request, context):
        await _identity(context)
        payload = json.loads(request.json or "{}")
        strategy = payload.get("strategy")
        if not isinstance(strategy, str) or not strategy:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "strategy is required")
        try:
            result = await _manager(self.daemon).uninstall(request.name, strategy)
        except ValueError as exc:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, str(exc))
        await _refresh(self.daemon)
        return json_response(self.pb2, result)

    async def Reactivate(self, request, context):
        await _identity(context)
        async with self.daemon.controller._factory()() as session:
            row = await get_installed_extension(session, request.name)
            if row is None:
                await context.abort(grpc.StatusCode.NOT_FOUND, f"extension {request.name} not found")
            row.enabled = True
            session.add(row)
            await session.commit()
        await _refresh(self.daemon)
        return json_response(self.pb2, {"enabled": True})


def _manager(daemon) -> ExtensionManager:
    config = _load_runtime_base_config(daemon.config_dir)
    return ExtensionManager(
        extensions_dir=_extensions_dirs(daemon)[-1],
        handlers_dir=daemon.controller.handlers_dir,
        engine=daemon.controller.engine,
        config_entity_types=config.entity_types,
    )


def _extensions_dirs(daemon) -> list[Path]:
    return list(getattr(daemon.controller, "extensions_dirs", [Path("extensions")]))


async def _refresh(daemon) -> None:
    config = _load_runtime_base_config(daemon.config_dir)
    await daemon.controller.install_snapshot(config, await daemon.controller.load_bootstrap())


async def _identity(context) -> str:
    from edera_core.server import _identity as identity

    return await identity(context)
