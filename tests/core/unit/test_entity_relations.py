from pathlib import Path

from edera_core.config.loader import (
    load_entities_config,
    load_entity_relations_config,
    load_entity_type_configs,
)


def test_load_relations(tmp_path: Path) -> None:
    schemas = load_entity_type_configs(Path("schemas/entity-types"))
    entities = load_entities_config(Path("config/entities.yaml"), schemas)
    path = tmp_path / "entity-relations.yaml"
    path.write_text(
        "relations:\n"
        "- id: stock-peer\n"
        "  entities:\n"
        "  - stock:00100.HK\n"
        "  - stock:00700.HK\n"
        "  type: peer\n",
        encoding="utf-8",
    )
    relations = load_entity_relations_config(path, entities, schemas)
    assert any("stock:00100.HK" in relation.entities for relation in relations.relations)
    assert all(relation.type for relation in relations.relations)
