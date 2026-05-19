from pathlib import Path

from stockimformation.config.loader import (
    load_entities_config,
    load_entity_relations_config,
    load_entity_type_configs,
)


def test_load_relations() -> None:
    schemas = load_entity_type_configs(Path("schemas/entity-types"))
    entities = load_entities_config(Path("config/entities.yaml"), schemas)
    relations = load_entity_relations_config(Path("config/entity-relations.yaml"), entities, schemas)
    assert any("stock:00700.HK" in relation.entities for relation in relations.relations)
    assert all(relation.type for relation in relations.relations)
