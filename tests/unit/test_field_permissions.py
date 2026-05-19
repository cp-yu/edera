from stockimformation.config.entities import PERMISSIONS, field_permission
from stockimformation.config.schema import EntityTypeConfig


def test_default_read_write() -> None:
    entity_type = EntityTypeConfig.model_validate(
        {"display_name": "Stock", "business_id_field": "code", "display_template": "{code}"}
    )
    assert field_permission(entity_type, "holding") == "read-write"


def test_permission_enum() -> None:
    assert set(PERMISSIONS) == {"none", "read-only", "write-only", "read-write"}


def test_permission_inheritance() -> None:
    entity_type = EntityTypeConfig.model_validate(
        {
            "display_name": "Stock",
            "business_id_field": "code",
            "display_template": "{code}",
            "field_permissions": {"holding": "read-only"},
        }
    )
    assert field_permission(entity_type, "holding.quantity") == "read-only"
