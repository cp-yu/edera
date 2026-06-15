from pathlib import Path

import pytest
from sqlalchemy import text

from edera_core.config.schema import EntityConfig, EntityTypeConfig
from edera_core.config.schema import RuntimeSettings, SystemConfig
from edera_core.bootstrap import load_installed_extensions
from edera_core.extension_manager import ExtensionManager
from edera_core.node.executor import NodeExecutor
from edera_core.resolver import HandlerMeta, StaticHandlerResolver
from edera_core.snapshot import DagExecutionClosure, DagExecutionSnapshot
from edera_core.storage import create_engine, init_db, session_factory, sqlite_url
from edera_core.storage.import_export import export_entities_to_yaml
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
        assert (tmp_path / "handlers" / "demo.demo-handler" / "handler.py").exists()
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
        assert not (tmp_path / "handlers" / "demo.demo-handler").exists()
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


@pytest.mark.asyncio
async def test_install_standalone_handler_uses_namespace(tmp_path: Path) -> None:
    _write_extension(tmp_path, "demo")
    engine = create_engine(sqlite_url(tmp_path / "edera.db"))
    try:
        await init_db(engine)
        manager = ExtensionManager(
            extensions_dir=tmp_path / "extensions",
            handlers_dir=tmp_path / "handlers",
            engine=engine,
            config_entity_types={"stock": _stock_type()},
        )

        await manager.install("demo")

        factory = session_factory(engine)
        async with factory() as session:
            installed = await get_installed_extension(session, "demo")

        assert installed is not None
        assert installed.manifest_data["handlers"][0]["name"] == "demo.demo-handler"
        assert installed.manifest_data["handlers"][0]["package"] == "demo.demo-handler"
        assert (tmp_path / "handlers" / "demo.demo-handler" / "handler.py").exists()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_install_workflow_extension_recursively_installs_providers(tmp_path: Path) -> None:
    _write_workflow_extension(tmp_path)
    engine = create_engine(sqlite_url(tmp_path / "edera.db"))
    try:
        await init_db(engine)
        manager = ExtensionManager(
            extensions_dir=tmp_path / "extensions",
            handlers_dir=tmp_path / "handlers",
            engine=engine,
            config_entity_types={"stock": _stock_type()},
        )

        result = await manager.install("workflow")

        factory = session_factory(engine)
        async with factory() as session:
            installed = await get_installed_extension(session, "workflow")

        assert result == {"handlers": 2, "entities": 1, "providers": 2, "libraries": 1}
        assert installed is not None
        assert installed.manifest_data["type"] == "workflow_extension"
        assert [handler["name"] for handler in installed.manifest_data["handlers"]] == [
            "workflow.reader.read",
            "workflow.reader-alt.read",
        ]
        assert (tmp_path / "handlers" / "workflow.reader" / "handler.py").exists()
        assert (tmp_path / "handlers" / "workflow.reader-alt" / "handler.py").exists()
        assert (tmp_path / "libs" / "workflow.http_fetch" / "client.py").exists()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_install_workflow_extension_expands_library_glob(tmp_path: Path) -> None:
    root = _write_workflow_extension(tmp_path)
    manifest = root / "manifest.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace("    - _lib/http_fetch\n", "    - _lib/*\n"),
        encoding="utf-8",
    )
    engine = create_engine(sqlite_url(tmp_path / "edera.db"))
    try:
        await init_db(engine)
        manager = ExtensionManager(
            extensions_dir=tmp_path / "extensions",
            handlers_dir=tmp_path / "handlers",
            engine=engine,
            config_entity_types={"stock": _stock_type()},
        )

        await manager.install("workflow")

        factory = session_factory(engine)
        async with factory() as session:
            installed = await get_installed_extension(session, "workflow")

        assert installed is not None
        assert installed.manifest_data["imports"]["libraries"] == ["_lib/http_fetch"]
        assert (tmp_path / "libs" / "workflow.http_fetch" / "client.py").exists()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_installed_workflow_handler_imports_packaged_lib(tmp_path: Path) -> None:
    root = _write_workflow_extension(tmp_path)
    lib = root / "_lib" / "http_fetch"
    (lib / "_lib").mkdir()
    (lib / "_lib" / "__init__.py").write_text("", encoding="utf-8")
    (lib / "_lib" / "shared.py").write_text("VALUE = 42\n", encoding="utf-8")
    provider = root / "_providers" / "reader"
    (provider / "handler.py").write_text(
        "from _lib.shared import VALUE\n"
        "async def run(ctx):\n"
        "    return VALUE\n",
        encoding="utf-8",
    )
    engine = create_engine(sqlite_url(tmp_path / "edera.db"))
    try:
        await init_db(engine)
        manager = ExtensionManager(
            extensions_dir=tmp_path / "extensions",
            handlers_dir=tmp_path / "handlers",
            engine=engine,
            config_entity_types={"stock": _stock_type()},
        )
        await manager.install("workflow")
        factory = session_factory(engine)
        async with factory() as session:
            await load_installed_extensions(session, tmp_path / "handlers")

        meta_path = tmp_path / "handlers" / "workflow.reader" / "handler.py"
        snapshot = DagExecutionSnapshot(
            DagExecutionClosure("test", {}, {}),
            {},
            StaticHandlerResolver({"workflow.reader.read": HandlerMeta(meta_path)}),
            {},
            {},
        )
        executor = NodeExecutor({}, SystemConfig(), RuntimeSettings(), snapshot)
        result = await executor._load_handler("workflow.reader.read")

        assert result is not None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_install_fails_when_manifest_glob_has_no_matches(tmp_path: Path) -> None:
    root = tmp_path / "extensions" / "demo"
    root.mkdir(parents=True)
    (root / "manifest.yaml").write_text(
        "name: demo\n"
        "version: 0.1.0\n"
        "imports:\n"
        "  entities:\n"
        "    - entities/**/*.yaml\n",
        encoding="utf-8",
    )
    engine = create_engine(sqlite_url(tmp_path / "edera.db"))
    try:
        await init_db(engine)
        manager = ExtensionManager(
            extensions_dir=tmp_path / "extensions",
            handlers_dir=tmp_path / "handlers",
            engine=engine,
            config_entity_types={"stock": _stock_type()},
        )

        with pytest.raises(ValueError, match=r"glob pattern matched no files: entities/\*\*/\*\.yaml"):
            await manager.install("demo")
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_install_rejects_duplicate_handler_namespace(tmp_path: Path) -> None:
    root = _write_workflow_extension(tmp_path)
    duplicate = root / "_providers" / "dupe"
    duplicate.mkdir(parents=True)
    (duplicate / "handler.py").write_text("def run(payload):\n    return payload\n", encoding="utf-8")
    (duplicate / "manifest.yaml").write_text(
        "name: reader\n"
        "version: 0.1.0\n"
        "handlers:\n"
        "  - name: read\n"
        "    role: processor\n"
        "    input_type: Any\n"
        "    entry: handler.py\n",
        encoding="utf-8",
    )
    engine = create_engine(sqlite_url(tmp_path / "edera.db"))
    try:
        await init_db(engine)
        manager = ExtensionManager(
            extensions_dir=tmp_path / "extensions",
            handlers_dir=tmp_path / "handlers",
            engine=engine,
            config_entity_types={"stock": _stock_type()},
        )

        with pytest.raises(ValueError, match="handler namespace conflict: workflow.reader"):
            await manager.install("workflow")
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_overwrite_rejected_by_default(tmp_path: Path) -> None:
    _write_extension(tmp_path, "demo")
    engine = create_engine(sqlite_url(tmp_path / "edera.db"))
    try:
        await init_db(engine)
        manager = ExtensionManager(
            extensions_dir=tmp_path / "extensions",
            handlers_dir=tmp_path / "handlers",
            engine=engine,
            config_entity_types={"stock": _stock_type()},
        )
        await manager.install("demo", installed_by="cli")

        with pytest.raises(ValueError, match="already installed"):
            await manager.install("demo")

        factory = session_factory(engine)
        async with factory() as session:
            installed = await get_installed_extension(session, "demo")

        assert installed is not None
        assert installed.installed_by == "cli"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_overwrite_rebuilds_tables_and_records(tmp_path: Path) -> None:
    _write_extension(tmp_path, "demo", entity_name="Original")
    engine = create_engine(sqlite_url(tmp_path / "edera.db"))
    try:
        await init_db(engine)
        manager = ExtensionManager(
            extensions_dir=tmp_path / "extensions",
            handlers_dir=tmp_path / "handlers",
            engine=engine,
            config_entity_types={"stock": _stock_type()},
        )
        await manager.install("demo")

        async with engine.begin() as conn:
            await conn.execute(text("INSERT INTO ext_demo_raw_items (id) VALUES (1)"))

        _write_extension(tmp_path, "demo", entity_name="Updated")

        await manager.install("demo", overwrite=True)

        factory = session_factory(engine)
        async with factory() as session:
            installed = await get_installed_extension(session, "demo")
            entity = await get_ordinary_entity(session, "stock", "stock-1", {"stock": _stock_type()})
        async with engine.begin() as conn:
            rows = (await conn.execute(text("SELECT COUNT(*) FROM ext_demo_raw_items"))).scalar()

        assert installed is not None
        assert installed.import_record_data[0]["status"] == "imported"
        assert entity is not None
        assert entity.attributes["name"] == "Updated"
        assert rows == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_overwrite_data_warning(tmp_path: Path) -> None:
    _write_extension(tmp_path, "demo")
    engine = create_engine(sqlite_url(tmp_path / "edera.db"))
    try:
        await init_db(engine)
        manager = ExtensionManager(
            extensions_dir=tmp_path / "extensions",
            handlers_dir=tmp_path / "handlers",
            engine=engine,
            config_entity_types={"stock": _stock_type()},
        )
        await manager.install("demo")

        result = await manager.install("demo", overwrite=True)

        assert result["overwrite"] is True
        assert isinstance(result["data_warning"], str) and result["data_warning"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_overwrite_missing_dependency(tmp_path: Path) -> None:
    _write_extension(tmp_path, "demo", depends=["missing"])
    engine = create_engine(sqlite_url(tmp_path / "edera.db"))
    try:
        await init_db(engine)
        factory = session_factory(engine)
        async with factory() as session:
            await save_installed_extension(
                session,
                name="demo",
                version="0.1.0",
                manifest_snapshot={"name": "demo", "version": "0.1.0"},
                import_records=[],
            )
            await session.commit()
        manager = ExtensionManager(
            extensions_dir=tmp_path / "extensions",
            handlers_dir=tmp_path / "handlers",
            engine=engine,
            config_entity_types={"stock": _stock_type()},
        )

        with pytest.raises(ValueError, match="missing extension dependencies: missing"):
            await manager.install("demo", overwrite=True)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_overwrite_restore_roundtrip(tmp_path: Path) -> None:
    from edera_core.storage.import_export import import_entities_from_yaml

    _write_extension(tmp_path, "demo", entity_name="Original")
    engine = create_engine(sqlite_url(tmp_path / "edera.db"))
    backup = tmp_path / "backup.yaml"
    try:
        await init_db(engine)
        manager = ExtensionManager(
            extensions_dir=tmp_path / "extensions",
            handlers_dir=tmp_path / "handlers",
            engine=engine,
            config_entity_types={"stock": _stock_type()},
        )
        await manager.install("demo")
        factory = session_factory(engine)

        async with factory() as session:
            await export_entities_to_yaml(session, backup, {"stock": _stock_type()}, "stock")
            await session.commit()

        _write_extension(tmp_path, "demo", entity_name="ManifestReset")
        await manager.install("demo", overwrite=True)
        async with factory() as session:
            entity = await get_ordinary_entity(session, "stock", "stock-1", {"stock": _stock_type()})
        assert entity is not None
        assert entity.attributes["name"] == "ManifestReset"

        async with factory() as session:
            result = await import_entities_from_yaml(session, backup, {"stock": _stock_type()})
            await session.commit()
        async with factory() as session:
            restored = await get_ordinary_entity(session, "stock", "stock-1", {"stock": _stock_type()})

        assert result.updated == 1
        assert restored is not None
        assert restored.attributes["name"] == "Original"
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
    root.mkdir(parents=True, exist_ok=True)
    (root / "entities").mkdir(parents=True, exist_ok=True)
    (root / "_lib").mkdir(exist_ok=True)
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


def _write_workflow_extension(tmp_path: Path) -> Path:
    root = tmp_path / "extensions" / "workflow"
    (root / "entities" / "nested").mkdir(parents=True)
    (root / "_lib" / "http_fetch").mkdir(parents=True)
    (root / "_providers" / "reader").mkdir(parents=True)
    (root / "_providers" / "reader-alt").mkdir(parents=True)
    (root / "_lib" / "http_fetch" / "client.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "entities" / "nested" / "stock.yaml").write_text(
        "type: stock\n"
        "id: stock-1\n"
        "attributes:\n"
        "  code: '00700'\n"
        "  name: Tencent\n",
        encoding="utf-8",
    )
    for provider in ("reader", "reader-alt"):
        provider_root = root / "_providers" / provider
        (provider_root / "handler.py").write_text("def run(payload):\n    return payload\n", encoding="utf-8")
        (provider_root / "manifest.yaml").write_text(
            f"name: {provider}\n"
            "version: 0.1.0\n"
            "depends:\n"
            "  - _lib/http_fetch\n"
            "handlers:\n"
            "  - name: read\n"
            "    role: processor\n"
            "    input_type: Any\n"
            "    entry: handler.py\n",
            encoding="utf-8",
        )
    (root / "manifest.yaml").write_text(
        "name: workflow\n"
        "version: 0.1.0\n"
        "type: workflow_extension\n"
        "imports:\n"
        "  entities:\n"
        "    - entities/**/*.yaml\n"
        "  providers:\n"
        "    - _providers/*/manifest.yaml\n"
        "  libraries:\n"
        "    - _lib/http_fetch\n",
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
