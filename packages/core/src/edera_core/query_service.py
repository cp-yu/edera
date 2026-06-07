from __future__ import annotations

import grpc

from edera_core.service_common import (
    advice_payload,
    briefing_metadata,
    briefing_payload,
    event_payload,
    json_response,
    limit,
    metadata_bar,
    parse_datetime,
    source_map_from_store,
    summary_item,
)
from edera_core.storage.repository import (
    analyses_for_advice,
    event_evidence_details,
    event_records_for_advices,
    get_advice,
    get_briefing,
    latest_briefing,
    list_advices,
    list_briefings,
    list_event_records,
    node_runs_for_run,
    node_run_for_run_node,
    query_log_index,
    query_node_output_entities,
    raw_items_for_analyses,
    recent_dag_runs,
    source_execution_logs,
    source_health_summary,
    get_dag_config,
)


class _QueryService:
    def __init__(self, daemon) -> None:
        self.daemon = daemon
        self.pb2 = daemon.pb2

    async def LatestBriefing(self, request, context):
        async with self.daemon.controller._factory()() as session:
            briefing = await latest_briefing(session)
        return json_response(self.pb2, {"briefing": briefing_payload(briefing) if briefing else None})

    async def ListBriefings(self, request, context):
        async with self.daemon.controller._factory()() as session:
            briefings = await list_briefings(session, parse_datetime(request.created_from), parse_datetime(request.created_to), limit(request.limit))
        return json_response(self.pb2, {"briefings": [briefing_payload(briefing) for briefing in briefings]})

    async def GetBriefing(self, request, context):
        async with self.daemon.controller._factory()() as session:
            briefing = await get_briefing(session, request.name)
        if briefing is None:
            await context.abort(grpc.StatusCode.NOT_FOUND, "briefing not found")
        return json_response(self.pb2, {"briefing": briefing_payload(briefing)})

    async def ListAdvices(self, request, context):
        async with self.daemon.controller._factory()() as session:
            advices = await list_advices(
                session,
                limit(request.limit),
                request.stock_code or None,
                request.direction or None,
                parse_datetime(request.created_from),
                parse_datetime(request.created_to),
            )
        return json_response(self.pb2, {"advices": [advice_payload(advice) for advice in advices]})

    async def GetAdvice(self, request, context):
        async with self.daemon.controller._factory()() as session:
            advice = await get_advice(session, request.name)
            if advice is None:
                await context.abort(grpc.StatusCode.NOT_FOUND, "advice not found")
            analyses = await analyses_for_advice(session, advice)
            raw_items = await raw_items_for_analyses(session, analyses)
            related_events = await event_records_for_advices(session, [advice])
            event_details = await event_evidence_details(session, related_events.get(advice.id, []))
        return json_response(
            self.pb2,
            {
                "advice": advice_payload(advice),
                "analyses": [item.model_dump(mode="json") for item in analyses],
                "raw_items": [item.model_dump(mode="json") for item in raw_items],
                "related_events": [event_payload(event) for event in related_events.get(advice.id, [])],
                "event_details": event_details,
            },
        )

    async def ResultsSummary(self, request, context):
        async with self.daemon.controller._factory()() as session:
            briefing = await latest_briefing(session)
            briefings = await list_briefings(session)
            advices = await list_advices(
                session,
                50,
                request.stock_code or None,
                request.direction or None,
                parse_datetime(request.created_from),
                parse_datetime(request.created_to),
            )
            events = await list_event_records(session, 50, request.stock_code or None)
            event_details = await event_evidence_details(session, events)
        failed_sources = briefing_metadata(briefing).get("failed_sources", {}) if briefing is not None else {}
        if not isinstance(failed_sources, dict):
            failed_sources = {}
        return json_response(
            self.pb2,
            {
                "briefing": briefing_payload(briefing) if briefing else None,
                "metadata_bar": metadata_bar(briefing, failed_sources),
                "briefings": [briefing_payload(item) for item in briefings],
                "advices": [advice_payload(advice) for advice in advices],
                "events": [event_payload(event) for event in events],
                "event_details": event_details,
                "summary_items": [summary_item(advice, bool(failed_sources)) for advice in advices],
                "failed_sources": failed_sources,
            },
        )

    async def SourceHealth(self, request, context):
        async with self.daemon.controller._factory()() as session:
            source_names = list((await source_map_from_store(session, self.daemon.controller.entity_store())).keys())
            health = await source_health_summary(session, source_names)
            logs = await source_execution_logs(session, source_names=source_names)
        return json_response(self.pb2, {"sources": health, "logs": logs})

    async def SourceLogs(self, request, context):
        async with self.daemon.controller._factory()() as session:
            source_names = list((await source_map_from_store(session, self.daemon.controller.entity_store())).keys())
            logs = await source_execution_logs(session, request.source_name or None, limit(request.limit), source_names)
        return json_response(self.pb2, {"logs": logs})

    async def NodeOutputs(self, request, context):
        async with self.daemon.controller._factory()() as session:
            outputs = await query_node_output_entities(
                session,
                run_id=request.run_id or None,
                node_id=request.node_id or None,
                limit=limit(request.limit, 100),
            )
        return json_response(self.pb2, {"outputs": [output.model_dump(mode="json") for output in outputs]})

    async def NodeLogs(self, request, context):
        async with self.daemon.controller._factory()() as session:
            logs = await query_log_index(
                session,
                run_id=request.run_id or None,
                node_id=request.node_id or None,
                limit=limit(request.limit, 100),
            )
        return json_response(self.pb2, {"logs": [item.model_dump(mode="json") for item in logs]})

    async def NodeHistory(self, request, context):
        async with self.daemon.controller._factory()() as session:
            dag_exists = await get_dag_config(session, request.dag_name) is not None
            recent = await recent_dag_runs(session, limit(request.limit), request.dag_name)
            if not dag_exists and not recent:
                await context.abort(grpc.StatusCode.NOT_FOUND, f"dag '{request.dag_name}' not found")
            history = []
            for run in recent:
                runs = [item for item in await node_runs_for_run(session, run.run_id) if item.node_name == request.node_id]
                outputs = await query_node_output_entities(session, run_id=run.run_id, node_id=request.node_id, limit=100)
                logs = await query_log_index(session, run_id=run.run_id, node_id=request.node_id, limit=100)
                for node_run in runs:
                    history.append(
                        {
                            "run": run.model_dump(mode="json"),
                            "node_run": node_run.model_dump(mode="json"),
                            "outputs": [output.model_dump(mode="json") for output in outputs],
                            "logs": [log.model_dump(mode="json") for log in logs],
                        }
                    )
        return json_response(self.pb2, {"history": history})

    async def ChildRunForParent(self, request, context):
        if not request.parent_run_id or not request.parent_node_id:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "parent_run_id and parent_node_id are required")
        async with self.daemon.controller._factory()() as session:
            node_run = await node_run_for_run_node(session, request.parent_run_id, request.parent_node_id)
        metadata = node_run.metadata_ if node_run is not None else {}
        child_run_id = metadata.get("sub_dag_run_id") if isinstance(metadata, dict) else None
        return json_response(self.pb2, {"child_run_id": child_run_id if isinstance(child_run_id, str) else None})
