from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from edera_core.config.schema import EntityConfig
from edera_core.storage.entities import NodeOutputEntity, NodeRun, DagRun, SourceRecovery, utc_now
from edera_core.storage.entities import EdgeInput


async def store_node_output_entities(
    session: AsyncSession,
    run_id: str,
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
            run_id=str(value.get("run_id") or run_id or ""),
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
    run_id: str | None = None,
    node_id: str | None = None,
    tags: list[str] | None = None,
    limit: int = 100,
) -> list[EntityConfig]:
    statement = select(NodeOutputEntity).order_by(col(NodeOutputEntity.created_at).desc()).limit(limit)
    if entity_type is not None:
        statement = statement.where(NodeOutputEntity.type == entity_type)
    if run_id is not None:
        statement = statement.where(NodeOutputEntity.run_id == run_id)
    if node_id is not None:
        statement = statement.where(NodeOutputEntity.node_id == node_id)
    result = await session.exec(statement)
    entities = [node_output_to_entity(item) for item in result.all()]
    if tags is None:
        return entities
    wanted = set(tags)
    return [entity for entity in entities if wanted.issubset(set(_entity_tags(entity)))]


async def save_node_output_entity(session: AsyncSession, entity: EntityConfig) -> EntityConfig:
    result = await session.exec(select(NodeOutputEntity).where(NodeOutputEntity.entity_id == entity.id))
    current = result.first()
    if current is None:
        raise ValueError(f"node output entity not found: {entity.id}")
    if current.type != entity.type:
        raise ValueError(f"node output entity type cannot change: {entity.id}")
    current.run_id = str(entity.attributes.get("run_id") or current.run_id)
    current.node_id = str(entity.attributes.get("node_id") or current.node_id)
    current.session_id = str(entity.attributes["session_id"]) if entity.attributes.get("session_id") is not None else None
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


async def delete_node_outputs_for_nodes(session: AsyncSession, run_id: str, node_ids: set[str]) -> None:
    if not node_ids:
        return
    result = await session.exec(
        select(NodeOutputEntity).where(
            NodeOutputEntity.run_id == run_id,
            col(NodeOutputEntity.node_id).in_(node_ids),
        )
    )
    for output in result.all():
        await session.delete(output)
    await session.flush()


def node_output_to_entity(output: NodeOutputEntity) -> EntityConfig:
    attributes = dict(output.payload)
    attributes.setdefault("id", output.entity_id)
    attributes.update({"run_id": output.run_id, "node_id": output.node_id, "payload": output.payload})
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
        result = await session.exec(select(NodeOutputEntity.run_id).order_by(col(NodeOutputEntity.created_at).desc()))
        run_ids: list[str] = []
        for run_id in result.all():
            if run_id not in run_ids:
                run_ids.append(run_id)
        expired = run_ids[retention_count:]
        if expired:
            result = await session.exec(select(NodeOutputEntity).where(col(NodeOutputEntity.run_id).in_(expired)))
            for output in result.all():
                await session.delete(output)
    await session.flush()


async def create_dag_run(
    session: AsyncSession,
    run_id: str,
    source: str,
    node_names: list[str] | None = None,
    dag_name: str = "default",
    retry_of: str | None = None,
) -> DagRun:
    run = DagRun(run_id=run_id, source=source, status="running", dag_name=dag_name, retry_of=retry_of)
    session.add(run)
    for node_name in node_names or []:
        session.add(NodeRun(run_id=run_id, node_name=node_name, status="pending"))
    await session.flush()
    return run


async def finish_dag_run(
    session: AsyncSession,
    run_id: str,
    status: str,
    error: str | None = None,
    ended_at: datetime | None = None,
) -> DagRun | None:
    run = await get_dag_run(session, run_id)
    if run is None:
        return None
    run.status = status
    run.error = error
    run.ended_at = ended_at or utc_now()
    session.add(run)
    await session.flush()
    return run


async def restart_dag_run(session: AsyncSession, run_id: str) -> DagRun | None:
    run = await get_dag_run(session, run_id)
    if run is None:
        return None
    run.status = "running"
    run.error = None
    run.ended_at = None
    session.add(run)
    await session.flush()
    return run


async def mark_node_run(
    session: AsyncSession,
    run_id: str,
    node_name: str,
    status: str,
    error: str | None = None,
    failure_kind: str | None = None,
    metadata: dict[str, object] | None = None,
) -> NodeRun:
    result = await session.exec(select(NodeRun).where(NodeRun.run_id == run_id, NodeRun.node_name == node_name))
    node_run = result.first()
    now = utc_now()
    if node_run is None:
        node_run = NodeRun(run_id=run_id, node_name=node_name, status=status)
    node_run.status = status
    node_run.error = error
    node_run.failure_kind = failure_kind if status == "failed" else None
    if metadata:
        node_run.metadata_ = {**node_run.metadata_, **metadata}
    if status == "running" and node_run.started_at is None:
        node_run.started_at = now
    if status in {"succeeded", "failed", "skipped", "cancelled"}:
        node_run.ended_at = now
    session.add(node_run)
    await session.flush()
    return node_run


async def upsert_edge_input(
    session: AsyncSession,
    run_id: str,
    from_node_id: str,
    to_node_id: str,
    edge_optional: bool,
    status: str,
    has_payload: bool,
    error_summary: str | None = None,
) -> EdgeInput:
    result = await session.exec(
        select(EdgeInput).where(
            EdgeInput.run_id == run_id,
            EdgeInput.from_node_id == from_node_id,
            EdgeInput.to_node_id == to_node_id,
        )
    )
    edge_input = result.first()
    if edge_input is None:
        edge_input = EdgeInput(
            run_id=run_id,
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            edge_optional=edge_optional,
            status=status,
            has_payload=has_payload,
            error_summary=error_summary,
        )
    else:
        edge_input.edge_optional = edge_optional
        edge_input.status = status
        edge_input.has_payload = has_payload
        edge_input.error_summary = error_summary
    session.add(edge_input)
    await session.flush()
    return edge_input


async def edge_inputs_for_run(session: AsyncSession, run_id: str) -> list[EdgeInput]:
    result = await session.exec(
        select(EdgeInput).where(EdgeInput.run_id == run_id).order_by(col(EdgeInput.id))
    )
    return list(result.all())


async def upsert_source_recovery(
    session: AsyncSession,
    run_id: str,
    node_id: str,
    source_name: str,
    summary: dict[str, object],
) -> SourceRecovery:
    result = await session.exec(
        select(SourceRecovery).where(
            SourceRecovery.run_id == run_id,
            SourceRecovery.node_id == node_id,
            SourceRecovery.source_name == source_name,
        )
    )
    recovery = result.first()
    if recovery is None:
        recovery = SourceRecovery(
            run_id=run_id,
            node_id=node_id,
            source_name=source_name,
            recovery_status=str(summary.get("recovery_status") or "none"),
        )
    recovery.recovery_status = str(summary.get("recovery_status") or recovery.recovery_status)
    recovery.attempt_count = _int_value(summary.get("attempt_count"))
    recovery.recoverable_reason = _optional_str(summary.get("recoverable_reason"))
    recovery.latest_failure_reason = _optional_str(summary.get("latest_failure_reason"))
    recovery.escalated = bool(summary.get("escalated") or recovery.recovery_status == "escalated")
    recovery.escalation_reason = _optional_str(summary.get("escalation_reason"))
    session.add(recovery)
    await session.flush()
    return recovery


async def source_recoveries(
    session: AsyncSession,
    source_name: str | None = None,
    limit: int = 100,
    source_names: list[str] | None = None,
) -> list[SourceRecovery]:
    statement = select(SourceRecovery).order_by(col(SourceRecovery.created_at).desc(), col(SourceRecovery.id).desc()).limit(limit)
    if source_name is not None:
        statement = statement.where(SourceRecovery.source_name == source_name)
    elif source_names is not None:
        statement = statement.where(col(SourceRecovery.source_name).in_(source_names))
    result = await session.exec(statement)
    return list(result.all())


async def get_dag_run(session: AsyncSession, run_id: str) -> DagRun | None:
    result = await session.exec(select(DagRun).where(DagRun.run_id == run_id))
    return result.first()


async def current_dag_run(session: AsyncSession, dag_name: str | None = None) -> DagRun | None:
    statement = (
        select(DagRun)
        .where(DagRun.status == "running")
        .order_by(col(DagRun.started_at).desc())
        .limit(1)
    )
    if dag_name is not None:
        statement = statement.where(DagRun.dag_name == dag_name)
    result = await session.exec(statement)
    return result.first()


async def recent_dag_runs(
    session: AsyncSession,
    limit: int = 20,
    dag_name: str | None = None,
) -> list[DagRun]:
    statement = select(DagRun).order_by(col(DagRun.started_at).desc()).limit(limit)
    if dag_name is not None:
        statement = statement.where(DagRun.dag_name == dag_name)
    result = await session.exec(statement)
    return list(result.all())


async def latest_finished_dag_run(session: AsyncSession, dag_name: str) -> DagRun | None:
    result = await session.exec(
        select(DagRun)
        .where(DagRun.dag_name == dag_name, DagRun.status != "running")
        .order_by(col(DagRun.started_at).desc())
        .limit(1)
    )
    return result.first()


async def node_runs_for_run(session: AsyncSession, run_id: str) -> list[NodeRun]:
    result = await session.exec(select(NodeRun).where(NodeRun.run_id == run_id).order_by(col(NodeRun.id)))
    return list(result.all())


async def node_run_for_run_node(session: AsyncSession, run_id: str, node_name: str) -> NodeRun | None:
    result = await session.exec(select(NodeRun).where(NodeRun.run_id == run_id, NodeRun.node_name == node_name))
    return result.first()


async def source_execution_logs(
    session: AsyncSession,
    source_name: str | None = None,
    limit: int = 50,
    source_names: list[str] | None = None,
) -> list[dict[str, object]]:
    allowed_sources = set(source_names or [])
    if source_name is not None and source_names is not None and source_name not in allowed_sources:
        return []
    recovery_rows = await source_recoveries(session, source_name, limit, source_names)
    logs = [_source_recovery_log_dict(item) for item in recovery_rows]
    if source_name is None and not allowed_sources:
        return logs[:limit]
    statement = (
        select(NodeRun, DagRun)
        .join(DagRun, col(NodeRun.run_id) == col(DagRun.run_id))
        .order_by(col(NodeRun.started_at).desc(), col(NodeRun.id).desc())
        .limit(limit)
    )
    if source_name:
        statement = statement.where(NodeRun.node_name == source_name)
    else:
        statement = statement.where(col(NodeRun.node_name).in_(allowed_sources))
    result = await session.exec(statement)
    logs.extend(_source_log_dict(node, run) for node, run in result.all())
    logs.sort(key=_source_log_time, reverse=True)
    return logs[:limit]


async def source_health_summary(
    session: AsyncSession,
    source_names: list[str],
    window: int = 20,
) -> list[dict[str, object]]:
    summaries = []
    for source_name in source_names:
        recoveries = await source_recoveries(session, source_name, 1)
        latest_recovery = recoveries[0] if recoveries else None
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
        latest_failure_reason = latest_recovery.latest_failure_reason if latest_recovery else None
        if not latest_failure_reason and failed:
            latest_failure_reason = failed.error
        summaries.append({
            "source_name": source_name,
            "latest_status": latest.status if latest else "unknown",
            "run_id": latest.run_id if latest else None,
            "latest_run_at": latest.started_at.isoformat() if latest and latest.started_at else None,
            "success_rate": success_count / len(finished) if finished else None,
            "window_size": len(finished),
            "latest_failure_reason": latest_failure_reason,
            "recovery_status": latest_recovery.recovery_status if latest_recovery else "none",
            "recovery": _source_recovery_dict(latest_recovery) if latest_recovery else None,
        })
    return summaries


async def latest_briefing(session: AsyncSession) -> EntityConfig | None:
    items = await _node_outputs(session, "briefing", 1)
    return items[0] if items else None


async def list_briefings(
    session: AsyncSession,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: int = 50,
) -> list[EntityConfig]:
    return [item for item in await _node_outputs(session, "briefing", limit) if _within_window(_created_at(item), created_from, created_to)]


async def get_briefing(session: AsyncSession, entity_id: str) -> EntityConfig | None:
    return await _node_output_by_entity_id(session, "briefing", entity_id)


async def list_advices(
    session: AsyncSession,
    limit: int = 50,
    stock_code: str | None = None,
    direction: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> list[EntityConfig]:
    items = await _node_outputs(session, "advice", limit)
    return [
        item for item in items
        if (stock_code is None or item.attributes.get("stock_code") == stock_code)
        and (direction is None or item.attributes.get("direction") == direction)
        and _within_window(_created_at(item), created_from, created_to)
    ]


async def get_advice(session: AsyncSession, entity_id: str) -> EntityConfig | None:
    return await _node_output_by_entity_id(session, "advice", entity_id)


async def analyses_for_advice(session: AsyncSession, advice: EntityConfig) -> list[EntityConfig]:
    urls = advice.attributes.get("source_urls")
    if not isinstance(urls, list):
        return []
    analyses = await _node_outputs(session, "analysis")
    wanted = {str(url) for url in urls}
    return [item for item in analyses if str(item.attributes.get("source_url") or "") in wanted]


async def raw_items_for_analyses(session: AsyncSession, analyses: list[EntityConfig]) -> list[EntityConfig]:
    urls = {str(item.attributes.get("source_url") or "") for item in analyses}
    raw_items = await _node_outputs(session, "raw-item")
    return [item for item in raw_items if str(item.attributes.get("url") or "") in urls]


async def list_event_records(session: AsyncSession, limit: int = 50, stock_code: str | None = None) -> list[EntityConfig]:
    return []


async def event_records_for_advices(session: AsyncSession, advices: list[EntityConfig]) -> dict[str, list[EntityConfig]]:
    return {}


async def event_evidence_details(session: AsyncSession, events: list[EntityConfig]) -> dict[str, object]:
    return {}


def _entity_tags(entity: EntityConfig) -> list[str]:
    tags = entity.attributes.get("tags")
    return [str(tag) for tag in tags] if isinstance(tags, list) else []


def _source_log_dict(node: NodeRun, run: DagRun) -> dict[str, object]:
    return {
        "source_name": node.node_name, "run_id": node.run_id, "dag_name": run.dag_name,
        "node_id": node.node_name, "status": node.status, "dag_status": run.status,
        "started_at": node.started_at.isoformat() if node.started_at else None,
        "ended_at": node.ended_at.isoformat() if node.ended_at else None,
        "error": node.error,
    }


def _source_recovery_log_dict(recovery: SourceRecovery) -> dict[str, object]:
    return {
        "source_name": recovery.source_name, "run_id": recovery.run_id, "dag_name": None,
        "node_id": recovery.node_id, "status": "failed" if recovery.escalated else "succeeded",
        "dag_status": None, "started_at": recovery.created_at.isoformat(),
        "ended_at": recovery.created_at.isoformat(), "error": recovery.latest_failure_reason,
        "recovery": _source_recovery_dict(recovery),
    }


def _source_log_time(log: dict[str, object]) -> str:
    return str(log.get("started_at") or log.get("ended_at") or "")


def _source_recovery_dict(recovery: SourceRecovery | None) -> dict[str, object] | None:
    if recovery is None:
        return None
    return {
        "run_id": recovery.run_id, "node_id": recovery.node_id, "source_name": recovery.source_name,
        "recovery_status": recovery.recovery_status, "attempt_count": recovery.attempt_count,
        "recoverable_reason": recovery.recoverable_reason, "latest_failure_reason": recovery.latest_failure_reason,
        "escalated": recovery.escalated, "escalation_reason": recovery.escalation_reason,
        "created_at": recovery.created_at.isoformat(),
    }


def _optional_str(value: object) -> str | None:
    return str(value) if value is not None and str(value) else None


def _int_value(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    return 0


async def _node_outputs(session: AsyncSession, entity_type: str, limit: int = 100) -> list[EntityConfig]:
    statement = (
        select(NodeOutputEntity)
        .where(NodeOutputEntity.type == entity_type)
        .order_by(col(NodeOutputEntity.created_at).desc())
        .limit(limit)
    )
    result = await session.exec(statement)
    return [node_output_to_entity(item) for item in result.all()]


async def _node_output_by_entity_id(session: AsyncSession, entity_type: str, entity_id: str) -> EntityConfig | None:
    result = await session.exec(
        select(NodeOutputEntity).where(NodeOutputEntity.type == entity_type, NodeOutputEntity.entity_id == entity_id)
    )
    output = result.first()
    return node_output_to_entity(output) if output is not None else None


def _created_at(entity: EntityConfig) -> datetime | None:
    value = entity.attributes.get("created_at")
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _within_window(value: datetime | None, created_from: datetime | None, created_to: datetime | None) -> bool:
    if value is None:
        return True
    if created_from is not None and value < created_from:
        return False
    if created_to is not None and value > created_to:
        return False
    return True
