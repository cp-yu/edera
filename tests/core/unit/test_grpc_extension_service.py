from pathlib import Path
import json

import pytest

from edera_core.dag_controller import DagController
from edera_core.grpc_extension_service import _ExtensionService
from edera_core.proto import edera_pb2 as pb2
from edera_core.storage.repository import get_installed_extension


class _Context:
    def invocation_metadata(self):
        return (("x-edera-identity", "human:test"),)

    def auth_context(self):
        return {}

    async def abort(self, _code, message):
        raise AssertionError(message)


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

        response = await service.Install(pb2.NameRequest(name="demo"), _Context())

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

        response = await service.Install(pb2.NameRequest(name="workflow"), _Context())
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

        with pytest.raises(AssertionError, match=r"glob pattern matched no files: _providers/\*/manifest.yaml"):
            await service.Install(pb2.NameRequest(name="workflow"), _Context())
    finally:
        await controller.shutdown()


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
