from pathlib import Path

from stockimformation.config.loader import load_entity_type_configs


def test_load_stock_schema() -> None:
    schemas = load_entity_type_configs(Path("schemas/entity-types"))
    stock = schemas["stock"]
    assert stock.business_id_field == "code"
    assert stock.display_template
    assert stock.field_permissions["code"] == "read-only"
    assert stock.system_protected is False


def test_entity_type_capability_detection() -> None:
    schemas = load_entity_type_configs(Path("schemas/entity-types"))
    node = schemas["node"]
    dag = schemas["dag"]
    trigger = schemas["trigger"]
    run_metadata = schemas["run-metadata"]

    assert node.storage_tier == "filesystem"
    assert node.system_protected is True
    assert node.is_executable
    assert not node.is_dag
    assert dag.storage_tier == "filesystem"
    assert dag.system_protected is True
    assert dag.is_dag
    assert trigger.storage_tier == "filesystem"
    assert trigger.system_protected is True
    assert trigger.is_trigger
    assert run_metadata.storage_tier == "memory"
    assert run_metadata.system_protected is True
