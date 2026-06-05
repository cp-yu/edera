from __future__ import annotations

from dataclasses import FrozenInstanceError
from contextlib import asynccontextmanager

import pytest

from edera_core.config.schema import DagConfig, EntityTypeConfig, NodeConfig
from edera_core.resolver import DatabaseHandlerResolver
from edera_core.snapshot import DagExecutionSnapshot
from edera_core.storage import create_engine, init_db, session_factory
from edera_core.storage.repository import save_installed_extension


@pytest.mark.asyncio
async def test_create_snapshot(tmp_path):
    snapshot = await _snapshot(tmp_path)

    assert snapshot.dag_config.name == "demo"
    assert "reader" in snapshot.node_configs
    assert "stock" in snapshot.entity_types


@pytest.mark.asyncio
async def test_snapshot_has_resolver(tmp_path):
    assert isinstance((await _snapshot(tmp_path)).handler_resolver, DatabaseHandlerResolver)


@pytest.mark.asyncio
async def test_snapshot_copies_entity_types(tmp_path):
    entity_types = _entity_types()
    async with _session(tmp_path) as session:
        await _install(session)
        snapshot = await DagExecutionSnapshot.create(_dag(), _nodes(), entity_types, session, tmp_path / "handlers")

    entity_types["new"] = _entity_type("New")

    assert "new" not in snapshot.entity_types


@pytest.mark.asyncio
async def test_snapshot_immutable(tmp_path):
    with pytest.raises(FrozenInstanceError):
        (await _snapshot(tmp_path)).entity_types = {}


async def _snapshot(tmp_path) -> DagExecutionSnapshot:
    async with _session(tmp_path) as session:
        await _install(session)
        return await DagExecutionSnapshot.create(_dag(), _nodes(), _entity_types(), session, tmp_path / "handlers")


def _dag() -> DagConfig:
    return DagConfig.model_validate({"name": "demo", "nodes": [{"id": "n1", "type": "reader"}], "edges": [], "ui": {}})


def _nodes() -> dict[str, NodeConfig]:
    return {
        "reader": NodeConfig(
            name="reader",
            type="function",
            input_type="Any",
            output_type="Any",
            handler="reader",
        )
    }


def _entity_types() -> dict[str, EntityTypeConfig]:
    return {"stock": _entity_type("Stock")}


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
