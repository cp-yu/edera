from __future__ import annotations

from contextlib import asynccontextmanager

import pytest

from edera_core.bootstrap import BootstrapResult
from edera_core.config.schema import AppConfig, DagConfig, DagNodeInstance, EntityTypeConfig, EntitiesConfig, EntityRelationsConfig, NodeConfig, RuntimeSettings, SystemConfig
from edera_core.dag.loader import load_graph
from edera_core.dag_controller import DagController, RuntimeSnapshot
from edera_core.snapshot import DagExecutionSnapshot
from edera_core.storage import create_engine, init_db, session_factory
from edera_core.storage.repository import save_installed_extension


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


def _runtime_snapshot() -> RuntimeSnapshot:
    config = AppConfig(
        system=SystemConfig(),
        entity_types={"stock": _entity_type("Stock")},
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
            "schema": {"properties": {"code": {"type": "string"}}},
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
