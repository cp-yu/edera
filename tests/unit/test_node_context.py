import pytest
import yaml

from stockimformation.config.entities import EntityStore
from stockimformation.config.schema import EntitiesConfig, EntityRelationsConfig, EntityTypeConfig
from stockimformation.errors import ConfigError
from stockimformation.node.models import NodeContext


def _context() -> NodeContext:
    entity_types = {
        "stock": EntityTypeConfig.model_validate(
            {"display_name": "Stock", "business_id_field": "code", "display_template": "{code}"}
        )
    }
    entities = EntitiesConfig.model_validate(
        {"entities": [{"id": "stock-1", "type": "stock", "attributes": {"code": "00700.HK"}}]}
    )
    return NodeContext("cycle", "node", entity_store=EntityStore(entities, entity_types, EntityRelationsConfig()))


def test_get_entity() -> None:
    assert _context().get_entity("stock:00700.HK") is not None


def test_save_entity() -> None:
    context = _context()
    entity = context.get_entity("stock-1")
    assert entity is not None
    entity.attributes["name"] = "Tencent"
    saved = context.save_entity(entity)
    assert saved is not None
    assert saved.attributes["name"] == "Tencent"


def test_create_entity() -> None:
    entity = _context().create_entity("stock", {"code": "600519.SH"})
    assert entity is not None
    assert entity.type == "stock"


def test_create_entity_validates_attributes() -> None:
    entity_types = {
        "stock": EntityTypeConfig.model_validate(
            {
                "display_name": "Stock",
                "business_id_field": "code",
                "display_template": "{code}",
                "schema": {"required": ["code", "name"]},
            }
        )
    }
    context = NodeContext("cycle", "node", entity_store=EntityStore(EntitiesConfig(), entity_types, EntityRelationsConfig()))
    with pytest.raises(ConfigError):
        context.create_entity("stock", {"code": "600519.SH"})


def test_save_entity_persists_config(tmp_path) -> None:
    config_dir = tmp_path / "config"
    schema_dir = tmp_path / "schemas" / "entity-types"
    config_dir.mkdir()
    schema_dir.mkdir(parents=True)
    schema_dir.joinpath("stock.yaml").write_text(
        "display_name: Stock\n"
        "business_id_field: code\n"
        "display_template: '{code}'\n"
        "schema:\n"
        "  required: [code]\n"
        "field_permissions:\n"
        "  code: read-only\n",
        encoding="utf-8",
    )
    path = config_dir / "entities.yaml"
    path.write_text("entities:\n- id: stock-1\n  type: stock\n  attributes:\n    code: 00700.HK\n", encoding="utf-8")
    entity_types = {
        "stock": EntityTypeConfig.model_validate(
            {
                "display_name": "Stock",
                "business_id_field": "code",
                "display_template": "{code}",
                "schema": {"required": ["code"]},
                "field_permissions": {"code": "read-only"},
            }
        )
    }
    entities = EntitiesConfig.model_validate(
        {"entities": [{"id": "stock-1", "type": "stock", "attributes": {"code": "00700.HK"}}]}
    )
    context = NodeContext(
        "cycle",
        "node",
        entity_store=EntityStore(entities, entity_types, EntityRelationsConfig(), path),
    )
    entity = context.get_entity("stock-1")
    assert entity is not None
    entity.attributes["name"] = "Tencent"
    context.save_entity(entity)
    saved = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert saved["entities"][0]["attributes"]["name"] == "Tencent"
