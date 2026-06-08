from pathlib import Path

from edera_core.config.entities import EntityStore
from edera_core.config.loader import load_entity_type_configs
from edera_core.config.schema import EntitiesConfig, EntityConfig, EntityRelationsConfig


def _store() -> EntityStore:
    schemas = load_entity_type_configs(Path("schemas/entity-types"))
    entities = EntitiesConfig(
        entities=[
            EntityConfig(id="stock-00700-hk", type="stock", attributes={"code": "00700.HK"}),
            EntityConfig(id="stock-00100-hk", type="stock", attributes={"code": "00100.HK"}),
        ]
    )
    relations = EntityRelationsConfig(relations=[])
    return EntityStore(entities, schemas, relations)


def test_resolve_uuid() -> None:
    store = _store()
    entity = store.resolve("stock-00700-hk")
    assert entity.attributes["code"] == "00700.HK"


def test_resolve_business_id() -> None:
    store = _store()
    entity = store.resolve("stock:00700.HK")
    assert entity.id == "stock-00700-hk"
