from __future__ import annotations

from edera_core.config.entities import EntityStore
from edera_core.config.schema import EntitiesConfig, EntityRelationsConfig, EntityTypeConfig
from edera_core.storage import create_engine, init_db, session_factory, sqlite_url
from edera_core.storage.entities import EventGroupBit
from edera_core.trigger import TriggerExecutor
from sqlmodel import select

import pytest


@pytest.mark.asyncio
async def test_persist_and_restore(tmp_path) -> None:
    engine = create_engine(sqlite_url(tmp_path / "test.db"))
    await init_db(engine)
    factory = session_factory(engine)
    executor = TriggerExecutor(_store(), factory=factory)
    await executor.events.set("event:price-drop")

    restored = TriggerExecutor(_store(), factory=factory)
    await restored.load()

    try:
        assert "event:price-drop" in restored.events.events
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_set_clear_consume(tmp_path) -> None:
    engine = create_engine(sqlite_url(tmp_path / "test.db"))
    await init_db(engine)
    factory = session_factory(engine)
    executor = TriggerExecutor(_store(), factory=factory)

    await executor.events.set("event:price-drop")
    await executor.events.clear("event:price-drop")
    await executor.events.set("event:price-drop")
    await executor.events.consume(["event:price-drop"])

    async with factory() as session:
        bits = (await session.exec(select(EventGroupBit))).all()
    try:
        assert bits == []
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_auto_consume() -> None:
    fired: list[str] = []
    executor = TriggerExecutor(_store(), run_dag=lambda name, payload: _record(fired, name))

    await executor.emit('cron:"0 9 * * *"')
    await executor.emit("event:market-open")

    assert fired == ["morning"]
    assert executor.events.events == set()


async def _record(items: list[str], value: str) -> None:
    items.append(value)


def _store() -> EntityStore:
    return EntityStore(_triggers(), _types(), EntityRelationsConfig())


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


def _triggers() -> EntitiesConfig:
    return EntitiesConfig.model_validate(
        {
            "entities": [
                {
                    "id": "morning",
                    "type": "trigger",
                    "attributes": {
                        "name": "morning",
                        "wait_for": 'cron:"0 9 * * *" AND event:market-open',
                        "target": "dag:morning",
                    },
                }
            ]
        }
    )
