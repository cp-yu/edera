from datetime import datetime

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from stockimformation.models.entities import (
    Advice,
    AnalysisResult,
    Briefing,
    NodeRun,
    PipelineRun,
    RawItem,
    utc_now,
)


async def add_raw_item(session: AsyncSession, item: RawItem) -> RawItem | None:
    existing = await session.exec(select(RawItem).where(RawItem.url == item.url))
    if existing.first() is not None:
        return None
    session.add(item)
    await session.flush()
    return item


async def url_exists(session: AsyncSession, url: str) -> bool:
    result = await session.exec(select(RawItem.id).where(RawItem.url == url))
    return result.first() is not None


async def store_cycle_outputs(
    session: AsyncSession,
    raw_items: list[RawItem],
    analyses: list[AnalysisResult],
    advices: list[Advice],
    briefing: Briefing | None,
) -> None:
    url_to_id: dict[str, int] = {}
    for raw_item in raw_items:
        stored = await add_raw_item(session, raw_item)
        if stored is not None and stored.id is not None:
            url_to_id[stored.url] = stored.id
        else:
            existing = await session.exec(select(RawItem).where(RawItem.url == raw_item.url))
            item = existing.first()
            if item and item.id is not None:
                url_to_id[item.url] = item.id
    for analysis in analyses:
        analysis.raw_item_id = url_to_id.get(analysis.source_url, analysis.raw_item_id)
        session.add(analysis)
    for advice in advices:
        session.add(advice)
    if briefing is not None:
        session.add(briefing)


async def create_pipeline_run(
    session: AsyncSession,
    cycle_id: str,
    trigger: str,
    node_names: list[str] | None = None,
) -> PipelineRun:
    run = PipelineRun(cycle_id=cycle_id, trigger=trigger, status="running")
    session.add(run)
    for node_name in node_names or []:
        session.add(NodeRun(cycle_id=cycle_id, node_name=node_name, status="pending"))
    await session.flush()
    return run


async def finish_pipeline_run(
    session: AsyncSession,
    cycle_id: str,
    status: str,
    error: str | None = None,
    ended_at: datetime | None = None,
) -> PipelineRun | None:
    run = await get_pipeline_run(session, cycle_id)
    if run is None:
        return None
    run.status = status
    run.error = error
    run.ended_at = ended_at or utc_now()
    session.add(run)
    await session.flush()
    return run


async def mark_node_run(
    session: AsyncSession,
    cycle_id: str,
    node_name: str,
    status: str,
    error: str | None = None,
) -> NodeRun:
    result = await session.exec(
        select(NodeRun).where(NodeRun.cycle_id == cycle_id, NodeRun.node_name == node_name)
    )
    node_run = result.first()
    now = utc_now()
    if node_run is None:
        node_run = NodeRun(cycle_id=cycle_id, node_name=node_name, status=status)
    node_run.status = status
    node_run.error = error
    if status == "running" and node_run.started_at is None:
        node_run.started_at = now
    if status in {"succeeded", "failed", "skipped", "cancelled"}:
        node_run.ended_at = now
    session.add(node_run)
    await session.flush()
    return node_run


async def get_pipeline_run(session: AsyncSession, cycle_id: str) -> PipelineRun | None:
    result = await session.exec(select(PipelineRun).where(PipelineRun.cycle_id == cycle_id))
    return result.first()


async def current_pipeline_run(session: AsyncSession) -> PipelineRun | None:
    result = await session.exec(
        select(PipelineRun)
        .where(PipelineRun.status == "running")
        .order_by(col(PipelineRun.started_at).desc())
        .limit(1)
    )
    return result.first()


async def recent_pipeline_runs(session: AsyncSession, limit: int = 20) -> list[PipelineRun]:
    result = await session.exec(
        select(PipelineRun).order_by(col(PipelineRun.started_at).desc()).limit(limit)
    )
    return list(result.all())


async def node_runs_for_cycle(session: AsyncSession, cycle_id: str) -> list[NodeRun]:
    result = await session.exec(
        select(NodeRun).where(NodeRun.cycle_id == cycle_id).order_by(col(NodeRun.id))
    )
    return list(result.all())


async def latest_briefing(session: AsyncSession) -> Briefing | None:
    result = await session.exec(select(Briefing).order_by(col(Briefing.created_at).desc()).limit(1))
    return result.first()


async def list_advices(session: AsyncSession, limit: int = 50) -> list[Advice]:
    result = await session.exec(select(Advice).order_by(col(Advice.created_at).desc()).limit(limit))
    return list(result.all())


async def get_advice(session: AsyncSession, advice_id: int) -> Advice | None:
    result = await session.exec(select(Advice).where(Advice.id == advice_id))
    return result.first()


async def analyses_for_advice(session: AsyncSession, advice: Advice) -> list[AnalysisResult]:
    ids = [item for item in advice.evidence if item > 0]
    if ids:
        result = await session.exec(select(AnalysisResult).where(col(AnalysisResult.id).in_(ids)))
        by_id = {item.id: item for item in result.all()}
        return [by_id[item_id] for item_id in ids if item_id in by_id]
    if advice.source_urls:
        result = await session.exec(
            select(AnalysisResult).where(col(AnalysisResult.source_url).in_(advice.source_urls))
        )
        return list(result.all())
    return []


async def raw_items_for_analyses(
    session: AsyncSession,
    analyses: list[AnalysisResult],
) -> list[RawItem]:
    ids = sorted({item.raw_item_id for item in analyses})
    if not ids:
        return []
    result = await session.exec(select(RawItem).where(col(RawItem.id).in_(ids)))
    return list(result.all())
