from __future__ import annotations

import json

import grpc

from edera_core.config.loader import load_dag_configs
from edera_core.pipeline import PipelineRunNotFoundError, RunAlreadyActiveError
from edera_core.service_common import (
    briefing_metadata,
    entity_store,
    json_response,
    repair_task_dir,
    repair_task_payload,
    source_map,
    write_repair_task,
)
from edera_core.storage.repository import (
    latest_briefing,
    save_node_output_entity,
    source_execution_logs,
    source_health_summary,
)


class _PipelineService:
    def __init__(self, daemon) -> None:
        self.daemon = daemon
        self.pb2 = daemon.pb2

    async def Emit(self, request, context):
        payload = json.loads(request.payload_json) if request.payload_json else None
        fired = await self.daemon.controller.emit(
            request.event,
            payload,
            source=request.source or "rpc",
            depth=request.depth,
        )
        return json_response(self.pb2, {"event": request.event, "fired": fired})

    async def Run(self, request, context):
        try:
            fired = await self.daemon.controller.emit("manual:dag:default", source="pipeline-service", depth=0)
        except RunAlreadyActiveError as exc:
            await context.abort(grpc.StatusCode.ALREADY_EXISTS, exc.cycle_id)
        return json_response(self.pb2, {"event": "manual:dag:default", "fired": fired})

    async def Pause(self, request, context):
        self.daemon.controller.pause_scheduler()
        return json_response(self.pb2, await self.daemon.controller.status())

    async def Resume(self, request, context):
        self.daemon.controller.resume_scheduler()
        return json_response(self.pb2, await self.daemon.controller.status())

    async def Stop(self, request, context):
        cycle_id = await self.daemon.controller.stop_current()
        return json_response(self.pb2, {"stopped": cycle_id is not None, "cycle_id": cycle_id})

    async def Status(self, request, context):
        return json_response(self.pb2, await self.daemon.controller.status())

    async def DagStop(self, request, context):
        if request.dag_name not in load_dag_configs(self.daemon.config_dir / "dags"):
            await context.abort(grpc.StatusCode.NOT_FOUND, f"dag '{request.dag_name}' not found")
        cycle_id = await self.daemon.controller.stop_current(request.dag_name, force=request.force)
        return json_response(self.pb2, {"stopped": cycle_id is not None, "cycle_id": cycle_id})

    async def DagRetry(self, request, context):
        if request.dag_name not in load_dag_configs(self.daemon.config_dir / "dags"):
            await context.abort(grpc.StatusCode.NOT_FOUND, f"dag '{request.dag_name}' not found")
        if not request.node_ids:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "node_ids is required")
        payload = json.loads(request.payload_json) if request.payload_json else None
        try:
            result = await self.daemon.controller.retry_node(
                request.dag_name,
                request.cycle_id or None,
                list(request.node_ids),
                request.mode or "single",
                payload,
            )
        except RunAlreadyActiveError as exc:
            await context.abort(grpc.StatusCode.ALREADY_EXISTS, exc.cycle_id)
        except PipelineRunNotFoundError as exc:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(exc))
        except ValueError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return json_response(
            self.pb2,
            {
                "cycle_id": result.cycle_id,
                "retry_of": result.retry_of,
                "node_ids": result.node_ids,
                "mode": result.mode,
                "retry_nodes": result.retry_nodes,
            },
        )

    async def CreateRepairTask(self, request, context):
        source = source_map(entity_store(self.daemon.config_dir)).get(request.name)
        if source is None:
            await context.abort(grpc.StatusCode.NOT_FOUND, "source not found")
        async with self.daemon.controller._factory()() as session:
            health = await source_health_summary(session, [request.name])
            logs = await source_execution_logs(session, request.name, 1)
            briefing = await latest_briefing(session)
            if not health or not health[0].get("escalated") or briefing is None:
                await context.abort(grpc.StatusCode.FAILED_PRECONDITION, "source is not escalated")
            task = repair_task_payload(
                repair_task_dir(self.daemon.config_dir),
                source.model_dump(mode="json"),
                health[0],
                logs[0] if logs else {},
            )
            write_repair_task(task)
            metadata = dict(briefing_metadata(briefing))
            repair_tasks = dict(metadata.get("repair_tasks", {}))
            repair_tasks[request.name] = {"task_id": task["task_id"], "task_path": task["task_path"], "created_at": task["created_at"]}
            metadata["repair_tasks"] = repair_tasks
            payload = briefing.attributes.get("payload")
            attributes = dict(payload) if isinstance(payload, dict) else dict(briefing.attributes)
            attributes["metadata"] = metadata
            await save_node_output_entity(session, briefing.model_copy(update={"attributes": attributes}))
            await session.commit()
        return json_response(
            self.pb2,
            {
                "task_id": task["task_id"],
                "task_path": task["task_path"],
                "source_name": request.name,
                "created_at": task["created_at"],
            },
        )
