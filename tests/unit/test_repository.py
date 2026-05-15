from datetime import datetime, timezone
from pathlib import Path
from typing import cast

import pytest
from sqlmodel import select

from stockimformation.models.database import create_engine, init_db, session_factory, sqlite_url
from stockimformation.models.entities import Advice, Briefing, EventRecord, NodeRun, PipelineRun, RawItem
from stockimformation.models.repository import (
    add_raw_item,
    create_pipeline_run,
    current_pipeline_run,
    finish_pipeline_run,
    get_briefing,
    list_advices,
    list_briefings,
    mark_node_run,
    events_for_analysis_ids,
    node_runs_for_cycle,
    recent_pipeline_runs,
    source_execution_logs,
    source_health_summary,
)


@pytest.mark.asyncio
async def test_add_raw_item_skips_existing_url(tmp_path: Path) -> None:
    engine = create_engine(sqlite_url(tmp_path / "repo.db"))
    await init_db(engine)
    factory = session_factory(engine)
    async with factory() as session:
        first = await add_raw_item(session, _raw_item("https://example.com/a"))
        second = await add_raw_item(session, _raw_item("https://example.com/a"))
        await session.commit()
        result = await session.exec(select(RawItem))
    assert first is not None
    assert second is None
    assert len(result.all()) == 1


@pytest.mark.asyncio
async def test_pipeline_run_records_success_and_nodes(tmp_path: Path) -> None:
    engine = create_engine(sqlite_url(tmp_path / "runs.db"))
    await init_db(engine)
    factory = session_factory(engine)
    async with factory() as session:
        await create_pipeline_run(session, "cycle-1", "manual", ["reader"])
        await mark_node_run(session, "cycle-1", "reader", "running")
        await mark_node_run(session, "cycle-1", "reader", "succeeded")
        await finish_pipeline_run(session, "cycle-1", "succeeded")
        await session.commit()
        runs = await session.exec(select(PipelineRun))
        nodes = await session.exec(select(NodeRun))
    run = runs.one()
    node = nodes.one()
    assert run.status == "succeeded"
    assert run.ended_at is not None
    assert node.status == "succeeded"
    assert node.started_at is not None
    assert node.ended_at is not None


@pytest.mark.asyncio
async def test_pipeline_run_queries_current_and_recent(tmp_path: Path) -> None:
    engine = create_engine(sqlite_url(tmp_path / "queries.db"))
    await init_db(engine)
    factory = session_factory(engine)
    async with factory() as session:
        await create_pipeline_run(session, "cycle-1", "manual")
        await finish_pipeline_run(session, "cycle-1", "failed", "boom")
        await create_pipeline_run(session, "cycle-2", "schedule", ["reader"])
        await session.commit()
        current = await current_pipeline_run(session)
        recent = await recent_pipeline_runs(session)
        nodes = await node_runs_for_cycle(session, "cycle-2")
    assert current is not None
    assert current.cycle_id == "cycle-2"
    assert [run.cycle_id for run in recent] == ["cycle-2", "cycle-1"]
    assert nodes[0].status == "pending"


@pytest.mark.asyncio
async def test_briefing_history_filters_and_orders_by_created_at(tmp_path: Path) -> None:
    engine = create_engine(sqlite_url(tmp_path / "briefings.db"))
    await init_db(engine)
    factory = session_factory(engine)
    older = datetime(2026, 1, 1, tzinfo=timezone.utc)
    newer = datetime(2026, 1, 2, tzinfo=timezone.utc)
    async with factory() as session:
        session.add(Briefing(cycle_id="old", content="old", created_at=older))
        session.add(Briefing(cycle_id="new", content="new", created_at=newer))
        await session.commit()
        briefings = await list_briefings(session)
        filtered = await list_briefings(session, created_from=newer)
        detail = await get_briefing(session, briefings[0].id or 0)
    assert [item.cycle_id for item in briefings] == ["new", "old"]
    assert [item.cycle_id for item in filtered] == ["new"]
    assert detail is not None
    assert detail.cycle_id == "new"


@pytest.mark.asyncio
async def test_advice_filters_and_orders_by_created_at(tmp_path: Path) -> None:
    engine = create_engine(sqlite_url(tmp_path / "advices.db"))
    await init_db(engine)
    factory = session_factory(engine)
    older = datetime(2026, 1, 1, tzinfo=timezone.utc)
    newer = datetime(2026, 1, 2, tzinfo=timezone.utc)
    async with factory() as session:
        session.add(_advice("00700.HK", "hold", older))
        session.add(_advice("600519.SH", "buy", newer))
        await session.commit()
        all_items = await list_advices(session)
        stock_items = await list_advices(session, stock_code="600519.SH")
        direction_items = await list_advices(session, direction="hold")
        time_items = await list_advices(session, created_from=newer)
    assert [item.stock_code for item in all_items] == ["600519.SH", "00700.HK"]
    assert [item.stock_code for item in stock_items] == ["600519.SH"]
    assert [item.direction for item in direction_items] == ["hold"]
    assert [item.stock_code for item in time_items] == ["600519.SH"]


@pytest.mark.asyncio
async def test_source_health_summary_uses_window_and_failed_sources(tmp_path: Path) -> None:
    engine = create_engine(sqlite_url(tmp_path / "source-health.db"))
    await init_db(engine)
    factory = session_factory(engine)
    async with factory() as session:
        await create_pipeline_run(session, "cycle-1", "manual", ["sample-web"])
        await mark_node_run(session, "cycle-1", "sample-web", "running")
        await mark_node_run(session, "cycle-1", "sample-web", "failed", "node timeout")
        await finish_pipeline_run(session, "cycle-1", "failed", "boom")
        await create_pipeline_run(session, "cycle-2", "manual", ["sample-web"])
        await mark_node_run(session, "cycle-2", "sample-web", "running")
        await mark_node_run(session, "cycle-2", "sample-web", "succeeded")
        await finish_pipeline_run(session, "cycle-2", "succeeded")
        session.add(
            Briefing(
                cycle_id="cycle-2",
                content="briefing",
                metadata_={
                    "failed_sources": {"sample-web": "source timeout"},
                    "source_recovery": {
                        "sample-web": {
                            "recovery_status": "recovered",
                            "attempt_count": 1,
                            "recoverable_reason": "timeout",
                            "updated_at": _dt(2).isoformat(),
                        }
                    },
                },
            )
        )
        await session.commit()
        health = await source_health_summary(session, ["sample-web", "missing-source"])
    sample = health[0]
    missing = health[1]
    assert sample["latest_status"] == "succeeded"
    assert sample["success_rate"] == 0.5
    assert sample["window_size"] == 2
    assert sample["recovery_status"] == "recovered"
    assert sample["attempt_count"] == 1
    assert sample["recoverable_reason"] == "timeout"
    assert sample["latest_failure_reason"] == "source timeout"
    assert sample["escalated"] is False
    assert missing["latest_status"] == "unknown"
    assert missing["success_rate"] is None
    assert missing["window_size"] == 0


@pytest.mark.asyncio
async def test_source_execution_logs_filter_and_pipeline_context(tmp_path: Path) -> None:
    engine = create_engine(sqlite_url(tmp_path / "source-logs.db"))
    await init_db(engine)
    factory = session_factory(engine)
    async with factory() as session:
        await create_pipeline_run(session, "cycle-1", "manual", ["sample-rss", "sample-web"])
        await mark_node_run(session, "cycle-1", "sample-rss", "running")
        await mark_node_run(session, "cycle-1", "sample-rss", "succeeded")
        await mark_node_run(session, "cycle-1", "sample-web", "running")
        await mark_node_run(session, "cycle-1", "sample-web", "failed", "timeout")
        await finish_pipeline_run(session, "cycle-1", "failed", "boom")
        await session.commit()
        logs = await source_execution_logs(session, "sample-web")
    assert len(logs) == 1
    assert logs[0]["cycle_id"] == "cycle-1"
    assert logs[0]["source_name"] == "sample-web"
    assert logs[0]["node_status"] == "failed"
    assert logs[0]["pipeline_status"] == "failed"
    assert logs[0]["error"] == "timeout"


@pytest.mark.asyncio
async def test_source_health_summary_escalation_and_repair_task(tmp_path: Path) -> None:
    engine = create_engine(sqlite_url(tmp_path / "source-escalation.db"))
    await init_db(engine)
    factory = session_factory(engine)
    async with factory() as session:
        await create_pipeline_run(session, "cycle-1", "manual", ["sample-web"])
        await mark_node_run(session, "cycle-1", "sample-web", "failed", "timeout")
        await finish_pipeline_run(session, "cycle-1", "failed", "boom")
        session.add(
            Briefing(
                cycle_id="cycle-1",
                content="briefing",
                metadata_={
                    "failed_sources": {"sample-web": "timeout"},
                    "source_recovery": {
                        "sample-web": {
                            "recovery_status": "escalated",
                            "attempt_count": 2,
                            "recoverable_reason": "timeout",
                            "latest_failure_reason": "timeout",
                            "escalated": True,
                            "escalation_reason": "recovery_exhausted",
                        }
                    },
                    "repair_tasks": {
                        "sample-web": {
                            "task_id": "sample-web-1",
                            "task_path": "/tmp/sample-web-1.json",
                            "created_at": _dt(1).isoformat(),
                        }
                    },
                },
            )
        )
        await session.commit()
        health = await source_health_summary(session, ["sample-web"])
    assert health[0]["recovery_status"] == "escalated"
    assert health[0]["attempt_count"] == 2
    assert health[0]["escalated"] is True
    assert health[0]["escalation_reason"] == "recovery_exhausted"
    repair_task = cast(dict[str, object], health[0]["repair_task"])
    assert repair_task["task_id"] == "sample-web-1"


@pytest.mark.asyncio
async def test_event_record_validates_status_and_evidence(tmp_path: Path) -> None:
    engine = create_engine(sqlite_url(tmp_path / "events.db"))
    await init_db(engine)
    with pytest.raises(Exception):
        EventRecord.model_validate(
            {
                "stock_code": "00700.HK",
                "title": "title",
                "normalized_keywords": ["tencent"],
                "status": "invalid",
                "heat_score": 10,
                "heat_score_components": {"total": 10},
                "contradiction": False,
                "evidence_analysis_ids": [],
                "evidence_raw_item_ids": [],
                "source_names": [],
                "first_seen_at": _dt(1),
                "last_seen_at": _dt(1),
            }
        )


@pytest.mark.asyncio
async def test_events_for_analysis_ids_matches_related_events(tmp_path: Path) -> None:
    engine = create_engine(sqlite_url(tmp_path / "events-query.db"))
    await init_db(engine)
    factory = session_factory(engine)
    async with factory() as session:
        session.add(
            EventRecord(
                stock_code="00700.HK",
                title="title",
                normalized_keywords=["tencent"],
                status="discovered",
                heat_score=22,
                heat_score_components={"total": 22},
                evidence_analysis_ids=[11, 12],
                evidence_raw_item_ids=[1, 2],
                source_names=["sample-web"],
                first_seen_at=_dt(1),
                last_seen_at=_dt(1),
            )
        )
        await session.commit()
        events = await events_for_analysis_ids(session, [12])
    assert len(events) == 1
    assert events[0].stock_code == "00700.HK"


def _raw_item(url: str) -> RawItem:
    return RawItem(
        url=url,
        title="title",
        content="content",
        source_name="fixture",
        source_type="rss",
        stock_codes=["00700.HK"],
        published_at=datetime.now(timezone.utc),
    )


def _advice(stock_code: str, direction: str, created_at: datetime) -> Advice:
    return Advice(
        stock_code=stock_code,
        stock_name=stock_code,
        direction=direction,
        confidence=0.55,
        reason="reason",
        evidence=[1],
        source_quotes=["quote"],
        source_urls=["https://example.com/a"],
        portfolio_snapshot={"quantity": 1},
        created_at=created_at,
        data_window_start=created_at,
        data_window_end=created_at,
    )


def _dt(day: int) -> datetime:
    return datetime(2026, 1, day, tzinfo=timezone.utc)
