from __future__ import annotations

from edera_core.config.entities import EntityStore
from edera_core.config.schema import (
    EntitiesConfig,
    EntityConfig,
    EntityRelationsConfig,
    EntityTypeConfig,
)
from edera_core.server import _query_relations, _relation_filters


def _store(*, relations: list[EntityConfig] | None = None) -> EntityStore:
    entity_types = {
        "stock": EntityTypeConfig(
            display_name="Stock",
            business_id_field="code",
            display_template="{code}",
            schema_={"type": "object", "properties": {"code": {"type": "string"}}},
        ),
        "relation": EntityTypeConfig(
            display_name="Relation",
            business_id_field="id",
            display_template="{id}",
            schema_={"type": "object"},
        ),
    }
    return EntityStore(
        EntitiesConfig(entities=relations or []),
        entity_types,
        EntityRelationsConfig(),
        None,
    )


def _relation(
    id: str = "r1",
    entities: list[str] | None = None,
    type: str = "reflects",
) -> EntityConfig:
    refs = entities or ["stock:A", "stock:B"]
    return EntityConfig(
        id=id,
        type="relation",
        attributes={
            "entities": refs,
            "relation_type": type,
            "from": refs[0],
            "to": refs[1],
            "metadata": {},
        },
    )


# --- _relation_filters ---


def test_type_relation_returns_non_none():
    assert _relation_filters(["type=relation"]) is not None


def test_type_relation_returns_empty_dict():
    result = _relation_filters(["type=relation"])
    assert result == {}


def test_non_relation_type_returns_none():
    assert _relation_filters(["type=stock"]) is None


def test_extracts_relation_type():
    result = _relation_filters(["type=relation", "relation_type=uses-source"])
    assert result == {"relation_type": "uses-source"}


def test_extracts_from_to():
    result = _relation_filters(["type=relation", "from=stock:A", "to=stock:B"])
    assert result == {"from": "stock:A", "to": "stock:B"}


def test_combined_filters():
    result = _relation_filters(["type=relation", "relation_type=X", "from=stock:A"])
    assert result == {"relation_type": "X", "from": "stock:A"}


# --- _query_relations ---


async def test_returns_all_with_empty_filters():
    rels = [_relation(id="r1"), _relation(id="r2")]
    store = _store(relations=rels)
    result = await _query_relations(store, {})
    assert len(result) == 2


async def test_filters_by_type():
    rels = [_relation(id="r1", type="uses-source"), _relation(id="r2", type="reflects")]
    store = _store(relations=rels)
    result = await _query_relations(store, {"relation_type": "uses-source"})
    assert len(result) == 1
    assert result[0].attributes["relation_type"] == "uses-source"


async def test_result_has_relation_structure():
    store = _store(relations=[_relation(id="r1", entities=["stock:A", "stock:B"], type="reflects")])
    result = await _query_relations(store, {})
    assert result[0].type == "relation"
    attrs = result[0].attributes
    assert attrs["relation_type"] == "reflects"
    assert attrs["entities"] == ["stock:A", "stock:B"]
    assert "from" in attrs and "to" in attrs
