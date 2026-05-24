from stockimformation_core.config.entities import EntityStore
from stockimformation_core.config.schema import EntitiesConfig, EntityRelationsConfig, EntityTypeConfig


def _store() -> EntityStore:
    entity_types = {
        "stock": EntityTypeConfig.model_validate(
            {"display_name": "Stock", "business_id_field": "code", "display_template": "{code}"}
        ),
        "rss-source": EntityTypeConfig.model_validate(
            {"display_name": "RSS", "business_id_field": "name", "display_template": "{name}"}
        ),
    }
    entities = EntitiesConfig.model_validate(
        {
            "entities": [
                {"id": "stock-1", "type": "stock", "attributes": {"code": "00700.HK"}},
                {"id": "source-1", "type": "rss-source", "attributes": {"name": "sample-rss"}},
            ]
        }
    )
    relations = EntityRelationsConfig.model_validate(
        {"relations": [{"entities": ["stock:00700.HK", "rss-source:sample-rss"], "type": "uses-source"}]}
    )
    return EntityStore(entities, entity_types, relations)


def test_discover_from_source() -> None:
    assert _store().related_refs("rss-source:sample-rss") == ["stock:00700.HK"]


def test_explicit_override() -> None:
    explicit = ["stock:600519.SH"]
    assert explicit == ["stock:600519.SH"]
