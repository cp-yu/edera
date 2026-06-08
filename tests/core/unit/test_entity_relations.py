from pathlib import Path

from edera_core.config.entities import EntityStore
from edera_core.config.loader import load_entity_type_configs
from edera_core.config.schema import EntitiesConfig, EntityConfig, EntityRelationsConfig


def test_entity_relations_resolve_business_refs() -> None:
    schemas = load_entity_type_configs(Path("schemas/entity-types"))
    entities = EntitiesConfig(
        entities=[
            EntityConfig(id="stock-00100-hk", type="stock", attributes={"code": "00100.HK"}),
            EntityConfig(id="stock-00700-hk", type="stock", attributes={"code": "00700.HK"}),
        ]
    )
    relations = EntityRelationsConfig(
        relations=[
            {
                "id": "stock-peer",
                "entities": ["stock:00100.HK", "stock:00700.HK"],
                "type": "peer",
            }
        ]
    )
    store = EntityStore(entities, schemas, relations)

    assert store.related_refs("stock:00100.HK") == ["stock:00700.HK"]
