from pathlib import Path

from stockimformation.config.loader import load_entity_type_configs


def test_load_stock_schema() -> None:
    schemas = load_entity_type_configs(Path("schemas/entity-types"))
    stock = schemas["stock"]
    assert stock.business_id_field == "code"
    assert stock.display_template
    assert stock.field_permissions["code"] == "read-only"
