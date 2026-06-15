from __future__ import annotations

import json
import shutil
import tarfile
import tempfile
from pathlib import Path

import grpc
import yaml

from edera_core.bootstrap import discover_available_extensions
from edera_core.config.loader import _load_runtime_base_config
from edera_core.extension_manager import ExtensionManager
from edera_core.manifest import parse_manifest
from edera_core.service_common import json_response
from edera_core.storage.import_export import import_entities_from_yaml
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
            result = await _manager(self.daemon).install(
                request.name, overwrite=bool(getattr(request, "overwrite", False)), installed_by="grpc"
            )
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

    async def Delete(self, request, context):
        await _identity(context)
        async with self.daemon.controller._factory()() as session:
            if await get_installed_extension(session, request.name) is not None:
                await context.abort(
                    grpc.StatusCode.FAILED_PRECONDITION, f"extension is installed, uninstall first: {request.name}"
                )
        target = _extensions_dirs(self.daemon)[-1] / request.name
        if not target.exists():
            await context.abort(grpc.StatusCode.NOT_FOUND, f"extension source not found: {request.name}")
        shutil.rmtree(target)
        return json_response(self.pb2, {"deleted": True, "name": request.name})

    async def ImportEntities(self, request, context):
        await _identity(context)
        config = _load_runtime_base_config(self.daemon.config_dir)
        try:
            entities_payload = _extract_entities_payload(request.content)
        except (tarfile.TarError, ValueError) as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        async with self.daemon.controller._factory()() as session:
            result = await import_entities_from_yaml(session, entities_payload, config.entity_types)
            await session.commit()
        return json_response(self.pb2, {"imported": result.imported, "updated": result.updated})


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


def _extract_entities_payload(content: bytes) -> Path:
    with tempfile.TemporaryDirectory() as tmp:
        extract_dir = Path(tmp)
        _extract_tar_content(content, extract_dir)
        manifests = list(extract_dir.rglob("manifest.yaml"))
        if len(manifests) != 1:
            raise ValueError("import package must contain exactly one manifest.yaml")
        manifest_path = manifests[0]
        manifest_root = manifest_path.parent
        manifest_data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        imports = manifest_data.get("imports") if isinstance(manifest_data, dict) else None
        entity_paths = imports.get("entities") if isinstance(imports, dict) else None
        if not isinstance(entity_paths, list) or not entity_paths:
            raise ValueError("import manifest declares no entities")
        entities = []
        for entity_path in entity_paths:
            document = yaml.safe_load((manifest_root / entity_path).read_text(encoding="utf-8")) or {}
            if isinstance(document, dict):
                entities.append(document)
        merged = extract_dir / "entities.yaml"
        merged.write_text(yaml.safe_dump({"entities": entities}, allow_unicode=True, sort_keys=False), encoding="utf-8")
        target = Path(tempfile.mkdtemp()) / "entities.yaml"
        shutil.copy2(merged, target)
        return target


def _extract_tar_content(content: bytes, target: Path) -> None:
    import io

    with tarfile.open(fileobj=io.BytesIO(content), mode="r:gz") as archive:
        for member in archive.getmembers():
            member_path = Path(member.name)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise ValueError("unsafe import package path")
        archive.extractall(target)
