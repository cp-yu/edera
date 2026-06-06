from __future__ import annotations

from pathlib import Path

import pytest

from edera_core.config.loader import _load_runtime_base_config, load_app_config, load_entity_types, materialize_runtime_app_config
from edera_core.storage import create_engine, init_db, session_factory
from edera_core.storage.repository import list_ordinary_entities, list_relations


@pytest.mark.asyncio
async def test_materialize_migrates_entity_yaml_to_database(tmp_path):
    root = tmp_path / "config"
    _write_runtime_config(root)
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'edera.db'}")
    await init_db(engine)

    config = await materialize_runtime_app_config(root, _load_runtime_base_config(root), engine)

    assert [entity.id for entity in config.entities.entities if entity.type == "stock"] == []
    assert [entity.id for entity in config.entities.entities if entity.type == "relation"] == []
    assert config.entity_relations.relations == []
    async with session_factory(engine)() as session:
        ordinary_entities = await list_ordinary_entities(session, config.entity_types)
        relation_records = await list_relations(session)
    assert [entity.id for entity in ordinary_entities if entity.type == "stock"] == ["stock-row-1"]
    assert [relation.relation_type for relation in relation_records] == ["uses-source"]
    assert [(relation.from_entity_id, relation.to_entity_id) for relation in relation_records] == [
        ("stock:TEST", "rss-source:feed")
    ]
    assert not (root / "entities.yaml").exists()
    assert not (root / "entity-relations.yaml").exists()
    assert (root / "entities.yaml.migrated").exists()
    assert (root / "entity-relations.yaml.migrated").exists()


def _write_runtime_config(root):
    (root / "schemas").mkdir(parents=True)
    (root / "skills").mkdir()
    (root / "dags").mkdir()
    (root / "nodes").mkdir()
    (root / "schemas" / "stock.yaml").write_text(
        "display_name: Stock\nbusiness_id_field: code\ndisplay_template: '{code}'\nstorage_tier: database\nschema:\n  properties:\n    code:\n      type: string\n",
        encoding="utf-8",
    )
    (root / "schemas" / "rss-source.yaml").write_text(
        "display_name: RSS\nbusiness_id_field: url\ndisplay_template: '{url}'\nstorage_tier: database\nschema:\n  properties:\n    url:\n      type: string\n",
        encoding="utf-8",
    )
    (root / "entities.yaml").write_text(
        "entities:\n- id: stock-row-1\n  type: stock\n  attributes:\n    code: TEST\n- id: source-row-1\n  type: rss-source\n  attributes:\n    url: feed\n",
        encoding="utf-8",
    )
    (root / "entity-relations.yaml").write_text(
        "relations:\n- entities: [stock:TEST, rss-source:feed]\n  type: uses-source\n",
        encoding="utf-8",
    )
    (root / "system.toml").write_text(
        "database_url = \"sqlite+aiosqlite:///tmp/test.db\"\nschedule_minutes = 1\n",
        encoding="utf-8",
    )


def test_load_app_config_without_entity_yaml(tmp_path):
    root = tmp_path / "config"
    _write_runtime_config(root)
    (root / "entities.yaml").unlink()
    (root / "entity-relations.yaml").unlink()

    config = load_app_config(root)

    assert config.entities.entities == []
    assert config.entity_relations.relations == []


def test_project_ordinary_entity_schemas_are_database_backed():
    entity_types = load_entity_types(Path("config"))

    for name in ("stock", "rss-source", "api-source", "city", "web-source"):
        assert entity_types[name].storage_tier == "database"


@pytest.mark.asyncio
async def test_materialize_keeps_legacy_yaml_on_migration_failure(tmp_path):
    root = tmp_path / "config"
    _write_runtime_config(root)
    (root / "entities.yaml").write_text(
        "entities:\n- id: broken\n  type: missing-type\n  attributes:\n    code: TEST\n",
        encoding="utf-8",
    )
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'edera.db'}")
    await init_db(engine)

    config = await materialize_runtime_app_config(root, _load_runtime_base_config(root), engine)

    assert config.entities.entities == []
    assert (root / "entities.yaml").exists()
    assert (root / "entity-relations.yaml").exists()
    assert not (root / "entities.yaml.migrated").exists()
