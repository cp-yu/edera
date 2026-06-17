from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from edera_core.bootstrap import BootstrapResult
from edera_core.config.entities import EntityStore
from edera_core.config.schema import AppConfig, DagConfig, DagNodeInstance, EntityConfig, EntityTypeConfig, EntitiesConfig, EntityRelationsConfig, NodeConfig, RuntimeSettings, SystemConfig
from edera_core.dag.loader import load_graph
from edera_core.dag_controller import DagController, RuntimeControlSnapshot, _parse_node_trigger_target
from edera_core.node.models import NodeOutput
from edera_core.snapshot import DagExecutionSnapshot
from edera_core.storage import create_engine, init_db, session_factory
from edera_core.storage.repository import create_dag_run, create_ordinary_entity, create_relation, finish_dag_run, recent_dag_runs, save_core_entity, save_installed_extension
from edera_core.trigger import TriggerExpression


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
    assert controller.runtime_config().dags["demo"].name == "demo"


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

    meta = await executor.snapshot.handler_resolver.get("demo-ext.reader")

    assert meta.path == tmp_path / "handlers" / "demo-ext.reader" / "handler.py"


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
    controller = DagController(_config_dir(tmp_path))
    controller.engine = engine
    controller.factory = factory
    _install_runtime_state(controller, _app_config(), RuntimeControlSnapshot(SystemConfig(config_git_commit=False), RuntimeSettings(), None, None))
    config = controller.runtime_config()
    config.dags["demo"].nodes[0].config["entities"] = ["stock:TEST"]
    captured: dict[str, object] = {}

    class FakeDagRunner:
        def __init__(self, executor, **_kwargs):
            captured["store"] = executor.entity_store

        async def run(self, _graph, run_id, **_kwargs):
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
async def test_run_preloads_resource_refs_from_dag_closure(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'edera.db'}")
    await init_db(engine)
    factory = session_factory(engine)
    controller = DagController(_config_dir(tmp_path))
    controller.engine = engine
    controller.factory = factory
    _install_runtime_state(controller, _app_config(), RuntimeControlSnapshot(SystemConfig(config_git_commit=False), RuntimeSettings(), None, None))
    captured: dict[str, object] = {}

    class FakeDagRunner:
        def __init__(self, executor, **_kwargs):
            captured["store"] = executor.entity_store

        async def run(self, _graph, run_id, **_kwargs):
            store = captured["store"]
            captured["resource_permits"] = store.resolve("v8_isolate").attributes["permits"]
            return SimpleNamespace(
                node_outputs={"child": NodeOutput(node_name="child", ok=True)},
                failures={},
                payload={"ok": True},
            )

    monkeypatch.setattr("edera_core.dag_controller.DagRunner", FakeDagRunner)
    async with factory() as session:
        await _install(session)
        await save_core_entity(session, EntityConfig(id="node:reader", type="node", attributes=_reader_node()))
        await save_core_entity(session, EntityConfig(id="v8_isolate", type="resource", attributes={"id": "v8_isolate", "permits": 1}))
        await save_core_entity(
            session,
            EntityConfig(
                id="dag:demo",
                type="dag",
                attributes={"name": "demo", "nodes": [{"id": "child", "type": "dag", "dag_ref": "child"}], "edges": [], "ui": {}},
            ),
        )
        await save_core_entity(
            session,
            EntityConfig(
                id="dag:child",
                type="dag",
                attributes={"name": "child", "nodes": [{"id": "n1", "type": "reader", "resource": "v8_isolate"}], "edges": [], "ui": {}},
            ),
        )
        await session.commit()

    try:
        result = await controller._run("run-resource", "manual", "demo", snapshot=controller.runtime_snapshot())
    finally:
        await engine.dispose()

    assert result == {"ok": True}
    assert captured["resource_permits"] == 1


@pytest.mark.asyncio
async def test_run_rejects_invalid_closure_before_creating_dag_run(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'edera.db'}")
    await init_db(engine)
    factory = session_factory(engine)
    controller = DagController(_config_dir(tmp_path))
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

    async def fake_run_single_node(run_id, source, dag_name, instance, stop_event, snapshot, execution_snapshot=None, node_inputs=None, **_kwargs):
        captured["dag_name"] = dag_name
        captured["node_id"] = instance.id
        captured["payload"] = node_inputs.get(instance.id) if node_inputs else None
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
    controller = DagController(_config_dir(tmp_path))
    _install_runtime_state(
        controller,
        _app_config(),
        RuntimeControlSnapshot(SystemConfig(config_git_commit=False), RuntimeSettings(), None, None),
    )
    return controller


def _config_dir(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir(exist_ok=True)
    (config_dir / "system.toml").write_text(f'handlers_dir = "{tmp_path / "handlers"}"\n', encoding="utf-8")
    return config_dir


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
        "handler": "demo-ext.reader",
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
            "handlers": [{"name": "demo-ext.reader", "package": "demo-ext.reader", "entry": "handler.py"}],
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


@pytest.mark.asyncio
async def test_controller_start_idle_no_startup_trigger(tmp_path):
    controller, _factory = await _startup_controller(tmp_path, window_seconds=10, triggers=[])

    async def fake_start_run(source="manual", dag_name="default", **_kwargs):
        raise AssertionError(f"unexpected start_run: source={source} dag={dag_name}")

    controller.start_run = fake_start_run  # type: ignore[assignment]
    try:
        await controller._open_startup_window(10)
        assert controller.active_runs == {}
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_trigger_run_dag_injects_payload_as_source_shared_inputs(tmp_path):
    controller = _controller(tmp_path)
    captured: dict[str, object] = {}

    async def fake_start_run(source="manual", dag_name="default", **kwargs):
        captured["source"] = source
        captured["dag_name"] = dag_name
        captured["source_shared_inputs"] = kwargs.get("source_shared_inputs")
        return "run-1"

    controller.start_run = fake_start_run  # type: ignore[assignment]
    executor = controller._new_trigger_executor(controller.runtime_config(), None)

    await executor.fire("dag:demo", {"ticker": "300470.SZ"}, source="trigger:cron")

    assert captured == {
        "source": "trigger:cron",
        "dag_name": "demo",
        "source_shared_inputs": {"ticker": "300470.SZ"},
    }


@pytest.mark.asyncio
async def test_startup_single_trigger_fires_once(tmp_path):
    controller, factory = await _startup_controller(tmp_path, window_seconds=10, triggers=[
        {"id": "boot", "wait_for": "startup", "target": "dag:bootstrap"},
    ])

    fired: list[tuple[str, str]] = []

    async def fake_start_run(source="manual", dag_name="default", **_kwargs):
        fired.append((source, dag_name))
        return "run-startup"

    controller.start_run = fake_start_run  # type: ignore[assignment]
    try:
        await controller._open_startup_window(10)
        assert fired == [("startup", "bootstrap")]
        assert "startup" in controller.trigger_executor.events.events
    finally:
        await controller.shutdown()
        await factory().bind.cache_clear() if hasattr(factory().bind, "cache_clear") else None


@pytest.mark.asyncio
async def test_startup_multiple_triggers_concurrent(tmp_path):
    controller, factory = await _startup_controller(tmp_path, window_seconds=10, triggers=[
        {"id": "t1", "wait_for": "startup", "target": "dag:alpha"},
        {"id": "t2", "wait_for": "startup", "target": "dag:beta"},
        {"id": "t3", "wait_for": "startup", "target": "dag:gamma"},
    ])

    fired: list[tuple[str, str]] = []

    async def fake_start_run(source="manual", dag_name="default", **_kwargs):
        fired.append((source, dag_name))
        return f"run-{dag_name}"

    controller.start_run = fake_start_run  # type: ignore[assignment]
    try:
        await controller._open_startup_window(10)
        assert fired == [
            ("startup", "alpha"),
            ("startup", "beta"),
            ("startup", "gamma"),
        ]
        assert "startup" in controller.trigger_executor.events.events
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_startup_window_expires_clears_bit(tmp_path):
    controller, _factory = await _startup_controller(tmp_path, window_seconds=10, triggers=[
        {"id": "boot", "wait_for": "startup", "target": "dag:bootstrap"},
    ])

    async def fake_start_run(source="manual", dag_name="default", **_kwargs):
        return "run-startup"

    controller.start_run = fake_start_run  # type: ignore[assignment]
    try:
        await controller._open_startup_window(0.1)
        await asyncio.sleep(0.2)
        assert "startup" not in controller.trigger_executor.events.events
        expr = TriggerExpression("startup")
        assert expr.evaluate(set(controller.trigger_executor.events.events)) is False
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_startup_window_configurable(tmp_path):
    controller, _factory = await _startup_controller(tmp_path, window_seconds=10, triggers=[
        {"id": "boot", "wait_for": "startup", "target": "dag:bootstrap"},
    ])

    async def fake_start_run(source="manual", dag_name="default", **_kwargs):
        return "run-startup"

    controller.start_run = fake_start_run  # type: ignore[assignment]
    try:
        await controller._open_startup_window(0.1)
        await asyncio.sleep(0.2)
        assert "startup" not in controller.trigger_executor.events.events
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_startup_clears_residue_before_window(tmp_path):
    controller, factory = await _startup_controller(tmp_path, window_seconds=10, triggers=[
        {"id": "boot", "wait_for": "startup", "target": "dag:bootstrap"},
    ])

    from edera_core.storage.entities import EventGroupBit
    from sqlmodel import select

    async with factory() as session:
        session.add(EventGroupBit(event="startup"))
        await session.commit()

    async def fake_start_run(source="manual", dag_name="default", **_kwargs):
        return "run-startup"

    controller.start_run = fake_start_run  # type: ignore[assignment]
    try:
        await controller._open_startup_window(10)
        async with factory() as session:
            rows = (await session.exec(select(EventGroupBit.event))).all()
        assert list(rows) == ["startup"]
    finally:
        await controller.shutdown()


@pytest.mark.asyncio
async def test_shutdown_cancels_startup_run_no_replay(tmp_path):
    controller, factory = await _startup_controller(tmp_path, window_seconds=10, triggers=[
        {"id": "boot", "wait_for": "startup", "target": "dag:bootstrap"},
    ])

    started = asyncio.Event()

    async def fake_start_run(source="manual", dag_name="default", **_kwargs):
        started.set()
        return "run-startup"

    controller.start_run = fake_start_run  # type: ignore[assignment]
    await controller._open_startup_window(10)
    assert controller._startup_window_task is not None
    await controller.shutdown()
    assert controller._startup_window_task.cancelled() or controller._startup_window_task.done()


@pytest.mark.asyncio
async def test_startup_compound_expression_within_window(tmp_path):
    controller, factory = await _startup_controller(tmp_path, window_seconds=10, triggers=[
        {"id": "compound", "wait_for": "startup AND event:market-open", "target": "dag:open"},
    ])

    fired: list[tuple[str, str]] = []

    async def fake_start_run(source="manual", dag_name="default", **_kwargs):
        fired.append((source, dag_name))
        return f"run-{dag_name}"

    controller.start_run = fake_start_run  # type: ignore[assignment]
    try:
        await controller._open_startup_window(10)
        assert fired == []
        await controller.trigger_executor.emit("event:market-open", source="test")
        assert fired == [("startup", "open")]
    finally:
        await controller.shutdown()


async def _startup_controller(tmp_path, *, window_seconds: int, triggers: list[dict[str, str]]):
    from edera_core.config.schema import EntitiesConfig, EntityConfig, EntityRelationsConfig
    from edera_core.storage import create_engine, init_db, session_factory
    from edera_core.storage.repository import save_core_entity

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "system.toml").write_text(
        f'handlers_dir = "{tmp_path / "handlers"}"\nstartup_window_seconds = {window_seconds}\n',
        encoding="utf-8",
    )

    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'edera.db'}")
    await init_db(engine)
    factory = session_factory(engine)

    controller = DagController(config_dir)
    controller.engine = engine
    controller.factory = factory
    _install_runtime_state(
        controller,
        _app_config(),
        RuntimeControlSnapshot(SystemConfig(config_git_commit=False), RuntimeSettings(), None, None),
    )

    store = EntityStore(
        EntitiesConfig(),
        _app_config().entity_types,
        EntityRelationsConfig(),
        None,
    )
    store.memory_entities[""] = {
        trigger["id"]: EntityConfig(
            id=str(trigger["id"]),
            type="trigger",
            attributes={
                "name": trigger["id"],
                "wait_for": trigger["wait_for"],
                "target": trigger["target"],
                "enabled": True,
            },
        )
        for trigger in triggers
    }
    executor = controller._new_trigger_executor(controller.runtime_config(), store)
    await executor.load()
    controller.trigger_executor = executor
    controller._entity_store = store

    async with factory() as session:
        for trigger in triggers:
            await save_core_entity(
                session,
                EntityConfig(
                    id=str(trigger["id"]),
                    type="trigger",
                    attributes={
                        "name": trigger["id"],
                        "wait_for": trigger["wait_for"],
                        "target": trigger["target"],
                        "enabled": True,
                    },
                ),
            )
        await session.commit()

    return controller, factory
