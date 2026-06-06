from __future__ import annotations

import pytest
from sqlalchemy import inspect

from edera_core.storage import create_engine, init_db


@pytest.mark.asyncio
async def test_create_table(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'edera.db'}")
    await init_db(engine)

    async with engine.connect() as conn:
        columns = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_columns("skills"))
        indexes = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_indexes("skills"))

    assert {column["name"] for column in columns} == {
        "id",
        "name",
        "display_name",
        "description",
        "config_body",
        "created_at",
        "updated_at",
    }
    assert "ix_skills_name" in {index["name"] for index in indexes}
    await engine.dispose()
