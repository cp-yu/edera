from __future__ import annotations

import pytest
from sqlalchemy import inspect, text
from sqlmodel import select

from edera_core.config.schema import EntityConfig, EntityTypeConfig
from edera_core.proto import edera_pb2 as pb2
from edera_core.server import _EntityService
from edera_core.storage import create_engine, init_db, session_factory, sqlite_url
from edera_core.storage.entities import CoreEntityNode
from edera_core.storage.repository import (
    get_core_entity,
    list_core_entities,
    list_entity_type_configs,
    save_core_entity,
    seed_entity_type_records,
    store_node_output_entities,
)
from edera_core.trigger import TriggerExpressionError


class _Daemon:
    pb2 = pb2

    def __init__(self, config_dir) -> None:
        self.config_dir = config_dir
        self.controller = _Controller()


class _Controller:
    def __init__(self) -> None:
        self.events: list[str] = []

    async def emit(self, event: str, payload: object | None = None, *, source: str = "rpc", depth: int = 0) -> list[str]:
        self.events.append(event)
        return []


class _Context:
    def invocation_metadata(self):
        return ()

    def auth_context(self):
        return {"x509_common_name": [b"human:test"]}

    async def abort(self, _code, message):
        raise AssertionError(message)


@pytest.mark.asyncio
async def test_emit_entity_changed(tmp_path) -> None:
    _write_config(tmp_path)
    daemon = _Daemon(tmp_path)
    service = _EntityService(daemon)

    created = await service.Create(pb2.Entity(type="stock", json='{"code":"TEST","name":"Test"}'), _Context())
    await service.Update(pb2.Entity(id=created.id, json='{"field":"name","value":"Changed"}'), _Context())
    await service.Delete(pb2.EntityRef(ref="stock:TEST"), _Context())

    assert daemon.controller.events == [
        "event:entity-changed:stock:TEST",
        "event:entity-changed:stock:TEST",
        "event:entity-changed:stock:TEST",
    ]


@pytest.mark.asyncio
async def test_trigger_wait_for_rejects_manual_prefix(tmp_path) -> None:
    _write_config(tmp_path)
    daemon = _Daemon(tmp_path)
    service = _EntityService(daemon)

    with pytest.raises(TriggerExpressionError, match="manual prefix"):
        await service.Create(
            pb2.Entity(
                type="trigger",
                json='{"name":"bad","wait_for":"manual:dag:default","target":"dag:default"}',
            ),
            _Context(),
        )


@pytest.mark.asyncio
async def test_core_entity_tables_round_trip_without_node_outputs(tmp_path) -> None:
    engine = create_engine(sqlite_url(tmp_path / "edera.db"))
    try:
        await init_db(engine)
        async with engine.connect() as conn:
            tables = await conn.run_sync(lambda sync: set(inspect(sync).get_table_names()))
        assert {"entity_types", "entity_node", "entity_dag", "entity_trigger", "entity_resource", "log_index"} <= tables

        factory = session_factory(engine)
        async with factory() as session:
            entity_types = _core_entity_types()
            await seed_entity_type_records(session, entity_types)
            node = await save_core_entity(
                session,
                EntityConfig(
                    id="node-reader",
                    type="node",
                    attributes={
                        "name": "reader",
                        "type": "function",
                        "role": "source",
                        "handler": "read",
                        "input_type": "Any",
                        "output_type": "Analysis",
                        "skills": ["summarize"],
                        "parameters": {"limit": 1},
                    },
                ),
            )
            dag = await save_core_entity(
                session,
                EntityConfig(
                    id="dag-default",
                    type="dag",
                    attributes={
                        "name": "default",
                        "inputs": [],
                        "nodes": [{"id": "reader", "type": "reader"}],
                        "edges": [],
                        "ui": {"nodes": {}},
                    },
                ),
            )
            trigger = await save_core_entity(
                session,
                EntityConfig(
                    id="trigger-default",
                    type="trigger",
                    attributes={
                        "name": "default-cron",
                        "wait_for": 'cron:"*/30 * * * *"',
                        "target": "dag:default",
                        "enabled": True,
                    },
                ),
            )
            resource = await save_core_entity(
                session,
                EntityConfig(id="v8_isolate", type="resource", attributes={"id": "v8_isolate", "permits": 1}),
            )
            await session.commit()

        async with factory() as session:
            assert (await get_core_entity(session, "node:reader", entity_types)).id == node.id
            assert (await get_core_entity(session, "dag:default", entity_types)).id == dag.id
            assert (await get_core_entity(session, "trigger:default-cron", entity_types)).id == trigger.id
            assert (await get_core_entity(session, "resource:v8_isolate", entity_types)).id == resource.id
            assert len(await list_core_entities(session)) == 4
            result = await session.exec(text("select count(*) from node_outputs"))
            assert result.one()[0] == 0
            result = await session.exec(select(CoreEntityNode).where(CoreEntityNode.entity_id == "node-reader"))
            assert result.one().attributes_json == {}
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_output_entities_remain_in_node_outputs(tmp_path) -> None:
    engine = create_engine(sqlite_url(tmp_path / "edera.db"))
    try:
        await init_db(engine)
        factory = session_factory(engine)
        async with factory() as session:
            await store_node_output_entities(session, "run-1", "reader", "analysis", {"score": 1})
            await session.commit()
        async with factory() as session:
            assert await list_core_entities(session, "analysis") == []
            result = await session.exec(text("select count(*) from node_outputs"))
            assert result.one()[0] == 1
            result = await session.exec(text("select count(*) from entity_node"))
            assert result.one()[0] == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_entity_type_metadata_round_trips_from_db(tmp_path) -> None:
    engine = create_engine(sqlite_url(tmp_path / "edera.db"))
    try:
        await init_db(engine)
        factory = session_factory(engine)
        async with factory() as session:
            await seed_entity_type_records(session, _core_entity_types())
            await session.commit()
        async with factory() as session:
            entity_types = await list_entity_type_configs(session)
        assert entity_types["node"].business_id_field == "name"
        assert entity_types["node"].display_template == "{name}"
        assert entity_types["node"].storage_tier == "database"
        assert entity_types["node"].system_protected is True
    finally:
        await engine.dispose()


def _core_entity_types() -> dict[str, EntityTypeConfig]:
    return {
        "node": EntityTypeConfig.model_validate(
            {
                "display_name": "Node",
                "business_id_field": "name",
                "display_template": "{name}",
                "storage_tier": "database",
                "system_protected": True,
                "schema": {
                    "required": ["name", "type", "input_type", "output_type"],
                    "properties": {
                        "name": {"type": "string"},
                        "type": {"type": "string"},
                        "handler": {"type": "string"},
                        "input_type": {"type": "string"},
                        "output_type": {"type": "string"},
                    },
                },
            }
        ),
        "dag": EntityTypeConfig.model_validate(
            {
                "display_name": "DAG",
                "business_id_field": "name",
                "display_template": "{name}",
                "storage_tier": "database",
                "system_protected": True,
                "schema": {"required": ["name", "nodes", "edges"], "properties": {"name": {"type": "string"}}},
            }
        ),
        "trigger": EntityTypeConfig.model_validate(
            {
                "display_name": "Trigger",
                "business_id_field": "name",
                "display_template": "{name}",
                "storage_tier": "database",
                "system_protected": True,
                "schema": {"required": ["name", "wait_for", "target"], "properties": {"name": {"type": "string"}}},
            }
        ),
        "resource": EntityTypeConfig.model_validate(
            {
                "display_name": "Resource",
                "business_id_field": "id",
                "display_template": "{id}",
                "storage_tier": "database",
                "system_protected": True,
                "schema": {"required": ["permits"], "properties": {"permits": {"type": "integer"}}},
            }
        ),
    }


def _write_config(root) -> None:
    (root.parent / "schemas" / "entity-types").mkdir(parents=True, exist_ok=True)
    (root.parent / "schemas" / "entity-types" / "stock.yaml").write_text(
        "display_name: Stock\n"
        "business_id_field: code\n"
        "display_template: '{code}'\n"
        "schema:\n"
        "  type: object\n"
        "  required: [code, name]\n"
        "  properties:\n"
        "    code: {type: string}\n"
        "    name: {type: string}\n",
        encoding="utf-8",
    )
    (root.parent / "schemas" / "entity-types" / "trigger.yaml").write_text(
        "display_name: Trigger\n"
        "business_id_field: name\n"
        "display_template: '{name}'\n"
        "schema:\n"
        "  type: object\n"
        "  required: [name, wait_for, target]\n"
        "  properties:\n"
        "    name: {type: string}\n"
        "    wait_for: {type: string}\n"
        "    target: {type: string}\n",
        encoding="utf-8",
    )
    (root / "dags").mkdir()
    (root / "nodes").mkdir()
    (root / "skills").mkdir()
    (root / "entities.yaml").write_text("entities: []\n", encoding="utf-8")
    (root / "entity-relations.yaml").write_text("relations: []\n", encoding="utf-8")
    (root / "system.toml").write_text("database_url = \"sqlite+aiosqlite:///test.db\"\n", encoding="utf-8")
