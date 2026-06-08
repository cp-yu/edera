from __future__ import annotations

import json

import grpc
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from edera_core.graph_service import _GraphService
from edera_core.proto import edera_pb2 as pb2
from edera_core.bootstrap import BootstrapResult
from edera_core.config.entities import EntityStore
from edera_core.config.loader import _load_runtime_base_config, materialize_runtime_app_config
from edera_core.dag_controller import RuntimeControlSnapshot
from edera_core.storage import create_engine, init_db, session_factory
from edera_core.storage.repository import create_dag_run, create_relation, get_dag_config, mark_node_run, save_installed_extension
from edera_core.storage.repository import get_skill

from fixtures.entity_fixtures import seed_entity_records
from service_fakes import AbortError, FakeContext, FakeDaemon


_ENGINES: list[AsyncEngine] = []


@pytest.fixture(autouse=True)
async def _dispose_engines():
    try:
        yield
    finally:
        while _ENGINES:
            await _ENGINES.pop().dispose()


@pytest.mark.asyncio
async def test_save_invalid_dag(tmp_path):
    root = tmp_path / "config"
    _write_graph_config(root)
    service = _GraphService(await _graph_daemon(root, tmp_path))

    with pytest.raises(AbortError) as exc:
        await service.SaveDag(
            pb2.NamedJsonRequest(
                name="demo",
                json=json.dumps({"nodes": [{"id": "n1", "type": "missing"}], "edges": []}),
            ),
            FakeContext(),
        )

    assert exc.value.code == grpc.StatusCode.INVALID_ARGUMENT


@pytest.mark.asyncio
async def test_delete_referenced_node_type(tmp_path):
    root = tmp_path / "config"
    _write_graph_config(root)
    service = _GraphService(await _graph_daemon(root, tmp_path))

    with pytest.raises(AbortError) as exc:
        await service.DeleteNodeType(pb2.NameRequest(name="reader"), FakeContext())

    assert exc.value.code == grpc.StatusCode.FAILED_PRECONDITION


@pytest.mark.asyncio
async def test_create_skill(tmp_path):
    root = tmp_path / "config"
    _write_graph_config(root)
    service = _GraphService(await _graph_daemon(root, tmp_path))

    result = await service.CreateSkill(
        pb2.JsonRequest(json=json.dumps({"name": "summarize", "description": "x", "handler_code": "def handle(): pass"})),
        FakeContext(),
    )

    assert json.loads(result.json)["skill"]["name"] == "summarize"
    async with service.daemon.controller._factory()() as session:
        skill = await get_skill(session, "summarize")
    assert skill is not None
    assert skill.config_body["files"][0]["path"] == "SKILL.md"
    assert not (root / "skills" / "summarize.yaml").exists()


@pytest.mark.asyncio
async def test_get_dag_detail(tmp_path):
    root = tmp_path / "config"
    _write_graph_config(root)
    service = _GraphService(await _graph_daemon(root, tmp_path))

    result = await service.GetDag(pb2.NameRequest(name="demo"), FakeContext())
    payload = json.loads(result.json)

    assert {"nodes", "edges", "ui", "entity_types", "entities", "entity_relations"}.issubset(payload)


@pytest.mark.asyncio
async def test_get_dag_detail_includes_database_entities_and_relations(tmp_path):
    root = tmp_path / "config"
    _write_graph_config(root)
    service = _GraphService(await _graph_daemon(root, tmp_path))
    app = service.daemon.controller.runtime_config()
    async with service.daemon.controller._factory()() as session:
        await create_relation(session, "stock:TEST", "rss-source:rss", "uses-source", {}, app.entity_types)
        await session.commit()

    result = await service.GetDag(pb2.NameRequest(name="demo"), FakeContext())
    payload = json.loads(result.json)

    refs = {entity["ref"] for entity in payload["entities"]}
    assert {"stock:TEST", "rss-source:rss"}.issubset(refs)
    assert payload["entity_relations"][0]["entities"] == ["stock:TEST", "rss-source:rss"]
    assert payload["entity_relations"][0]["type"] == "uses-source"


@pytest.mark.asyncio
async def test_optional_save_response(tmp_path):
    root = tmp_path / "config"
    _write_graph_config(root)
    service = _GraphService(await _graph_daemon(root, tmp_path))

    result = await service.SaveDag(
        pb2.NamedJsonRequest(
            name="demo",
            json=json.dumps(
                {
                    "nodes": [{"id": "n1", "type": "reader", "optional": True}, {"id": "n2", "type": "reader"}],
                    "edges": [{"from": "n1", "to": "n2", "optional": True, "fan_in": True, "fan_in_mode": "collect"}],
                    "ui": {},
                }
            ),
        ),
        FakeContext(),
    )
    payload = json.loads(result.json)["dag"]

    assert payload["nodes"][0]["optional"] is True
    assert payload["edges"][0]["optional"] is True
    assert payload["edges"][0]["fan_in"] is True
    assert payload["edges"][0]["fan_in_mode"] == "collect"


@pytest.mark.asyncio
async def test_optional_round_trip(tmp_path):
    root = tmp_path / "config"
    _write_graph_config(root)
    service = _GraphService(await _graph_daemon(root, tmp_path))

    first = await service.SaveDag(
        pb2.NamedJsonRequest(
            name="demo",
            json=json.dumps(
                {
                    "nodes": [{"id": "n1", "type": "reader", "optional": True}, {"id": "n2", "type": "reader"}],
                    "edges": [{"from": "n1", "to": "n2", "optional": True}],
                    "ui": {},
                }
            ),
        ),
        FakeContext(),
    )
    saved = json.loads(first.json)["dag"]
    second = await service.SaveDag(pb2.NamedJsonRequest(name="demo", json=json.dumps(saved)), FakeContext())
    payload = json.loads(second.json)["dag"]
    async with service.daemon.controller._factory()() as session:
        stored = await get_dag_config(session, "demo")

    assert payload["nodes"][0]["optional"] is True
    assert payload["edges"][0]["optional"] is True
    assert stored is not None
    assert stored.nodes[0].optional is True
    assert "event:config-changed" in service.daemon.controller.emitted


@pytest.mark.asyncio
async def test_node_type_write_emits_without_control_snapshot_rebuild(tmp_path):
    root = tmp_path / "config"
    _write_graph_config(root)
    service = _GraphService(await _graph_daemon(root, tmp_path))
    snapshot = service.daemon.controller.runtime_snapshot()
    generation = snapshot.generation

    await service.SaveNodeType(
        pb2.NamedJsonRequest(
            name="writer",
            json=json.dumps({"role": "processor", "handler": "writer", "input_type": "Any", "output_type": "Any"}),
        ),
        FakeContext(),
    )

    assert "event:config-changed" in service.daemon.controller.emitted
    assert service.daemon.controller.runtime_snapshot() is snapshot
    assert service.daemon.controller.runtime_snapshot().generation == generation


@pytest.mark.asyncio
async def test_sub_dag_instance_round_trip(tmp_path):
    root = tmp_path / "config"
    _write_graph_config(root)
    service = _GraphService(await _graph_daemon(root, tmp_path))

    first = await service.SaveDag(
        pb2.NamedJsonRequest(
            name="demo",
            json=json.dumps(
                {
                    "nodes": [
                        {
                            "id": "sub-a",
                            "type": "dag",
                            "dag_ref": "common-subdag",
                            "input_mapping": {"topic": "payload.topic"},
                            "alias": "common",
                            "config": {"mode": "strict"},
                        }
                    ],
                    "edges": [],
                    "ui": {},
                }
            ),
        ),
        FakeContext(),
    )
    assert json.loads(first.json)["dag"]["nodes"][0]["config"] == {"mode": "strict"}
    loaded = await service.GetDag(pb2.NameRequest(name="demo"), FakeContext())
    saved = json.loads(loaded.json)
    second = await service.SaveDag(pb2.NamedJsonRequest(name="demo", json=json.dumps(saved)), FakeContext())
    payload = json.loads(second.json)["dag"]
    async with service.daemon.controller._factory()() as session:
        stored = await get_dag_config(session, "demo")

    assert payload["nodes"][0]["dag_ref"] == "common-subdag"
    assert payload["nodes"][0]["input_mapping"] == {"topic": "payload.topic"}
    assert payload["nodes"][0]["alias"] == "common"
    assert payload["nodes"][0]["config"] == {"mode": "strict"}
    assert stored is not None
    assert stored.nodes[0].dag_ref == "common-subdag"
    assert stored.nodes[0].input_mapping == {"topic": "payload.topic"}
    assert stored.nodes[0].alias == "common"
    assert stored.nodes[0].config == {"mode": "strict"}


@pytest.mark.asyncio
async def test_save_sub_dag_cycle_rejected(tmp_path):
    root = tmp_path / "config"
    _write_graph_config(root)
    service = _GraphService(await _graph_daemon(root, tmp_path))

    with pytest.raises(AbortError) as exc:
        await service.SaveDag(
            pb2.NamedJsonRequest(
                name="demo",
                json=json.dumps(
                    {
                        "nodes": [{"id": "self", "type": "dag", "dag_ref": "demo"}],
                        "edges": [],
                        "ui": {},
                    }
                ),
            ),
            FakeContext(),
        )

    assert exc.value.code == grpc.StatusCode.INVALID_ARGUMENT
    assert "Sub DAG cycle detected" in exc.value.details
    assert "节点 'self'" in exc.value.details
    assert "修复建议" in exc.value.details
    async with service.daemon.controller._factory()() as session:
        stored = await get_dag_config(session, "demo")
    assert stored is not None
    assert [node.id for node in stored.nodes] == ["n1", "n2"]


@pytest.mark.asyncio
async def test_runtime_status_can_scope_to_run_id(tmp_path):
    root = tmp_path / "config"
    _write_graph_config(root)
    service = _GraphService(await _graph_daemon(root, tmp_path))
    async with service.daemon.controller._factory()() as session:
        await create_dag_run(session, "run-old", "manual", ["same-node"], dag_name="demo")
        await mark_node_run(session, "run-old", "same-node", "failed", "old")
        await create_dag_run(session, "run-child", "manual", ["same-node"], dag_name="common-subdag")
        await mark_node_run(session, "run-child", "same-node", "succeeded")
        await session.commit()

    result = await service.RuntimeStatus(pb2.RuntimeStatusRequest(run_id="run-child"), FakeContext())
    payload = json.loads(result.json)

    assert payload["node_statuses"]["same-node"]["run_id"] == "run-child"
    assert payload["node_statuses"]["same-node"]["status"] == "succeeded"


# --- Handler database tests ---


async def _daemon_with_handlers(tmp_path, handler_files: dict[str, str]):
    root = tmp_path / "config"
    _write_graph_config(root)
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'handlers.db'}")
    _ENGINES.append(engine)
    await init_db(engine)
    factory = session_factory(engine)
    handlers = []
    for name, content in handler_files.items():
        package = f"demo-ext.{name}"
        path = tmp_path / "data" / "handlers" / package / f"{name}.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        handlers.append({"name": f"demo-ext.{name}", "package": package, "entry": f"{name}.py"})
    async with factory() as session:
        await save_installed_extension(
            session,
            name="demo-ext",
            version="1.0.0",
            manifest_snapshot={"name": "demo-ext", "version": "1.0.0", "handlers": handlers},
        )
        await session.commit()
    return _FakeDaemonWithHandlers(root, factory, tmp_path / "data" / "handlers")


class _FakeDaemonWithHandlers:
    def __init__(self, config_dir, factory, handlers_dir):
        self.config_dir = config_dir
        self.pb2 = pb2
        self.controller = _FakeSnapshot(factory, handlers_dir)


class _FakeSnapshot:
    def __init__(self, factory, handlers_dir):
        self.factory = factory
        self.handlers_dir = handlers_dir

    def runtime_snapshot(self):
        return self

    def _factory(self):
        return self.factory


async def _graph_daemon(root, tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'edera.db'}")
    _ENGINES.append(engine)
    await init_db(engine)
    config = _load_runtime_base_config(root)
    factory = session_factory(engine)
    async with factory() as session:
        await seed_entity_records(session, config.entity_types)
        await session.commit()
    controller = GraphController(root, engine)
    await controller.install_snapshot(config, controller.bootstrap)
    return FakeDaemon(root, controller)


class GraphController:
    def __init__(self, config_dir, engine):
        self.config_dir = config_dir
        self.engine = engine
        self.factory = session_factory(engine)
        self.bootstrap = BootstrapResult([], {}, {}, {})
        self._snapshot = None
        self._config = None
        self.emitted: list[str] = []

    def _factory(self):
        return self.factory

    def runtime_snapshot(self):
        if self._snapshot is None:
            raise RuntimeError("missing runtime snapshot")
        return self._snapshot

    def runtime_config(self):
        if self._config is None:
            raise RuntimeError("missing runtime config")
        return self._config

    async def emit(self, event, payload=None, *, source="rpc", depth=0):
        self.emitted.append(event)
        return []

    async def install_snapshot(self, config, bootstrap):
        config = await materialize_runtime_app_config(self.config_dir, config, self.engine)
        store = EntityStore(config.entities, config.entity_types, config.entity_relations, None)
        self._config = config
        self._store = store
        self._snapshot = RuntimeControlSnapshot(
            system=config.system,
            runtime=config.runtime,
            trigger_executor=None,
            cron_emitter=None,
        )
        return self._snapshot


@pytest.mark.asyncio
async def test_list_handlers_from_database(tmp_path):
    daemon = await _daemon_with_handlers(tmp_path, {"reader": "def run(): pass", "fetcher": "def run(): pass"})
    service = _GraphService(daemon)
    result = await service.ListHandlers(pb2.EmptyRequest(), FakeContext())
    payload = json.loads(result.json)
    names = [h["name"] for h in payload["handlers"]]
    assert "demo-ext.reader" in names
    assert "demo-ext.fetcher" in names


@pytest.mark.asyncio
async def test_get_handler_reads_from_database_path(tmp_path):
    daemon = await _daemon_with_handlers(tmp_path, {"reader": "async def run(ctx): return []\n"})
    service = _GraphService(daemon)
    result = await service.GetHandler(pb2.NameRequest(name="demo-ext.reader"), FakeContext())
    payload = json.loads(result.json)
    assert payload["name"] == "demo-ext.reader"
    assert payload["code"] == "async def run(ctx): return []\n"


@pytest.mark.asyncio
async def test_get_handler_not_found_not_in_database(tmp_path):
    daemon = await _daemon_with_handlers(tmp_path, {"reader": "def run(): pass"})
    service = _GraphService(daemon)
    with pytest.raises(AbortError) as exc:
        await service.GetHandler(pb2.NameRequest(name="nonexistent"), FakeContext())
    assert exc.value.code == grpc.StatusCode.NOT_FOUND


@pytest.mark.asyncio
async def test_save_handler_writes_to_database_path(tmp_path):
    daemon = await _daemon_with_handlers(tmp_path, {"reader": "def run(): pass"})
    service = _GraphService(daemon)
    result = await service.SaveHandler(
        pb2.NamedTextRequest(name="demo-ext.reader", content="def run(): updated"),
        FakeContext(),
    )
    payload = json.loads(result.json)
    assert payload["code"] == "def run(): updated"
    handler_path = tmp_path / "data" / "handlers" / "demo-ext.reader" / "reader.py"
    assert handler_path.read_text(encoding="utf-8") == "def run(): updated"


def _write_graph_config(root):
    (root / "dags").mkdir(parents=True)
    (root / "nodes").mkdir()
    (root / "skills").mkdir()
    (root.parent / "schemas" / "entity-types").mkdir(parents=True)
    (root.parent / "schemas" / "entity-types" / "stock.yaml").write_text(
        "display_name: Stock\nbusiness_id_field: code\ndisplay_template: '{code}'\nstorage_tier: database\nschema:\n  properties:\n    code: {}\n",
        encoding="utf-8",
    )
    (root.parent / "schemas" / "entity-types" / "rss-source.yaml").write_text(
        "display_name: RSS\nbusiness_id_field: name\ndisplay_template: '{name}'\nstorage_tier: database\nschema:\n  properties:\n    name: {}\n",
        encoding="utf-8",
    )
    (root / "nodes" / "reader.yaml").write_text(
        "name: reader\ntype: function\nrole: processor\nhandler: reader\ninput_type: Any\noutput_type: Any\n",
        encoding="utf-8",
    )
    (root / "dags" / "demo.yaml").write_text(
        "name: demo\nnodes:\n- id: n1\n  type: reader\n- id: n2\n  type: reader\nedges: []\nui: {}\n",
        encoding="utf-8",
    )
    (root / "dags" / "common-subdag.yaml").write_text(
        "name: common-subdag\nnodes:\n- id: child\n  type: reader\nedges: []\nui: {}\n",
        encoding="utf-8",
    )
    (root / "system.toml").write_text("database_url = \"sqlite+aiosqlite:///tmp/test.db\"\nschedule_minutes = 1\n", encoding="utf-8")
