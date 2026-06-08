import pytest

from edera_core.config.entities import EntityStore
from edera_core.config.schema import EntitiesConfig, EntityRelationsConfig, EntityTypeConfig
from edera_core.storage import create_engine, init_db, session_factory, sqlite_url
from edera_core.storage.entities import EmitRecord, EventGroupBit
from edera_core.trigger import TriggerExpressionError, TriggerExecutor, parse_trigger_expression
from sqlmodel import select


@pytest.mark.asyncio
async def test_trigger_system() -> None:
    fired: list[str] = []
    store = EntityStore(_triggers(), _types(), EntityRelationsConfig())
    executor = TriggerExecutor(store, run_dag=lambda name, payload: _record(fired, f"dag:{name}"))

    assert await executor.emit("event:price-drop") == ["dag:default"]
    assert "event:price-drop" not in executor.events.events
    assert executor.records[0]["event"] == "event:price-drop"

    assert await executor.emit('cron:"0 9 * * *"') == []
    assert await executor.emit("event:market-open") == ["dag:morning"]


@pytest.mark.asyncio
async def test_trigger_node_target_and_event_sources() -> None:
    fired: list[str] = []
    store = EntityStore(_triggers(node=True), _types(), EntityRelationsConfig())
    executor = TriggerExecutor(store, run_node=lambda name, payload: _record(fired, f"node:{name}"))

    assert executor.entity_changed("stock:00700") == "event:entity-changed:stock:00700"
    assert executor.config_changed() == "event:config-changed"
    assert executor.schedule_event("0 9 * * *") == 'cron:"0 9 * * *"'
    assert executor.node_output_event("negative-news") == "event:negative-news"
    assert await executor.emit("event:config-changed") == ["node:reader"]
    assert fired == ["node:reader"]


def test_trigger_expression_parser() -> None:
    expr = parse_trigger_expression('cron:"0 9 * * *" AND (event:market-open OR event:breaking-news)')
    assert expr.tokens == ['cron:"0 9 * * *"', "event:breaking-news", "event:market-open"]
    assert expr.evaluate({'cron:"0 9 * * *"', "event:breaking-news"})
    assert not expr.evaluate({'cron:"0 9 * * *"'})


def test_invalid_cron_requires_quotes() -> None:
    with pytest.raises(TriggerExpressionError):
        parse_trigger_expression("cron:0 9 * * *")


@pytest.mark.asyncio
async def test_event_group_persist_and_restore(tmp_path) -> None:
    engine = create_engine(sqlite_url(tmp_path / "test.db"))
    await init_db(engine)
    factory = session_factory(engine)
    store = EntityStore(_triggers(), _types(), EntityRelationsConfig())
    executor = TriggerExecutor(store, factory=factory)
    await executor.events.set("event:price-drop")

    restored = TriggerExecutor(store, factory=factory)
    await restored.load()

    try:
        assert "event:price-drop" in restored.events.events
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_set_clear_consume_and_emit_records(tmp_path) -> None:
    engine = create_engine(sqlite_url(tmp_path / "test.db"))
    await init_db(engine)
    factory = session_factory(engine)
    store = EntityStore(_triggers(), _types(), EntityRelationsConfig())
    executor = TriggerExecutor(store, run_dag=lambda name, payload: _record([], name), factory=factory)

    await executor.events.set("event:price-drop")
    await executor.events.clear("event:price-drop")
    await executor.emit("event:price-drop", {"symbol": "TEST"})

    async with factory() as session:
        bits = (await session.exec(select(EventGroupBit))).all()
        records = (await session.exec(select(EmitRecord))).all()
    try:
        assert bits == []
        assert len(records) == 1
        assert records[0].event == "event:price-drop"
        assert records[0].payload == {"symbol": "TEST"}
        assert records[0].source == "rpc"
        assert records[0].depth == 0
        assert records[0].created_at is not None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_reverse_index_only_evaluates_affected_trigger() -> None:
    fired: list[str] = []
    store = EntityStore(_triggers(), _types(), EntityRelationsConfig())
    executor = TriggerExecutor(store, run_dag=lambda name, payload: _record(fired, f"dag:{name}"))

    assert [trigger.id for trigger in executor.reverse_index()["event:price-drop"]] == ["price"]
    assert await executor.emit("event:unrelated") == []
    assert fired == []


@pytest.mark.asyncio
async def test_manual_prefix() -> None:
    fired: list[str] = []
    store = EntityStore(_triggers(), _types(), EntityRelationsConfig())
    executor = TriggerExecutor(store, run_dag=lambda name, payload: _record(fired, f"dag:{name}"))

    assert await executor.emit("manual:dag:default") == ["dag:default"]
    assert executor.events.events == set()
    assert fired == ["dag:default"]


@pytest.mark.asyncio
async def test_manual_node_prefix() -> None:
    fired: list[str] = []
    store = EntityStore(_triggers(), _types(), EntityRelationsConfig())
    executor = TriggerExecutor(store, run_node=lambda name, payload: _record(fired, f"node:{name}"))

    assert await executor.emit("manual:node:default/reader") == ["node:default/reader"]
    assert executor.events.events == set()
    assert fired == ["node:default/reader"]


@pytest.mark.asyncio
async def test_manual_no_bit(tmp_path) -> None:
    engine = create_engine(sqlite_url(tmp_path / "manual.db"))
    await init_db(engine)
    factory = session_factory(engine)
    store = EntityStore(_triggers(), _types(), EntityRelationsConfig())
    executor = TriggerExecutor(store, run_dag=lambda name, payload: _record([], name), factory=factory)

    try:
        await executor.emit("manual:dag:default")

        async with factory() as session:
            bits = (await session.exec(select(EventGroupBit))).all()
        assert executor.events.events == set()
        assert bits == []
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_disabled_skip() -> None:
    store = EntityStore(_triggers(disabled=True), _types(), EntityRelationsConfig())
    executor = TriggerExecutor(store)

    assert await executor.emit("event:price-drop") == []
    assert "event:price-drop" in executor.events.events


@pytest.mark.asyncio
async def test_oneshot_auto_disable() -> None:
    store = EntityStore(_triggers(oneshot=True), _types(), EntityRelationsConfig())
    executor = TriggerExecutor(store, run_dag=lambda name, payload: _record([], name))

    assert await executor.emit('cron:"0 9 1 1 *"') == ["dag:annual"]
    assert store.resolve("annual").attributes["enabled"] is False


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
                    "properties": {
                        "name": {"type": "string"},
                        "wait_for": {"type": "string"},
                        "target": {"type": "string"},
                        "enabled": {"type": "boolean"},
                    },
                },
            }
        )
    }


def _triggers(node: bool = False, disabled: bool = False, oneshot: bool = False) -> EntitiesConfig:
    entities = [
        {
            "id": "price",
            "type": "trigger",
            "attributes": {
                "name": "price",
                "wait_for": "event:price-drop",
                "target": "dag:default",
                "enabled": not disabled,
            },
        },
        {
            "id": "morning",
            "type": "trigger",
            "attributes": {
                "name": "morning",
                "wait_for": 'cron:"0 9 * * *" AND event:market-open',
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
                    "wait_for": "event:config-changed",
                    "target": "node:reader",
                },
            }
        ]
    if oneshot:
        entities = [
            {
                "id": "annual",
                "type": "trigger",
                "attributes": {
                    "name": "annual",
                    "wait_for": 'cron:"0 9 1 1 *"',
                    "target": "dag:annual",
                    "enabled": True,
                },
            }
        ]
    return EntitiesConfig.model_validate({"entities": entities})
