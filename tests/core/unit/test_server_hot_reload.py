from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from edera_core.bootstrap import scan_extensions
from edera_core.config_service import _ConfigService
from edera_core.config.loader import load_app_config
from edera_core.dag_controller import DagController
from edera_core.errors import ConfigError
from edera_core.graph_service import _GraphService
from edera_core.proto import edera_pb2 as pb2
from edera_core.query_service import _QueryService
from edera_core.server import Server, _EntityService


class _Controller:
    agent_certificate_issuer = None
    daemon_data_dir = None
    extensions_dirs: list[Path] = []

    async def emit(self, event: str, payload: object | None = None, *, source: str = "rpc", depth: int = 0) -> list[str]:
        return [event]


class _Context:
    def invocation_metadata(self):
        return ()

    def auth_context(self):
        return {"x509_common_name": [b"human:test"]}

    async def abort(self, _code, message):
        raise AssertionError(message)


@pytest.mark.asyncio
async def test_lifecycle(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cancelled = asyncio.Event()

    class FakeHotReloader:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        async def watch(self) -> None:
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise

    monkeypatch.setattr("edera_core.server.HotReloader", FakeHotReloader)
    daemon = Server(tmp_path / "data", "127.0.0.1:0", tmp_path / "config", controller=_Controller())  # type: ignore[arg-type]

    await daemon.start()
    task = daemon._hot_reload_task
    assert task is not None
    assert not task.done()

    await asyncio.sleep(0)
    await daemon.stop()
    assert cancelled.is_set()
    assert daemon._hot_reload_task is None


@pytest.mark.asyncio
async def test_reload_installs_snapshot(tmp_path: Path) -> None:
    _write_config(tmp_path)
    controller = DagController(tmp_path, extensions_dirs=[tmp_path.parent / "extensions"])
    await controller.start(run_startup=False)
    try:
        daemon = Server(tmp_path / "data", "127.0.0.1:0", tmp_path, controller=controller)
        _write_dag(tmp_path, nodes=["worker"])
        _write_node(tmp_path, "worker", handler="worker-v2")

        await daemon._reload_config(load_app_config(tmp_path), scan_extensions([tmp_path.parent / "extensions"], tmp_path))

        assert controller.runtime_snapshot().config.dags["default"].nodes[0].type == "worker"
        assert controller.runtime_snapshot().config.nodes["worker"].handler == "worker-v2"
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_runtime_read_api_committed_snapshot(tmp_path: Path) -> None:
    _write_config(tmp_path)
    controller = DagController(tmp_path, extensions_dirs=[tmp_path.parent / "extensions"])
    await controller.start(run_startup=False)
    try:
        daemon = Server(tmp_path / "data", "127.0.0.1:0", tmp_path, controller=controller)
        graph = _GraphService(daemon)
        entities = _EntityService(daemon)
        _write_dag(tmp_path, nodes=["worker"])
        _write_node(tmp_path, "worker", handler="worker-v2")
        _write_stock(tmp_path, "NEW")

        before = json.loads((await graph.GetDag(pb2.NameRequest(name="default"), _Context())).json)
        before_types = json.loads((await graph.ListNodeTypes(pb2.EmptyRequest(), _Context())).json)
        await daemon._reload_config(load_app_config(tmp_path), scan_extensions([tmp_path.parent / "extensions"], tmp_path))
        after = json.loads((await graph.GetDag(pb2.NameRequest(name="default"), _Context())).json)
        after_types = json.loads((await graph.ListNodeTypes(pb2.EmptyRequest(), _Context())).json)
        node_type = json.loads((await graph.GetNodeType(pb2.NameRequest(name="worker"), _Context())).json)
        entity = await entities.Get(pb2.EntityRef(ref="stock:NEW"), _Context())

        assert before["nodes"] == []
        assert before_types["types"][0]["handler"] == "worker"
        assert [node["type_name"] for node in after["nodes"]] == ["worker"]
        assert after_types["types"][0]["handler"] == "worker-v2"
        assert node_type["node"]["handler"] == "worker-v2"
        assert json.loads(entity.json)["ref"] == "stock:NEW"
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_runtime_read_api_ignores_failed_candidate(tmp_path: Path) -> None:
    _write_config(tmp_path)
    controller = DagController(tmp_path, extensions_dirs=[tmp_path.parent / "extensions"])
    await controller.start(run_startup=False)
    try:
        daemon = Server(tmp_path / "data", "127.0.0.1:0", tmp_path, controller=controller)
        graph = _GraphService(daemon)
        entities = _EntityService(daemon)
        _write_dag(tmp_path, nodes=["worker"])
        _write_node(tmp_path, "worker", handler="worker-v2")
        _write_stock(tmp_path, "NEW")

        async def fail_install_snapshot(*_args, **_kwargs):
            raise RuntimeError("commit failed")

        controller.install_snapshot = fail_install_snapshot  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match="commit failed"):
            await daemon._reload_config(load_app_config(tmp_path), scan_extensions([tmp_path.parent / "extensions"], tmp_path))

        payload = json.loads((await graph.GetDag(pb2.NameRequest(name="default"), _Context())).json)
        node_type = json.loads((await graph.GetNodeType(pb2.NameRequest(name="worker"), _Context())).json)
        assert payload["nodes"] == []
        assert node_type["node"]["handler"] == "worker"
        with pytest.raises(ConfigError, match="Entity not found"):
            await entities.Get(pb2.EntityRef(ref="stock:NEW"), _Context())
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_query_runtime_api_committed_snapshot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_config(tmp_path)
    _write_source_schema(tmp_path)
    controller = DagController(tmp_path, extensions_dirs=[tmp_path.parent / "extensions"])
    await controller.start(run_startup=False)
    try:
        daemon = Server(tmp_path / "data", "127.0.0.1:0", tmp_path, controller=controller)
        query = _QueryService(daemon)
        captured_health: list[list[str]] = []
        captured_logs: list[list[str]] = []

        async def fake_source_health_summary(_session, source_names):
            captured_health.append(list(source_names))
            return []

        async def fake_source_execution_logs(_session, *args, source_names=None, **_kwargs):
            names = source_names if source_names is not None else args[2] if len(args) >= 3 else []
            captured_logs.append(list(names or []))
            return []

        monkeypatch.setattr("edera_core.query_service.source_health_summary", fake_source_health_summary)
        monkeypatch.setattr("edera_core.query_service.source_execution_logs", fake_source_execution_logs)
        _write_rss_source(tmp_path, "candidate")
        _write_named_dag(tmp_path, "candidate")

        await query.SourceHealth(pb2.EmptyRequest(), _Context())
        await query.SourceLogs(pb2.SourceLogsRequest(), _Context())
        with pytest.raises(AssertionError, match="dag 'candidate' not found"):
            await query.NodeHistory(pb2.NodeHistoryRequest(dag_name="candidate", node_id="worker"), _Context())

        await daemon._reload_config(load_app_config(tmp_path), scan_extensions([tmp_path.parent / "extensions"], tmp_path))
        await query.SourceHealth(pb2.EmptyRequest(), _Context())
        await query.SourceLogs(pb2.SourceLogsRequest(), _Context())
        history = json.loads((await query.NodeHistory(pb2.NodeHistoryRequest(dag_name="candidate", node_id="worker"), _Context())).json)

        assert captured_health == [[], ["candidate"]]
        assert captured_logs == [[], [], ["candidate"], ["candidate"]]
        assert history == {"history": []}
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_config_edit_api_file_backed(tmp_path: Path) -> None:
    _write_config(tmp_path)
    controller = DagController(tmp_path, extensions_dirs=[tmp_path.parent / "extensions"])
    await controller.start(run_startup=False)
    try:
        daemon = Server(tmp_path / "data", "127.0.0.1:0", tmp_path, controller=controller)
        graph = _GraphService(daemon)
        config = _ConfigService(daemon)
        _write_dag(tmp_path, nodes=["worker"])

        runtime_payload = json.loads((await graph.GetDag(pb2.NameRequest(name="default"), _Context())).json)
        file_payload = load_app_config(tmp_path).dags["default"]
        raw = json.loads((await config.ReadConfig(pb2.ConfigFileRequest(kind="dag", name="default"), _Context())).json)

        assert runtime_payload["nodes"] == []
        assert [node.type for node in file_payload.nodes] == ["worker"]
        assert "worker" in raw["file"]["content"]
    finally:
        await controller.shutdown()


def _write_config(root: Path) -> None:
    (root / "dags").mkdir()
    (root / "nodes").mkdir()
    (root / "skills").mkdir()
    (root.parent / "schemas" / "entity-types").mkdir(parents=True, exist_ok=True)
    (root.parent / "schemas" / "entity-types" / "stock.yaml").write_text(
        "display_name: Stock\nbusiness_id_field: code\ndisplay_template: '{code}'\nschema: {}\n",
        encoding="utf-8",
    )
    (root / "entities.yaml").write_text("entities: []\n", encoding="utf-8")
    (root / "entity-relations.yaml").write_text("relations: []\n", encoding="utf-8")
    (root / "system.toml").write_text(f'database_url = "sqlite+aiosqlite:///{root / "test.db"}"\n', encoding="utf-8")
    (root / "nodes" / "worker.yaml").write_text(
        _node_content("worker", "worker"),
        encoding="utf-8",
    )
    _write_dag(root, nodes=[])


def _write_node(root: Path, name: str, *, handler: str) -> None:
    (root / "nodes" / f"{name}.yaml").write_text(_node_content(name, handler), encoding="utf-8")


def _node_content(name: str, handler: str) -> str:
    return f"name: {name}\nrole: processor\ntype: function\nhandler: {handler}\ninput_type: Any\noutput_type: Any\n"


def _write_dag(root: Path, nodes: list[str]) -> None:
    if not nodes:
        (root / "dags" / "default.yaml").write_text("name: default\nnodes: []\nedges: []\n", encoding="utf-8")
        return
    entries = "\n".join(f"  - id: {name}\n    type: {name}\n    config: {{}}" for name in nodes)
    (root / "dags" / "default.yaml").write_text(f"name: default\nnodes:\n{entries}\nedges: []\n", encoding="utf-8")


def _write_named_dag(root: Path, name: str) -> None:
    (root / "dags" / f"{name}.yaml").write_text(
        f"name: {name}\nnodes:\n  - id: worker\n    type: worker\n    config: {{}}\nedges: []\n",
        encoding="utf-8",
    )


def _write_stock(root: Path, code: str) -> None:
    (root / "entities.yaml").write_text(
        f"entities:\n  - id: stock-{code.lower()}\n    type: stock\n    attributes:\n      code: {code}\n",
        encoding="utf-8",
    )


def _write_source_schema(root: Path) -> None:
    (root.parent / "schemas" / "entity-types" / "rss-source.yaml").write_text(
        "display_name: RSS Source\nbusiness_id_field: name\ndisplay_template: '{name}'\nschema: {}\n",
        encoding="utf-8",
    )


def _write_rss_source(root: Path, name: str) -> None:
    (root / "entities.yaml").write_text(
        f"entities:\n  - id: source-{name}\n    type: rss-source\n    attributes:\n      name: {name}\n",
        encoding="utf-8",
    )
