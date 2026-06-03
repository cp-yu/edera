from __future__ import annotations

import asyncio

import pytest

from edera_core.config.entities import EntityStore
from edera_core.config.schema import EntitiesConfig, EntityRelationsConfig, EntityTypeConfig
from edera_core.trigger import TriggerExecutor


@pytest.mark.asyncio
async def test_emit_wakes_waiter() -> None:
    executor = TriggerExecutor(_store())
    future = executor.register_waiter("event:approve:abc")

    await executor.emit("event:approve:abc", {"ok": True})

    assert future.done()
    assert future.result() == {"ok": True}


@pytest.mark.asyncio
async def test_emit_nomatch_does_not_wake_waiter() -> None:
    executor = TriggerExecutor(_store())
    future = executor.register_waiter("event:approve:abc")

    await executor.emit("event:approve:xyz", {"ok": True})

    assert not future.done()


@pytest.mark.asyncio
async def test_emit_both_drives_trigger_and_waiter() -> None:
    fired: list[str] = []

    async def run_dag(name: str, payload: object | None) -> None:
        fired.append(f"dag:{name}:{payload}")

    executor = TriggerExecutor(_store(trigger=True), run_dag=run_dag)
    future = executor.register_waiter("event:approve:abc")

    result = await executor.emit("event:approve:abc", "payload")
    await asyncio.sleep(0)

    assert result == ["dag:default"]
    assert fired == ["dag:default:payload"]
    assert future.result() == "payload"


def _store(trigger: bool = False) -> EntityStore:
    entities = []
    if trigger:
        entities.append(
            {
                "id": "approval",
                "type": "trigger",
                "attributes": {
                    "name": "approval",
                    "wait_for": "event:approve:abc",
                    "target": "dag:default",
                },
            }
        )
    return EntityStore(
        EntitiesConfig.model_validate({"entities": entities}),
        {
            "trigger": EntityTypeConfig.model_validate(
                {
                    "display_name": "Trigger",
                    "business_id_field": "name",
                    "display_template": "{name}",
                    "schema": {
                        "properties": {
                            "name": {"type": "string"},
                            "wait_for": {"type": "string"},
                            "target": {"type": "string"},
                        }
                    },
                }
            )
        },
        EntityRelationsConfig(),
    )
