from pathlib import Path

from stockimformation.config.loader import load_entities_config, load_entity_type_configs


def test_load_entities() -> None:
    schemas = load_entity_type_configs(Path("schemas/entity-types"))
    entities = load_entities_config(Path("config/entities.yaml"), schemas)
    refs = {f"{entity.type}:{entity.attributes[schemas[entity.type].business_id_field]}" for entity in entities.entities}
    assert "stock:00700.HK" in refs
    assert "rss-source:sample-rss" in refs
