from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import yaml
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError

from edera_core.config.editor import ConfigKind, RuntimeConfigEditor
from edera_core.config.entities import EntityStore, validate_permission_overrides
from edera_core.config.loader import (
    load_dag_configs,
    load_entities_config,
    load_entity_relations_config,
    load_entity_type_configs,
    load_node_configs,
    load_skill_configs,
    load_system_config,
)
from edera_core.config.schema import (
    DagConfig,
    EntitiesConfig,
    EntityConfig,
    EntityRelationsConfig,
    EntityTypeConfig,
    NodeConfig,
    SkillConfig,
    entity_ref,
)
from edera_core.errors import ConfigEditError, ConfigError
from edera_core.events import event_bus
from edera_core.storage.repository import (
    analyses_for_advice,
    event_evidence_details,
    event_records_for_advices,
    get_briefing,
    get_advice,
    latest_briefing,
    list_event_records,
    list_advices,
    list_briefings,
    node_runs_for_cycle,
    query_node_output_entities,
    raw_items_for_analyses,
    recent_pipeline_runs,
    save_node_output_entity,
    source_execution_logs,
    source_health_summary,
)
from edera_core.pipeline import PipelineRunNotFoundError, RunAlreadyActiveError
from edera_core.web.deps import config_dir, controller, error_response, grpc_client, handler_registry

router = APIRouter()

INSTANCE_CONFIG_FIELDS = {
    "model",
    "skills",
    "source_names",
    "entities",
    "entity_permissions",
    "timeout_seconds",
    "session_dir",
    "workdir",
    "tools",
    "input_binding",
}




@router.get("/api/briefings/latest")
async def api_latest_briefing(request: Request) -> dict[str, object]:
    async with controller(request)._factory()() as session:
        briefing = await latest_briefing(session)
    return {"briefing": _briefing_payload(briefing) if briefing else None}


@router.get("/api/briefings")
async def api_briefings(
    request: Request,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: int = 50,
) -> dict[str, object]:
    async with controller(request)._factory()() as session:
        briefings = await list_briefings(session, created_from, created_to, _limit(limit))
    return {"briefings": [_briefing_payload(briefing) for briefing in briefings]}


@router.get("/api/briefings/{briefing_id}", response_model=None)
async def api_briefing_detail(
    request: Request,
    briefing_id: str,
) -> JSONResponse | dict[str, object]:
    async with controller(request)._factory()() as session:
        briefing = await get_briefing(session, briefing_id)
    if briefing is None:
        return error_response(404, "not_found", "briefing not found")
    return {"briefing": _briefing_payload(briefing)}


@router.get("/api/advices")
async def api_advices(
    request: Request,
    stock_code: str | None = None,
    direction: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: int = 50,
) -> dict[str, object]:
    async with controller(request)._factory()() as session:
        advices = await list_advices(
            session,
            _limit(limit),
            stock_code,
            direction,
            created_from,
            created_to,
        )
    return {"advices": [_advice_payload(advice) for advice in advices]}


@router.get("/api/advices/{advice_id}", response_model=None)
async def api_advice_detail(request: Request, advice_id: str) -> JSONResponse | dict[str, object]:
    data = await _advice_detail(request, advice_id)
    if data["advice"] is None:
        return error_response(404, "not_found", "advice not found")
    return data


async def _advice_detail(request: Request, advice_id: str) -> dict[str, object]:
    async with controller(request)._factory()() as session:
        advice = await get_advice(session, advice_id)
        if advice is None:
            return {"advice": None, "analyses": [], "raw_items": []}
        analyses = await analyses_for_advice(session, advice)
        raw_items = await raw_items_for_analyses(session, analyses)
        related_events = await event_records_for_advices(session, [advice])
        event_details = await event_evidence_details(
            session, related_events.get(advice.id, [])
        )
    return {
        "advice": _advice_payload(advice),
        "analyses": [item.model_dump(mode="json") for item in analyses],
        "raw_items": [item.model_dump(mode="json") for item in raw_items],
        "related_events": [
            _event_payload(event) for event in related_events.get(advice.id, [])
        ],
        "event_details": event_details,
    }


@router.get("/api/results")
async def api_results(
    request: Request,
    stock_code: str | None = None,
    direction: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> dict[str, object]:
    return await _result_summary(request, stock_code, direction, created_from, created_to)


@router.get("/api/pipeline/status")
async def api_pipeline_status(request: Request) -> dict[str, object]:
    return await controller(request).status()


@router.get("/api/sources/health")
async def api_source_health(request: Request) -> dict[str, object]:
    return await _source_health(request)


@router.get("/api/sources/logs")
async def api_source_logs(
    request: Request,
    source_name: str | None = None,
    limit: int = 50,
) -> dict[str, object]:
    source_names = list(_source_map(_entity_store(config_dir(request))).keys())
    async with controller(request)._factory()() as session:
        logs = await source_execution_logs(session, source_name, _limit(limit), source_names)
    return {"logs": logs}


@router.post("/api/sources/{source_name}/repair-task", response_model=None)
async def api_source_repair_task(
    request: Request,
    source_name: str,
) -> JSONResponse | dict[str, object]:
    source = _source_map(_entity_store(config_dir(request))).get(source_name)
    if source is None:
        return error_response(404, "not_found", "source not found")
    async with controller(request)._factory()() as session:
        health = await source_health_summary(session, [source_name])
        logs = await source_execution_logs(session, source_name, 1)
        briefing = await latest_briefing(session)
        if not health or not health[0].get("escalated") or briefing is None:
            return error_response(400, "source_not_escalated", "source is not escalated")
        task = _repair_task_payload(request, source.model_dump(mode="json"), health[0], logs[0] if logs else {})
        _write_repair_task(task)
        metadata = dict(_briefing_metadata(briefing))
        repair_tasks = dict(metadata.get("repair_tasks", {}))
        repair_tasks[source_name] = {
            "task_id": task["task_id"],
            "task_path": task["task_path"],
            "created_at": task["created_at"],
        }
        metadata["repair_tasks"] = repair_tasks
        payload = briefing.attributes.get("payload")
        attributes = dict(payload) if isinstance(payload, dict) else dict(briefing.attributes)
        attributes["metadata"] = metadata
        await save_node_output_entity(session, EntityConfig(id=briefing.id, type=briefing.type, attributes=attributes))
        await session.commit()
    return {
        "task_id": task["task_id"],
        "task_path": task["task_path"],
        "source_name": source_name,
        "created_at": task["created_at"],
    }


@router.post("/api/pipeline/dag/{dag_name}/run", response_model=None)
async def api_dag_run(request: Request, dag_name: str) -> JSONResponse | dict[str, object]:
    client = grpc_client(request)
    if client is not None:
        try:
            body = await request.json()
        except json.JSONDecodeError:
            body = {}
        payload = body["inputs"] if isinstance(body, dict) and "inputs" in body else body.get("payload") if isinstance(body, dict) and "payload" in body else body
        return await client.dag_trigger(dag_name, payload if payload != {} else None)
    dags = load_dag_configs(config_dir(request) / "dags")
    if dag_name not in dags:
        return error_response(404, "not_found", f"dag '{dag_name}' not found")
    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    if isinstance(body, dict) and "inputs" in body:
        payload = body["inputs"]
    else:
        payload = body.get("payload") if isinstance(body, dict) and "payload" in body else body
    try:
        if payload is None:
            cycle_id = await controller(request).start_run("manual", dag_name)
        else:
            cycle_id = await controller(request).start_run("manual", dag_name, payload)
    except RunAlreadyActiveError as exc:
        return error_response(409, "run_already_active", exc.cycle_id)
    return {"cycle_id": cycle_id}


@router.post("/api/pipeline/dag/{dag_name}/stop", response_model=None)
async def api_dag_stop(request: Request, dag_name: str) -> JSONResponse | dict[str, object]:
    dags = load_dag_configs(config_dir(request) / "dags")
    if dag_name not in dags:
        return error_response(404, "not_found", f"dag '{dag_name}' not found")
    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    force = bool(body.get("force")) if isinstance(body, dict) else False
    cycle_id = await controller(request).stop_current(dag_name, force=force)
    return {"stopped": cycle_id is not None, "cycle_id": cycle_id}


@router.post("/api/pipeline/dag/{dag_name}/retry", response_model=None)
async def api_dag_retry(request: Request, dag_name: str, body: dict[str, object]) -> JSONResponse | dict[str, object]:
    dags = load_dag_configs(config_dir(request) / "dags")
    if dag_name not in dags:
        return error_response(404, "not_found", f"dag '{dag_name}' not found")
    cycle_id = body.get("cycle_id")
    node_ids = body.get("node_ids")
    mode = str(body.get("mode") or "single")
    if cycle_id is not None and (not isinstance(cycle_id, str) or not cycle_id):
        return error_response(400, "config_error", "cycle_id must be a non-empty string")
    if not isinstance(node_ids, list) or not all(isinstance(node_id, str) and node_id for node_id in node_ids):
        return error_response(400, "config_error", "node_ids is required")
    try:
        result = await controller(request).retry_node(dag_name, cycle_id, node_ids, mode, body.get("payload"))
    except RunAlreadyActiveError as exc:
        return error_response(409, "run_already_active", exc.cycle_id)
    except PipelineRunNotFoundError as exc:
        return error_response(404, "not_found", str(exc))
    except ValueError as exc:
        return error_response(400, "config_error", str(exc))
    return {
        "cycle_id": result.cycle_id,
        "retry_of": result.retry_of,
        "node_ids": result.node_ids,
        "mode": result.mode,
        "retry_nodes": result.retry_nodes,
    }


@router.post("/api/node/{node_id}/stop", response_model=None)
async def api_node_stop(request: Request, node_id: str) -> JSONResponse | dict[str, object]:
    client = grpc_client(request)
    if client is not None:
        return await client.node_stop(node_id)
    dag_name = _dag_for_node(config_dir(request), node_id)
    if dag_name is None:
        return error_response(404, "not_found", f"node '{node_id}' not found")
    cycle_id = await controller(request).stop_current(dag_name)
    return {"stopped": cycle_id is not None, "cycle_id": cycle_id, "node_id": node_id}


@router.post("/api/node/{node_id}/resume", response_model=None)
async def api_node_resume(request: Request, node_id: str, body: dict[str, object]) -> JSONResponse | dict[str, object]:
    client = grpc_client(request)
    if client is not None:
        cycle_id = body.get("cycle_id")
        prompt = body.get("prompt")
        return await client.node_resume(node_id, cycle_id if isinstance(cycle_id, str) else None, prompt if isinstance(prompt, str) else "")
    dag_name = _dag_for_node(config_dir(request), node_id)
    if dag_name is None:
        return error_response(404, "not_found", f"node '{node_id}' not found")
    cycle_id = body.get("cycle_id")
    if not isinstance(cycle_id, str) or not cycle_id:
        cycle_id = _latest_sandbox_cycle(load_system_config(config_dir(request) / "system.toml").workspace_root, node_id)
    if not cycle_id:
        return error_response(404, "not_found", f"session sandbox not found for node '{node_id}'")
    prompt = body.get("prompt")
    payload: dict[str, object] = {"resume_session": f"sandbox:{node_id}:{cycle_id}"}
    if isinstance(prompt, str) and prompt:
        payload["prompt"] = prompt
    try:
        retry_cycle_id = await controller(request).resume_node(dag_name, cycle_id, node_id, payload)
    except RunAlreadyActiveError as exc:
        return error_response(409, "run_already_active", exc.cycle_id)
    except PipelineRunNotFoundError as exc:
        return error_response(404, "not_found", str(exc))
    except ValueError as exc:
        return error_response(400, "config_error", str(exc))
    return {"cycle_id": retry_cycle_id, "retry_of": cycle_id, "node_id": node_id, "mode": "cascade"}


@router.get("/api/pipeline/dag/{dag_name}/status", response_model=None)
async def api_dag_status(request: Request, dag_name: str) -> JSONResponse | dict[str, object]:
    client = grpc_client(request)
    if client is not None:
        return await client.dag_status(dag_name)
    dags = load_dag_configs(config_dir(request) / "dags")
    if dag_name not in dags:
        return error_response(404, "not_found", f"dag '{dag_name}' not found")
    return await controller(request).status(dag_name)


@router.get("/api/node/{node_id}/status", response_model=None)
async def api_node_status(request: Request, node_id: str) -> JSONResponse | dict[str, object]:
    client = grpc_client(request)
    if client is not None:
        return await client.node_status(node_id)
    if _dag_for_node(config_dir(request), node_id) is None:
        return error_response(404, "not_found", f"node '{node_id}' not found")
    return {"node_id": node_id, "status": await controller(request).node_status(node_id)}


@router.get("/api/events/node/{node_id}")
async def api_node_events(request: Request, node_id: str) -> StreamingResponse:
    return _event_stream(request, node_id=node_id)


@router.get("/api/events/dag/{dag_name}")
async def api_dag_events(request: Request, dag_name: str) -> StreamingResponse:
    return _event_stream(request, dag_name=dag_name)


def _event_stream(request: Request, node_id: str = "", dag_name: str = "") -> StreamingResponse:
    client = grpc_client(request)

    async def stream():
        if client is not None:
            async for event in client.subscribe_events(node_id=node_id, dag_name=dag_name):
                yield f"event: {event['type']}\ndata: {json.dumps(event['payload'], ensure_ascii=False)}\n\n"
            return
        async for event in event_bus.subscribe():
            if node_id and event.payload.get("node_id") != node_id:
                continue
            if dag_name and event.payload.get("dag_name") != dag_name:
                continue
            yield f"event: {event.type}\ndata: {json.dumps(event.payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.post("/api/pipeline/run", response_model=None)
async def api_pipeline_run(request: Request) -> JSONResponse | dict[str, object]:
    try:
        cycle_id = await controller(request).start_run("manual")
    except RunAlreadyActiveError as exc:
        return error_response(409, "run_already_active", exc.cycle_id)
    return {"cycle_id": cycle_id}


@router.post("/api/pipeline/pause")
async def api_pipeline_pause(request: Request) -> dict[str, object]:
    controller(request).pause_scheduler()
    return await controller(request).status()


@router.post("/api/pipeline/resume")
async def api_pipeline_resume(request: Request) -> dict[str, object]:
    controller(request).resume_scheduler()
    return await controller(request).status()


@router.post("/api/pipeline/stop")
async def api_pipeline_stop(request: Request) -> dict[str, object]:
    cycle_id = await controller(request).stop_current()
    return {"stopped": cycle_id is not None, "cycle_id": cycle_id}


@router.get("/api/config")
async def api_config_list(request: Request) -> dict[str, object]:
    return {"files": [file.__dict__ for file in _editor(config_dir(request)).list_files()]}


@router.api_route("/api/config/portfolio", methods=["GET", "PUT"], response_model=None)
async def api_removed_config() -> JSONResponse:
    return error_response(404, "not_found", "portfolio config is deprecated; use entities")


@router.get("/api/config/entities", response_model=None)
async def api_config_entities_read(request: Request) -> JSONResponse | dict[str, object]:
    path = config_dir(request) / "entities.yaml"
    if not path.exists():
        return error_response(404, "not_found", "entities.yaml not found")
    return {"content": path.read_text(encoding="utf-8")}


@router.post("/api/config/entities", response_model=None)
async def api_config_entities_save(
    request: Request,
    body: dict[str, object],
) -> JSONResponse | dict[str, object]:
    try:
        content = yaml.safe_dump(EntitiesConfig.model_validate(body).model_dump(mode="json"), allow_unicode=True, sort_keys=False)
        saved = _editor(config_dir(request)).save("entities", "entities", content)
        root = config_dir(request)
        entity_types = load_entity_type_configs(root.parent / "schemas" / "entity-types")
        entities = load_entities_config(root / "entities.yaml", entity_types)
        response = _entities_response(entity_types, entities)
        response["file"] = saved.__dict__
        return response
    except (ConfigEditError, ConfigError, ValidationError) as exc:
        return error_response(400, "config_error", str(exc))


@router.get("/api/config/entity-types", response_model=None)
async def api_entity_types_list(request: Request) -> JSONResponse | dict[str, object]:
    try:
        return {"types": _entity_types_payload(load_entity_type_configs(config_dir(request).parent / "schemas" / "entity-types"))}
    except ConfigError as exc:
        return error_response(400, "config_error", str(exc))


@router.post("/api/config/entity-types", response_model=None)
async def api_entity_type_create(request: Request, body: dict[str, object]) -> JSONResponse | dict[str, object]:
    name = str(body.get("name", "")).strip()
    content = body.get("content", "")
    if not name:
        return error_response(400, "config_error", "entity type name is required")
    if not isinstance(content, str):
        return error_response(400, "config_error", "entity type content must be a string")
    path = _entity_type_path(config_dir(request), name)
    if path.exists():
        return error_response(409, "conflict", f"entity type '{name}' already exists")
    try:
        _validate_entity_type_content(content)
        _atomic_write(path, content)
        return {"created": True, "name": name}
    except (ConfigEditError, ValidationError, yaml.YAMLError) as exc:
        return error_response(400, "config_error", str(exc))


@router.get("/api/config/entity-types/{name}", response_model=None)
async def api_entity_type_read(request: Request, name: str) -> JSONResponse | dict[str, object]:
    path = _resolve_entity_type_path(config_dir(request), name)
    if not path.exists():
        return error_response(404, "not_found", f"entity type {name} not found")
    return {"name": name, "content": path.read_text(encoding="utf-8")}


@router.put("/api/config/entity-types/{name}", response_model=None)
async def api_entity_type_update(request: Request, name: str, body: dict[str, object]) -> JSONResponse | dict[str, object]:
    content = body.get("content", "")
    if not isinstance(content, str):
        return error_response(400, "config_error", "entity type content must be a string")
    root = config_dir(request)
    path = _entity_type_path(root, name)
    protected_error = _protected_entity_type_error(root, name)
    if protected_error is not None:
        return protected_error
    if not path.exists():
        return error_response(404, "not_found", f"entity type {name} not found")
    try:
        _validate_entity_type_content(content)
        _atomic_write(path, content)
        return {"updated": True, "name": name}
    except (ConfigEditError, ValidationError, yaml.YAMLError) as exc:
        return error_response(400, "config_error", str(exc))


@router.delete("/api/config/entity-types/{name}", response_model=None)
async def api_entity_type_delete(
    request: Request,
    name: str,
    cascade: bool = False,
) -> JSONResponse | dict[str, object]:
    root = config_dir(request)
    path = _entity_type_path(root, name)
    protected_error = _protected_entity_type_error(root, name)
    if protected_error is not None:
        return protected_error
    if not path.exists():
        return error_response(404, "not_found", f"entity type {name} not found")
    store = _entity_store(root)
    matching = [entity for entity in store.entities.entities if entity.type == name]
    if matching and not cascade:
        return JSONResponse(
            status_code=409,
            content={"error": {"type": "conflict", "message": f"entity type '{name}' has instances"}, "instance_count": len(matching)},
        )
    try:
        removed_refs = {ref for entity in matching for ref in (entity.id, entity_ref(entity, store.entity_types))}
        store.entities.entities = [entity for entity in store.entities.entities if entity.type != name]
        store.relations.relations = [
            relation for relation in store.relations.relations if not any(ref in removed_refs for ref in relation.entities)
        ]
        content = yaml.safe_dump(store.entities.model_dump(mode="json"), allow_unicode=True, sort_keys=False)
        _editor(root).save("entities", "entities", content)
        content = yaml.safe_dump(store.relations.model_dump(mode="json"), allow_unicode=True, sort_keys=False)
        _editor(root).save("entity-relations", "entity-relations", content)
        path.unlink()
        return {"deleted": True, "instances_removed": len(matching)}
    except (ConfigEditError, ConfigError, OSError) as exc:
        return error_response(400, "config_error", str(exc))


@router.get("/api/config/entity-relations", response_model=None)
async def api_config_entity_relations_read(request: Request) -> JSONResponse | dict[str, object]:
    path = config_dir(request) / "entity-relations.yaml"
    if not path.exists():
        return error_response(404, "not_found", "entity-relations.yaml not found")
    return {"content": path.read_text(encoding="utf-8")}


@router.post("/api/config/entity-relations", response_model=None)
async def api_config_entity_relations_save(
    request: Request,
    body: dict[str, object],
) -> JSONResponse | dict[str, object]:
    try:
        content = yaml.safe_dump(EntityRelationsConfig.model_validate(body).model_dump(mode="json"), allow_unicode=True, sort_keys=False)
        saved = _editor(config_dir(request)).save("entity-relations", "entity-relations", content)
        root = config_dir(request)
        entity_types = load_entity_type_configs(root.parent / "schemas" / "entity-types")
        entities = load_entities_config(root / "entities.yaml", entity_types)
        relations = load_entity_relations_config(root / "entity-relations.yaml", entities, entity_types)
        return {
            "file": saved.__dict__,
            "relations": [relation.model_dump(mode="json") for relation in relations.relations],
        }
    except (ConfigEditError, ConfigError, ValidationError) as exc:
        return error_response(400, "config_error", str(exc))


@router.get("/api/entities", response_model=None)
async def api_entities_list(
    request: Request,
    type: str | None = None,
) -> JSONResponse | dict[str, object]:
    try:
        store = _entity_store(config_dir(request))
        entities = EntitiesConfig(
            entities=[entity for entity in store.entities.entities if type is None or entity.type == type]
        )
        return _entities_response(store.entity_types, entities)
    except ConfigError as exc:
        return error_response(400, "config_error", str(exc))


@router.post("/api/entities", response_model=None)
async def api_entity_create(request: Request, body: dict[str, object]) -> JSONResponse | dict[str, object]:
    entity_type = str(body.get("type", ""))
    attributes = body.get("attributes", {})
    if not isinstance(attributes, dict):
        return error_response(400, "config_error", "attributes must be a mapping")
    try:
        store = _entity_store(config_dir(request))
        entity = store.create(entity_type, dict(attributes))
        return {"entity": _entity_payload(store.entity_types, entity)}
    except (ConfigEditError, ConfigError) as exc:
        return error_response(400, "config_error", str(exc))


@router.put("/api/entities/{entity_id}", response_model=None)
async def api_entity_update(
    request: Request,
    entity_id: str,
    body: dict[str, object],
) -> JSONResponse | dict[str, object]:
    attributes = body.get("attributes", {})
    if not isinstance(attributes, dict):
        return error_response(400, "config_error", "attributes must be a mapping")
    try:
        store = _entity_store(config_dir(request))
        current = store.resolve(entity_id)
        entity = store.save(EntityConfig(id=current.id, type=current.type, attributes=dict(attributes)))
        return {"entity": _entity_payload(store.entity_types, entity)}
    except ConfigError as exc:
        status = 404 if str(exc).startswith("Entity not found:") else 400
        return error_response(status, "not_found" if status == 404 else "config_error", str(exc))
    except ConfigEditError as exc:
        return error_response(400, "config_error", str(exc))


@router.delete("/api/entities/{entity_id}", response_model=None)
async def api_entity_delete(request: Request, entity_id: str) -> JSONResponse | dict[str, object]:
    try:
        store = _entity_store(config_dir(request))
        removed = store.delete(entity_id)
        return {"deleted": True, "relations_removed": removed}
    except ConfigError as exc:
        status = 404 if str(exc).startswith("Entity not found:") else 400
        return error_response(status, "not_found" if status == 404 else "config_error", str(exc))
    except ConfigEditError as exc:
        return error_response(400, "config_error", str(exc))


@router.get("/api/entity-relations", response_model=None)
async def api_entity_relations_query(
    request: Request,
    entity: str | None = None,
    relation_type: str | None = Query(default=None, alias="type"),
) -> JSONResponse | dict[str, object]:
    try:
        root = config_dir(request)
        entity_types = load_entity_type_configs(root.parent / "schemas" / "entity-types")
        entities = load_entities_config(root / "entities.yaml", entity_types)
        relations = load_entity_relations_config(root / "entity-relations.yaml", entities, entity_types)
        target_ref = entity_ref(_resolve_entity(entities, entity_types, entity), entity_types) if entity else None
        matched = []
        related_refs: set[str] = set()
        for relation in relations.relations:
            if relation_type is not None and relation.type != relation_type:
                continue
            relation_refs = [_entity_ref_from_any(entities, entity_types, ref) for ref in relation.entities]
            if target_ref is not None and target_ref not in relation_refs:
                continue
            payload = relation.model_dump(mode="json")
            payload["entities"] = relation_refs
            matched.append(payload)
            if target_ref is None:
                continue
            related_refs.update(ref for ref in relation_refs if ref != target_ref)
        related = [
            item
            for item in _entity_list_payload(entity_types, entities)
            if item["ref"] in related_refs
        ]
        return {
            "relations": matched,
            "entities": related,
        }
    except ConfigError as exc:
        return error_response(400, "config_error", str(exc))


@router.get("/api/entity-relations/types", response_model=None)
async def api_entity_relation_types(request: Request) -> JSONResponse | dict[str, object]:
    try:
        store = _entity_store(config_dir(request))
        return {"types": sorted({relation.type for relation in store.relations.relations})}
    except ConfigError as exc:
        return error_response(400, "config_error", str(exc))


@router.post("/api/entity-relations", response_model=None)
async def api_entity_relation_create(request: Request, body: dict[str, object]) -> JSONResponse | dict[str, object]:
    refs = body.get("entities", [])
    relation_type = str(body.get("type", ""))
    metadata = body.get("metadata", {})
    if not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs):
        return error_response(400, "config_error", "entities must be a list of strings")
    if not relation_type:
        return error_response(400, "config_error", "relation type is required")
    if not isinstance(metadata, dict):
        return error_response(400, "config_error", "metadata must be a mapping")
    try:
        store = _entity_store(config_dir(request))
        relation = store.create_relation(refs, relation_type, dict(metadata))
        return {"relation": relation.model_dump(mode="json")}
    except ConfigEditError as exc:
        return error_response(409, "conflict", str(exc))
    except ConfigError as exc:
        return error_response(400, "config_error", str(exc))


@router.delete("/api/entity-relations/{relation_id}", response_model=None)
async def api_entity_relation_delete(request: Request, relation_id: str) -> JSONResponse | dict[str, object]:
    try:
        store = _entity_store(config_dir(request))
        store.delete_relation(relation_id)
        return {"deleted": True}
    except ConfigError as exc:
        status = 404 if str(exc).startswith("Entity relation not found:") else 400
        return error_response(status, "not_found" if status == 404 else "config_error", str(exc))
    except ConfigEditError as exc:
        return error_response(400, "config_error", str(exc))


@router.get("/api/config/system", response_model=None)
async def api_config_system_read(request: Request) -> JSONResponse | dict[str, object]:
    path = config_dir(request) / "system.toml"
    if not path.exists():
        return error_response(404, "not_found", "system.toml not found")
    return {"content": path.read_text(encoding="utf-8")}


@router.put("/api/config/system", response_model=None)
async def api_config_system_save(
    request: Request,
    body: dict[str, str],
) -> JSONResponse | dict[str, object]:
    try:
        saved = _editor(config_dir(request)).save("system", "system", body.get("content", ""))
        return {"file": saved.__dict__, "content": saved.content}
    except ConfigEditError as exc:
        return error_response(400, "config_error", str(exc))


@router.get("/api/config/{kind}/{name:path}", response_model=None)
async def api_config_read(request: Request, kind: str, name: str) -> JSONResponse | dict[str, object]:
    try:
        return {"file": _editor(config_dir(request)).read(_kind(kind), name).__dict__}
    except ConfigEditError as exc:
        return error_response(400, "config_error", str(exc))


@router.put("/api/config/{kind}/{name:path}", response_model=None)
async def api_config_save(
    request: Request,
    kind: str,
    name: str,
    body: dict[str, str],
) -> JSONResponse | dict[str, object]:
    try:
        return {
            "file": _editor(config_dir(request)).save(
                _kind(kind),
                name,
                body.get("content", ""),
            ).__dict__
        }
    except ConfigEditError as exc:
        return error_response(400, "config_error", str(exc))



@router.get("/api/graph/nodes")
async def api_graph_node_prototypes(request: Request) -> dict[str, object]:
    root = config_dir(request)
    nodes = load_node_configs(root / "nodes")
    skills = load_skill_configs(root / "skills")
    entity_types = load_entity_type_configs(root.parent / "schemas" / "entity-types")
    entities = load_entities_config(root / "entities.yaml", entity_types)
    model_names = _available_model_names(nodes)
    return {
        "prototypes": [_node_payload(node, skills, entity_types, entities, model_names) for node in nodes.values()]
    }


@router.get("/api/graph/node-types")
async def api_graph_node_types(request: Request) -> dict[str, object]:
    root = config_dir(request)
    nodes = load_node_configs(root / "nodes")
    skills = load_skill_configs(root / "skills")
    entity_types = load_entity_type_configs(root.parent / "schemas" / "entity-types")
    entities = load_entities_config(root / "entities.yaml", entity_types)
    model_names = _available_model_names(nodes)
    return {"types": [_node_payload(node, skills, entity_types, entities, model_names) for node in nodes.values()]}


@router.get("/api/graph/dag/{name}", response_model=None)
async def api_graph_dag_state(request: Request, name: str) -> JSONResponse | dict[str, object]:
    root = config_dir(request)
    try:
        dag = load_dag_configs(root / "dags")[name]
    except KeyError:
        return error_response(404, "not_found", f"dag {name} not found")
    nodes = load_node_configs(root / "nodes")
    skills = load_skill_configs(root / "skills")
    entity_types = load_entity_type_configs(root.parent / "schemas" / "entity-types")
    entities = load_entities_config(root / "entities.yaml", entity_types)
    relations = load_entity_relations_config(root / "entity-relations.yaml", entities, entity_types)
    model_names = _available_model_names(nodes)
    node_instances = []
    for instance in dag.nodes:
        node_config = nodes.get(instance.type)
        if node_config:
            n = _node_payload(node_config, skills, entity_types, entities, model_names)
            n.update(
                {
                    "id": instance.id,
                    "type_name": instance.type,
                    "alias": instance.alias,
                    "config": instance.config,
                }
            )
            for key, value in instance.config.items():
                if key in INSTANCE_CONFIG_FIELDS | {"parameters"}:
                    n[key] = value
            node_instances.append(n)
        else:
            node_instances.append(
                {
                    "id": instance.id,
                    "name": instance.type,
                    "type": "function",
                    "type_name": instance.type,
                    "input_type": "Any",
                    "output_type": "Any",
                }
            )
    edges = [
        {
            "from": e.from_,
            "to": e.to,
            "fan_out": e.fan_out,
            "fan_in": e.fan_in,
            "optional": e.optional,
            "fan_in_mode": e.fan_in_mode,
        }
        for e in dag.edges
    ]
    return {
        "name": dag.name,
        "inputs": [item.model_dump(mode="json") for item in dag.inputs],
        "nodes": node_instances,
        "edges": edges,
        "ui": dag.ui,
        "entity_types": _entity_types_payload(entity_types),
        "entities": _entity_list_payload(entity_types, entities),
        "entity_relations": [relation.model_dump(mode="json") for relation in relations.relations],
    }


@router.get("/api/graph/dags")
async def api_graph_dags(request: Request) -> dict[str, object]:
    dags = load_dag_configs(config_dir(request) / "dags")
    return {"dags": sorted(dags)}


@router.post("/api/graph/dag", response_model=None)
async def api_graph_dag_create(request: Request, body: dict[str, object]) -> JSONResponse | dict[str, object]:
    name = str(body.get("name") or "").strip()
    if not _valid_dag_name(name):
        return error_response(400, "config_error", "dag name must be kebab-case")
    path = config_dir(request) / "dags" / f"{name}.yaml"
    if path.exists():
        return error_response(409, "conflict", f"dag '{name}' already exists")
    payload = {"name": name, "nodes": [], "edges": [], "ui": {}}
    _atomic_write(path, yaml.safe_dump(payload, allow_unicode=True, sort_keys=False))
    return JSONResponse(status_code=201, content={"dag": payload})


@router.put("/api/graph/dag/{name}", response_model=None)
async def api_graph_dag_save(
    request: Request,
    name: str,
    body: dict[str, object],
) -> JSONResponse | dict[str, object]:
    editor = _editor(config_dir(request))
    try:
        payload = _graph_dag_payload(name, body)
        _validate_graph_entity_permissions(config_dir(request), payload)
        content = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
        saved = editor.save("dag", name, content)
        dag_config = DagConfig.model_validate(yaml.safe_load(saved.content) or {})
        return {
            "file": saved.__dict__,
            "dag": {
                "name": dag_config.name,
                "nodes": [node.model_dump(mode="json") for node in dag_config.nodes],
                "edges": [{"from": e.from_, "to": e.to, "fan_out": e.fan_out, "fan_in": e.fan_in} for e in dag_config.edges],
                "ui": dag_config.ui,
            },
        }
    except (ConfigEditError, ConfigError, KeyError) as exc:
        return error_response(400, "config_error", str(exc))


@router.post("/api/graph/dag/{name}/nodes", response_model=None)
async def api_graph_dag_create_node(
    request: Request,
    name: str,
    body: dict[str, object],
) -> JSONResponse | dict[str, object]:
    dags_dir = config_dir(request) / "dags"
    dags = load_dag_configs(dags_dir)
    if name not in dags:
        return error_response(404, "not_found", f"dag '{name}' not found")
    node_name = str(body.get("name", ""))
    if not node_name:
        return error_response(400, "config_error", "node name is required")
    nodes_dir = config_dir(request) / "nodes"
    node_path = nodes_dir / f"{node_name}.yaml"
    if node_path.exists():
        return error_response(409, "conflict", f"node '{node_name}' already exists")
    editor = _editor(config_dir(request))
    node_payload = _graph_node_payload(node_name, body)
    node_content = yaml.safe_dump(node_payload, allow_unicode=True, sort_keys=False)
    editor.save("node", node_name, node_content)
    dag = dags[name]
    dag_nodes = [node.model_dump(mode="json") for node in dag.nodes] + [
        {"id": uuid4().hex, "type": node_name, "alias": node_name, "config": {}}
    ]
    dag_payload = {
        "name": dag.name,
        "nodes": dag_nodes,
        "edges": [{"from": e.from_, "to": e.to, "fan_out": e.fan_out, "fan_in": e.fan_in} for e in dag.edges],
        "ui": dag.ui,
    }
    dag_content = yaml.safe_dump(
        DagConfig.model_validate(dag_payload).model_dump(by_alias=True, mode="json"),
        allow_unicode=True,
        sort_keys=False,
    )
    editor.save("dag", name, dag_content)
    node_config = NodeConfig.model_validate(node_payload)
    skills = load_skill_configs(config_dir(request) / "skills")
    entity_types = load_entity_type_configs(config_dir(request).parent / "schemas" / "entity-types")
    entities = load_entities_config(config_dir(request) / "entities.yaml", entity_types)
    model_names = _available_model_names(load_node_configs(nodes_dir))
    return {"node": _node_payload(node_config, skills, entity_types, entities, model_names)}


@router.get("/api/graph/node/{name}", response_model=None)
async def api_graph_node_read(request: Request, name: str) -> JSONResponse | dict[str, object]:
    try:
        root = config_dir(request)
        nodes = load_node_configs(root / "nodes")
        skills = load_skill_configs(root / "skills")
        entity_types = load_entity_type_configs(root.parent / "schemas" / "entity-types")
        entities = load_entities_config(root / "entities.yaml", entity_types)
        model_names = _available_model_names(nodes)
        return {"node": _node_payload(nodes[name], skills, entity_types, entities, model_names)}
    except KeyError:
        return error_response(404, "not_found", f"node {name} not found")


@router.put("/api/graph/node/{name}", response_model=None)
async def api_graph_node_save(
    request: Request,
    name: str,
    body: dict[str, object],
) -> JSONResponse | dict[str, object]:
    editor = _editor(config_dir(request))
    try:
        payload = _graph_node_payload(name, body)
        content = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
        saved = editor.save("node", name, content)
        _save_node_assets(config_dir(request).parent, payload, body)
        node_config = NodeConfig.model_validate(yaml.safe_load(saved.content) or {})
        nodes = load_node_configs(config_dir(request) / "nodes")
        skills = load_skill_configs(config_dir(request) / "skills")
        entity_types = load_entity_type_configs(config_dir(request).parent / "schemas" / "entity-types")
        entities = load_entities_config(config_dir(request) / "entities.yaml", entity_types)
        model_names = _available_model_names(nodes)
        return {"file": saved.__dict__, "node": _node_payload(node_config, skills, entity_types, entities, model_names)}
    except (ConfigEditError, KeyError) as exc:
        return error_response(400, "config_error", str(exc))


@router.post("/api/graph/node-types", response_model=None)
async def api_graph_node_type_create(
    request: Request,
    body: dict[str, object],
) -> JSONResponse | dict[str, object]:
    name = str(body.get("name", ""))
    if not name:
        return error_response(400, "config_error", "node type name is required")
    path = config_dir(request) / "nodes" / f"{name}.yaml"
    if path.exists():
        return error_response(409, "conflict", f"node type '{name}' already exists")
    return await api_graph_node_save(request, name, body)


@router.put("/api/graph/node-types/{name}", response_model=None)
async def api_graph_node_type_update(
    request: Request,
    name: str,
    body: dict[str, object],
) -> JSONResponse | dict[str, object]:
    return await api_graph_node_save(request, name, body)


@router.delete("/api/graph/node-types/{name}", response_model=None)
async def api_graph_node_type_delete(request: Request, name: str) -> JSONResponse | dict[str, object]:
    for dag in load_dag_configs(config_dir(request) / "dags").values():
        if any(node.type == name for node in dag.nodes):
            return error_response(409, "conflict", f"node type '{name}' is referenced by DAG '{dag.name}'")
    path = config_dir(request) / "nodes" / f"{name}.yaml"
    if not path.exists():
        return error_response(404, "not_found", f"node type {name} not found")
    node = NodeConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
    path.unlink()
    _delete_node_assets(config_dir(request).parent, node)
    return {"deleted": True}


@router.get("/api/graph/skills")
async def api_graph_skills(request: Request) -> dict[str, object]:
    skills = load_skill_configs(config_dir(request) / "skills")
    return {"skills": [skill.model_dump(mode="json") for skill in skills.values()]}


@router.post("/api/graph/skills", response_model=None)
async def api_graph_skill_create(
    request: Request,
    body: dict[str, object],
) -> JSONResponse | dict[str, object]:
    name = str(body.get("name", ""))
    if not name:
        return error_response(400, "config_error", "skill name is required")
    path = config_dir(request) / "skills" / f"{name}.yaml"
    if path.exists():
        return error_response(409, "conflict", f"skill '{name}' already exists")
    return _save_skill(config_dir(request).parent, path, body)


@router.put("/api/graph/skills/{name}", response_model=None)
async def api_graph_skill_update(
    request: Request,
    name: str,
    body: dict[str, object],
) -> JSONResponse | dict[str, object]:
    return _save_skill(config_dir(request).parent, config_dir(request) / "skills" / f"{name}.yaml", {**body, "name": name})


@router.delete("/api/graph/skills/{name}", response_model=None)
async def api_graph_skill_delete(request: Request, name: str) -> JSONResponse | dict[str, object]:
    path = config_dir(request) / "skills" / f"{name}.yaml"
    if not path.exists():
        return error_response(404, "not_found", f"skill {name} not found")
    skill = SkillConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
    path.unlink()
    (config_dir(request).parent / "extensions" / skill.handler / "handler.py").unlink(missing_ok=True)
    return {"deleted": True}


@router.get("/api/graph/handlers/{name}", response_model=None)
async def api_graph_handler_read(request: Request, name: str) -> JSONResponse | dict[str, object]:
    path = _handler_path(request, name)
    if not path.exists():
        return error_response(404, "not_found", f"handler {name} not found")
    return {"name": name, "code": path.read_text(encoding="utf-8")}


@router.put("/api/graph/handlers/{name}", response_model=None)
async def api_graph_handler_save(request: Request, name: str, body: dict[str, object]) -> JSONResponse | dict[str, object]:
    code = body.get("code", "")
    if not isinstance(code, str):
        return error_response(400, "config_error", "handler code must be a string")
    path = _handler_path(request, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(code, encoding="utf-8")
    return {"name": name, "code": code}


def _handler_path(request: Request, name: str) -> Path:
    registry = handler_registry(request)
    if registry is not None and name in registry:
        return registry[name].path
    return config_dir(request).parent / "extensions" / name / "handler.py"


@router.get("/api/graph/runtime-status")
async def api_graph_runtime_status(request: Request) -> dict[str, object]:
    ctrl = controller(request)
    factory = ctrl._factory()
    async with factory() as session:
        recent = await recent_pipeline_runs(session)
    node_statuses: dict[str, dict[str, object]] = {}
    if recent:
        async with factory() as session:
            for run in recent[:1]:
                node_runs = await node_runs_for_cycle(session, run.cycle_id)
                for nr in node_runs:
                    node_statuses[nr.node_name] = {
                        "status": nr.status,
                        "started_at": nr.started_at.isoformat() if nr.started_at else None,
                        "ended_at": nr.ended_at.isoformat() if nr.ended_at else None,
                        "error": nr.error,
                        "cycle_id": nr.cycle_id,
                    }
    return {"node_statuses": node_statuses}


@router.get("/api/node-outputs")
async def api_node_outputs(
    request: Request,
    node_id: str | None = None,
    cycle_id: str | None = None,
    limit: int = 100,
) -> dict[str, object]:
    async with controller(request)._factory()() as session:
        outputs = await query_node_output_entities(session, cycle_id=cycle_id, node_id=node_id, limit=_limit(limit))
    return {"outputs": [output.model_dump(mode="json") for output in outputs]}


@router.get("/api/history/dag/{dag_name}/nodes/{node_id}", response_model=None)
async def api_node_history(request: Request, dag_name: str, node_id: str, limit: int = 50) -> JSONResponse | dict[str, object]:
    if dag_name not in load_dag_configs(config_dir(request) / "dags"):
        return error_response(404, "not_found", f"dag '{dag_name}' not found")
    async with controller(request)._factory()() as session:
        recent = await recent_pipeline_runs(session, _limit(limit), dag_name)
        history = []
        for run in recent:
            runs = [item for item in await node_runs_for_cycle(session, run.cycle_id) if item.node_name == node_id]
            outputs = await query_node_output_entities(session, cycle_id=run.cycle_id, node_id=node_id, limit=100)
            for node_run in runs:
                history.append(
                    {
                        "run": run.model_dump(mode="json"),
                        "node_run": node_run.model_dump(mode="json"),
                        "outputs": [output.model_dump(mode="json") for output in outputs],
                    }
                )
    return {"history": history}




async def _result_summary(
    request: Request,
    stock_code: str | None = None,
    direction: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> dict[str, Any]:
    async with controller(request)._factory()() as session:
        briefing = await latest_briefing(session)
        briefings = await list_briefings(session)
        advices = await list_advices(session, 50, stock_code, direction, created_from, created_to)
        events = await list_event_records(session, 50, stock_code)
        event_details = await event_evidence_details(session, events)
    failed_sources = {}
    if briefing is not None:
        failed_sources = _briefing_metadata(briefing).get("failed_sources", {})
        if not isinstance(failed_sources, dict):
            failed_sources = {}
    return {
        "briefing": _briefing_payload(briefing) if briefing else None,
        "metadata_bar": _metadata_bar(briefing, failed_sources),
        "briefings": [_briefing_payload(item) for item in briefings],
        "advices": [_advice_payload(advice) for advice in advices],
        "events": [_event_payload(event) for event in events],
        "event_details": event_details,
        "summary_items": [_summary_item(advice, bool(failed_sources)) for advice in advices],
        "failed_sources": failed_sources,
    }


async def _source_health(request: Request) -> dict[str, object]:
    source_names = list(_source_map(_entity_store(config_dir(request))).keys())
    async with controller(request)._factory()() as session:
        health = await source_health_summary(session, source_names)
        logs = await source_execution_logs(session, source_names=source_names)
    return {"sources": health, "logs": logs}


def _entity_store(root: Path) -> EntityStore:
    entity_types = load_entity_type_configs(root.parent / "schemas" / "entity-types")
    entities = load_entities_config(root / "entities.yaml", entity_types)
    relations = load_entity_relations_config(root / "entity-relations.yaml", entities, entity_types)
    return EntityStore(entities, entity_types, relations, root / "entities.yaml")


def _source_map(store: EntityStore) -> dict[str, EntityConfig]:
    return {
        str(entity.attributes.get("name") or entity.id): entity
        for entity in store.entities.entities
        if entity.type in {"rss-source", "web-source", "api-source"}
    }


def _editor(config_path: Path) -> RuntimeConfigEditor:
    return RuntimeConfigEditor(config_path, config_path.parent / "skills")


def _kind(value: str) -> ConfigKind:
    if value not in {"system", "entities", "entity-relations", "node", "dag", "skill"}:
        raise ConfigEditError(f"unsupported config kind: {value}")
    return cast(ConfigKind, value)


def _limit(value: int) -> int:
    return min(max(value, 1), 100)


def _metadata_bar(briefing: Any | None, failed_sources: dict[str, object]) -> dict[str, object]:
    if briefing is None:
        return {
            "cycle_id": "无",
            "created_at": "",
            "window": "无数据窗口",
            "failed_count": 0,
            "degraded": False,
            "disclaimer": "本系统产出仅供学习参考，不构成投资建议。",
        }
    data = _model_payload(briefing)
    data_window = _briefing_metadata(briefing).get("data_window", {})
    if not isinstance(data_window, dict):
        data_window = {}
    start = data_window.get("start", "")
    end = data_window.get("end", "")
    window = f"{start} 至 {end}" if start or end else "无数据窗口"
    return {
        "cycle_id": data.get("cycle_id", ""),
        "created_at": str(data.get("created_at") or ""),
        "window": window,
        "failed_count": len(failed_sources),
        "degraded": bool(failed_sources),
        "disclaimer": "本系统产出仅供学习参考，不构成投资建议。",
    }


def _summary_item(
    advice: Any,
    degraded: bool,
) -> dict[str, object]:
    data = _model_payload(advice)
    direction = str(data.get("direction") or "hold")
    if data.get("low_confidence"):
        state = "low-confidence"
        label = "低置信度"
    else:
        state = direction
        label = {"buy": "买入", "sell": "卖出", "hold": "持有"}.get(direction, direction)
    data.update(
        {
            "state": state,
            "state_class": f"state-{state}",
            "direction_label": label,
            "degraded": degraded,
            "comparison": _empty_comparison(),
        }
    )
    return data


def _advice_payload(advice: Any) -> dict[str, object]:
    data = _model_payload(advice)
    data["id"] = str(data.get("id") or getattr(advice, "id", ""))
    data["comparison"] = _empty_comparison()
    return data


def _briefing_payload(briefing: EntityConfig) -> dict[str, object]:
    data = _model_payload(briefing)
    return {
        "id": str(data.get("id") or briefing.id),
        "cycle_id": str(data.get("cycle_id") or ""),
        "content": str(data.get("content") or ""),
        "metadata": _briefing_metadata(briefing),
        "created_at": str(data.get("created_at") or ""),
    }


def _briefing_metadata(briefing: EntityConfig) -> dict[str, object]:
    metadata = _model_payload(briefing).get("metadata", {})
    return metadata if isinstance(metadata, dict) else {}


def _event_payload(event: Any) -> dict[str, object]:
    if isinstance(event, EntityConfig):
        data = _model_payload(event)
        return {
            "id": data.get("id"),
            "stock_code": data.get("stock_code", ""),
            "title": data.get("title", ""),
            "status": data.get("status", ""),
            "heat_score": data.get("heat_score", 0),
            "heat_score_components": data.get("heat_score_components", {}),
            "contradiction": data.get("contradiction", False),
            "source_names": data.get("source_names", []),
            "evidence_analysis_ids": data.get("evidence_analysis_ids", []),
            "evidence_raw_item_ids": data.get("evidence_raw_item_ids", []),
            "evidence_count": len(data.get("evidence_analysis_ids", [])),
            "source_count": len(data.get("source_names", [])),
            "first_seen_at": data.get("first_seen_at", ""),
            "last_seen_at": data.get("last_seen_at", ""),
        }
    return {
        "id": event.id,
        "stock_code": event.stock_code,
        "title": event.title,
        "status": event.status,
        "heat_score": event.heat_score,
        "heat_score_components": event.heat_score_components,
        "contradiction": event.contradiction,
        "source_names": event.source_names,
        "evidence_analysis_ids": event.evidence_analysis_ids,
        "evidence_raw_item_ids": event.evidence_raw_item_ids,
        "evidence_count": len(event.evidence_analysis_ids),
        "source_count": len(event.source_names),
        "first_seen_at": event.first_seen_at.isoformat() if event.first_seen_at else "",
        "last_seen_at": event.last_seen_at.isoformat() if event.last_seen_at else "",
    }


def _model_payload(value: Any) -> dict[str, object]:
    if isinstance(value, EntityConfig):
        return dict(value.attributes)
    return cast(dict[str, object], value.model_dump(mode="json"))


def _empty_comparison() -> dict[str, object]:
    return {"verdict": "unknown", "verdict_label": "未知"}


def _entity_type_path(root: Path, name: str) -> Path:
    if "/" in name or "\\" in name or name in {"", ".", ".."}:
        raise ConfigEditError("invalid entity type name")
    return root.parent / "schemas" / "entity-types" / f"{name}.yaml"


def _resolve_entity_type_path(root: Path, name: str) -> Path:
    path = _entity_type_path(root, name)
    if path.exists():
        return path
    return root / "schemas" / f"{name}.yaml"


def _entity_type_config(root: Path, name: str) -> EntityTypeConfig | None:
    return load_entity_type_configs(root.parent / "schemas" / "entity-types").get(name)


def _protected_entity_type_error(root: Path, name: str) -> JSONResponse | None:
    try:
        entity_type = _entity_type_config(root, name)
    except ConfigError as exc:
        return error_response(400, "config_error", str(exc))
    if entity_type is not None and entity_type.system_protected:
        return error_response(403, "forbidden", f"entity type '{name}' is system protected")
    return None


def _validate_entity_type_content(content: str) -> None:
    data = yaml.safe_load(content) or {}
    if not isinstance(data, dict):
        raise ConfigEditError("YAML content must be a mapping")
    EntityTypeConfig.model_validate(data)


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as tmp:
            tmp.write(content)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def _valid_dag_name(name: str) -> bool:
    return bool(name) and all(part and part.islower() and part.replace("-", "").isalnum() for part in name.split("-"))


def _dag_edge_payload(edge: object) -> dict[str, object]:
    if not isinstance(edge, dict):
        raise ConfigEditError("dag edge must be a mapping")
    from_node = edge.get("from")
    to_node = edge.get("to")
    if not isinstance(from_node, str) or not isinstance(to_node, str):
        raise ConfigEditError("dag edge requires from and to")
    payload: dict[str, object] = {"from": from_node, "to": to_node}
    if bool(edge.get("fan_out")):
        payload["fan_out"] = True
    if bool(edge.get("fan_in")):
        payload["fan_in"] = True
    mode = edge.get("fan_in_mode")
    if mode in {"barrier", "accumulate", "collect", "stream"}:
        payload["fan_in_mode"] = mode
    return payload


def _graph_dag_payload(name: str, body: dict[str, object]) -> dict[str, object]:
    nodes = body.get("nodes", [])
    edges = body.get("edges", [])
    ui = body.get("ui", {})
    if not isinstance(nodes, list):
        raise ConfigEditError("dag nodes must be a list")
    if not isinstance(edges, list):
        raise ConfigEditError("dag edges must be a list")
    payload: dict[str, object] = {
        "name": name,
        "nodes": [_dag_node_payload(node) for node in nodes],
        "edges": [_dag_edge_payload(edge) for edge in edges],
        "ui": ui if isinstance(ui, dict) else {},
    }
    try:
        return DagConfig.model_validate(payload).model_dump(by_alias=True, mode="json")
    except ValidationError as exc:
        raise ConfigEditError(str(exc)) from exc


def _validate_graph_entity_permissions(config_root: Path, payload: dict[str, object]) -> None:
    entity_types = load_entity_type_configs(config_root.parent / "schemas" / "entity-types")
    nodes = payload.get("nodes", [])
    if not isinstance(nodes, list):
        return
    for node in nodes:
        if not isinstance(node, dict):
            continue
        config = node.get("config")
        if not isinstance(config, dict):
            continue
        permissions = config.get("entity_permissions")
        if isinstance(permissions, dict):
            validate_permission_overrides(entity_types, permissions)


def _graph_node_payload(name: str, body: dict[str, object]) -> dict[str, object]:
    skills = body.get("skills", [])
    if not isinstance(skills, list):
        skills = []
    inferred_type = body.get("type")
    if inferred_type != "function":
        inferred_type = "function"
    payload: dict[str, object] = {
        "name": name,
        "type": inferred_type,
        "role": body.get("role", "processor"),
        "skills": [str(s) for s in skills],
        "handler": body.get("handler", name if inferred_type == "function" else None),
        "system_prompt_file": body.get(
            "system_prompt_file",
            None,
        ),
        "tools": body.get("tools", []),
        "input_type": body.get("input_type", "Any"),
        "output_type": body.get("output_type", "Any"),
        "timeout_seconds": body.get("timeout_seconds"),
        "source_names": body.get("source_names", []),
        "parameters": body.get("parameters", {}),
        "parameters_schema": body.get("parameters_schema", {}),
    }
    try:
        return NodeConfig.model_validate(payload).model_dump(mode="json")
    except ValidationError as exc:
        raise ConfigEditError(str(exc)) from exc


def _dag_node_payload(node: object) -> dict[str, object]:
    if isinstance(node, str):
        return {"id": node, "type": node, "alias": node, "config": {}}
    if not isinstance(node, dict):
        raise ConfigEditError("dag node must be a mapping")
    node_type = node.get("type_name") or node.get("type") or node.get("name")
    node_id = node.get("id", node.get("name"))
    if not isinstance(node_id, str) or not isinstance(node_type, str):
        raise ConfigEditError("dag node requires id and type")
    config = _split_instance_config(node.get("config", {}))
    payload: dict[str, object] = {"id": node_id, "type": node_type}
    alias = node.get("alias")
    if isinstance(alias, str) and alias:
        payload["alias"] = alias
    if isinstance(config, dict):
        payload["config"] = config
    else:
        payload["config"] = {}
    return payload


def _dag_for_node(root: Path, node_id: str) -> str | None:
    for dag in load_dag_configs(root / "dags").values():
        if any(instance.id == node_id or instance.alias == node_id for instance in dag.nodes):
            return dag.name
    return None


def _latest_sandbox_cycle(workspace_root: Path, node_id: str) -> str | None:
    node_dir = workspace_root / "sandbox" / node_id
    if not node_dir.exists():
        return None
    candidates = [item for item in node_dir.iterdir() if item.is_dir()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime).name


def _node_payload(
    node: NodeConfig,
    skills: dict[str, SkillConfig] | None = None,
    entity_types: dict[str, EntityTypeConfig] | None = None,
    entities: EntitiesConfig | None = None,
    model_names: list[str] | None = None,
) -> dict[str, object]:
    payload = node.model_dump(mode="json")
    if skills is not None and entity_types is not None and entities is not None:
        payload["inspector_schema"] = _build_inspector_schema(
            node,
            skills,
            entity_types,
            entities,
            model_names or [],
        )
    return payload


def _build_inspector_schema(
    node: NodeConfig,
    skills: dict[str, SkillConfig],
    entity_types: dict[str, EntityTypeConfig],
    entities: EntitiesConfig,
    model_names: list[str],
) -> dict[str, object]:
    properties: dict[str, object] = {}
    if node.type == "function" and node.role == "source":
        properties["entities"] = {
            "type": "array",
            "items": {
                "type": "string",
                "enum": sorted(entity_ref(entity, entity_types) for entity in entities.entities if entity.type in {"rss-source", "web-source", "api-source"}),
            },
            "default": [_source_ref_for_name(entities, entity_types, name) for name in node.source_names],
        }
    properties["entity_permissions"] = {
        "type": "object",
        "properties": {
            name: {
                "type": "object",
                "properties": {
                    field: {"type": "string", "enum": ["none", "read-only", "write-only", "read-write"]}
                    for field in entity_type.field_permissions
                },
            }
            for name, entity_type in entity_types.items()
        },
        "default": {},
    }
    properties["timeout_seconds"] = {
        "type": "number",
        "default": node.timeout_seconds,
    }
    properties["model"] = {"type": "string", "default": None, "enum": model_names}
    properties["session_dir"] = {"type": "string", "default": None}
    properties["tools"] = {
        "type": "array",
        "items": {"type": "string", "enum": ["bash", "read", "edit", "write", "grep", "find"]},
        "default": node.tools,
    }
    for key, value in node.parameters_schema.get("properties", {}).items():
        if isinstance(value, dict):
            properties[f"param.{key}"] = value
    return {"type": "object", "properties": properties}


def _entities_response(
    entity_types: dict[str, EntityTypeConfig],
    entities: EntitiesConfig,
) -> dict[str, object]:
    return {
        "entity_types": _entity_types_payload(entity_types),
        "entities": _entity_list_payload(entity_types, entities),
    }


def _entity_payload(
    entity_types: dict[str, EntityTypeConfig],
    entity: EntityConfig,
) -> dict[str, object]:
    item = entity.model_dump(mode="json")
    item["ref"] = entity_ref(entity, entity_types)
    item["display"] = _render_entity_display(entity, entity_types[entity.type])
    return item


def _entity_types_payload(entity_types: dict[str, EntityTypeConfig]) -> dict[str, object]:
    return {
        name: entity_type.model_dump(mode="json", by_alias=True)
        for name, entity_type in entity_types.items()
    }


def _entity_list_payload(
    entity_types: dict[str, EntityTypeConfig],
    entities: EntitiesConfig,
) -> list[dict[str, object]]:
    payload = []
    for entity in entities.entities:
        payload.append(_entity_payload(entity_types, entity))
    return payload


def _resolve_entity(
    entities: EntitiesConfig,
    entity_types: dict[str, EntityTypeConfig],
    ref: str,
) -> EntityConfig:
    for entity in entities.entities:
        if ref == entity.id or ref == entity_ref(entity, entity_types):
            return entity
    raise ConfigError(f"Entity not found: {ref}")


def _entity_ref_from_any(
    entities: EntitiesConfig,
    entity_types: dict[str, EntityTypeConfig],
    ref: str,
) -> str:
    return entity_ref(_resolve_entity(entities, entity_types, ref), entity_types)


def _render_entity_display(entity: EntityConfig, entity_type: EntityTypeConfig) -> str:
    try:
        return entity_type.display_template.format(**entity.attributes)
    except KeyError:
        return str(entity.attributes.get(entity_type.business_id_field, entity.id))


def _source_ref_for_name(
    entities: EntitiesConfig,
    entity_types: dict[str, EntityTypeConfig],
    name: str,
) -> str:
    for entity in entities.entities:
        if entity.type in {"rss-source", "web-source", "api-source"} and entity.attributes.get("name") == name:
            return entity_ref(entity, entity_types)
    return name


def _available_model_names(nodes: dict[str, NodeConfig]) -> list[str]:
    models: set[str] = set()
    model_file = Path.home() / ".pi" / "agent" / "models.json"
    if model_file.exists():
        try:
            data = json.loads(model_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = None
        models.update(_extract_model_names(data))
    return sorted(models)


def _extract_model_names(data: object) -> set[str]:
    if isinstance(data, list):
        return {
            str(item.get("id") or item.get("name"))
            for item in data
            if isinstance(item, dict) and (item.get("id") or item.get("name"))
        }
    if isinstance(data, dict):
        if isinstance(data.get("models"), list):
            return _extract_model_names(data["models"])
        return {
            str(key)
            for key, value in data.items()
            if isinstance(key, str) and value is not None
        }
    return set()


def _split_instance_config(raw: object) -> dict[str, object]:
    if not isinstance(raw, dict):
        return {}
    payload: dict[str, object] = {}
    parameters = dict(raw.get("parameters", {})) if isinstance(raw.get("parameters"), dict) else {}
    for key, value in raw.items():
        if key == "parameters":
            continue
        if key.startswith("param."):
            if value is not None:
                parameters[key.removeprefix("param.")] = value
            continue
        payload[key] = value
    if parameters:
        payload["parameters"] = parameters
    return payload


def _save_node_assets(root: Path, payload: dict[str, object], body: dict[str, object]) -> None:
    node_type = payload.get("type")
    if node_type == "function":
        handler = payload.get("handler")
        code = body.get("handler_code", body.get("code"))
        if isinstance(handler, str) and isinstance(code, str):
            path = root / "extensions" / handler / "handler.py"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(code, encoding="utf-8")


def _delete_node_assets(root: Path, node: NodeConfig) -> None:
    if node.type == "function" and node.handler:
        (root / "extensions" / node.handler / "handler.py").unlink(missing_ok=True)


def _save_skill(root: Path, path: Path, body: dict[str, object]) -> dict[str, object]:
    raw_handler = body.get("handler", body.get("name"))
    code = body.get("handler_code", body.get("code"))
    handler = body.get("name") if isinstance(raw_handler, str) and "\n" in raw_handler else raw_handler
    if not isinstance(code, str) and isinstance(raw_handler, str) and "\n" in raw_handler:
        code = raw_handler
    payload = SkillConfig.model_validate(
        {
            "name": body.get("name"),
            "description": body.get("description", ""),
            "handler": handler,
            "parameters_schema": body.get("parameters_schema", {}),
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    if isinstance(code, str):
        handler_path = root / "extensions" / payload.handler / "handler.py"
        handler_path.parent.mkdir(parents=True, exist_ok=True)
        handler_path.write_text(code, encoding="utf-8")
    return {"skill": payload.model_dump(mode="json")}


def _repair_task_payload(
    request: Request,
    source_config: dict[str, object],
    health: dict[str, object],
    log: dict[str, object],
) -> dict[str, object]:
    now = datetime.now().astimezone().isoformat()
    task_id = f"{health['source_name']}-{uuid4().hex[:12]}"
    task_path = _repair_task_dir(request) / f"{task_id}.json"
    return {
        "task_id": task_id,
        "task_path": str(task_path),
        "source_name": health["source_name"],
        "created_at": now,
        "source_config": source_config,
        "failure_context": {
            "cycle_id": health.get("cycle_id"),
            "latest_failure_reason": health.get("latest_failure_reason"),
            "node_error": log.get("error"),
            "pipeline_status": log.get("pipeline_status"),
        },
        "recovery_summary": {
            "recovery_status": health.get("recovery_status"),
            "attempt_count": health.get("attempt_count"),
            "recoverable_reason": health.get("recoverable_reason"),
            "escalation_reason": health.get("escalation_reason"),
        },
        "expected_fix": "Update only this source configuration or parser so the next pipeline cycle succeeds.",
    }


def _repair_task_dir(request: Request) -> Path:
    config_path = config_dir(request)
    system_config = load_system_config(config_path / "system.toml")
    return system_config.source_repair_task_output_dir or system_config.workspace_root / "source-repair-tasks"


def _write_repair_task(task: dict[str, object]) -> None:
    path = Path(str(task["task_path"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
