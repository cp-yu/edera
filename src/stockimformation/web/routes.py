from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import yaml
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from stockimformation.config.editor import ConfigKind, EditableFile, RuntimeConfigEditor
from stockimformation.config.loader import (
    load_dag_configs,
    load_node_configs,
    load_portfolio_config,
    load_skill_configs,
    load_system_config,
)
from stockimformation.config.schema import DagConfig, NodeConfig, PortfolioConfig, SkillConfig
from stockimformation.errors import ConfigEditError, ConfigError
from stockimformation.models.repository import (
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
    raw_items_for_analyses,
    recent_pipeline_runs,
    source_execution_logs,
    source_health_summary,
)
from stockimformation.pipeline import RunAlreadyActiveError
from stockimformation.services.price_comparison import PriceComparisonService
from stockimformation.web.deps import config_dir, controller, error_response

router = APIRouter()





@router.get("/api/briefings/latest")
async def api_latest_briefing(request: Request) -> dict[str, object]:
    async with controller(request)._factory()() as session:
        briefing = await latest_briefing(session)
    return {"briefing": briefing.model_dump(mode="json") if briefing else None}


@router.get("/api/briefings")
async def api_briefings(
    request: Request,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: int = 50,
) -> dict[str, object]:
    async with controller(request)._factory()() as session:
        briefings = await list_briefings(session, created_from, created_to, _limit(limit))
    return {"briefings": [briefing.model_dump(mode="json") for briefing in briefings]}


@router.get("/api/briefings/{briefing_id}", response_model=None)
async def api_briefing_detail(
    request: Request,
    briefing_id: int,
) -> JSONResponse | dict[str, object]:
    async with controller(request)._factory()() as session:
        briefing = await get_briefing(session, briefing_id)
    if briefing is None:
        return error_response(404, "not_found", "briefing not found")
    return {"briefing": briefing.model_dump(mode="json")}


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
    comparison = _price_comparison_service(request)
    return {"advices": [_advice_payload(advice, comparison) for advice in advices]}


@router.get("/api/advices/{advice_id}", response_model=None)
async def api_advice_detail(request: Request, advice_id: int) -> JSONResponse | dict[str, object]:
    data = await _advice_detail(request, advice_id)
    if data["advice"] is None:
        return error_response(404, "not_found", "advice not found")
    return data


async def _advice_detail(request: Request, advice_id: int) -> dict[str, object]:
    async with controller(request)._factory()() as session:
        advice = await get_advice(session, advice_id)
        if advice is None:
            return {"advice": None, "analyses": [], "raw_items": []}
        analyses = await analyses_for_advice(session, advice)
        raw_items = await raw_items_for_analyses(session, analyses)
        related_events = await event_records_for_advices(session, [advice])
        event_details = await event_evidence_details(
            session, related_events.get(advice.id or 0, [])
        )
    comparison = _price_comparison_service(request)
    return {
        "advice": _advice_payload(advice, comparison),
        "analyses": [item.model_dump(mode="json") for item in analyses],
        "raw_items": [item.model_dump(mode="json") for item in raw_items],
        "related_events": [
            _event_payload(event) for event in related_events.get(advice.id or 0, [])
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
    async with controller(request)._factory()() as session:
        logs = await source_execution_logs(session, source_name, _limit(limit))
    return {"logs": logs}


@router.post("/api/sources/{source_name}/repair-task", response_model=None)
async def api_source_repair_task(
    request: Request,
    source_name: str,
) -> JSONResponse | dict[str, object]:
    portfolio = load_portfolio_config(config_dir(request) / "portfolio.yaml")
    source = portfolio.source_map().get(source_name)
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
        metadata = dict(briefing.metadata_)
        repair_tasks = dict(metadata.get("repair_tasks", {}))
        repair_tasks[source_name] = {
            "task_id": task["task_id"],
            "task_path": task["task_path"],
            "created_at": task["created_at"],
        }
        metadata["repair_tasks"] = repair_tasks
        briefing.metadata_ = metadata
        session.add(briefing)
        await session.commit()
    return {
        "task_id": task["task_id"],
        "task_path": task["task_path"],
        "source_name": source_name,
        "created_at": task["created_at"],
    }


@router.post("/api/pipeline/dag/{dag_name}/run", response_model=None)
async def api_dag_run(request: Request, dag_name: str) -> JSONResponse | dict[str, object]:
    dags = load_dag_configs(config_dir(request) / "dags")
    if dag_name not in dags:
        return error_response(404, "not_found", f"dag '{dag_name}' not found")
    try:
        cycle_id = await controller(request).start_run("manual", dag_name)
    except RunAlreadyActiveError as exc:
        return error_response(409, "run_already_active", exc.cycle_id)
    return {"cycle_id": cycle_id}


@router.post("/api/pipeline/dag/{dag_name}/stop", response_model=None)
async def api_dag_stop(request: Request, dag_name: str) -> JSONResponse | dict[str, object]:
    dags = load_dag_configs(config_dir(request) / "dags")
    if dag_name not in dags:
        return error_response(404, "not_found", f"dag '{dag_name}' not found")
    cycle_id = await controller(request).stop_current(dag_name)
    return {"stopped": cycle_id is not None, "cycle_id": cycle_id}


@router.get("/api/pipeline/dag/{dag_name}/status", response_model=None)
async def api_dag_status(request: Request, dag_name: str) -> JSONResponse | dict[str, object]:
    dags = load_dag_configs(config_dir(request) / "dags")
    if dag_name not in dags:
        return error_response(404, "not_found", f"dag '{dag_name}' not found")
    return await controller(request).status(dag_name)


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


@router.put("/api/config/portfolio", response_model=None)
async def api_portfolio_save(
    request: Request,
    body: dict[str, object],
) -> JSONResponse | dict[str, object]:
    try:
        file = _save_portfolio(_editor(config_dir(request)), body)
        return {"file": file.__dict__, "portfolio": _portfolio_payload(body)}
    except ConfigEditError as exc:
        return error_response(400, "config_error", str(exc))


@router.get("/api/config/portfolio", response_model=None)
async def api_config_portfolio_read(request: Request) -> JSONResponse | dict[str, object]:
    path = config_dir(request) / "portfolio.yaml"
    if not path.exists():
        return error_response(404, "not_found", "portfolio.yaml not found")
    return {"content": path.read_text(encoding="utf-8")}


@router.get("/api/config/system", response_model=None)
async def api_config_system_read(request: Request) -> JSONResponse | dict[str, object]:
    path = config_dir(request) / "system.toml"
    if not path.exists():
        return error_response(404, "not_found", "system.toml not found")
    return {"content": path.read_text(encoding="utf-8")}


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
    nodes = load_node_configs(config_dir(request) / "nodes")
    return {"prototypes": [_node_payload(node) for node in nodes.values()]}


@router.get("/api/graph/node-types")
async def api_graph_node_types(request: Request) -> dict[str, object]:
    nodes = load_node_configs(config_dir(request) / "nodes")
    return {"types": [_node_payload(node) for node in nodes.values()]}


@router.get("/api/graph/dag/{name}", response_model=None)
async def api_graph_dag_state(request: Request, name: str) -> JSONResponse | dict[str, object]:
    try:
        dag = load_dag_configs(config_dir(request) / "dags")[name]
    except KeyError:
        return error_response(404, "not_found", f"dag {name} not found")
    nodes = load_node_configs(config_dir(request) / "nodes")
    node_instances = []
    for instance in dag.nodes:
        node_config = nodes.get(instance.type)
        if node_config:
            n = _node_payload(node_config)
            n.update(
                {
                    "id": instance.id,
                    "type_name": instance.type,
                    "alias": instance.alias,
                    "config": instance.config,
                }
            )
            for key, value in instance.config.items():
                if key in {"skills", "model", "source_names", "parameters"}:
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
    edges = [{"from": e.from_, "to": e.to, "fan_out": e.fan_out, "fan_in": e.fan_in} for e in dag.edges]
    return {
        "name": dag.name,
        "nodes": node_instances,
        "edges": edges,
        "ui": dag.ui,
    }


@router.put("/api/graph/dag/{name}", response_model=None)
async def api_graph_dag_save(
    request: Request,
    name: str,
    body: dict[str, object],
) -> JSONResponse | dict[str, object]:
    editor = _editor(config_dir(request))
    try:
        payload = _graph_dag_payload(name, body)
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
    except (ConfigEditError, KeyError) as exc:
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
    return {"node": _node_payload(node_config)}


@router.get("/api/graph/node/{name}", response_model=None)
async def api_graph_node_read(request: Request, name: str) -> JSONResponse | dict[str, object]:
    try:
        nodes = load_node_configs(config_dir(request) / "nodes")
        return {"node": _node_payload(nodes[name])}
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
        return {"file": saved.__dict__, "node": _node_payload(node_config)}
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
    (config_dir(request).parent / "skill_handlers" / f"{skill.handler}.py").unlink(missing_ok=True)
    return {"deleted": True}


@router.get("/api/graph/handlers/{name}", response_model=None)
async def api_graph_handler_read(request: Request, name: str) -> JSONResponse | dict[str, object]:
    path = config_dir(request).parent / "handlers" / f"{name}.py"
    if not path.exists():
        return error_response(404, "not_found", f"handler {name} not found")
    return {"name": name, "code": path.read_text(encoding="utf-8")}


@router.put("/api/graph/handlers/{name}", response_model=None)
async def api_graph_handler_save(request: Request, name: str, body: dict[str, object]) -> JSONResponse | dict[str, object]:
    code = body.get("code", "")
    if not isinstance(code, str):
        return error_response(400, "config_error", "handler code must be a string")
    path = config_dir(request).parent / "handlers" / f"{name}.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(code, encoding="utf-8")
    return {"name": name, "code": code}


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
                        "error": nr.error,
                        "cycle_id": nr.cycle_id,
                    }
    return {"node_statuses": node_statuses}




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
        failed_sources = briefing.metadata_.get("failed_sources", {})
    comparison = _price_comparison_service(request)
    return {
        "briefing": briefing.model_dump(mode="json") if briefing else None,
        "metadata_bar": _metadata_bar(briefing, failed_sources),
        "briefings": [item.model_dump(mode="json") for item in briefings],
        "advices": [_advice_payload(advice, comparison) for advice in advices],
        "events": [_event_payload(event) for event in events],
        "event_details": event_details,
        "summary_items": [_summary_item(advice, bool(failed_sources), comparison) for advice in advices],
        "failed_sources": failed_sources,
    }


async def _source_health(request: Request) -> dict[str, object]:
    source_names = [source.name for source in load_portfolio_config(config_dir(request) / "portfolio.yaml").sources]
    async with controller(request)._factory()() as session:
        health = await source_health_summary(session, source_names)
        logs = await source_execution_logs(session)
    return {"sources": health, "logs": logs}


def _editor(config_path: Path) -> RuntimeConfigEditor:
    return RuntimeConfigEditor(config_path, config_path.parent / "skills")


def _kind(value: str) -> ConfigKind:
    if value not in {"system", "portfolio", "node", "dag", "skill"}:
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
    data_window = briefing.metadata_.get("data_window", {})
    start = data_window.get("start", "")
    end = data_window.get("end", "")
    window = f"{start} 至 {end}" if start or end else "无数据窗口"
    return {
        "cycle_id": briefing.cycle_id,
        "created_at": briefing.created_at.isoformat(),
        "window": window,
        "failed_count": len(failed_sources),
        "degraded": bool(failed_sources),
        "disclaimer": "本系统产出仅供学习参考，不构成投资建议。",
    }


def _summary_item(
    advice: Any,
    degraded: bool,
    comparison: PriceComparisonService,
) -> dict[str, object]:
    data = cast(dict[str, object], advice.model_dump(mode="json"))
    if advice.low_confidence:
        state = "low-confidence"
        label = "低置信度"
    else:
        state = advice.direction
        label = {"buy": "买入", "sell": "卖出", "hold": "持有"}[advice.direction]
    data.update(
        {
            "state": state,
            "state_class": f"state-{state}",
            "direction_label": label,
            "degraded": degraded,
            "comparison": comparison.compare(advice),
        }
    )
    return data


def _advice_payload(advice: Any, comparison: PriceComparisonService) -> dict[str, object]:
    data = cast(dict[str, object], advice.model_dump(mode="json"))
    data["comparison"] = comparison.compare(advice)
    return data


def _event_payload(event: Any) -> dict[str, object]:
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


def _price_comparison_service(request: Request) -> PriceComparisonService:
    config_path = config_dir(request)
    try:
        system = load_system_config(config_path / "system.toml")
    except (ConfigError, ValueError):
        return PriceComparisonService.disabled()
    return PriceComparisonService.from_system(system, config_path)


def _save_portfolio(editor: RuntimeConfigEditor, body: object) -> EditableFile:
    payload = _portfolio_payload(body)
    content = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
    return editor.save("portfolio", "portfolio", content)


def _portfolio_payload(body: object) -> dict[str, object]:
    if not isinstance(body, dict):
        raise ConfigEditError("portfolio payload must be a mapping")
    try:
        portfolio = PortfolioConfig.model_validate(body)
    except ValueError as exc:
        raise ConfigEditError(str(exc)) from exc
    source_names = {source.name for source in portfolio.sources}
    missing = sorted(
        {
            source_name
            for target in portfolio.targets
            for source_name in target.sources
            if source_name not in source_names
        }
    )
    if missing:
        raise ConfigEditError(f"target references missing sources: {', '.join(missing)}")
    return portfolio.model_dump(mode="json")



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


def _graph_node_payload(name: str, body: dict[str, object]) -> dict[str, object]:
    skills = body.get("skills", [])
    if not isinstance(skills, list):
        skills = []
    inferred_type = body.get("type")
    if inferred_type not in {"function", "llm"}:
        inferred_type = "llm" if skills or body.get("model") else "function"
    payload: dict[str, object] = {
        "name": name,
        "type": inferred_type,
        "role": body.get("role", "processor"),
        "skills": [str(s) for s in skills],
        "handler": body.get("handler", name if inferred_type == "function" else None),
        "system_prompt_file": body.get(
            "system_prompt_file",
            f"prompts/{name}.md" if inferred_type == "llm" else None,
        ),
        "model": body.get("model"),
        "input_type": body.get("input_type", "Any"),
        "output_type": body.get("output_type", "Any"),
        "timeout_seconds": body.get("timeout_seconds"),
        "source_names": body.get("source_names", []),
        "parameters": body.get("parameters", {}),
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
    config = node.get("config", {})
    payload: dict[str, object] = {"id": node_id, "type": node_type}
    alias = node.get("alias")
    if isinstance(alias, str) and alias:
        payload["alias"] = alias
    if isinstance(config, dict):
        payload["config"] = config
    else:
        payload["config"] = {}
    return payload


def _node_payload(node: NodeConfig) -> dict[str, object]:
    return node.model_dump(mode="json")


def _save_node_assets(root: Path, payload: dict[str, object], body: dict[str, object]) -> None:
    node_type = payload.get("type")
    if node_type == "llm":
        prompt_file = payload.get("system_prompt_file")
        if isinstance(prompt_file, str):
            path = root / prompt_file
            prompt = body.get("system_prompt", body.get("prompt"))
            if isinstance(prompt, str) or not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(prompt if isinstance(prompt, str) else "", encoding="utf-8")
    if node_type == "function":
        handler = payload.get("handler")
        code = body.get("handler_code", body.get("code"))
        if isinstance(handler, str) and isinstance(code, str):
            path = root / "handlers" / f"{handler}.py"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(code, encoding="utf-8")


def _delete_node_assets(root: Path, node: NodeConfig) -> None:
    if node.type == "llm" and node.system_prompt_file:
        (root / node.system_prompt_file).unlink(missing_ok=True)
    if node.type == "function" and node.handler:
        (root / "handlers" / f"{node.handler}.py").unlink(missing_ok=True)


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
        handler_path = root / "skill_handlers" / f"{payload.handler}.py"
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
