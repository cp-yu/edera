from __future__ import annotations

import pytest

from edera_core.config.schema import EntityTypeConfig
from edera_core.storage import create_engine, init_db, session_factory
from edera_core.storage.repository import (
    create_ordinary_entity,
    create_relation,
    delete_ordinary_entity,
    get_ordinary_entity,
    update_ordinary_entity,
)


@pytest.mark.asyncio
async def test_create_ordinary_entity(tmp_path):
    entity_types = {"stock": _entity_type()}
    async with await _session(tmp_path) as session:
        entity = await create_ordinary_entity(session, "stock", "stock:test", {"code": "TEST", "name": "Test"}, entity_types)

        saved = await get_ordinary_entity(session, "stock", "stock:test", entity_types)

    assert saved == entity


@pytest.mark.asyncio
async def test_update_entity(tmp_path):
    entity_types = {"stock": _entity_type()}
    async with await _session(tmp_path) as session:
        await create_ordinary_entity(session, "stock", "stock:test", {"code": "TEST", "name": "Old"}, entity_types)

        updated = await update_ordinary_entity(session, "stock:test", {"name": "New"}, entity_types)

    assert updated.attributes == {"code": "TEST", "name": "New"}


@pytest.mark.asyncio
async def test_delete_entity_with_relations(tmp_path):
    entity_types = {"stock": _entity_type(), "rss-source": _entity_type("url")}
    async with await _session(tmp_path) as session:
        await create_ordinary_entity(session, "stock", "stock:test", {"code": "TEST"}, entity_types)
        await create_ordinary_entity(session, "rss-source", "source:test", {"url": "https://example.test/rss"}, entity_types)
        relation = await create_relation(session, "stock:test", "source:test", "uses-source", entity_types=entity_types)

        result = await delete_ordinary_entity(session, "stock:test", entity_types)

    assert result.deleted is False
    assert [item.id for item in result.relations] == [relation.id]


@pytest.mark.asyncio
async def test_delete_entity_with_relation_business_ref_blocks_row_id_delete(tmp_path):
    entity_types = {"stock": _entity_type(), "rss-source": _entity_type("url")}
    async with await _session(tmp_path) as session:
        await create_ordinary_entity(session, "stock", "stock-row-1", {"code": "TEST"}, entity_types)
        await create_ordinary_entity(session, "rss-source", "source:test", {"url": "feed"}, entity_types)
        relation = await create_relation(session, "stock:TEST", "rss-source:feed", "uses-source", entity_types=entity_types)

        result = await delete_ordinary_entity(session, "stock-row-1", entity_types)

    assert result.deleted is False
    assert [item.id for item in result.relations] == [relation.id]


@pytest.mark.asyncio
async def test_create_entity_rejects_invalid_attributes(tmp_path):
    entity_types = {"stock": _entity_type()}
    async with await _session(tmp_path) as session:
        with pytest.raises(ValueError, match="must be string"):
            await create_ordinary_entity(session, "stock", "stock:test", {"code": 123}, entity_types)


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


async def _session(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'edera.db'}")
    await init_db(engine)
    return session_factory(engine)()
