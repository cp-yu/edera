from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Awaitable, Callable

import grpc
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from edera_core.grpc_client import GrpcClient
from edera_core.web.deps import error_response, grpc_client

router = APIRouter()


async def _call(request: Request, invoke: Callable[[GrpcClient], Awaitable[dict[str, object]]]) -> Any:
    client = grpc_client(request)
    if client is None:
        return error_response(503, "grpc_unavailable", "edera-server gRPC client is not configured")
    try:
        return await invoke(client)
    except grpc.aio.AioRpcError as exc:
        return _grpc_error(exc)


def _grpc_error(exc: grpc.aio.AioRpcError) -> JSONResponse:
    code = exc.code()
    status, error_type = {
        grpc.StatusCode.INVALID_ARGUMENT: (400, "config_error"),
        grpc.StatusCode.NOT_FOUND: (404, "not_found"),
        grpc.StatusCode.ALREADY_EXISTS: (409, "conflict"),
        grpc.StatusCode.FAILED_PRECONDITION: (409, "conflict"),
        grpc.StatusCode.PERMISSION_DENIED: (403, "forbidden"),
        grpc.StatusCode.UNAUTHENTICATED: (401, "unauthenticated"),
    }.get(code, (500, "grpc_error"))
    return error_response(status, error_type, exc.details() or code.name)


def _dt(value: datetime | None) -> str:
    return value.isoformat() if value is not None else ""


async def _body(request: Request) -> dict[str, object]:
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


@router.get("/api/briefings/latest")
async def api_latest_briefing(request: Request) -> Any:
    return await _call(request, lambda client: client.query_latest_briefing())


@router.get("/api/briefings")
async def api_briefings(request: Request, created_from: datetime | None = None, created_to: datetime | None = None, limit: int = 50) -> Any:
    return await _call(request, lambda client: client.query_list_briefings(_dt(created_from), _dt(created_to), limit))


@router.get("/api/briefings/{briefing_id}", response_model=None)
async def api_briefing_detail(request: Request, briefing_id: str) -> Any:
    return await _call(request, lambda client: client.query_get_briefing(briefing_id))


@router.get("/api/advices")
async def api_advices(
    request: Request,
    stock_code: str | None = None,
    direction: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: int = 50,
) -> Any:
    return await _call(request, lambda client: client.query_list_advices(stock_code or "", direction or "", _dt(created_from), _dt(created_to), limit))


@router.get("/api/advices/{advice_id}", response_model=None)
async def api_advice_detail(request: Request, advice_id: str) -> Any:
    return await _call(request, lambda client: client.query_get_advice(advice_id))


@router.get("/api/results")
async def api_results(
    request: Request,
    stock_code: str | None = None,
    direction: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> Any:
    return await _call(request, lambda client: client.query_results_summary(stock_code or "", direction or "", _dt(created_from), _dt(created_to)))


@router.get("/api/system/scheduler-status")
async def api_scheduler_status(request: Request) -> Any:
    return await _call(request, lambda client: client.system_scheduler_status())


@router.get("/api/extensions/available")
async def api_extensions_available(request: Request) -> Any:
    return await _call(request, lambda client: client.extension_list_available())


@router.get("/api/extensions/installed")
async def api_extensions_installed(request: Request) -> Any:
    return await _call(request, lambda client: client.extension_list_installed())


@router.get("/api/extensions/{name}", response_model=None)
async def api_extension_show(request: Request, name: str) -> Any:
    return await _call(request, lambda client: client.extension_show(name))


@router.post("/api/extensions/{name}/install", response_model=None)
async def api_extension_install(request: Request, name: str) -> Any:
    return await _call(request, lambda client: client.extension_install(name))


@router.post("/api/extensions/{name}/uninstall", response_model=None)
async def api_extension_uninstall(request: Request, name: str, body: dict[str, object]) -> Any:
    strategy = body.get("strategy")
    if not isinstance(strategy, str):
        return error_response(400, "invalid_request", "strategy is required")
    return await _call(request, lambda client: client.extension_uninstall(name, strategy))


@router.get("/api/sources/health")
async def api_source_health(request: Request) -> Any:
    return await _call(request, lambda client: client.query_source_health())


@router.get("/api/sources/logs")
async def api_source_logs(request: Request, source_name: str | None = None, limit: int = 50) -> Any:
    return await _call(request, lambda client: client.query_source_logs(source_name or "", limit))


@router.post("/api/sources/{source_name}/repair-task", response_model=None)
async def api_source_repair_task(request: Request, source_name: str) -> Any:
    return await _call(request, lambda client: client.system_create_repair_task(source_name))


@router.post("/api/dags/{dag_name}/run", response_model=None)
async def api_dag_run(request: Request, dag_name: str) -> Any:
    body = await _body(request)
    payload = body["inputs"] if "inputs" in body else body.get("payload") if "payload" in body else body
    source_shared_inputs = body.get("sourceSharedInputs")
    node_inputs = body.get("nodeInputs")
    append_nodes = body.get("appendNodes")
    temp_keys = {"sourceSharedInputs", "nodeInputs", "appendNodes"}
    payload = {key: value for key, value in payload.items() if key not in temp_keys} if isinstance(payload, dict) else payload
    return await _call(
        request,
        lambda client: client.dag_run(
            dag_name,
            payload if payload != {} else None,
            source_shared_inputs=source_shared_inputs,
            node_inputs=node_inputs if isinstance(node_inputs, dict) else None,
            append_nodes=append_nodes if isinstance(append_nodes, list) else None,
        ),
    )


@router.post("/api/events/emit", response_model=None)
async def api_event_emit(request: Request, body: dict[str, object]) -> Any:
    event = body.get("event")
    if not isinstance(event, str) or not event:
        return error_response(400, "invalid_request", "event is required")
    source = body.get("source")
    depth = body.get("depth")
    return await _call(
        request,
        lambda client: client.event_emit(
            event,
            body.get("payload"),
            source=source if isinstance(source, str) and source else "web",
            depth=depth if isinstance(depth, int) else 0,
        ),
    )


@router.post("/api/dags/{dag_name}/stop", response_model=None)
async def api_dag_stop(request: Request, dag_name: str) -> Any:
    body = await _body(request)
    return await _call(request, lambda client: client.dag_stop(dag_name, bool(body.get("force"))))


@router.post("/api/dags/{dag_name}/retry", response_model=None)
async def api_dag_retry(request: Request, dag_name: str, body: dict[str, object]) -> Any:
    run_id = body.get("run_id")
    node_ids = body.get("node_ids")
    mode = body.get("mode")
    payload = body.get("payload")
    source_shared_inputs = body.get("sourceSharedInputs")
    node_inputs = body.get("nodeInputs")
    append_nodes = body.get("appendNodes")
    return await _call(
        request,
        lambda client: client.dag_retry(
            dag_name,
            run_id if isinstance(run_id, str) else "",
            [node_id for node_id in node_ids if isinstance(node_id, str)] if isinstance(node_ids, list) else [],
            mode if isinstance(mode, str) else "single",
            payload,
            source_shared_inputs=source_shared_inputs,
            node_inputs=node_inputs if isinstance(node_inputs, dict) else None,
            append_nodes=append_nodes if isinstance(append_nodes, list) else None,
        ),
    )


@router.post("/api/node/{node_id}/stop", response_model=None)
async def api_node_stop(request: Request, node_id: str) -> Any:
    return await _call(request, lambda client: client.node_stop(node_id))


@router.post("/api/node/{node_id}/resume", response_model=None)
async def api_node_resume(request: Request, node_id: str, body: dict[str, object]) -> Any:
    run_id = body.get("run_id")
    prompt = body.get("prompt")
    return await _call(request, lambda client: client.node_resume(node_id, run_id if isinstance(run_id, str) else None, prompt if isinstance(prompt, str) else ""))


@router.get("/api/dags/{dag_name}/status", response_model=None)
async def api_dag_status(request: Request, dag_name: str) -> Any:
    return await _call(request, lambda client: client.dag_status(dag_name))


@router.get("/api/node/{node_id}/status", response_model=None)
async def api_node_status(request: Request, node_id: str) -> Any:
    return await _call(request, lambda client: client.node_status(node_id))


@router.get("/api/events/node/{node_id}")
async def api_node_events(request: Request, node_id: str) -> StreamingResponse:
    return _event_stream(request, node_id=node_id)


@router.get("/api/events/dag/{dag_name}")
async def api_dag_events(request: Request, dag_name: str) -> StreamingResponse:
    return _event_stream(request, dag_name=dag_name)


def _event_stream(request: Request, node_id: str = "", dag_name: str = "") -> StreamingResponse:
    client = grpc_client(request)

    async def stream():
        if client is None:
            yield "event: error\ndata: {\"message\":\"edera-server gRPC client is not configured\"}\n\n"
            return
        async for event in client.subscribe_events(node_id=node_id, dag_name=dag_name):
            yield f"event: {event['type']}\ndata: {json.dumps(event['payload'], ensure_ascii=False)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.post("/api/system/pause-scheduler")
async def api_system_pause_scheduler(request: Request) -> Any:
    return await _call(request, lambda client: client.system_pause_scheduler())


@router.post("/api/system/resume-scheduler")
async def api_system_resume_scheduler(request: Request) -> Any:
    return await _call(request, lambda client: client.system_resume_scheduler())


@router.get("/api/config")
async def api_config_list(request: Request) -> Any:
    return await _call(request, lambda client: client.config_list())


@router.api_route("/api/config/portfolio", methods=["GET", "PUT"], response_model=None)
async def api_removed_config() -> JSONResponse:
    return error_response(404, "not_found", "portfolio config is deprecated; use entities")


@router.get("/api/config/entities", response_model=None)
async def api_config_entities_read(request: Request) -> Any:
    return await _call(request, lambda client: client.config_read_entities())


@router.post("/api/config/entities", response_model=None)
async def api_config_entities_save(request: Request, body: dict[str, object]) -> Any:
    return await _call(request, lambda client: client.config_save_entities(body))


@router.get("/api/config/entity-types", response_model=None)
async def api_entity_types_list(request: Request) -> Any:
    return await _call(request, lambda client: client.config_list_entity_types())


@router.post("/api/config/entity-types", response_model=None)
async def api_entity_type_create(request: Request, body: dict[str, object]) -> Any:
    name = str(body.get("name", "")).strip()
    content = body.get("content", "")
    return await _call(request, lambda client: client.config_create_entity_type(name, content if isinstance(content, str) else ""))


@router.get("/api/config/entity-types/{name}", response_model=None)
async def api_entity_type_read(request: Request, name: str) -> Any:
    return await _call(request, lambda client: client.config_get_entity_type(name))


@router.put("/api/config/entity-types/{name}", response_model=None)
async def api_entity_type_update(request: Request, name: str, body: dict[str, object]) -> Any:
    content = body.get("content", "")
    return await _call(request, lambda client: client.config_save_entity_type(name, content if isinstance(content, str) else ""))


@router.delete("/api/config/entity-types/{name}", response_model=None)
async def api_entity_type_delete(request: Request, name: str, cascade: bool = False) -> Any:
    return await _call(request, lambda client: client.config_delete_entity_type(name, cascade))


@router.get("/api/config/entity-relations", response_model=None)
async def api_config_entity_relations_read(request: Request) -> Any:
    return await _call(request, lambda client: client.config_read_entity_relations())


@router.post("/api/config/entity-relations", response_model=None)
async def api_config_entity_relations_save(request: Request, body: dict[str, object]) -> Any:
    return await _call(request, lambda client: client.config_save_entity_relations(body))


@router.get("/api/entities", response_model=None)
async def api_entities_list(request: Request, type: str | None = None) -> Any:
    async def _list(client: GrpcClient) -> dict[str, object]:
        return {"entities": await client.entity_list(type)}
    return await _call(request, _list)


@router.post("/api/entities", response_model=None)
async def api_entity_create(request: Request, body: dict[str, object]) -> Any:
    attributes = body.get("attributes", {})
    return await _call(request, lambda client: client.entity_create(str(body.get("type", "")), attributes if isinstance(attributes, dict) else {}))


@router.put("/api/entities/{entity_id}", response_model=None)
async def api_entity_update(request: Request, entity_id: str, body: dict[str, object]) -> Any:
    attributes = body.get("attributes", {})
    if not isinstance(attributes, dict):
        attributes = {}
    async def update(client: GrpcClient) -> dict[str, object]:
        current = await client.entity_get(entity_id)
        merged = dict(current.get("attributes", {})) if isinstance(current.get("attributes"), dict) else {}
        merged.update(attributes)
        result: dict[str, object] = {}
        for field, value in merged.items():
            result = await client.entity_update(entity_id, str(field), value)
        return {"entity": result}
    return await _call(request, update)


@router.delete("/api/entities/{entity_id}", response_model=None)
async def api_entity_delete(request: Request, entity_id: str) -> Any:
    return await _call(request, lambda client: client.entity_delete(entity_id))


@router.get("/api/entity-relations", response_model=None)
async def api_entity_relations_query(request: Request, entity: str | None = None, relation_type: str | None = Query(default=None, alias="type")) -> Any:
    expression = "type=relation"
    if relation_type:
        expression += f" AND relation_type={relation_type}"
    if entity:
        expression += f" AND from={entity}"
    async def _query(client: GrpcClient) -> dict[str, object]:
        items = await client.entity_search(expression, client.identity or "human")
        relations = [{"id": r["id"], "entities": r.get("attributes", {}).get("entities", []), "type": r.get("attributes", {}).get("relation_type", ""), "metadata": r.get("attributes", {}).get("metadata", {})} for r in items if isinstance(r, dict)]
        return {"relations": relations}
    return await _call(request, _query)


@router.get("/api/entity-relations/types", response_model=None)
async def api_entity_relation_types(request: Request) -> Any:
    async def _types(client: GrpcClient) -> dict[str, object]:
        relations = await client.entity_search("type=relation", client.identity or "human")
        types = sorted({str(r.get("attributes", {}).get("relation_type", "")) for r in relations if isinstance(r, dict) and r.get("attributes", {}).get("relation_type")})
        return {"types": types}
    return await _call(request, _types)


@router.post("/api/entity-relations", response_model=None)
async def api_entity_relation_create(request: Request, body: dict[str, object]) -> Any:
    return await _call(request, lambda client: client.config_create_entity_relation(body))


@router.delete("/api/entity-relations/{relation_id}", response_model=None)
async def api_entity_relation_delete(request: Request, relation_id: str) -> Any:
    return await _call(request, lambda client: client.config_delete_entity_relation(relation_id))


@router.get("/api/config/system", response_model=None)
async def api_config_system_read(request: Request) -> Any:
    return await _call(request, lambda client: client.config_read_system())


@router.put("/api/config/system", response_model=None)
async def api_config_system_save(request: Request, body: dict[str, str]) -> Any:
    return await _call(request, lambda client: client.config_save_system(body.get("content", "")))


@router.get("/api/config/{kind}/{name:path}", response_model=None)
async def api_config_read(request: Request, kind: str, name: str) -> Any:
    return await _call(request, lambda client: client.config_read(kind, name))


@router.put("/api/config/{kind}/{name:path}", response_model=None)
async def api_config_save(request: Request, kind: str, name: str, body: dict[str, str]) -> Any:
    return await _call(request, lambda client: client.config_save(kind, name, body.get("content", "")))


@router.get("/api/graph/nodes")
async def api_graph_node_prototypes(request: Request) -> Any:
    return await _call(request, lambda client: client.graph_list_node_types())


@router.get("/api/graph/node-types")
async def api_graph_node_types(request: Request) -> Any:
    return await _call(request, lambda client: client.graph_list_node_types())


@router.get("/api/graph/dag/{name}", response_model=None)
async def api_graph_dag_state(request: Request, name: str) -> Any:
    return await _call(request, lambda client: client.graph_get_dag(name))


@router.get("/api/graph/dags")
async def api_graph_dags(request: Request) -> Any:
    return await _call(request, lambda client: client.graph_list_dags())


@router.post("/api/graph/dag", response_model=None)
async def api_graph_dag_create(request: Request, body: dict[str, object]) -> Any:
    return await _call(request, lambda client: client.graph_create_dag(str(body.get("name") or "").strip()))


@router.put("/api/graph/dag/{name}", response_model=None)
async def api_graph_dag_save(request: Request, name: str, body: dict[str, object]) -> Any:
    return await _call(request, lambda client: client.graph_save_dag(name, body))


@router.post("/api/graph/dag/{name}/nodes", response_model=None)
async def api_graph_dag_create_node(request: Request, name: str, body: dict[str, object]) -> Any:
    return await _call(request, lambda client: client.graph_create_dag_node(name, body))


@router.get("/api/graph/node/{name}", response_model=None)
async def api_graph_node_read(request: Request, name: str) -> Any:
    return await _call(request, lambda client: client.graph_get_node_type(name))


@router.put("/api/graph/node/{name}", response_model=None)
async def api_graph_node_save(request: Request, name: str, body: dict[str, object]) -> Any:
    return await _call(request, lambda client: client.graph_save_node_type(name, body))


@router.post("/api/graph/node-types", response_model=None)
async def api_graph_node_type_create(request: Request, body: dict[str, object]) -> Any:
    return await _call(request, lambda client: client.graph_create_node_type(str(body.get("name", "")), body))


@router.put("/api/graph/node-types/{name}", response_model=None)
async def api_graph_node_type_update(request: Request, name: str, body: dict[str, object]) -> Any:
    return await _call(request, lambda client: client.graph_save_node_type(name, body))


@router.delete("/api/graph/node-types/{name}", response_model=None)
async def api_graph_node_type_delete(request: Request, name: str) -> Any:
    return await _call(request, lambda client: client.graph_delete_node_type(name))


@router.get("/api/graph/skills")
async def api_graph_skills(request: Request) -> Any:
    return await _call(request, lambda client: client.graph_list_skills())


@router.post("/api/graph/skills", response_model=None)
async def api_graph_skill_create(request: Request, body: dict[str, object]) -> Any:
    return await _call(request, lambda client: client.graph_create_skill(body))


@router.put("/api/graph/skills/{name}", response_model=None)
async def api_graph_skill_update(request: Request, name: str, body: dict[str, object]) -> Any:
    return await _call(request, lambda client: client.graph_save_skill(name, body))


@router.delete("/api/graph/skills/{name}", response_model=None)
async def api_graph_skill_delete(request: Request, name: str) -> Any:
    return await _call(request, lambda client: client.graph_delete_skill(name))


@router.get("/api/graph/handlers", response_model=None)
async def api_graph_handler_list(request: Request) -> Any:
    return await _call(request, lambda client: client.graph_list_handlers())


@router.get("/api/graph/handlers/{name}", response_model=None)
async def api_graph_handler_read(request: Request, name: str) -> Any:
    return await _call(request, lambda client: client.graph_get_handler(name))


@router.put("/api/graph/handlers/{name}", response_model=None)
async def api_graph_handler_save(request: Request, name: str, body: dict[str, object]) -> Any:
    code = body.get("code", "")
    return await _call(request, lambda client: client.graph_save_handler(name, code if isinstance(code, str) else ""))


@router.get("/api/graph/runtime-status")
async def api_graph_runtime_status(request: Request, run_id: str | None = None) -> Any:
    return await _call(request, lambda client: client.graph_runtime_status(run_id or ""))


@router.get("/api/node-outputs")
async def api_node_outputs(request: Request, node_id: str | None = None, run_id: str | None = None, limit: int = 100) -> Any:
    return await _call(request, lambda client: client.query_node_outputs(node_id or "", run_id or "", limit))


@router.get("/api/node-logs")
async def api_node_logs(request: Request, node_id: str | None = None, run_id: str | None = None, limit: int = 100) -> Any:
    return await _call(request, lambda client: client.query_node_logs(node_id or "", run_id or "", limit))


@router.get("/api/history/dag/{dag_name}/nodes/{node_id}", response_model=None)
async def api_node_history(request: Request, dag_name: str, node_id: str, limit: int = 50) -> Any:
    return await _call(request, lambda client: client.query_node_history(dag_name, node_id, limit))


@router.get("/api/child-run")
async def api_child_run_for_parent(request: Request, parent_run_id: str, parent_node_id: str) -> Any:
    return await _call(request, lambda client: client.query_child_run_for_parent(parent_run_id, parent_node_id))
