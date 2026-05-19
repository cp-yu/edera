from pathlib import Path

from stockimformation.config.entities import EntityStore
from stockimformation.config.loader import (
    load_entities_config,
    load_entity_relations_config,
    load_entity_type_configs,
)


def _store() -> EntityStore:
    schemas = load_entity_type_configs(Path("schemas/entity-types"))
    entities = load_entities_config(Path("config/entities.yaml"), schemas)
    relations = load_entity_relations_config(Path("config/entity-relations.yaml"), entities, schemas)
    return EntityStore(entities, schemas, relations)


def test_resolve_uuid() -> None:
    store = _store()
    entity = store.resolve("stock-00700-hk")
    assert entity.attributes["code"] == "00700.HK"


def test_resolve_business_id() -> None:
    store = _store()
    entity = store.resolve("stock:00700.HK")
    assert entity.id == "stock-00700-hk"
