from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from edera_core.bootstrap import BootstrapResult
from edera_core.config.schema import AppConfig, DagConfig, DagNodeInstance, EntityTypeConfig, EntitiesConfig, EntityRelationsConfig, NodeConfig, RuntimeSettings, SystemConfig
from edera_core.dag.loader import load_graph
from edera_core.dag_controller import DagController, RuntimeSnapshot
from edera_core.node.models import NodeOutput
from edera_core.snapshot import DagExecutionSnapshot
from edera_core.storage import create_engine, init_db, session_factory
from edera_core.storage.repository import create_ordinary_entity, create_relation, save_installed_extension


@pytest.mark.asyncio
async def test_create_snapshot_for_dag_execution(tmp_path):
    controller = DagController(tmp_path / "config")
    snapshot = _runtime_snapshot()
    graph = load_graph(snapshot.config.dags["demo"], snapshot.config.nodes)
    async with _session(tmp_path) as session:
        await _install(session)
        executor = await controller._build_run_executor(snapshot, graph, session)

    assert isinstance(executor.snapshot, DagExecutionSnapshot)
    assert executor.snapshot.dag_config.name == "demo"


@pytest.mark.asyncio
async def test_snapshot_isolation(tmp_path):
    controller = DagController(tmp_path / "config")
    snapshot = _runtime_snapshot()
    graph = load_graph(snapshot.config.dags["demo"], snapshot.config.nodes)
    async with _session(tmp_path) as session:
        await _install(session)
        executor = await controller._build_run_executor(snapshot, graph, session)

    snapshot.config.entity_types["new"] = _entity_type("New")

    assert "new" not in executor.snapshot.entity_types


@pytest.mark.asyncio
async def test_snapshot_freezes_handler_metadata(tmp_path):
    controller = DagController(tmp_path / "config")
    snapshot = _runtime_snapshot()
    graph = load_graph(snapshot.config.dags["demo"], snapshot.config.nodes)
    async with _session(tmp_path) as session:
        await _install(session)
        executor = await controller._build_run_executor(snapshot, graph, session)
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
async def test_run_preloads_and_clears_dag_entity_cache(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'edera.db'}")
    await init_db(engine)
    factory = session_factory(engine)
    controller = DagController(tmp_path / "config")
    controller.engine = engine
    controller.factory = factory
    snapshot = _runtime_snapshot()
    snapshot.config.dags["demo"].nodes[0].config["entities"] = ["stock:TEST"]
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
        await create_ordinary_entity(
            session,
            "stock",
            "stock-row-1",
            {"code": "TEST"},
            snapshot.config.entity_types,
        )
        await create_ordinary_entity(
            session,
            "rss-source",
            "source-rss",
            {"name": "rss"},
            snapshot.config.entity_types,
        )
        await create_relation(session, "stock:TEST", "rss-source:rss", "uses-source", {}, snapshot.config.entity_types)
        await session.commit()

    try:
        result = await controller._run("run-1", "manual", "demo", snapshot=snapshot)
    finally:
        await engine.dispose()

    assert result == {"ok": True}
    assert captured["cached_before_run"] is True
    assert captured["entity_id"] == "stock-row-1"
    assert captured["related_refs"] == ["rss-source:rss"]
    assert "run-1" not in captured["store"].memory_entities


def _runtime_snapshot() -> RuntimeSnapshot:
    config = AppConfig(
        system=SystemConfig(config_git_commit=False),
        entity_types={"stock": _entity_type("Stock"), "rss-source": _source_entity_type()},
        entities=EntitiesConfig(),
        entity_relations=EntityRelationsConfig(),
        runtime=RuntimeSettings(),
        nodes={
            "reader": NodeConfig(
                name="reader",
                type="function",
                handler="reader",
                input_type="Any",
                output_type="Any",
            )
        },
        skills={},
        dags={"demo": DagConfig(name="demo", nodes=[DagNodeInstance(id="n1", type="reader")], edges=[], ui={})},
    )
    return RuntimeSnapshot(config, BootstrapResult([], {}, {}, {}), None, None, None, {})


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
