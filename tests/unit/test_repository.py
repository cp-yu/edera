from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlmodel import select

from stockimformation.models.database import create_engine, init_db, session_factory, sqlite_url
from stockimformation.models.entities import NodeRun, PipelineRun, RawItem
from stockimformation.models.repository import (
    add_raw_item,
    create_pipeline_run,
    current_pipeline_run,
    finish_pipeline_run,
    mark_node_run,
    node_runs_for_cycle,
    recent_pipeline_runs,
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
