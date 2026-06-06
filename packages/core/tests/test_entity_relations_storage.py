from __future__ import annotations

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from edera_core.storage import create_engine, init_db, session_factory
from edera_core.storage.entities import EntityRelation


@pytest.mark.asyncio
async def test_create_table(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'edera.db'}")
    await init_db(engine)

    async with engine.connect() as conn:
        columns = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_columns("entity_relations"))
        indexes = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_indexes("entity_relations"))

    assert {column["name"] for column in columns} == {
        "id",
        "from_entity_id",
        "to_entity_id",
        "relation_type",
        "metadata",
        "created_at",
        "updated_at",
    }
    assert {"ix_entity_relations_from_entity_id", "ix_entity_relations_to_entity_id", "ix_entity_relations_relation_type"}.issubset(
        {index["name"] for index in indexes}
    )
    await engine.dispose()


@pytest.mark.asyncio
async def test_unique_constraint(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'edera.db'}")
    await init_db(engine)

    async with session_factory(engine)() as session:
        session.add(EntityRelation(id="r1", from_entity_id="stock:test", to_entity_id="source:test", relation_type="uses-source"))
        session.add(EntityRelation(id="r2", from_entity_id="stock:test", to_entity_id="source:test", relation_type="uses-source"))
        with pytest.raises(IntegrityError):
            await session.commit()

    await engine.dispose()
