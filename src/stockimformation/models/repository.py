from datetime import datetime
from uuid import uuid4

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from stockimformation.models.entities import (
    Advice,
    AnalysisResult,
    Briefing,
    EventRecord,
    NodeOutputEntity,
    NodeRun,
    PipelineRun,
    RawItem,
    utc_now,
)
from stockimformation.config.schema import EntityConfig
from stockimformation.services.event_analysis import (
    apply_contradiction_flags,
    build_event_record,
    rebuild_event_records,
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
    cycle_id: str = "",
) -> None:
    url_to_id: dict[str, int] = {}
    for raw_item in raw_items:
        stored = await add_raw_item(session, raw_item)
        if stored is not None and stored.id is not None:
            url_to_id[stored.url] = stored.id
            raw_item.id = stored.id
        else:
            existing = await session.exec(select(RawItem).where(RawItem.url == raw_item.url))
            item = existing.first()
            if item and item.id is not None:
                url_to_id[item.url] = item.id
                raw_item.id = item.id
    for analysis in analyses:
        analysis.raw_item_id = url_to_id.get(analysis.source_url, analysis.raw_item_id)
        session.add(analysis)
    for advice in advices:
        session.add(advice)
    if briefing is not None:
        session.add(briefing)
    await store_node_output_entities(session, cycle_id, "rss-fetcher", "raw-item", [item.model_dump(mode="json") for item in raw_items])
    await store_node_output_entities(session, cycle_id, "reader", "analysis", [item.model_dump(mode="json") for item in analyses])
    await store_node_output_entities(session, cycle_id, "advisor", "advice", [item.model_dump(mode="json") for item in advices])
    if briefing is not None:
        await store_node_output_entities(session, briefing.cycle_id, "briefing-generator", "briefing", briefing.model_dump(mode="json"))
    await session.flush()
    existing_events = list((await session.exec(select(EventRecord))).all())
    event_upserts = rebuild_event_records(raw_items, analyses, existing_events)
    existing_by_id = {event.id: event for event in existing_events if event.id is not None}
    for upsert in event_upserts:
        apply_contradiction_flags(analyses, upsert)
        if upsert.event_id is not None and upsert.event_id in existing_by_id:
            event = existing_by_id[upsert.event_id]
            if event.status == "archived":
                continue
            event.stock_code = upsert.stock_code
            event.title = upsert.title
            event.normalized_keywords = upsert.normalized_keywords
            event.status = upsert.status
            event.heat_score = upsert.heat_score
            event.heat_score_components = upsert.heat_score_components
            event.contradiction = upsert.contradiction
            event.evidence_analysis_ids = upsert.evidence_analysis_ids
            event.evidence_raw_item_ids = upsert.evidence_raw_item_ids
            event.source_names = upsert.source_names
            event.first_seen_at = upsert.first_seen_at
            event.last_seen_at = upsert.last_seen_at
            event.updated_at = utc_now()
            session.add(event)
            continue
        if upsert.status == "archived":
            continue
        session.add(build_event_record(upsert))
    await session.flush()


async def store_node_output_entities(
    session: AsyncSession,
    cycle_id: str,
    node_id: str,
    entity_type: str,
    payload: object,
    session_id: str | None = None,
) -> list[NodeOutputEntity]:
    values = payload if isinstance(payload, list) else [payload]
    stored: list[NodeOutputEntity] = []
    for value in values:
        if not isinstance(value, dict):
            value = {"value": value}
        url = value.get("url") if isinstance(value.get("url"), str) else None
        if entity_type == "raw-item" and url is not None:
            existing = await session.exec(
                select(NodeOutputEntity).where(
                    NodeOutputEntity.type == "raw-item",
                    NodeOutputEntity.url == url,
                )
            )
            if existing.first() is not None:
                continue
        entity = NodeOutputEntity(
            entity_id=uuid4().hex,
            type=entity_type,
            cycle_id=str(value.get("cycle_id") or cycle_id or ""),
            node_id=node_id,
            payload=dict(value),
            tags=[str(tag) for tag in value.get("tags", [])] if isinstance(value.get("tags"), list) else [],
            session_id=session_id,
            url=url,
        )
        session.add(entity)
        stored.append(entity)
    await session.flush()
    return stored


async def query_node_output_entities(
    session: AsyncSession,
    entity_type: str | None = None,
    cycle_id: str | None = None,
    node_id: str | None = None,
    tags: list[str] | None = None,
    limit: int = 100,
) -> list[EntityConfig]:
    statement = select(NodeOutputEntity).order_by(col(NodeOutputEntity.created_at).desc()).limit(limit)
    if entity_type is not None:
        statement = statement.where(NodeOutputEntity.type == entity_type)
    if cycle_id is not None:
        statement = statement.where(NodeOutputEntity.cycle_id == cycle_id)
    if node_id is not None:
        statement = statement.where(NodeOutputEntity.node_id == node_id)
    result = await session.exec(statement)
    entities = [node_output_to_entity(item) for item in result.all()]
    if tags is None:
        return entities
    wanted = set(tags)
    return [entity for entity in entities if wanted.issubset(set(_entity_tags(entity)))]


async def save_node_output_entity(
    session: AsyncSession,
    entity: EntityConfig,
) -> EntityConfig:
    result = await session.exec(select(NodeOutputEntity).where(NodeOutputEntity.entity_id == entity.id))
    current = result.first()
    if current is None:
        raise ValueError(f"node output entity not found: {entity.id}")
    if current.type != entity.type:
        raise ValueError(f"node output entity type cannot change: {entity.id}")
    current.cycle_id = str(entity.attributes.get("cycle_id") or current.cycle_id)
    current.node_id = str(entity.attributes.get("node_id") or current.node_id)
    current.session_id = (
        str(entity.attributes["session_id"]) if entity.attributes.get("session_id") is not None else None
    )
    current.url = str(entity.attributes["url"]) if entity.attributes.get("url") is not None else None
    payload = entity.attributes.get("payload")
    current.payload = dict(payload) if isinstance(payload, dict) else dict(entity.attributes)
    tags = entity.attributes.get("tags")
    current.tags = [str(tag) for tag in tags] if isinstance(tags, list) else []
    session.add(current)
    await session.flush()
    return node_output_to_entity(current)


async def delete_node_output_entity(session: AsyncSession, entity_id: str) -> bool:
    result = await session.exec(select(NodeOutputEntity).where(NodeOutputEntity.entity_id == entity_id))
    current = result.first()
    if current is None:
        return False
    await session.delete(current)
    await session.flush()
    return True


def node_output_to_entity(output: NodeOutputEntity) -> EntityConfig:
    attributes = dict(output.payload)
    attributes.setdefault("id", output.entity_id)
    attributes.update(
        {
            "cycle_id": output.cycle_id,
            "node_id": output.node_id,
            "payload": output.payload,
        }
    )
    if output.session_id:
        attributes["session_id"] = output.session_id
    return EntityConfig(id=output.entity_id, type=output.type, attributes=attributes)


async def cleanup_node_output_entities(
    session: AsyncSession,
    retention_count: int,
    retention_hours: int,
    now: datetime | None = None,
) -> None:
    current = now or utc_now()
    if retention_hours > 0:
        cutoff = current.timestamp() - retention_hours * 3600
        result = await session.exec(select(NodeOutputEntity))
        for output in result.all():
            if output.created_at.timestamp() < cutoff:
                await session.delete(output)
    if retention_count > 0:
        result = await session.exec(
            select(NodeOutputEntity.cycle_id)
            .order_by(col(NodeOutputEntity.created_at).desc())
        )
        cycles: list[str] = []
        for cycle in result.all():
            if cycle not in cycles:
                cycles.append(cycle)
        expired = cycles[retention_count:]
        if expired:
            result = await session.exec(select(NodeOutputEntity).where(col(NodeOutputEntity.cycle_id).in_(expired)))
            for output in result.all():
                await session.delete(output)
    await session.flush()


def _entity_tags(entity: EntityConfig) -> list[str]:
    tags = entity.attributes.get("tags")
    return [str(tag) for tag in tags] if isinstance(tags, list) else []


async def create_pipeline_run(
    session: AsyncSession,
    cycle_id: str,
    trigger: str,
    node_names: list[str] | None = None,
    dag_name: str = "default",
) -> PipelineRun:
    run = PipelineRun(cycle_id=cycle_id, trigger=trigger, status="running", dag_name=dag_name)
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


async def current_pipeline_run(
    session: AsyncSession, dag_name: str | None = None
) -> PipelineRun | None:
    statement = (
        select(PipelineRun)
        .where(PipelineRun.status == "running")
        .order_by(col(PipelineRun.started_at).desc())
        .limit(1)
    )
    if dag_name is not None:
        statement = statement.where(PipelineRun.dag_name == dag_name)
    result = await session.exec(statement)
    return result.first()


async def recent_pipeline_runs(
    session: AsyncSession, limit: int = 20, dag_name: str | None = None
) -> list[PipelineRun]:
    statement = select(PipelineRun).order_by(col(PipelineRun.started_at).desc()).limit(limit)
    if dag_name is not None:
        statement = statement.where(PipelineRun.dag_name == dag_name)
    result = await session.exec(statement)
    return list(result.all())


async def source_execution_logs(
    session: AsyncSession,
    source_name: str | None = None,
    limit: int = 50,
) -> list[dict[str, object]]:
    statement = (
        select(NodeRun, PipelineRun)
        .join(PipelineRun, col(NodeRun.cycle_id) == col(PipelineRun.cycle_id))
        .order_by(col(NodeRun.started_at).desc(), col(NodeRun.id).desc())
        .limit(limit)
    )
    if source_name:
        statement = statement.where(NodeRun.node_name == source_name)
    result = await session.exec(statement)
    return [_source_log_dict(node, run) for node, run in result.all()]


async def source_health_summary(
    session: AsyncSession,
    source_names: list[str],
    window: int = 20,
) -> list[dict[str, object]]:
    briefing = await latest_briefing(session)
    metadata = briefing.metadata_ if briefing else {}
    failed_sources = metadata.get("failed_sources", {})
    source_recovery = metadata.get("source_recovery", {})
    repair_tasks = metadata.get("repair_tasks", {})
    summaries = []
    for source_name in source_names:
        result = await session.exec(
            select(NodeRun)
            .where(NodeRun.node_name == source_name)
            .order_by(col(NodeRun.started_at).desc(), col(NodeRun.id).desc())
            .limit(window)
        )
        runs = list(result.all())
        finished = [run for run in runs if run.status in {"succeeded", "failed"}]
        success_count = sum(1 for run in finished if run.status == "succeeded")
        latest = runs[0] if runs else None
        failed = next((run for run in runs if run.status == "failed" and run.error), None)
        failure_reason = failed_sources.get(source_name)
        if failure_reason is None and failed is not None:
            failure_reason = failed.error
        recovery = source_recovery.get(source_name, {})
        if not isinstance(recovery, dict):
            recovery = {}
        repair_task = repair_tasks.get(source_name)
        summaries.append(
            {
                "source_name": source_name,
                "latest_status": latest.status if latest else "unknown",
                "cycle_id": latest.cycle_id if latest else briefing.cycle_id if briefing else None,
                "latest_run_at": latest.started_at.isoformat() if latest and latest.started_at else None,
                "success_rate": success_count / len(finished) if finished else None,
                "window_size": len(finished),
                "recovery_status": recovery.get("recovery_status", "none"),
                "attempt_count": recovery.get("attempt_count", 0),
                "recoverable_reason": recovery.get("recoverable_reason"),
                "latest_failure_reason": failure_reason,
                "escalated": bool(recovery.get("escalated")),
                "escalation_reason": recovery.get("escalation_reason"),
                "updated_at": recovery.get("updated_at"),
                "repair_task": repair_task if isinstance(repair_task, dict) else None,
            }
        )
    return summaries


async def node_runs_for_cycle(session: AsyncSession, cycle_id: str) -> list[NodeRun]:
    result = await session.exec(
        select(NodeRun).where(NodeRun.cycle_id == cycle_id).order_by(col(NodeRun.id))
    )
    return list(result.all())


async def latest_briefing(session: AsyncSession) -> Briefing | None:
    result = await session.exec(select(Briefing).order_by(col(Briefing.created_at).desc()).limit(1))
    briefing = result.first()
    if briefing is not None:
        return briefing
    entities = await _node_outputs(session, "briefing", 1)
    return _briefing_from_output(entities[0]) if entities else None


async def list_briefings(
    session: AsyncSession,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: int = 50,
) -> list[Briefing]:
    statement = select(Briefing)
    if created_from is not None:
        statement = statement.where(Briefing.created_at >= created_from)
    if created_to is not None:
        statement = statement.where(Briefing.created_at <= created_to)
    result = await session.exec(statement.order_by(col(Briefing.created_at).desc()).limit(limit))
    briefings = list(result.all())
    if briefings:
        return briefings
    return [
        item
        for item in (_briefing_from_output(output) for output in await _node_outputs(session, "briefing", limit))
        if item is not None and _within_window(item.created_at, created_from, created_to)
    ]


async def get_briefing(session: AsyncSession, briefing_id: int) -> Briefing | None:
    result = await session.exec(select(Briefing).where(Briefing.id == briefing_id))
    briefing = result.first()
    if briefing is not None:
        return briefing
    output = await _node_output_by_row_id(session, "briefing", briefing_id)
    return _briefing_from_output(output) if output is not None else None


async def list_advices(
    session: AsyncSession,
    limit: int = 50,
    stock_code: str | None = None,
    direction: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> list[Advice]:
    statement = select(Advice)
    if stock_code:
        statement = statement.where(Advice.stock_code == stock_code)
    if direction:
        statement = statement.where(Advice.direction == direction)
    if created_from is not None:
        statement = statement.where(Advice.created_at >= created_from)
    if created_to is not None:
        statement = statement.where(Advice.created_at <= created_to)
    result = await session.exec(statement.order_by(col(Advice.created_at).desc()).limit(limit))
    advices = list(result.all())
    if advices:
        return advices
    return [
        item
        for item in (_advice_from_output(output) for output in await _node_outputs(session, "advice", limit))
        if item is not None
        and (stock_code is None or item.stock_code == stock_code)
        and (direction is None or item.direction == direction)
        and _within_window(item.created_at, created_from, created_to)
    ]


async def get_advice(session: AsyncSession, advice_id: int) -> Advice | None:
    result = await session.exec(select(Advice).where(Advice.id == advice_id))
    advice = result.first()
    if advice is not None:
        return advice
    output = await _node_output_by_row_id(session, "advice", advice_id)
    return _advice_from_output(output) if output is not None else None


async def analyses_for_advice(session: AsyncSession, advice: Advice) -> list[AnalysisResult]:
    ids = [item for item in advice.evidence if item > 0]
    if ids:
        result = await session.exec(select(AnalysisResult).where(col(AnalysisResult.id).in_(ids)))
        by_id = {item.id: item for item in result.all()}
        analyses = [by_id[item_id] for item_id in ids if item_id in by_id]
        if analyses:
            return analyses
    if advice.source_urls:
        result = await session.exec(
            select(AnalysisResult).where(col(AnalysisResult.source_url).in_(advice.source_urls))
        )
        analyses = list(result.all())
        if analyses:
            return _order_analyses(analyses, advice.source_urls)
        analyses = [
            item
            for item in (_analysis_from_output(output) for output in await _node_outputs(session, "analysis"))
            if item is not None and item.source_url in advice.source_urls
        ]
        return _order_analyses(analyses, advice.source_urls)
    return []


async def raw_items_for_analyses(
    session: AsyncSession,
    analyses: list[AnalysisResult],
) -> list[RawItem]:
    ids = sorted({item.raw_item_id for item in analyses})
    if not ids:
        return []
    result = await session.exec(select(RawItem).where(col(RawItem.id).in_(ids)))
    raw_items = list(result.all())
    if raw_items:
        return _order_raw_items(raw_items, [item.source_url for item in analyses])
    source_urls = {item.source_url for item in analyses}
    raw_items = [
        item
        for item in (_raw_item_from_output(output) for output in await _node_outputs(session, "raw-item"))
        if item is not None and item.url in source_urls
    ]
    return _order_raw_items(raw_items, [item.source_url for item in analyses])


async def raw_items_for_tag(session: AsyncSession, tag: str) -> list[RawItem]:
    if not tag:
        return []
    result = await session.exec(select(RawItem).order_by(col(RawItem.published_at).desc()))
    return [item for item in result.all() if tag in item.tags]


async def add_event_record(session: AsyncSession, event: EventRecord) -> EventRecord:
    session.add(event)
    await session.flush()
    return event


async def get_event_record(session: AsyncSession, event_id: int) -> EventRecord | None:
    result = await session.exec(select(EventRecord).where(EventRecord.id == event_id))
    return result.first()


async def list_event_records(
    session: AsyncSession,
    limit: int = 50,
    stock_code: str | None = None,
) -> list[EventRecord]:
    statement = select(EventRecord)
    if stock_code:
        statement = statement.where(EventRecord.stock_code == stock_code)
    result = await session.exec(
        statement.order_by(col(EventRecord.last_seen_at).desc(), col(EventRecord.id).desc()).limit(limit)
    )
    return list(result.all())


async def update_event_record(session: AsyncSession, event: EventRecord) -> EventRecord:
    event.updated_at = utc_now()
    session.add(event)
    await session.flush()
    return event


async def events_for_analysis_ids(
    session: AsyncSession,
    analysis_ids: list[int],
) -> list[EventRecord]:
    ids = [item for item in analysis_ids if item > 0]
    if not ids:
        return []
    result = await session.exec(select(EventRecord))
    events = []
    for event in result.all():
        if any(analysis_id in event.evidence_analysis_ids for analysis_id in ids):
            events.append(event)
    return events


async def event_records_for_advices(
    session: AsyncSession,
    advices: list[Advice],
) -> dict[int, list[EventRecord]]:
    mapping: dict[int, list[EventRecord]] = {}
    for advice in advices:
        analyses = await analyses_for_advice(session, advice)
        mapping[advice.id or 0] = await events_for_analysis_ids(session, [item.id for item in analyses if item.id])
    return mapping


async def event_evidence_details(
    session: AsyncSession,
    events: list[EventRecord],
) -> dict[int, dict[str, list[dict[str, object]]]]:
    details: dict[int, dict[str, list[dict[str, object]]]] = {}
    for event in events:
        analyses = await _analyses_for_event(session, event)
        raw_items = await raw_items_for_analyses(session, analyses)
        details[event.id or 0] = {
            "analyses": [item.model_dump(mode="json") for item in analyses],
            "raw_items": [item.model_dump(mode="json") for item in raw_items],
        }
    return details


async def _analyses_for_event(session: AsyncSession, event: EventRecord) -> list[AnalysisResult]:
    ids = [item for item in event.evidence_analysis_ids if item > 0]
    if not ids:
        return []
    result = await session.exec(select(AnalysisResult).where(col(AnalysisResult.id).in_(ids)))
    by_id = {item.id: item for item in result.all()}
    return [by_id[item_id] for item_id in ids if item_id in by_id]


async def _node_outputs(
    session: AsyncSession,
    entity_type: str,
    limit: int = 100,
) -> list[NodeOutputEntity]:
    result = await session.exec(
        select(NodeOutputEntity)
        .where(NodeOutputEntity.type == entity_type)
        .order_by(col(NodeOutputEntity.created_at).desc())
        .limit(limit)
    )
    return list(result.all())


async def _node_output_by_row_id(
    session: AsyncSession,
    entity_type: str,
    row_id: int,
) -> NodeOutputEntity | None:
    result = await session.exec(
        select(NodeOutputEntity).where(NodeOutputEntity.type == entity_type, NodeOutputEntity.id == row_id)
    )
    return result.first()


def _advice_from_output(output: NodeOutputEntity) -> Advice | None:
    try:
        return Advice.model_validate({**output.payload, "id": output.id})
    except ValueError:
        return None


def _briefing_from_output(output: NodeOutputEntity) -> Briefing | None:
    try:
        return Briefing.model_validate(
            {
                **output.payload,
                "id": output.id,
                "cycle_id": output.cycle_id,
                "created_at": output.created_at,
            }
        )
    except ValueError:
        return None


def _analysis_from_output(output: NodeOutputEntity) -> AnalysisResult | None:
    try:
        return AnalysisResult.model_validate({**output.payload, "id": output.id})
    except ValueError:
        return None


def _raw_item_from_output(output: NodeOutputEntity) -> RawItem | None:
    try:
        return RawItem.model_validate({**output.payload, "id": output.id})
    except ValueError:
        return None


def _within_window(
    value: datetime,
    created_from: datetime | None,
    created_to: datetime | None,
) -> bool:
    if created_from is not None and value < created_from:
        return False
    if created_to is not None and value > created_to:
        return False
    return True


def _order_analyses(
    analyses: list[AnalysisResult],
    source_urls: list[str],
) -> list[AnalysisResult]:
    by_url = {item.source_url: item for item in analyses}
    return [by_url[url] for url in source_urls if url in by_url]


def _order_raw_items(
    raw_items: list[RawItem],
    source_urls: list[str],
) -> list[RawItem]:
    by_url = {item.url: item for item in raw_items}
    return [by_url[url] for url in source_urls if url in by_url]


def _source_log_dict(node: NodeRun, run: PipelineRun) -> dict[str, object]:
    return {
        "cycle_id": node.cycle_id,
        "source_name": node.node_name,
        "node_name": node.node_name,
        "node_status": node.status,
        "pipeline_status": run.status,
        "started_at": node.started_at.isoformat() if node.started_at else None,
        "ended_at": node.ended_at.isoformat() if node.ended_at else None,
        "error": node.error,
    }
