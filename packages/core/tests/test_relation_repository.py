from __future__ import annotations

from contextlib import asynccontextmanager

import pytest

from edera_core.config.schema import EntityTypeConfig
from edera_core.storage import create_engine, init_db, session_factory
from edera_core.storage.repository import create_ordinary_entity, create_relation, list_relations


@pytest.mark.asyncio
async def test_create_relation(tmp_path):
    entity_types = _entity_types()
    async with _session(tmp_path) as session:
        await _seed_entities(session, entity_types)

        relation = await create_relation(session, "stock:test", "source:test", "uses-source", entity_types=entity_types)

    assert relation.from_entity_id == "stock:test"
    assert relation.to_entity_id == "source:test"
    assert relation.relation_type == "uses-source"


@pytest.mark.asyncio
async def test_list_relations_filter(tmp_path):
    entity_types = _entity_types()
    async with _session(tmp_path) as session:
        await _seed_entities(session, entity_types)
        await create_relation(session, "stock:test", "source:test", "uses-source", entity_types=entity_types)
        await create_relation(session, "stock:test", "source:other", "mentions", entity_types=entity_types)

        relations = await list_relations(session, from_entity_id="stock:test", relation_type="uses-source")

    assert [(item.to_entity_id, item.relation_type) for item in relations] == [("source:test", "uses-source")]


def _entity_types() -> dict[str, EntityTypeConfig]:
    return {
        "stock": _entity_type("code"),
        "rss-source": _entity_type("url"),
    }


def _entity_type(business_id_field: str) -> EntityTypeConfig:
    return EntityTypeConfig.model_validate(
        {
            "display_name": "Entity",
            "business_id_field": business_id_field,
            "display_template": "{" + business_id_field + "}",
            "storage_tier": "database",
            "schema": {"properties": {business_id_field: {"type": "string"}}},
        }
    )


async def _seed_entities(session, entity_types):
    await create_ordinary_entity(session, "stock", "stock:test", {"code": "TEST"}, entity_types)
    await create_ordinary_entity(session, "rss-source", "source:test", {"url": "https://example.test/rss"}, entity_types)
    await create_ordinary_entity(session, "rss-source", "source:other", {"url": "https://example.test/other"}, entity_types)


@asynccontextmanager
async def _session(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'edera.db'}")
    try:
        await init_db(engine)
        async with session_factory(engine)() as session:
            yield session
    finally:
        await engine.dispose()
