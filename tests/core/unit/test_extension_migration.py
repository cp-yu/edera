from pathlib import Path

import pytest

from edera_core.config.schema import EntityTypeConfig
from edera_core.migration.migrate_extensions import migrate_existing_extensions
from edera_core.dag_controller import DagController
from edera_core.storage import create_engine, init_db, session_factory, sqlite_url
from edera_core.storage.repository import get_ordinary_entity, list_installed_extensions


@pytest.mark.asyncio
async def test_migrate_extensions(tmp_path: Path) -> None:
    extensions = tmp_path / "extensions"
    _write_manifest(extensions / "demo", "demo")
    engine = create_engine(sqlite_url(tmp_path / "edera.db"))
    try:
        await init_db(engine)
        factory = session_factory(engine)
        async with factory() as session:
            migrated = await migrate_existing_extensions(session, [extensions])
            rows = await list_installed_extensions(session)
            await session.commit()

        assert migrated == 1
        assert [row.name for row in rows] == ["demo"]
        assert rows[0].installed_by == "migration"

        _write_manifest(extensions / "other", "other")
        async with factory() as session:
            skipped = await migrate_existing_extensions(session, [extensions])
            rows = await list_installed_extensions(session)

        assert skipped == 0
        assert [row.name for row in rows] == ["demo"]
    finally:
        await engine.dispose()


def _write_manifest(root: Path, name: str) -> None:
    root.mkdir(parents=True)
    (root / "manifest.yaml").write_text(f"name: {name}\nversion: 0.1.0\n", encoding="utf-8")


@pytest.mark.asyncio
async def test_migrate_extensions_imports_manifest_entities(tmp_path: Path) -> None:
    extensions = tmp_path / "extensions"
    root = extensions / "demo"
    root.mkdir(parents=True)
    (root / "entities").mkdir()
    (root / "manifest.yaml").write_text(
        "name: demo\n"
        "version: 0.1.0\n"
        "entity_types:\n"
        "- name: demo-source\n"
        "  display_name: Demo Source\n"
        "  business_id_field: name\n"
        "  storage_tier: database\n"
        "  schema:\n"
        "    required: [name]\n"
        "    properties:\n"
        "      name: {type: string}\n"
        "imports:\n"
        "  entities:\n"
        "  - entities/source.yaml\n",
        encoding="utf-8",
    )
    (root / "entities" / "source.yaml").write_text(
        "id: source-1\n"
        "type: demo-source\n"
        "attributes:\n"
        "  name: primary\n",
        encoding="utf-8",
    )
    engine = create_engine(sqlite_url(tmp_path / "edera.db"))
    try:
        await init_db(engine)
        factory = session_factory(engine)
        async with factory() as session:
            await migrate_existing_extensions(session, [extensions])
            rows = await list_installed_extensions(session)
            entity = await get_ordinary_entity(
                session,
                "demo-source",
                "primary",
                {
                    "demo-source": EntityTypeConfig(
                        display_name="Demo Source",
                        business_id_field="name",
                        display_template="{name}",
                    )
                },
            )

        assert rows[0].import_record_data[0]["entity_ref"] == "demo-source:primary"
        assert entity is not None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_startup_migrates_existing_extensions(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    _write_config(config_dir)
    extensions = tmp_path / "extensions"
    _write_manifest(extensions / "demo", "demo")
    (extensions / "demo" / "handler.py").write_text("def run(payload):\n    return payload\n", encoding="utf-8")
    controller = DagController(config_dir, extensions_dirs=[extensions])
    await controller.start(run_startup=False)
    try:
        async with controller._factory()() as session:
            rows = await list_installed_extensions(session)
        assert [row.name for row in rows] == ["demo"]
        assert (tmp_path / "handlers" / "demo" / "handler.py").exists()
    finally:
        await controller.shutdown()


def _write_config(root: Path) -> None:
    (root / "dags").mkdir(parents=True)
    (root / "nodes").mkdir()
    (root / "skills").mkdir()
    (root.parent / "schemas" / "entity-types").mkdir(parents=True)
    (root.parent / "schemas" / "entity-types" / "stock.yaml").write_text(
        "display_name: Stock\nbusiness_id_field: code\ndisplay_template: '{code}'\nschema: {}\n",
        encoding="utf-8",
    )
    (root / "entities.yaml").write_text("entities: []\n", encoding="utf-8")
    (root / "entity-relations.yaml").write_text("relations: []\n", encoding="utf-8")
    (root / "system.toml").write_text(f'database_url = "sqlite+aiosqlite:///{root / "test.db"}"\n', encoding="utf-8")
    (root / "dags" / "default.yaml").write_text("name: default\nnodes: []\nedges: []\n", encoding="utf-8")
