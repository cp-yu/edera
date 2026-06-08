from __future__ import annotations

from contextlib import asynccontextmanager

import pytest

from edera_core.config.schema import EntityTypeConfig
from edera_core.storage import create_engine, init_db, session_factory
from edera_core.storage.repository import (
    create_ordinary_entity,
    create_relation,
    delete_ordinary_entity,
    get_dag_config,
    get_node_config,
    get_ordinary_entity,
    list_dag_names,
    list_node_summaries,
    save_core_entity,
    update_ordinary_entity,
)
from edera_core.config.schema import EntityConfig


@pytest.mark.asyncio
async def test_create_ordinary_entity(tmp_path):
    entity_types = {"stock": _entity_type()}
    async with _session(tmp_path) as session:
        entity = await create_ordinary_entity(session, "stock", "stock:test", {"code": "TEST", "name": "Test"}, entity_types)

        saved = await get_ordinary_entity(session, "stock", "stock:test", entity_types)

    assert saved == entity


@pytest.mark.asyncio
async def test_update_entity(tmp_path):
    entity_types = {"stock": _entity_type()}
    async with _session(tmp_path) as session:
        await create_ordinary_entity(session, "stock", "stock:test", {"code": "TEST", "name": "Old"}, entity_types)

        updated = await update_ordinary_entity(session, "stock:test", {"name": "New"}, entity_types)

    assert updated.attributes == {"code": "TEST", "name": "New"}


@pytest.mark.asyncio
async def test_delete_entity_with_relations(tmp_path):
    entity_types = {"stock": _entity_type(), "rss-source": _entity_type("url")}
    async with _session(tmp_path) as session:
        await create_ordinary_entity(session, "stock", "stock:test", {"code": "TEST"}, entity_types)
        await create_ordinary_entity(session, "rss-source", "source:test", {"url": "https://example.test/rss"}, entity_types)
        relation = await create_relation(session, "stock:test", "source:test", "uses-source", entity_types=entity_types)

        result = await delete_ordinary_entity(session, "stock:test", entity_types)

    assert result.deleted is False
    assert [item.id for item in result.relations] == [relation.id]


@pytest.mark.asyncio
async def test_delete_entity_with_relation_business_ref_blocks_row_id_delete(tmp_path):
    entity_types = {"stock": _entity_type(), "rss-source": _entity_type("url")}
    async with _session(tmp_path) as session:
        await create_ordinary_entity(session, "stock", "stock-row-1", {"code": "TEST"}, entity_types)
        await create_ordinary_entity(session, "rss-source", "source:test", {"url": "feed"}, entity_types)
        relation = await create_relation(session, "stock:TEST", "rss-source:feed", "uses-source", entity_types=entity_types)

        result = await delete_ordinary_entity(session, "stock-row-1", entity_types)

    assert result.deleted is False
    assert [item.id for item in result.relations] == [relation.id]


@pytest.mark.asyncio
async def test_create_entity_rejects_invalid_attributes(tmp_path):
    entity_types = {"stock": _entity_type()}
    async with _session(tmp_path) as session:
        with pytest.raises(ValueError, match="must be string"):
            await create_ordinary_entity(session, "stock", "stock:test", {"code": 123}, entity_types)


@pytest.mark.asyncio
async def test_indexed_core_dag_and_node_reads(tmp_path):
    async with _session(tmp_path) as session:
        await save_core_entity(
            session,
            EntityConfig(
                id="dag:demo",
                type="dag",
                attributes={
                    "name": "demo",
                    "nodes": [{"id": "n1", "type": "reader"}],
                    "edges": [],
                    "ui": {},
                },
            ),
        )
        await save_core_entity(
            session,
            EntityConfig(
                id="node:reader",
                type="node",
                attributes={
                    "name": "reader",
                    "type": "function",
                    "handler": "reader",
                    "input_type": "Any",
                    "output_type": "Any",
                },
            ),
        )

        dag = await get_dag_config(session, "demo")
        node = await get_node_config(session, "reader")

    assert dag is not None and dag.name == "demo"
    assert node is not None and node.name == "reader"


@pytest.mark.asyncio
async def test_core_node_save_ignores_removed_input_binding(tmp_path):
    async with _session(tmp_path) as session:
        saved = await save_core_entity(
            session,
            EntityConfig(
                id="node:reader",
                type="node",
                attributes={
                    "name": "reader",
                    "type": "function",
                    "handler": "reader",
                    "input_type": "Any",
                    "output_type": "Any",
                    "input_binding": "ticker",
                },
            ),
        )

        node = await get_node_config(session, "reader")

    assert "input_binding" not in saved.attributes
    assert node is not None and "input_binding" not in node.model_dump(mode="json")


@pytest.mark.asyncio
async def test_core_dag_and_node_summary_lists(tmp_path):
    async with _session(tmp_path) as session:
        await save_core_entity(
            session,
            EntityConfig(id="dag:demo", type="dag", attributes={"name": "demo", "nodes": [], "edges": [], "ui": {}}),
        )
        await save_core_entity(
            session,
            EntityConfig(
                id="node:reader",
                type="node",
                attributes={"name": "reader", "type": "function", "handler": "reader", "input_type": "Any", "output_type": "Any"},
            ),
        )

        dag_names = await list_dag_names(session)
        node_summaries = await list_node_summaries(session)

    assert dag_names == ["demo"]
    assert node_summaries == [{"name": "reader", "type": "function"}]


def _entity_type(business_id_field: str = "code") -> EntityTypeConfig:
    return EntityTypeConfig.model_validate(
        {
            "display_name": "Entity",
            "business_id_field": business_id_field,
            "display_template": "{" + business_id_field + "}",
            "storage_tier": "database",
            "schema": {"properties": {business_id_field: {"type": "string"}, "name": {"type": "string"}}},
        }
    )


@asynccontextmanager
async def _session(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'edera.db'}")
    try:
        await init_db(engine)
        async with session_factory(engine)() as session:
            yield session
    finally:
        await engine.dispose()
