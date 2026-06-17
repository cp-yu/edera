from __future__ import annotations

import pytest

from edera_core.config.entities import EntityStore
from edera_core.config.schema import EntitiesConfig, EntityConfig, EntityRelationsConfig, EntityTypeConfig
from edera_core.storage.entities import DagRun
from edera_core.trigger import EventGroup, TriggerExpression, TriggerExecutor


def test_dag_run_accepts_startup_source() -> None:
    run = DagRun(run_id="r1", source="startup", dag_name="bootstrap")

    assert run.source == "startup"


def test_startup_token_validates() -> None:
    expr = TriggerExpression("startup")

    assert expr.tokens == ["startup"]
    assert expr.evaluate({"startup"}) is True
    assert expr.evaluate(set()) is False


@pytest.mark.asyncio
async def test_startup_not_consumed_on_fire() -> None:
    fired: list[str] = []

    async def run_dag(name: str, payload: object | None, source: str) -> None:
        fired.append(name)

    store = _store(
        {"id": "t1", "wait_for": "startup", "target": "dag:alpha"},
        {"id": "t2", "wait_for": "startup", "target": "dag:beta"},
    )
    executor = TriggerExecutor(store, run_dag=run_dag)

    await executor.emit("startup", source="startup")

    assert fired == ["alpha", "beta"]
    assert "startup" in executor.events.events


@pytest.mark.asyncio
async def test_event_group_consume_skips_startup() -> None:
    group = EventGroup()

    await group.set("startup")
    await group.set("event:x")

    await group.consume({"startup", "event:x"})

    assert "startup" in group.events
    assert "event:x" not in group.events


def _store(*triggers: dict[str, object]) -> EntityStore:
    entities = [
        EntityConfig(
            id=str(trigger["id"]),
            type="trigger",
            attributes={
                "name": trigger["id"],
                "wait_for": trigger["wait_for"],
                "target": trigger["target"],
            },
        )
        for trigger in triggers
    ]
    return EntityStore(
        EntitiesConfig.model_validate({"entities": [e.model_dump() for e in entities]}),
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
