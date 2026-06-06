from __future__ import annotations

import json
from types import SimpleNamespace

import grpc
import pytest

from edera_core.config.entities import EntityStore
from edera_core.config.schema import EntitiesConfig, EntityRelationsConfig, EntityTypeConfig
from edera_core.query_service import _QueryService
from edera_core.proto import edera_pb2 as pb2
from edera_core.storage import create_engine, init_db, session_factory
from edera_core.storage.repository import create_dag_run, create_ordinary_entity, mark_node_run, record_log_index, store_node_output_entities

from service_fakes import AbortError, FakeContext, FakeDaemon


@pytest.mark.asyncio
async def test_latest_briefing(tmp_path):
    daemon = await _daemon(tmp_path)
    async with daemon.controller._factory()() as session:
        await store_node_output_entities(session, "c1", "briefing", "briefing", {"content": "hello", "created_at": "2026-01-01T00:00:00"})
        await session.commit()
    service = _QueryService(daemon)

    result = await service.LatestBriefing(pb2.EmptyRequest(), FakeContext())

    assert json.loads(result.json)["briefing"]["content"] == "hello"
    await daemon.controller.engine.dispose()


@pytest.mark.asyncio
async def test_advice_not_found(tmp_path):
    service = _QueryService(await _daemon(tmp_path))

    with pytest.raises(AbortError) as exc:
        await service.GetAdvice(pb2.NameRequest(name="missing"), FakeContext())

    assert exc.value.code == grpc.StatusCode.NOT_FOUND
    await service.daemon.controller.engine.dispose()


@pytest.mark.asyncio
async def test_results_summary(tmp_path):
    daemon = await _daemon(tmp_path)
    async with daemon.controller._factory()() as session:
        await store_node_output_entities(session, "c1", "briefing", "briefing", {"content": "hello", "created_at": "2026-01-01T00:00:00"})
        await store_node_output_entities(session, "c1", "advisor", "advice", {"stock_code": "AAPL", "direction": "buy", "created_at": "2026-01-01T00:00:00"})
        await session.commit()
    service = _QueryService(daemon)

    result = await service.ResultsSummary(pb2.AdviceQueryRequest(stock_code="AAPL"), FakeContext())
    payload = json.loads(result.json)

    assert {"briefing", "briefings", "advices", "events", "event_details", "summary_items", "metadata_bar", "failed_sources"}.issubset(payload)
    assert payload["advices"][0]["stock_code"] == "AAPL"
    await daemon.controller.engine.dispose()


@pytest.mark.asyncio
async def test_source_health_and_logs_use_database_sources(tmp_path):
    daemon = await _daemon(tmp_path)
    async with daemon.controller._factory()() as session:
        entity_types = daemon.controller.runtime_snapshot().entity_store.entity_types
        await create_ordinary_entity(session, "rss-source", "source:rss", {"name": "rss"}, entity_types)
        await create_dag_run(session, "run-1", "manual", ["rss"], dag_name="demo")
        await mark_node_run(session, "run-1", "rss", "failed", "network")
        await session.commit()
    service = _QueryService(daemon)

    health = json.loads((await service.SourceHealth(pb2.EmptyRequest(), FakeContext())).json)
    logs = json.loads((await service.SourceLogs(pb2.SourceLogsRequest(source_name="rss"), FakeContext())).json)

    assert [item["source_name"] for item in health["sources"]] == ["rss"]
    assert health["logs"][0]["source_name"] == "rss"
    assert logs["logs"][0]["source_name"] == "rss"
    await daemon.controller.engine.dispose()


@pytest.mark.asyncio
async def test_node_logs_filters_run_and_node(tmp_path):
    daemon = await _daemon(tmp_path)
    async with daemon.controller._factory()() as session:
        await record_log_index(session, "run-1", "node-a", "/tmp/summary.json", "digest-a", 12, kind="summary")
        await record_log_index(session, "run-1", "node-b", "/tmp/other.json", "digest-b", 10, kind="summary")
        await record_log_index(session, "run-2", "node-a", "/tmp/raw.log", "digest-c", 8, kind="raw")
        await session.commit()
    service = _QueryService(daemon)

    result = await service.NodeLogs(pb2.NodeOutputsRequest(run_id="run-1", node_id="node-a", limit=10), FakeContext())
    payload = json.loads(result.json)

    assert [item["path"] for item in payload["logs"]] == ["/tmp/summary.json"]
    assert payload["logs"][0]["kind"] == "summary"
    await daemon.controller.engine.dispose()


@pytest.mark.asyncio
async def test_child_run_for_parent_uses_node_run_metadata(tmp_path):
    daemon = await _daemon(tmp_path)
    async with daemon.controller._factory()() as session:
        await create_dag_run(session, "parent-1", "manual", ["node-x"], dag_name="dag-a")
        await mark_node_run(session, "parent-1", "node-x", "succeeded", metadata={"sub_dag_run_id": "child-1"})
        await create_dag_run(session, "parent-2", "manual", ["node-x"], dag_name="dag-b")
        await mark_node_run(session, "parent-2", "node-x", "succeeded", metadata={"sub_dag_run_id": "child-2"})
        await session.commit()
    service = _QueryService(daemon)

    result = await service.ChildRunForParent(pb2.ParentChildRunRequest(parent_run_id="parent-1", parent_node_id="node-x"), FakeContext())
    missing = await service.ChildRunForParent(pb2.ParentChildRunRequest(parent_run_id="parent-1", parent_node_id="missing"), FakeContext())

    assert json.loads(result.json)["child_run_id"] == "child-1"
    assert json.loads(missing.json)["child_run_id"] is None
    await daemon.controller.engine.dispose()


async def _daemon(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'edera.db'}")
    await init_db(engine)
    return FakeDaemon(tmp_path, Controller(engine, session_factory(engine)))


class Controller:
    def __init__(self, engine, factory):
        self.engine = engine
        self.factory = factory
        entity_types = {
            "rss-source": EntityTypeConfig.model_validate(
                {
                    "display_name": "RSS",
                    "business_id_field": "name",
                    "display_template": "{name}",
                    "storage_tier": "database",
                    "schema": {"properties": {"name": {"type": "string"}}},
                }
            )
        }
        self._snapshot = SimpleNamespace(
            entity_store=EntityStore(EntitiesConfig(), entity_types, EntityRelationsConfig(), None)
        )

    def _factory(self):
        return self.factory

    def runtime_snapshot(self):
        return self._snapshot
