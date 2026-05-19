import pytest

from stockimformation.config.entities import validate_permission_overrides
from stockimformation.config.schema import EntityTypeConfig
from stockimformation.errors import ConfigError


def test_valid_escalation() -> None:
    entity_types = {
        "stock": EntityTypeConfig.model_validate(
            {
                "display_name": "Stock",
                "business_id_field": "code",
                "display_template": "{code}",
                "field_permissions": {"code": "read-only"},
            }
        )
    }
    validate_permission_overrides(entity_types, {"stock": {"code": "read-write"}})


def test_write_only_escalates_to_read_write() -> None:
    entity_types = {
        "stock": EntityTypeConfig.model_validate(
            {
                "display_name": "Stock",
                "business_id_field": "code",
                "display_template": "{code}",
                "field_permissions": {"api_key": "write-only"},
            }
        )
    }
    validate_permission_overrides(entity_types, {"stock": {"api_key": "read-write"}})


def test_invalid_downgrade() -> None:
    entity_types = {
        "stock": EntityTypeConfig.model_validate(
            {"display_name": "Stock", "business_id_field": "code", "display_template": "{code}"}
        )
    }
    with pytest.raises(ConfigError):
        validate_permission_overrides(entity_types, {"stock": {"code": "read-only"}})


def test_rejects_read_write_lateral_swaps() -> None:
    entity_types = {
        "stock": EntityTypeConfig.model_validate(
            {
                "display_name": "Stock",
                "business_id_field": "code",
                "display_template": "{code}",
                "field_permissions": {"code": "read-only", "api_key": "write-only"},
            }
        )
    }
    with pytest.raises(ConfigError):
        validate_permission_overrides(entity_types, {"stock": {"code": "write-only"}})
    with pytest.raises(ConfigError):
        validate_permission_overrides(entity_types, {"stock": {"api_key": "read-only"}})
