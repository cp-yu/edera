from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
import yaml

from edera_core.config.schema import EntityConfig, EntityTypeConfig
from edera_core.storage import create_engine, init_db, session_factory
from edera_core.storage.import_export import (
    export_entities_to_yaml,
    import_entities_from_yaml,
    import_relations_from_yaml,
    export_relations_to_yaml,
)
from edera_core.storage.repository import create_ordinary_entity, get_core_entity, get_ordinary_entity, list_relations, save_core_entity


@pytest.mark.asyncio
async def test_import_entities(tmp_path):
    entity_types = _entity_types()
    path = tmp_path / "entities.yaml"
    path.write_text("entities:\n- id: stock:test\n  type: stock\n  attributes:\n    code: TEST\n", encoding="utf-8")

    async with _session(tmp_path) as session:
        result = await import_entities_from_yaml(session, path, entity_types)
        entity = await get_ordinary_entity(session, "stock", "stock:test", entity_types)

    assert result.imported == 1
    assert entity is not None


@pytest.mark.asyncio
async def test_import_conflict(tmp_path):
    entity_types = _entity_types()
    path = tmp_path / "entities.yaml"
    path.write_text("entities:\n- id: stock:test\n  type: stock\n  attributes:\n    code: TEST\n    name: New\n", encoding="utf-8")

    async with _session(tmp_path) as session:
        await create_ordinary_entity(session, "stock", "stock:test", {"code": "TEST", "name": "Old"}, entity_types)
        result = await import_entities_from_yaml(session, path, entity_types)
        entity = await get_ordinary_entity(session, "stock", "stock:test", entity_types)

    assert result.updated == 1
    assert entity is not None and entity.attributes["name"] == "New"


@pytest.mark.asyncio
async def test_export_entities(tmp_path):
    entity_types = _entity_types()
    path = tmp_path / "entities.yaml"
    async with _session(tmp_path) as session:
        await create_ordinary_entity(session, "stock", "stock:test", {"code": "TEST"}, entity_types)

        result = await export_entities_to_yaml(session, path, entity_types)

    assert result.exported == 1
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["entities"][0]["id"] == "stock:test"


@pytest.mark.asyncio
async def test_import_entities_routes_relation_entities(tmp_path):
    entity_types = {**_entity_types(), "relation": _entity_type("id")}
    path = tmp_path / "entities.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "entities": [
                    {
                        "id": "relation-1",
                        "type": "relation",
                        "attributes": {
                            "from_entity_id": "stock:test",
                            "to_entity_id": "source:test",
                            "relation_type": "uses-source",
                        },
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    async with _seeded_session(tmp_path, entity_types) as session:
        result = await import_entities_from_yaml(session, path, entity_types)
        relations = await list_relations(session)

    assert result.imported == 1
    assert [(item.from_entity_id, item.to_entity_id, item.relation_type) for item in relations] == [
        ("stock:test", "source:test", "uses-source")
    ]


@pytest.mark.asyncio
async def test_import_entities_routes_core_entities(tmp_path):
    entity_types = {**_entity_types(), "node": _entity_type("name")}
    path = tmp_path / "entities.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "entities": [
                    {
                        "id": "reader",
                        "type": "node",
                        "attributes": {
                            "name": "reader",
                            "input_type": "Any",
                            "output_type": "Any",
                        },
                    },
                    {
                        "id": "stock:test",
                        "type": "stock",
                        "attributes": {"code": "TEST"},
                    },
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    async with _session(tmp_path) as session:
        result = await import_entities_from_yaml(session, path, entity_types)
        node = await get_core_entity(session, "node:reader", entity_types)
        stock = await get_ordinary_entity(session, "stock", "stock:test", entity_types)

    assert result.imported == 2
    assert node is not None and node.attributes["name"] == "reader"
    assert stock is not None


@pytest.mark.asyncio
async def test_import_relations(tmp_path):
    entity_types = _entity_types()
    path = tmp_path / "relations.yaml"
    path.write_text("relations:\n- entities: [stock:test, source:test]\n  type: uses-source\n", encoding="utf-8")

    async with _seeded_session(tmp_path, entity_types) as session:
        result = await import_relations_from_yaml(session, path, entity_types)
        relations = await list_relations(session)

    assert result.imported == 1
    assert [(item.from_entity_id, item.to_entity_id) for item in relations] == [("stock:test", "source:test")]


@pytest.mark.asyncio
async def test_import_invalid_relations(tmp_path):
    entity_types = _entity_types()
    path = tmp_path / "relations.yaml"
    path.write_text("relations:\n- entities: [stock:test, missing:test]\n  type: uses-source\n", encoding="utf-8")

    async with _seeded_session(tmp_path, entity_types) as session:
        result = await import_relations_from_yaml(session, path, entity_types)
        relations = await list_relations(session)

    assert result.skipped == 1
    assert result.warnings == ["relation skipped: missing entity missing:test"]
    assert relations == []


@pytest.mark.asyncio
async def test_export_relations(tmp_path):
    entity_types = _entity_types()
    path = tmp_path / "relations.yaml"
    async with _seeded_session(tmp_path, entity_types) as session:
        await import_relations_from_yaml(
            session,
            _write_yaml(tmp_path / "input-relations.yaml", {"relations": [{"entities": ["stock:test", "source:test"], "type": "uses-source"}]}),
            entity_types,
        )

        result = await export_relations_to_yaml(session, path)

    assert result.exported == 1
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["relations"][0]["entities"] == ["stock:test", "source:test"]


@pytest.mark.asyncio
async def test_import_relations_allows_core_entity_refs(tmp_path):
    entity_types = {**_entity_types(), "node": _entity_type("name")}
    path = tmp_path / "relations.yaml"
    path.write_text("relations:\n- entities: [node:reader, stock:test]\n  type: uses-entity\n", encoding="utf-8")

    async with _session(tmp_path) as session:
        await save_core_entity(
            session,
            EntityConfig(
                id="reader",
                type="node",
                attributes={"name": "reader", "input_type": "Any", "output_type": "Any"},
            ),
        )
        await create_ordinary_entity(session, "stock", "stock:test", {"code": "TEST"}, entity_types)

        result = await import_relations_from_yaml(session, path, entity_types)

    assert result.imported == 1


def _entity_types() -> dict[str, EntityTypeConfig]:
    return {
        "stock": _entity_type("code"),
        "rss-source": _entity_type("url"),
    }


def _entity_type(business_id_field: str) -> EntityTypeConfig:
    return EntityTypeConfig.model_validate(
        {
            "display_name": "Entity",
            "business_id_field": business_id_field,
            "display_template": "{" + business_id_field + "}",
            "storage_tier": "database",
            "schema": {"properties": {business_id_field: {"type": "string"}, "name": {"type": "string"}}},
        }
    )


@asynccontextmanager
async def _session(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'edera.db'}")
    try:
        await init_db(engine)
        async with session_factory(engine)() as session:
            yield session
    finally:
        await engine.dispose()


@asynccontextmanager
async def _seeded_session(tmp_path, entity_types):
    async with _session(tmp_path) as session:
        await create_ordinary_entity(session, "stock", "stock:test", {"code": "TEST"}, entity_types)
        await create_ordinary_entity(session, "rss-source", "source:test", {"url": "https://example.test/rss"}, entity_types)
        yield session


def _write_yaml(path, payload):
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path
