from pathlib import Path
import json
import tarfile

import grpc
import pytest

from edera_core.dag_controller import DagController
from edera_core.grpc_extension_service import _ExtensionService
from edera_core.proto import edera_pb2 as pb2
from edera_core.storage.repository import get_installed_extension, save_ordinary_entity
from edera_core.config.schema import EntityConfig


class _Context:
    def __init__(self) -> None:
        self.aborted: list[tuple[grpc.StatusCode, str]] = []

    def invocation_metadata(self):
        return (("x-edera-identity", "human:test"),)

    def auth_context(self):
        return {}

    async def abort(self, code, message):
        self.aborted.append((code, message))
        raise _AbortError(code, message)


class _AbortError(Exception):
    def __init__(self, code, message) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@pytest.mark.asyncio
async def test_install_rpc(tmp_path: Path) -> None:
    config_dir = _write_config(tmp_path)
    (tmp_path / "extensions").mkdir()
    controller = DagController(config_dir, extensions_dirs=[tmp_path / "extensions"])
    await controller.start(run_startup=False)
    try:
        _write_extension(tmp_path / "extensions" / "demo")
        daemon = type("Daemon", (), {"pb2": pb2, "controller": controller, "config_dir": config_dir})()
        service = _ExtensionService(daemon)

        response = await service.Install(pb2.ExtensionInstallRequest(name="demo", overwrite=False), _Context())

        async with controller._factory()() as session:
            installed = await get_installed_extension(session, "demo")

        assert response.json
        assert installed is not None
        assert installed.name == "demo"
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_install_workflow_extension_rpc(tmp_path: Path) -> None:
    config_dir = _write_config(tmp_path)
    (tmp_path / "extensions").mkdir()
    controller = DagController(config_dir, extensions_dirs=[tmp_path / "extensions"])
    await controller.start(run_startup=False)
    try:
        _write_workflow_extension(tmp_path / "extensions" / "workflow")
        daemon = type("Daemon", (), {"pb2": pb2, "controller": controller, "config_dir": config_dir})()
        service = _ExtensionService(daemon)

        response = await service.Install(pb2.ExtensionInstallRequest(name="workflow", overwrite=False), _Context())
        body = json.loads(response.json)

        async with controller._factory()() as session:
            installed = await get_installed_extension(session, "workflow")

        assert body["providers"] == 1
        assert installed is not None
        assert installed.manifest_data["handlers"][0]["name"] == "workflow.reader.read"
        assert (tmp_path / "data" / "handlers" / "workflow.reader" / "handler.py").exists()
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_install_rpc_reports_unmatched_glob(tmp_path: Path) -> None:
    config_dir = _write_config(tmp_path)
    root = tmp_path / "extensions" / "workflow"
    root.mkdir(parents=True)
    (root / "manifest.yaml").write_text(
        "name: workflow\n"
        "version: 0.1.0\n"
        "type: workflow_extension\n"
        "imports:\n"
        "  providers:\n"
        "    - _providers/*/manifest.yaml\n",
        encoding="utf-8",
    )
    controller = DagController(config_dir, extensions_dirs=[tmp_path / "extensions"])
    await controller.start(run_startup=False)
    try:
        daemon = type("Daemon", (), {"pb2": pb2, "controller": controller, "config_dir": config_dir})()
        service = _ExtensionService(daemon)

        with pytest.raises(_AbortError, match=r"glob pattern matched no files: _providers/\*/manifest.yaml"):
            await service.Install(pb2.ExtensionInstallRequest(name="workflow", overwrite=False), _Context())
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_install_overwrite_refreshes_runtime(tmp_path: Path) -> None:
    config_dir = _write_config(tmp_path)
    (tmp_path / "extensions").mkdir()
    controller = DagController(config_dir, extensions_dirs=[tmp_path / "extensions"])
    await controller.start(run_startup=False)
    try:
        _write_extension(tmp_path / "extensions" / "demo")
        daemon = type("Daemon", (), {"pb2": pb2, "controller": controller, "config_dir": config_dir})()
        service = _ExtensionService(daemon)
        await service.Install(pb2.ExtensionInstallRequest(name="demo", overwrite=False), _Context())

        body = json.loads(
            (await service.Install(pb2.ExtensionInstallRequest(name="demo", overwrite=True), _Context())).json
        )

        assert body["overwrite"] is True
        assert body["data_warning"]

        context = _Context()
        with pytest.raises(_AbortError):
            await service.Install(pb2.ExtensionInstallRequest(name="demo", overwrite=False), context)
        assert context.aborted[-1][0] == grpc.StatusCode.FAILED_PRECONDITION
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_delete_rpc(tmp_path: Path) -> None:
    config_dir = _write_config(tmp_path)
    extensions_dir = tmp_path / "extensions"
    extensions_dir.mkdir()
    controller = DagController(config_dir, extensions_dirs=[extensions_dir])
    await controller.start(run_startup=False)
    try:
        _write_extension(extensions_dir / "demo")
        _write_extension(extensions_dir / "stale")
        daemon = type("Daemon", (), {"pb2": pb2, "controller": controller, "config_dir": config_dir})()
        service = _ExtensionService(daemon)
        await service.Install(pb2.ExtensionInstallRequest(name="demo", overwrite=False), _Context())

        installed_context = _Context()
        with pytest.raises(_AbortError):
            await service.Delete(pb2.NameRequest(name="demo"), installed_context)
        assert installed_context.aborted[-1][0] == grpc.StatusCode.FAILED_PRECONDITION
        assert (extensions_dir / "demo").exists()

        body = json.loads((await service.Delete(pb2.NameRequest(name="stale"), _Context())).json)
        assert body["deleted"] is True
        assert not (extensions_dir / "stale").exists()

        missing_context = _Context()
        with pytest.raises(_AbortError):
            await service.Delete(pb2.NameRequest(name="missing"), missing_context)
        assert missing_context.aborted[-1][0] == grpc.StatusCode.NOT_FOUND
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_import_entities_rpc(tmp_path: Path) -> None:
    config_dir = _write_config(tmp_path)
    (tmp_path / "extensions").mkdir()
    controller = DagController(config_dir, extensions_dirs=[tmp_path / "extensions"])
    await controller.start(run_startup=False)
    try:
        daemon = type("Daemon", (), {"pb2": pb2, "controller": controller, "config_dir": config_dir})()
        service = _ExtensionService(daemon)
        async with controller._factory()() as session:
            await save_ordinary_entity(
                session,
                EntityConfig(id="stock-1", type="stock", attributes={"code": "00700", "name": "Existing"}),
                _stock_type(),
            )
            await session.commit()

        content = _entities_tar("demo", "stock", "stock-1", "Imported")
        body = json.loads((await service.ImportEntities(pb2.ImportEntitiesRequest(content=content), _Context())).json)
        assert body["updated"] == 1

        invalid_context = _Context()
        with pytest.raises(_AbortError):
            await service.ImportEntities(pb2.ImportEntitiesRequest(content=b"not a tar"), invalid_context)
        assert invalid_context.aborted[-1][0] == grpc.StatusCode.INVALID_ARGUMENT

        multi_context = _Context()
        with pytest.raises(_AbortError):
            await service.ImportEntities(
                pb2.ImportEntitiesRequest(content=_two_manifest_tar()), multi_context
            )
        assert multi_context.aborted[-1][0] == grpc.StatusCode.INVALID_ARGUMENT
    finally:
        await controller.shutdown()


def _entities_tar(name: str, entity_type: str, entity_id: str, value: str) -> bytes:
    import io
    import yaml as _yaml

    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        manifest = {"name": name, "version": "0.1.0", "imports": {"entities": [f"entities/{entity_type}-{entity_id}.yaml"]}}
        entity = {"type": entity_type, "id": entity_id, "attributes": {"code": "00700", "name": value}}
        for arcname, payload in (
            (f"{name}/manifest.yaml", manifest),
            (f"{name}/entities/{entity_type}-{entity_id}.yaml", entity),
        ):
            data = _yaml.safe_dump(payload, allow_unicode=True, sort_keys=False).encode("utf-8")
            info = tarfile.TarInfo(arcname)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def _two_manifest_tar() -> bytes:
    import io
    import yaml as _yaml

    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for arcname in ("a/manifest.yaml", "b/manifest.yaml"):
            data = _yaml.safe_dump({"name": arcname[0], "version": "0.1.0"}, allow_unicode=False).encode("utf-8")
            info = tarfile.TarInfo(arcname)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def _stock_type():
    from edera_core.config.schema import EntityTypeConfig

    return EntityTypeConfig.model_validate(
        {
            "display_name": "Stock",
            "business_id_field": "code",
            "display_template": "{code}",
            "storage_tier": "database",
            "schema": {
                "required": ["code", "name"],
                "properties": {"code": {"type": "string"}, "name": {"type": "string"}},
            },
        }
    )


def _write_config(root: Path) -> Path:
    config_dir = root / "config"
    (root / "schemas" / "entity-types").mkdir(parents=True)
    (config_dir / "dags").mkdir(parents=True)
    (config_dir / "nodes").mkdir()
    (config_dir / "skills").mkdir()
    (root / "schemas" / "entity-types" / "stock.yaml").write_text(
        "display_name: Stock\n"
        "business_id_field: code\n"
        "display_template: '{code}'\n"
        "storage_tier: database\n"
        "schema:\n"
        "  required: [code, name]\n"
        "  properties:\n"
        "    code:\n"
        "      type: string\n"
        "    name:\n"
        "      type: string\n",
        encoding="utf-8",
    )
    (config_dir / "entities.yaml").write_text("entities: []\n", encoding="utf-8")
    (config_dir / "entity-relations.yaml").write_text("relations: []\n", encoding="utf-8")
    (config_dir / "system.toml").write_text(
        f'database_url = "sqlite+aiosqlite:///{root / "runtime.db"}"\n'
        f'handlers_dir = "{root / "data" / "handlers"}"\n',
        encoding="utf-8",
    )
    (config_dir / "dags" / "default.yaml").write_text("name: default\nnodes: []\nedges: []\n", encoding="utf-8")
    return config_dir


def _write_extension(root: Path) -> None:
    (root / "entities").mkdir(parents=True)
    (root / "handler.py").write_text("def run(payload):\n    return payload\n", encoding="utf-8")
    (root / "entities" / "stock.yaml").write_text(
        "type: stock\n"
        "id: stock-1\n"
        "attributes:\n"
        "  code: '00700'\n"
        "  name: Tencent\n",
        encoding="utf-8",
    )
    (root / "manifest.yaml").write_text(
        "name: demo\n"
        "version: 0.1.0\n"
        "handlers:\n"
        "  - name: demo-handler\n"
        "    role: processor\n"
        "    input_type: Any\n"
        "    entry: handler.py\n"
        "imports:\n"
        "  entities:\n"
        "    - entities/stock.yaml\n",
        encoding="utf-8",
    )


def _write_workflow_extension(root: Path) -> None:
    (root / "_providers" / "reader").mkdir(parents=True)
    (root / "_providers" / "reader" / "handler.py").write_text("def run(payload):\n    return payload\n", encoding="utf-8")
    (root / "_providers" / "reader" / "manifest.yaml").write_text(
        "name: reader\n"
        "version: 0.1.0\n"
        "handlers:\n"
        "  - name: read\n"
        "    role: processor\n"
        "    input_type: Any\n"
        "    entry: handler.py\n",
        encoding="utf-8",
    )
    (root / "manifest.yaml").write_text(
        "name: workflow\n"
        "version: 0.1.0\n"
        "type: workflow_extension\n"
        "imports:\n"
        "  providers:\n"
        "    - _providers/*/manifest.yaml\n",
        encoding="utf-8",
    )
