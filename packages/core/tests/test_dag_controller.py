from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from edera_core.bootstrap import BootstrapResult
from edera_core.config.schema import AppConfig, DagConfig, DagNodeInstance, EntityConfig, EntityTypeConfig, EntitiesConfig, EntityRelationsConfig, NodeConfig, RuntimeSettings, SystemConfig
from edera_core.dag.loader import load_graph
from edera_core.dag_controller import DagController, RuntimeControlSnapshot, _parse_node_trigger_target
from edera_core.node.models import NodeOutput
from edera_core.snapshot import DagExecutionSnapshot
from edera_core.storage import create_engine, init_db, session_factory
from edera_core.storage.repository import create_dag_run, create_ordinary_entity, create_relation, finish_dag_run, recent_dag_runs, save_core_entity, save_installed_extension


@pytest.mark.asyncio
async def test_create_snapshot_for_dag_execution(tmp_path):
    controller = _controller(tmp_path)
    config = controller.runtime_config()
    graph = load_graph(config.dags["demo"], config.nodes)
    async with _session(tmp_path) as session:
        await _install(session)
        await _seed_runtime_core(session, config)
        executor = await controller._build_run_executor(controller.runtime_snapshot(), graph, session)

    assert isinstance(executor.snapshot, DagExecutionSnapshot)
    assert executor.snapshot.dag_config.name == "demo"
    assert not hasattr(controller.runtime_snapshot(), "config")


@pytest.mark.asyncio
async def test_snapshot_isolation(tmp_path):
    controller = _controller(tmp_path)
    config = controller.runtime_config()
    graph = load_graph(config.dags["demo"], config.nodes)
    async with _session(tmp_path) as session:
        await _install(session)
        await _seed_runtime_core(session, config)
        executor = await controller._build_run_executor(controller.runtime_snapshot(), graph, session)

    config.entity_types["new"] = _entity_type("New")

    assert "new" not in executor.snapshot.entity_types


@pytest.mark.asyncio
async def test_snapshot_freezes_handler_metadata(tmp_path):
    controller = _controller(tmp_path)
    config = controller.runtime_config()
    graph = load_graph(config.dags["demo"], config.nodes)
    async with _session(tmp_path) as session:
        await _install(session)
        await _seed_runtime_core(session, config)
        executor = await controller._build_run_executor(controller.runtime_snapshot(), graph, session)
        await save_installed_extension(
            session,
            name="demo-ext",
            version="1.0.0",
            manifest_snapshot={"name": "demo-ext", "version": "1.0.0", "handlers": []},
        )
        await session.commit()

    meta = await executor.snapshot.handler_resolver.get("reader")

    assert meta.path == tmp_path / "handlers" / "demo-ext" / "handler.py"


@pytest.mark.asyncio
async def test_controller_builds_execution_closure_from_database(tmp_path):
    controller = _controller(tmp_path)
    async with _session(tmp_path) as session:
        await _install(session)
        await save_core_entity(session, EntityConfig(id="node:reader", type="node", attributes=_reader_node()))
        await save_core_entity(session, EntityConfig(id="dag:demo", type="dag", attributes={"name": "demo", "nodes": [{"id": "child", "type": "dag", "dag_ref": "child"}], "edges": [], "ui": {}}))
        await save_core_entity(session, EntityConfig(id="dag:child", type="dag", attributes={"name": "child", "nodes": [{"id": "n1", "type": "reader"}], "edges": [], "ui": {}}))
        await save_core_entity(session, EntityConfig(id="dag:unused", type="dag", attributes={"name": "unused", "nodes": [], "edges": [], "ui": {}}))
        await session.commit()

        snapshot = await controller._dag_execution_snapshot(session, "demo")

    assert set(snapshot.dag_closure.dags) == {"demo", "child"}
    assert set(snapshot.node_configs) == {"reader"}


@pytest.mark.asyncio
async def test_run_preloads_and_clears_dag_entity_cache(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'edera.db'}")
    await init_db(engine)
    factory = session_factory(engine)
    controller = DagController(tmp_path / "config")
    controller.engine = engine
    controller.factory = factory
    _install_runtime_state(controller, _app_config(), RuntimeControlSnapshot(SystemConfig(config_git_commit=False), RuntimeSettings(), None, None))
    config = controller.runtime_config()
    config.dags["demo"].nodes[0].config["entities"] = ["stock:TEST"]
    captured: dict[str, object] = {}

    class FakeDagRunner:
        def __init__(self, executor, **_kwargs):
            captured["store"] = executor.entity_store

        async def run(self, _graph, run_id, _payload, **_kwargs):
            store = captured["store"]
            captured["cached_before_run"] = run_id in store.memory_entities
            captured["entity_id"] = store.resolve("stock:TEST").id
            captured["related_refs"] = store.related_refs("stock:TEST")
            return SimpleNamespace(
                node_outputs={"n1": NodeOutput(node_name="n1", ok=True)},
                failures={},
                payload={"ok": True},
            )

    monkeypatch.setattr("edera_core.dag_controller.DagRunner", FakeDagRunner)
    async with factory() as session:
        await _seed_runtime_core(session, config)
        await create_ordinary_entity(
            session,
            "stock",
            "stock-row-1",
            {"code": "TEST"},
            config.entity_types,
        )
        await create_ordinary_entity(
            session,
            "rss-source",
            "source-rss",
            {"name": "rss"},
            config.entity_types,
        )
        await create_relation(session, "stock:TEST", "rss-source:rss", "uses-source", {}, config.entity_types)
        await session.commit()

    try:
        result = await controller._run("run-1", "manual", "demo", snapshot=controller.runtime_snapshot())
    finally:
        await engine.dispose()

    assert result == {"ok": True}
    assert captured["cached_before_run"] is True
    assert captured["entity_id"] == "stock-row-1"
    assert captured["related_refs"] == ["rss-source:rss"]
    assert "run-1" not in captured["store"].memory_entities


@pytest.mark.asyncio
async def test_run_rejects_invalid_closure_before_creating_dag_run(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'edera.db'}")
    await init_db(engine)
    factory = session_factory(engine)
    controller = DagController(tmp_path / "config")
    controller.engine = engine
    controller.factory = factory
    _install_runtime_state(
        controller,
        _app_config(),
        RuntimeControlSnapshot(SystemConfig(config_git_commit=False), RuntimeSettings(), None, None),
    )
    async with factory() as session:
        await save_core_entity(
            session,
            EntityConfig(
                id="dag:demo",
                type="dag",
                attributes={"name": "demo", "nodes": [{"id": "bad", "type": "missing"}], "edges": [], "ui": {}},
            ),
        )
        await session.commit()

    try:
        with pytest.raises(Exception, match="missing node config: missing"):
            await controller._run("run-invalid", "manual", "demo", snapshot=controller.runtime_snapshot())
        async with factory() as session:
            runs = await recent_dag_runs(session)
    finally:
        await engine.dispose()

    assert runs == []


@pytest.mark.asyncio
async def test_wait_for_idle_uses_database_dag_state(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'edera.db'}")
    await init_db(engine)
    factory = session_factory(engine)
    controller = _controller(tmp_path)
    controller.engine = engine
    controller.factory = factory
    controller._runtime_config.dags = {}
    release = asyncio.Event()
    active_task = asyncio.create_task(release.wait())
    controller.active_runs["other"] = SimpleNamespace(dag_name="other", run_id="run-active", task=active_task)
    async with factory() as session:
        await save_core_entity(
            session,
            EntityConfig(
                id="dag:demo",
                type="dag",
                attributes={
                    "name": "demo",
                    "nodes": [],
                    "edges": [],
                    "ui": {"wait_for": {"status": "idle", "node": "n1"}},
                },
            ),
        )
        await save_core_entity(
            session,
            EntityConfig(
                id="dag:other",
                type="dag",
                attributes={"name": "other", "nodes": [{"id": "n1", "type": "reader"}], "edges": [], "ui": {}},
            ),
        )
        await session.commit()

    try:
        waiter = asyncio.create_task(controller._wait_for_idle("demo", None))
        await asyncio.sleep(0.02)
        assert not waiter.done()
        release.set()
        await waiter
    finally:
        release.set()
        await active_task
        await engine.dispose()


@pytest.mark.asyncio
async def test_run_node_trigger_uses_dag_scope(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'edera.db'}")
    await init_db(engine)
    factory = session_factory(engine)
    controller = _controller(tmp_path)
    controller.engine = engine
    controller.factory = factory
    controller._runtime_config.dags = {}
    controller._locks["demo"] = asyncio.Lock()
    captured: dict[str, object] = {}

    async def fake_run_single_node(run_id, source, dag_name, instance, payload, stop_event, snapshot, execution_snapshot=None):
        captured["dag_name"] = dag_name
        captured["node_id"] = instance.id
        captured["payload"] = payload
        captured["snapshot_dag"] = execution_snapshot.dag_config.name if execution_snapshot else None
        return {"ok": True}

    monkeypatch.setattr(controller, "_run_single_node", fake_run_single_node)
    async with factory() as session:
        await save_core_entity(session, EntityConfig(id="node:reader", type="node", attributes=_reader_node()))
        await save_core_entity(session, EntityConfig(id="dag:demo", type="dag", attributes={"name": "demo", "nodes": [{"id": "n1", "type": "reader"}], "edges": [], "ui": {}}))
        await save_core_entity(session, EntityConfig(id="dag:other", type="dag", attributes={"name": "other", "nodes": [{"id": "n1", "type": "reader"}], "edges": [], "ui": {}}))
        await session.commit()

    try:
        run_id = await controller.run_node_trigger("demo/n1", {"value": 1})
        await controller.active_runs["demo"].task
    finally:
        await engine.dispose()

    assert run_id
    assert captured == {"dag_name": "demo", "node_id": "n1", "payload": {"value": 1}, "snapshot_dag": "demo"}


def test_legacy_node_trigger_target_rejected():
    with pytest.raises(ValueError, match="<dag_name>/<node_id>"):
        _parse_node_trigger_target("n1")


@pytest.mark.asyncio
async def test_retry_node_uses_database_execution_snapshot(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'edera.db'}")
    await init_db(engine)
    factory = session_factory(engine)
    controller = _controller(tmp_path)
    controller.engine = engine
    controller.factory = factory
    controller._runtime_config.dags = {}
    captured: dict[str, object] = {}

    async def fake_run(*_args, retry_nodes=None, execution_snapshot=None, **_kwargs):
        captured["retry_nodes"] = retry_nodes
        captured["snapshot_dag"] = execution_snapshot.dag_config.name if execution_snapshot else None
        return {"ok": True}

    monkeypatch.setattr(controller, "_run", fake_run)
    async with factory() as session:
        await _seed_demo_core(session)
        await create_dag_run(session, "run-old", "manual", ["n1"], "demo")
        await finish_dag_run(session, "run-old", "succeeded")
        await session.commit()

    try:
        result = await controller.retry_node("demo", None, ["n1"])
        await controller.active_runs["demo"].task
    finally:
        await engine.dispose()

    assert result.retry_of == "run-old"
    assert captured == {"retry_nodes": {"n1"}, "snapshot_dag": "demo"}


@pytest.mark.asyncio
async def test_resume_node_uses_database_execution_snapshot(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'edera.db'}")
    await init_db(engine)
    factory = session_factory(engine)
    controller = _controller(tmp_path)
    controller.engine = engine
    controller.factory = factory
    controller._runtime_config.dags = {}
    captured: dict[str, object] = {}

    async def fake_run(*_args, retry_nodes=None, execution_snapshot=None, **_kwargs):
        captured["retry_nodes"] = retry_nodes
        captured["snapshot_dag"] = execution_snapshot.dag_config.name if execution_snapshot else None
        return {"ok": True}

    monkeypatch.setattr(controller, "_run", fake_run)
    async with factory() as session:
        await _seed_demo_core(session)
        await create_dag_run(session, "run-old", "manual", ["n1"], "demo")
        await finish_dag_run(session, "run-old", "failed")
        await session.commit()

    try:
        run_id = await controller.resume_node("demo", "run-old", "n1", {"resume": True})
        await controller.active_runs["demo"].task
    finally:
        await engine.dispose()

    assert run_id == "run-old"
    assert captured == {"retry_nodes": {"n1"}, "snapshot_dag": "demo"}


def _controller(tmp_path) -> DagController:
    controller = DagController(tmp_path / "config")
    _install_runtime_state(
        controller,
        _app_config(),
        RuntimeControlSnapshot(SystemConfig(config_git_commit=False), RuntimeSettings(), None, None),
    )
    return controller


def _app_config() -> AppConfig:
    return AppConfig(
        system=SystemConfig(config_git_commit=False),
        entity_types={"stock": _entity_type("Stock"), "rss-source": _source_entity_type()},
        entities=EntitiesConfig(),
        entity_relations=EntityRelationsConfig(),
        runtime=RuntimeSettings(),
        nodes={
            "reader": NodeConfig(**_reader_node())
        },
        skills={},
        dags={"demo": DagConfig(name="demo", nodes=[DagNodeInstance(id="n1", type="reader")], edges=[], ui={})},
    )


def _reader_node() -> dict[str, object]:
    return {
        "name": "reader",
        "type": "function",
        "handler": "reader",
        "input_type": "Any",
        "output_type": "Any",
    }


def _install_runtime_state(controller: DagController, config: AppConfig, snapshot: RuntimeControlSnapshot) -> None:
    controller._runtime_config = config
    controller._snapshot = snapshot
    controller._bootstrap = BootstrapResult([], {}, {}, {})
    controller._entity_store = None
    controller._extension_table_names = {}


def _entity_type(display_name: str) -> EntityTypeConfig:
    return EntityTypeConfig.model_validate(
        {
            "display_name": display_name,
            "business_id_field": "code",
            "display_template": "{code}",
            "storage_tier": "database",
            "schema": {"properties": {"code": {"type": "string"}}},
        }
    )


def _source_entity_type() -> EntityTypeConfig:
    return EntityTypeConfig.model_validate(
        {
            "display_name": "RSS",
            "business_id_field": "name",
            "display_template": "{name}",
            "storage_tier": "database",
            "schema": {"properties": {"name": {"type": "string"}}},
        }
    )


@asynccontextmanager
async def _session(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'edera.db'}")
    await init_db(engine)
    try:
        async with session_factory(engine)() as session:
            yield session
    finally:
        await engine.dispose()


async def _install(session) -> None:
    await save_installed_extension(
        session,
        name="demo-ext",
        version="1.0.0",
        manifest_snapshot={
            "name": "demo-ext",
            "version": "1.0.0",
            "handlers": [{"name": "reader", "entry": "handler.py"}],
        },
    )
    await session.commit()


async def _seed_runtime_core(session, config: AppConfig) -> None:
    for name, node in config.nodes.items():
        await save_core_entity(session, EntityConfig(id=f"node:{name}", type="node", attributes=node.model_dump(mode="json")))
    for name, dag in config.dags.items():
        await save_core_entity(session, EntityConfig(id=f"dag:{name}", type="dag", attributes=dag.model_dump(mode="json", by_alias=True)))


async def _seed_demo_core(session) -> None:
    await save_core_entity(session, EntityConfig(id="node:reader", type="node", attributes=_reader_node()))
    await save_core_entity(session, EntityConfig(id="dag:demo", type="dag", attributes={"name": "demo", "nodes": [{"id": "n1", "type": "reader"}], "edges": [], "ui": {}}))
