from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import yaml
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import ValidationError

from stockimformation.config.editor import ConfigKind, EditableFile, RuntimeConfigEditor
from stockimformation.config.loader import load_dag_configs, load_node_configs, load_portfolio_config, load_system_config
from stockimformation.config.schema import DagConfig, NodeConfig, PortfolioConfig
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
from stockimformation.web.deps import config_dir, controller, error_response, templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates(request).TemplateResponse(
        request,
        "index.html",
        {"active": "home"},
    )


@router.get("/results", response_class=HTMLResponse)
async def results_page(
    request: Request,
    stock_code: str | None = None,
    direction: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> HTMLResponse:
    data = await _result_summary(request, stock_code, direction, created_from, created_to)
    return templates(request).TemplateResponse(
        request,
        "results.html",
        {
            "active": "results",
            "filters": _filters(stock_code, direction, created_from, created_to),
            "auto_refresh": _auto_refresh(data["briefing"]),
            **data,
        },
    )


@router.get("/results/briefings/{briefing_id}", response_class=HTMLResponse)
async def briefing_detail_page(request: Request, briefing_id: int) -> HTMLResponse:
    async with controller(request)._factory()() as session:
        briefing = await get_briefing(session, briefing_id)
    return templates(request).TemplateResponse(
        request,
        "briefing_detail.html",
        {"active": "results", "briefing": briefing},
        status_code=200 if briefing else 404,
    )


@router.get("/results/advices/{advice_id}", response_class=HTMLResponse)
async def advice_detail_page(request: Request, advice_id: int) -> HTMLResponse:
    data = await _advice_detail(request, advice_id)
    return templates(request).TemplateResponse(
        request,
        "advice_detail.html",
        {"active": "results", **data},
        status_code=200 if data["advice"] else 404,
    )


@router.get("/pipeline", response_class=HTMLResponse)
async def pipeline_page(request: Request) -> HTMLResponse:
    return templates(request).TemplateResponse(
        request,
        "pipeline.html",
        {"active": "pipeline", "status": await controller(request).status()},
    )


@router.get("/sources", response_class=HTMLResponse)
async def sources_page(request: Request) -> HTMLResponse:
    data = await _source_health(request)
    return templates(request).TemplateResponse(
        request,
        "sources.html",
        {"active": "sources", **data},
    )


@router.get("/config", response_class=HTMLResponse)
async def config_page(request: Request, kind: str = "system", name: str = "system") -> HTMLResponse:
    editor = _editor(config_dir(request))
    error = None
    try:
        current = editor.read(_kind(kind), name)
    except ConfigEditError as exc:
        current = editor.list_files()[0]
        error = str(exc)
    return templates(request).TemplateResponse(
        request,
        "config.html",
        {
            "active": "config",
            "files": editor.list_files(),
            "current": current,
            "error": error,
            "analysis_tuning": _analysis_tuning(editor.list_files()),
            "dag": _dag_view(config_dir(request), current),
            "portfolio": _portfolio_view(config_dir(request)),
        },
    )


@router.post("/config", response_class=HTMLResponse)
async def save_config(
    request: Request,
    kind: str = Form(),
    name: str = Form(),
    content: str = Form(),
) -> HTMLResponse:
    editor = _editor(config_dir(request))
    error = None
    try:
        current = editor.save(_kind(kind), name, content)
    except ConfigEditError as exc:
        current = editor.read(_kind(kind), name)
        error = str(exc)
    return templates(request).TemplateResponse(
        request,
        "config.html",
        {
            "active": "config",
            "files": editor.list_files(),
            "current": current,
            "error": error,
            "analysis_tuning": _analysis_tuning(editor.list_files()),
            "dag": _dag_view(config_dir(request), current),
            "portfolio": _portfolio_view(config_dir(request)),
        },
    )


@router.post("/config/portfolio", response_class=HTMLResponse)
async def save_portfolio_config(
    request: Request,
    portfolio_json: str = Form(),
) -> HTMLResponse:
    editor = _editor(config_dir(request))
    error = None
    try:
        payload = json.loads(portfolio_json)
        current = _save_portfolio(editor, payload)
    except (ConfigEditError, json.JSONDecodeError) as exc:
        current = editor.read("portfolio", "portfolio")
        error = str(exc)
    return templates(request).TemplateResponse(
        request,
        "config.html",
        {
            "active": "config",
            "files": editor.list_files(),
            "current": current,
            "error": error,
            "analysis_tuning": _analysis_tuning(editor.list_files()),
            "dag": _dag_view(config_dir(request), current),
            "portfolio": _portfolio_view(config_dir(request), portfolio_json),
        },
    )


@router.post("/config/dag", response_class=HTMLResponse)
async def save_dag_config(
    request: Request,
    name: str = Form(),
    nodes: list[str] = Form(default=[]),
    edges_json: str = Form(default="[]"),
) -> HTMLResponse:
    editor = _editor(config_dir(request))
    error = None
    dag_payload: dict[str, object] | None = None
    try:
        dag_payload = _dag_payload(name, nodes, json.loads(edges_json))
        current = _save_dag(editor, name, dag_payload)
    except (ConfigEditError, json.JSONDecodeError) as exc:
        current = editor.read("dag", name)
        error = str(exc)
    return templates(request).TemplateResponse(
        request,
        "config.html",
        {
            "active": "config",
            "files": editor.list_files(),
            "current": current,
            "error": error,
            "analysis_tuning": _analysis_tuning(editor.list_files()),
            "dag": _dag_view(config_dir(request), current, dag_payload),
            "portfolio": _portfolio_view(config_dir(request)),
        },
    )


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


@router.get("/config/dag-graph", response_class=HTMLResponse)
async def dag_graph_page(request: Request, name: str = "default") -> HTMLResponse:
    editor = _editor(config_dir(request))
    try:
        current = editor.read("dag", name)
    except ConfigEditError:
        current = editor.list_files()[0]
    return templates(request).TemplateResponse(
        request,
        "node_graph_editor.html",
        {
            "active": "config",
            "dag_name": current.name,
            "dag_names": [f.name for f in editor.list_files() if f.kind == "dag"],
        },
    )


@router.get("/api/graph/nodes")
async def api_graph_node_prototypes(request: Request) -> dict[str, object]:
    nodes = load_node_configs(config_dir(request) / "nodes")
    prototypes = []
    for node in nodes.values():
        d = node.model_dump(mode="json")
        # Flatten skills list to simple names for the frontend
        d["skills"] = [s["name"] for s in d["skills"]]
        prototypes.append(d)
    return {"prototypes": prototypes}


@router.get("/api/graph/dag/{name}", response_model=None)
async def api_graph_dag_state(request: Request, name: str) -> JSONResponse | dict[str, object]:
    try:
        dag = load_dag_configs(config_dir(request) / "dags")[name]
    except KeyError:
        return error_response(404, "not_found", f"dag {name} not found")
    nodes = load_node_configs(config_dir(request) / "nodes")
    node_instances = []
    for node_name in dag.nodes:
        node_config = nodes.get(node_name)
        if node_config:
            n = node_config.model_dump(mode="json")
            n["skills"] = [s["name"] for s in n["skills"]]
            node_instances.append(n)
        else:
            node_instances.append({"name": node_name, "type": "function", "input_type": "any", "output_type": "any"})
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
                "nodes": dag_config.nodes,
                "edges": [{"from": e.from_, "to": e.to, "fan_out": e.fan_out, "fan_in": e.fan_in} for e in dag_config.edges],
                "ui": dag_config.ui,
            },
        }
    except (ConfigEditError, KeyError) as exc:
        return error_response(400, "config_error", str(exc))


@router.get("/api/graph/node/{name}", response_model=None)
async def api_graph_node_read(request: Request, name: str) -> JSONResponse | dict[str, object]:
    try:
        nodes = load_node_configs(config_dir(request) / "nodes")
        node = nodes[name]
        d = node.model_dump(mode="json")
        d["skills"] = [s["name"] for s in d["skills"]]
        return {"node": d}
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
        node_config = NodeConfig.model_validate(yaml.safe_load(saved.content) or {})
        d = node_config.model_dump(mode="json")
        d["skills"] = [s["name"] for s in d["skills"]]
        return {"file": saved.__dict__, "node": d}
    except (ConfigEditError, KeyError) as exc:
        return error_response(400, "config_error", str(exc))


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


@router.post("/pipeline/run")
async def form_pipeline_run(request: Request) -> RedirectResponse:
    await api_pipeline_run(request)
    return RedirectResponse("/pipeline", status_code=303)


@router.post("/pipeline/pause")
async def form_pipeline_pause(request: Request) -> RedirectResponse:
    await api_pipeline_pause(request)
    return RedirectResponse("/pipeline", status_code=303)


@router.post("/pipeline/resume")
async def form_pipeline_resume(request: Request) -> RedirectResponse:
    await api_pipeline_resume(request)
    return RedirectResponse("/pipeline", status_code=303)


@router.post("/pipeline/stop")
async def form_pipeline_stop(request: Request) -> RedirectResponse:
    await api_pipeline_stop(request)
    return RedirectResponse("/pipeline", status_code=303)


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


def _filters(
    stock_code: str | None,
    direction: str | None,
    created_from: datetime | None,
    created_to: datetime | None,
) -> dict[str, str]:
    return {
        "stock_code": stock_code or "",
        "direction": direction or "",
        "created_from": created_from.isoformat() if created_from else "",
        "created_to": created_to.isoformat() if created_to else "",
    }


def _auto_refresh(briefing: object) -> dict[str, object]:
    version = cast(dict[str, object], briefing) if briefing else {}
    return {
        "briefing_id": version.get("id") or "",
        "briefing_created_at": version.get("created_at") or "",
        "interval_ms": 15_000,
    }


def _analysis_tuning(files: list[EditableFile]) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for file in files:
        if file.kind == "system":
            items.append(
                {
                    "kind": file.kind,
                    "name": file.name,
                    "path": file.path,
                    "fields": ["llm_timeout_seconds"],
                    "description": "全局 LLM 超时",
                }
            )
        elif file.kind == "node" and file.name in {"reader", "advisor", "briefing-generator"}:
            items.append(
                {
                    "kind": file.kind,
                    "name": file.name,
                    "path": file.path,
                    "fields": ["model", "timeout_seconds", "parameters"],
                    "description": "分析链节点参数",
                }
            )
        elif file.kind == "node" and "source_names:" in file.content:
            items.append(
                {
                    "kind": file.kind,
                    "name": file.name,
                    "path": file.path,
                    "fields": ["source_names"],
                    "description": "后续分析输入范围",
                }
            )
    return items


def _portfolio_view(config_path: Path, draft: str | None = None) -> dict[str, object]:
    payload = load_portfolio_config(config_path / "portfolio.yaml").model_dump(mode="json")
    return {
        "targets": payload["targets"],
        "sources": payload["sources"],
        "json": draft or json.dumps(payload, ensure_ascii=False, indent=2),
    }


def _save_portfolio(editor: RuntimeConfigEditor, body: object) -> EditableFile:
    payload = _portfolio_payload(body)
    content = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
    return editor.save("portfolio", "portfolio", content)


def _save_dag(editor: RuntimeConfigEditor, name: str, body: object) -> EditableFile:
    payload = _dag_payload(name, body.get("nodes", []), body.get("edges", [])) if isinstance(body, dict) else {}
    content = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
    return editor.save("dag", name, content)


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


def _dag_view(
    config_path: Path,
    current: EditableFile,
    draft: dict[str, object] | None = None,
) -> dict[str, object] | None:
    if current.kind != "dag":
        return None
    try:
        payload = draft or DagConfig.model_validate(yaml.safe_load(current.content) or {}).model_dump(
            by_alias=True,
            mode="json",
        )
    except ValueError:
        payload = {"name": current.name, "nodes": [], "edges": []}
    node_names = sorted(load_node_configs(config_path / "nodes"))
    raw_nodes = payload.get("nodes", [])
    selected_nodes = [str(node) for node in raw_nodes] if isinstance(raw_nodes, list) else []
    edges = payload.get("edges", [])
    if not isinstance(edges, list):
        edges = []
    return {
        "name": str(payload.get("name") or current.name),
        "nodes": selected_nodes,
        "all_nodes": node_names,
        "edges": [edge for edge in edges if isinstance(edge, dict)],
        "edges_json": json.dumps(edges, ensure_ascii=False),
    }


def _dag_payload(name: str, nodes: object, edges: object) -> dict[str, object]:
    if not isinstance(nodes, list):
        raise ConfigEditError("dag nodes must be a list")
    if not isinstance(edges, list):
        raise ConfigEditError("dag edges must be a list")
    payload = {
        "name": name,
        "nodes": [str(node) for node in nodes],
        "edges": [_dag_edge_payload(edge) for edge in edges],
    }
    return DagConfig.model_validate(payload).model_dump(by_alias=True, mode="json")


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
        "nodes": [str(node) if isinstance(node, str) else str(node.get("name", "")) for node in nodes],
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
    payload: dict[str, object] = {
        "name": name,
        "type": body.get("type", "function"),
        "skills": [{"name": str(s)} if isinstance(s, str) else s for s in skills],
        "model": body.get("model"),
        "input_type": body.get("input_type", "any"),
        "output_type": body.get("output_type", "any"),
        "timeout_seconds": body.get("timeout_seconds"),
        "source_names": body.get("source_names", []),
        "parameters": body.get("parameters", {}),
    }
    try:
        return NodeConfig.model_validate(payload).model_dump(mode="json")
    except ValidationError as exc:
        raise ConfigEditError(str(exc)) from exc


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
