from pathlib import Path

import pytest

from edera_core.config.schema import EntityConfig, EntityTypeConfig
from edera_core.extension_imports import import_manifest_entities
from edera_core.manifest import ExtensionManifest
from edera_core.storage import create_engine, init_db, session_factory, sqlite_url
from edera_core.storage.repository import (
    get_ordinary_entity,
    save_ordinary_entity,
    seed_entity_type_records,
)


@pytest.mark.asyncio
async def test_extension_entity_import_records_imported(tmp_path: Path) -> None:
    engine = create_engine(sqlite_url(tmp_path / "edera.db"))
    try:
        await init_db(engine)
        factory = session_factory(engine)
        root = _extension_root(tmp_path, "stock-1", "Tencent")

        async with factory() as session:
            entity_types = await seed_entity_type_records(session, {"stock": _stock_type()})
            records = await import_manifest_entities(session, root, _manifest(), entity_types)
            await session.commit()

        async with factory() as session:
            entity_types = {"stock": _stock_type()}
            entity = await get_ordinary_entity(session, "stock", "stock-1", entity_types)

        assert entity is not None
        assert entity.attributes["name"] == "Tencent"
        record = records[0]
        assert record is not None
        assert record["entity_ref"] == "stock:00700"
        assert record["status"] == "imported"
        assert record["content_digest"]
        assert record["imported_entity_digest"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_extension_entity_import_records_existing_without_overwrite(tmp_path: Path) -> None:
    engine = create_engine(sqlite_url(tmp_path / "edera.db"))
    try:
        await init_db(engine)
        factory = session_factory(engine)
        root = _extension_root(tmp_path, "stock-1", "Imported")

        async with factory() as session:
            stock = _stock_type()
            entity_types = await seed_entity_type_records(session, {"stock": stock})
            await save_ordinary_entity(
                session,
                EntityConfig(id="stock-1", type="stock", attributes={"code": "00700", "name": "Existing"}),
                stock,
            )
            records = await import_manifest_entities(session, root, _manifest(), entity_types)
            await session.commit()

        async with factory() as session:
            entity = await get_ordinary_entity(session, "stock", "stock-1", {"stock": _stock_type()})

        assert entity is not None
        assert entity.attributes["name"] == "Existing"
        assert records[0]["status"] == "skipped_existing"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_extension_entity_import_skips_recorded_path(tmp_path: Path) -> None:
    engine = create_engine(sqlite_url(tmp_path / "edera.db"))
    try:
        await init_db(engine)
        factory = session_factory(engine)
        root = _extension_root(tmp_path, "stock-1", "Tencent")

        async with factory() as session:
            entity_types = await seed_entity_type_records(session, {"stock": _stock_type()})
            records = await import_manifest_entities(session, root, _manifest(), entity_types)
            await session.commit()

        (root / "entities" / "stock.yaml").write_text("not: an entity\n", encoding="utf-8")

        async with factory() as session:
            await import_manifest_entities(session, root, _manifest(), {"stock": _stock_type()}, existing_records=records)
            entity = await get_ordinary_entity(session, "stock", "stock-1", {"stock": _stock_type()})

        assert entity is not None
        assert entity.attributes["name"] == "Tencent"
    finally:
        await engine.dispose()


def _extension_root(tmp_path: Path, entity_id: str, name: str) -> Path:
    root = tmp_path / "extensions" / "demo"
    (root / "entities").mkdir(parents=True)
    (root / "entities" / "stock.yaml").write_text(
        "type: stock\n"
        f"id: {entity_id}\n"
        "attributes:\n"
        "  code: '00700'\n"
        f"  name: {name}\n",
        encoding="utf-8",
    )
    return root


def _manifest() -> ExtensionManifest:
    return ExtensionManifest(name="demo", version="0.1.0", entity_imports=["entities/stock.yaml"])


def _stock_type() -> EntityTypeConfig:
    return EntityTypeConfig.model_validate(
        {
            "display_name": "Stock",
            "business_id_field": "code",
            "display_template": "{code}",
            "storage_tier": "database",
            "schema": {
                "required": ["code", "name"],
                "properties": {"code": {"type": "string"}, "name": {"type": "string"}},
            },
        }
    )
