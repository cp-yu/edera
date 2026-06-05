from pathlib import Path

import pytest
from sqlalchemy import text

from edera_core.storage import create_engine, init_db, session_factory, sqlite_url
from edera_core.storage.repository import (
    delete_installed_extension,
    get_installed_extension,
    list_enabled_extensions,
    list_installed_extensions,
    save_installed_extension,
)


@pytest.mark.asyncio
async def test_table_schema(tmp_path: Path) -> None:
    engine = create_engine(sqlite_url(tmp_path / "edera.db"))
    try:
        await init_db(engine)
        async with engine.begin() as conn:
            rows = (await conn.execute(text("PRAGMA table_info(installed_extensions)"))).fetchall()

        columns = {row[1]: row for row in rows}
        assert columns["id"][2] == "INTEGER"
        assert columns["name"][3] == 1
        assert columns["version"][3] == 1
        assert columns["manifest_snapshot"][2] == "TEXT"
        assert columns["manifest_snapshot"][3] == 1
        assert columns["import_records"][2] == "TEXT"
        assert columns["import_records"][3] == 1
        assert columns["import_records"][4] == "'[]'"
        assert columns["enabled"][4] in {"1", "true", "TRUE"}
        assert "installed_by" in columns
        assert columns["created_at"][2] == "TEXT"
        assert columns["created_at"][3] == 1
        assert columns["updated_at"][2] == "TEXT"
        assert columns["updated_at"][3] == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_save_and_get(tmp_path: Path) -> None:
    engine = create_engine(sqlite_url(tmp_path / "edera.db"))
    try:
        await init_db(engine)
        factory = session_factory(engine)
        manifest = {"name": "demo", "version": "0.1.0", "handlers": []}
        records = [
            {
                "import_path": "entities/stock.yaml",
                "entity_type": "stock",
                "entity_id": "stock-1",
                "entity_ref": "stock:00700",
                "content_digest": "abc",
                "imported_entity_digest": "def",
                "status": "imported",
            }
        ]

        async with factory() as session:
            saved = await save_installed_extension(
                session,
                name="demo",
                version="0.1.0",
                manifest_snapshot=manifest,
                import_records=records,
                installed_by="cli",
            )
            await session.commit()

        async with factory() as session:
            loaded = await get_installed_extension(session, "demo")
            all_rows = await list_installed_extensions(session)
            enabled = await list_enabled_extensions(session)
            deleted = await delete_installed_extension(session, "demo")
            missing = await get_installed_extension(session, "demo")

        assert saved.name == "demo"
        assert loaded is not None
        assert loaded.manifest_data == manifest
        assert loaded.import_record_data == records
        assert [row.name for row in all_rows] == ["demo"]
        assert [row.name for row in enabled] == ["demo"]
        assert deleted is True
        assert missing is None
    finally:
        await engine.dispose()
