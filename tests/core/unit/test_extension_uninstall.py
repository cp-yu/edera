from pathlib import Path

import pytest

from edera_core.config.schema import EntityConfig, EntityTypeConfig
from edera_core.extension_manager import ExtensionManager
from edera_core.storage import create_engine, init_db, session_factory, sqlite_url
from edera_core.storage.repository import (
    get_installed_extension,
    get_ordinary_entity,
    save_ordinary_entity,
)


@pytest.mark.asyncio
async def test_purge(tmp_path: Path) -> None:
    manager, engine = await _installed_manager(tmp_path)
    try:
        result = await manager.uninstall("demo", "purge")
        factory = session_factory(engine)
        async with factory() as session:
            installed = await get_installed_extension(session, "demo")
            entity = await get_ordinary_entity(session, "stock", "stock-1", {"stock": _stock_type()})

        assert result["deleted_entities"] == 1
        assert installed is None
        assert entity is None
        assert not (tmp_path / "handlers" / "demo.demo-handler").exists()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_keep_modified(tmp_path: Path) -> None:
    manager, engine = await _installed_manager(tmp_path)
    factory = session_factory(engine)
    try:
        async with factory() as session:
            await save_ordinary_entity(
                session,
                EntityConfig.model_validate(
                    {"id": "stock-1", "type": "stock", "attributes": {"code": "00700", "name": "Modified"}}
                ),
                _stock_type(),
            )
            await session.commit()

        result = await manager.uninstall("demo", "keep-modified")

        async with factory() as session:
            entity = await get_ordinary_entity(session, "stock", "stock-1", {"stock": _stock_type()})
            installed = await get_installed_extension(session, "demo")

        assert result["deleted_entities"] == 0
        assert entity is not None
        assert entity.attributes["name"] == "Modified"
        assert installed is None
        assert not (tmp_path / "handlers" / "demo.demo-handler").exists()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_dependency_block(tmp_path: Path) -> None:
    _write_extension(tmp_path, "demo")
    _write_extension(tmp_path, "child", depends=["demo"])
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
        await manager.install("child")

        with pytest.raises(ValueError, match="dependent extensions: child"):
            await manager.uninstall("demo", "purge")
    finally:
        await engine.dispose()


async def _installed_manager(tmp_path: Path) -> tuple[ExtensionManager, object]:
    _write_extension(tmp_path, "demo")
    engine = create_engine(sqlite_url(tmp_path / "edera.db"))
    await init_db(engine)
    manager = ExtensionManager(
        extensions_dir=tmp_path / "extensions",
        handlers_dir=tmp_path / "handlers",
        engine=engine,
        config_entity_types={"stock": _stock_type()},
    )
    await manager.install("demo")
    return manager, engine


def _write_extension(
    tmp_path: Path,
    name: str,
    *,
    depends: list[str] | None = None,
    entity_name: str = "Tencent",
) -> Path:
    root = tmp_path / "extensions" / name
    (root / "entities").mkdir(parents=True)
    (root / "_lib").mkdir()
    (root / "handler.py").write_text("def run(payload):\n    return payload\n", encoding="utf-8")
    (root / "_lib" / "shared.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "entities" / "stock.yaml").write_text(
        "type: stock\n"
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
        "imports:\n"
        "  entities:\n"
        "    - entities/stock.yaml\n",
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
