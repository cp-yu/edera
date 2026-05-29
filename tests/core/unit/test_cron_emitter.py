from __future__ import annotations

from datetime import datetime, timezone

import pytest

from edera_core.config.entities import EntityStore
from edera_core.config.schema import EntitiesConfig, EntityRelationsConfig, EntityTypeConfig
from edera_core.trigger import CronEmitter, TriggerExecutor


@pytest.mark.asyncio
async def test_tick_emit() -> None:
    emitted: list[str] = []
    executor = TriggerExecutor(_store(), run_dag=lambda name, payload: _record(emitted, name))
    emitter = CronEmitter(executor)

    fired = await emitter.tick(datetime(2026, 5, 29, 9, 0, tzinfo=timezone.utc))

    assert fired == ['cron:"0 9 * * *"']
    assert emitted == ["morning"]


@pytest.mark.asyncio
async def test_missed_tick_skip() -> None:
    emitted: list[str] = []
    executor = TriggerExecutor(_store(), run_dag=lambda name, payload: _record(emitted, name))
    emitter = CronEmitter(executor)

    assert await emitter.tick(datetime(2026, 5, 29, 9, 30, tzinfo=timezone.utc)) == []
    assert emitted == []


@pytest.mark.asyncio
async def test_shared_cron_token_emits_once() -> None:
    executor = TriggerExecutor(_store(shared=True))
    calls: list[str] = []

    async def emit(event: str, payload: object | None = None, *, source: str = "rpc", depth: int = 0) -> list[str]:
        calls.append(event)
        return []

    executor.emit = emit  # type: ignore[method-assign]
    emitter = CronEmitter(executor)

    fired = await emitter.tick(datetime(2026, 5, 29, 9, 0, tzinfo=timezone.utc))

    assert fired == ['cron:"0 9 * * *"']
    assert calls == ['cron:"0 9 * * *"']


async def _record(items: list[str], value: str) -> None:
    items.append(value)


def _store(shared: bool = False) -> EntityStore:
    entities = [
        {
            "id": "morning",
            "type": "trigger",
            "attributes": {
                "name": "morning",
                "wait_for": 'cron:"0 9 * * *"',
                "target": "dag:morning",
            },
        }
    ]
    if shared:
        entities.append(
            {
                "id": "morning-copy",
                "type": "trigger",
                "attributes": {
                    "name": "morning-copy",
                    "wait_for": 'cron:"0 9 * * *"',
                    "target": "dag:copy",
                },
            }
        )
    return EntityStore(EntitiesConfig.model_validate({"entities": entities}), _types(), EntityRelationsConfig())


def _types() -> dict[str, EntityTypeConfig]:
    return {
        "trigger": EntityTypeConfig.model_validate(
            {
                "display_name": "Trigger",
                "business_id_field": "name",
                "display_template": "{name}",
                "schema": {
                    "required": ["name", "wait_for", "target"],
                    "properties": {
                        "name": {"type": "string"},
                        "wait_for": {"type": "string"},
                        "target": {"type": "string"},
                    },
                },
            }
        )
    }
