import logging

from stockimformation.config.entities import EntityStore
from stockimformation.config.schema import EntitiesConfig, EntityRelationsConfig, EntityTypeConfig
from stockimformation.node.models import NodeContext


def _context() -> NodeContext:
    entity_types = {
        "stock": EntityTypeConfig.model_validate(
            {
                "display_name": "Stock",
                "business_id_field": "code",
                "display_template": "{code}",
                "field_permissions": {"code": "read-only", "secret": "none"},
            }
        )
    }
    entities = EntitiesConfig.model_validate(
        {"entities": [{"id": "stock-1", "type": "stock", "attributes": {"code": "00700.HK", "secret": "x"}}]}
    )
    store = EntityStore(entities, entity_types, EntityRelationsConfig())
    return NodeContext("cycle", "node", entity_store=store)


def test_read_protected_field(caplog) -> None:
    with caplog.at_level(logging.WARNING):
        assert _context().read_entity_field("stock-1", "secret") is None
    assert "Permission denied: stock.secret is not readable" in caplog.text


def test_get_entity_filters_unreadable_fields() -> None:
    entity = _context().get_entity("stock-1")
    assert entity is not None
    assert entity.attributes == {"code": "00700.HK"}


def test_write_protected_field(caplog) -> None:
    with caplog.at_level(logging.WARNING):
        assert _context().write_entity_field("stock-1", "code", "600519.SH") is False
    assert "Permission denied: stock.code is not writable" in caplog.text


def test_save_filters_protected_field(caplog) -> None:
    context = _context()
    entity = context.get_entity("stock-1")
    assert entity is not None
    entity.attributes["code"] = "600519.SH"
    entity.attributes["name"] = "Tencent"
    with caplog.at_level(logging.WARNING):
        saved = context.save_entity(entity)
    assert saved is not None
    assert saved.attributes["code"] == "00700.HK"
    assert saved.attributes["name"] == "Tencent"
    assert "Permission denied: stock.code is not writable" in caplog.text
    assert "Permission denied: stock.secret is not writable" not in caplog.text
