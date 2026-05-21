import pytest

from stockimformation.config.entities import EntityStore
from stockimformation.config.schema import EntitiesConfig, EntityRelationsConfig, EntityTypeConfig
from stockimformation.trigger import TriggerExecutor


@pytest.mark.asyncio
async def test_trigger_system() -> None:
    fired: list[str] = []
    store = EntityStore(_triggers(), _types(), EntityRelationsConfig())
    executor = TriggerExecutor(store, run_dag=lambda name: _record(fired, f"dag:{name}"))

    assert await executor.emit("event:price-drop") == ["dag:default"]
    assert "event:price-drop" not in executor.events.events
    assert executor.records[0]["target"] == "dag:default"

    assert await executor.emit("schedule:09:00") == []
    assert await executor.emit("event:market-open") == ["dag:morning"]


@pytest.mark.asyncio
async def test_trigger_node_target_and_event_sources() -> None:
    fired: list[str] = []
    store = EntityStore(_triggers(node=True), _types(), EntityRelationsConfig())
    executor = TriggerExecutor(store, run_node=lambda name: _record(fired, f"node:{name}"))

    assert executor.entity_changed("stock:00700") == "event:entity-changed:stock:00700"
    assert executor.config_changed() == "event:config-changed"
    assert executor.schedule_event("09:00") == "schedule:09:00"
    assert executor.node_output_event("negative-news") == "event:negative-news"
    assert await executor.emit("event:config-changed") == ["node:reader"]
    assert fired == ["node:reader"]


async def _record(items: list[str], value: str) -> None:
    items.append(value)


def _types() -> dict[str, EntityTypeConfig]:
    return {
        "trigger": EntityTypeConfig.model_validate(
            {
                "display_name": "Trigger",
                "business_id_field": "name",
                "display_template": "{name}",
                "schema": {
                    "required": ["name", "wait_for", "target"],
                    "properties": {"name": {"type": "string"}, "wait_for": {"type": "object"}, "target": {"type": "string"}},
                },
            }
        )
    }


def _triggers(node: bool = False) -> EntitiesConfig:
    entities = [
        {
            "id": "price",
            "type": "trigger",
            "attributes": {"name": "price", "wait_for": {"mode": "OR", "events": ["event:price-drop"]}, "target": "dag:default"},
        },
        {
            "id": "morning",
            "type": "trigger",
            "attributes": {
                "name": "morning",
                "wait_for": {"mode": "AND", "events": ["schedule:09:00", "event:market-open"]},
                "target": "dag:morning",
            },
        },
    ]
    if node:
        entities = [
            {
                "id": "config",
                "type": "trigger",
                "attributes": {
                    "name": "config",
                    "wait_for": {"mode": "OR", "events": ["event:config-changed"]},
                    "target": "node:reader",
                },
            }
        ]
    return EntitiesConfig.model_validate({"entities": entities})
