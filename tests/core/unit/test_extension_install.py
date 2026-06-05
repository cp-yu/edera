from pathlib import Path

import pytest
from sqlalchemy import text

from edera_core.config.schema import EntityConfig, EntityTypeConfig
from edera_core.extension_manager import ExtensionManager
from edera_core.storage import create_engine, init_db, session_factory, sqlite_url
from edera_core.storage.repository import get_installed_extension, get_ordinary_entity, save_ordinary_entity
from edera_core.storage.repository import save_installed_extension


@pytest.mark.asyncio
async def test_install_complete(tmp_path: Path) -> None:
    extension_root = _write_extension(tmp_path, "demo")
    engine = create_engine(sqlite_url(tmp_path / "edera.db"))
    try:
        await init_db(engine)
        manager = ExtensionManager(
            extensions_dir=tmp_path / "extensions",
            handlers_dir=tmp_path / "handlers",
            engine=engine,
            config_entity_types={"stock": _stock_type()},
        )

        result = await manager.install("demo", installed_by="cli")

        factory = session_factory(engine)
        async with factory() as session:
            installed = await get_installed_extension(session, "demo")
            entity = await get_ordinary_entity(session, "stock", "stock-1", {"stock": _stock_type()})

        assert result["handlers"] == 1
        assert result["entities"] == 1
        assert installed is not None
        assert installed.manifest_data["name"] == "demo"
        assert installed.import_record_data[0]["status"] == "imported"
        assert entity is not None
        assert entity.attributes["name"] == "Tencent"
        assert (tmp_path / "handlers" / "demo" / "handler.py").exists()
        assert (tmp_path / "handlers" / "_lib" / "shared.py").exists()
        assert extension_root.exists()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_dependency_check(tmp_path: Path) -> None:
    _write_extension(tmp_path, "dependent", depends=["missing"])
    engine = create_engine(sqlite_url(tmp_path / "edera.db"))
    try:
        await init_db(engine)
        manager = ExtensionManager(
            extensions_dir=tmp_path / "extensions",
            handlers_dir=tmp_path / "handlers",
            engine=engine,
            config_entity_types={"stock": _stock_type()},
        )

        with pytest.raises(ValueError, match="missing extension dependencies: missing"):
            await manager.install("dependent")
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_disabled_dependency_rejected(tmp_path: Path) -> None:
    _write_extension(tmp_path, "dependent", depends=["base"])
    engine = create_engine(sqlite_url(tmp_path / "edera.db"))
    try:
        await init_db(engine)
        factory = session_factory(engine)
        async with factory() as session:
            await save_installed_extension(
                session,
                name="base",
                version="0.1.0",
                manifest_snapshot={"name": "base", "version": "0.1.0"},
                import_records=[],
                enabled=False,
            )
            await session.commit()
        manager = ExtensionManager(
            extensions_dir=tmp_path / "extensions",
            handlers_dir=tmp_path / "handlers",
            engine=engine,
            config_entity_types={"stock": _stock_type()},
        )

        with pytest.raises(ValueError, match="missing extension dependencies: base"):
            await manager.install("dependent")
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_install_failure_rolls_back_handlers_and_tables(tmp_path: Path) -> None:
    _write_extension(tmp_path, "demo", import_type="missing")
    engine = create_engine(sqlite_url(tmp_path / "edera.db"))
    try:
        await init_db(engine)
        manager = ExtensionManager(
            extensions_dir=tmp_path / "extensions",
            handlers_dir=tmp_path / "handlers",
            engine=engine,
            config_entity_types={"stock": _stock_type()},
        )

        with pytest.raises(ValueError, match="unknown entity type"):
            await manager.install("demo")

        async with engine.begin() as conn:
            tables = [row[0] for row in (await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))).all()]
        assert "ext_demo_raw_items" not in tables
        assert not (tmp_path / "handlers" / "demo").exists()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_import_idempotent(tmp_path: Path) -> None:
    _write_extension(tmp_path, "demo", entity_name="Imported")
    engine = create_engine(sqlite_url(tmp_path / "edera.db"))
    try:
        await init_db(engine)
        factory = session_factory(engine)
        async with factory() as session:
            await save_ordinary_entity(
                session,
                EntityConfig(id="stock-1", type="stock", attributes={"code": "00700", "name": "Existing"}),
                _stock_type(),
            )
            await session.commit()
        manager = ExtensionManager(
            extensions_dir=tmp_path / "extensions",
            handlers_dir=tmp_path / "handlers",
            engine=engine,
            config_entity_types={"stock": _stock_type()},
        )

        result = await manager.install("demo")

        async with factory() as session:
            installed = await get_installed_extension(session, "demo")
            entity = await get_ordinary_entity(session, "stock", "stock-1", {"stock": _stock_type()})

        assert result["entities"] == 0
        assert installed is not None
        assert installed.import_record_data[0]["status"] == "skipped_existing"
        assert entity is not None
        assert entity.attributes["name"] == "Existing"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_install_imports_entity_type_declared_by_same_manifest(tmp_path: Path) -> None:
    _write_extension_with_declared_entity_type(tmp_path, "demo")
    engine = create_engine(sqlite_url(tmp_path / "edera.db"))
    try:
        await init_db(engine)
        manager = ExtensionManager(
            extensions_dir=tmp_path / "extensions",
            handlers_dir=tmp_path / "handlers",
            engine=engine,
        )

        result = await manager.install("demo")

        factory = session_factory(engine)
        async with factory() as session:
            entity = await get_ordinary_entity(session, "feed", "feed-1", {"feed": _feed_type()})

        assert result["entities"] == 1
        assert entity is not None
        assert entity.attributes["url"] == "https://example.test/rss"
    finally:
        await engine.dispose()


def _write_extension(
    tmp_path: Path,
    name: str,
    *,
    depends: list[str] | None = None,
    entity_name: str = "Tencent",
    import_type: str = "stock",
) -> Path:
    root = tmp_path / "extensions" / name
    (root / "entities").mkdir(parents=True)
    (root / "_lib").mkdir()
    (root / "handler.py").write_text("def run(payload):\n    return payload\n", encoding="utf-8")
    (root / "_lib" / "shared.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "entities" / "stock.yaml").write_text(
        f"type: {import_type}\n"
        "id: stock-1\n"
        "attributes:\n"
        "  code: '00700'\n"
        f"  name: {entity_name}\n",
        encoding="utf-8",
    )
    depends_yaml = "".join(f"  - {item}\n" for item in depends or [])
    depends_block = f"depends:\n{depends_yaml}" if depends else ""
    (root / "manifest.yaml").write_text(
        f"name: {name}\n"
        "version: 0.1.0\n"
        f"{depends_block}"
        "handlers:\n"
        f"  - name: {name}-handler\n"
        "    role: processor\n"
        "    input_type: Any\n"
        "    entry: handler.py\n"
        "storage:\n"
        "  tables:\n"
        "    - name: raw_items\n"
        "      columns:\n"
        "        - name: id\n"
        "          type: integer\n"
        "          primary_key: true\n"
        "imports:\n"
        "  entities:\n"
        "    - entities/stock.yaml\n",
        encoding="utf-8",
    )
    return root


def _write_extension_with_declared_entity_type(tmp_path: Path, name: str) -> Path:
    root = tmp_path / "extensions" / name
    (root / "entities").mkdir(parents=True)
    (root / "entities" / "feed.yaml").write_text(
        "type: feed\n"
        "id: feed-1\n"
        "attributes:\n"
        "  name: Example\n"
        "  url: https://example.test/rss\n",
        encoding="utf-8",
    )
    (root / "manifest.yaml").write_text(
        f"name: {name}\n"
        "version: 0.1.0\n"
        "entity_types:\n"
        "  - name: feed\n"
        "    display_name: Feed\n"
        "    business_id_field: url\n"
        "    storage_tier: database\n"
        "    schema:\n"
        "      required: [name, url]\n"
        "      properties:\n"
        "        name: {type: string}\n"
        "        url: {type: string}\n"
        "imports:\n"
        "  entities:\n"
        "    - entities/feed.yaml\n",
        encoding="utf-8",
    )
    return root


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


def _feed_type() -> EntityTypeConfig:
    return EntityTypeConfig.model_validate(
        {
            "display_name": "Feed",
            "business_id_field": "url",
            "display_template": "{url}",
            "storage_tier": "database",
            "schema": {
                "required": ["name", "url"],
                "properties": {"name": {"type": "string"}, "url": {"type": "string"}},
            },
        }
    )
