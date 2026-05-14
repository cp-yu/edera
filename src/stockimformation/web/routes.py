from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from stockimformation.config.editor import ConfigKind, RuntimeConfigEditor
from stockimformation.errors import ConfigEditError
from stockimformation.models.repository import (
    analyses_for_advice,
    get_advice,
    latest_briefing,
    list_advices,
    raw_items_for_analyses,
)
from stockimformation.pipeline import RunAlreadyActiveError
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
async def results_page(request: Request) -> HTMLResponse:
    data = await _result_summary(request)
    return templates(request).TemplateResponse(
        request,
        "results.html",
        {"active": "results", **data},
    )


@router.get("/pipeline", response_class=HTMLResponse)
async def pipeline_page(request: Request) -> HTMLResponse:
    return templates(request).TemplateResponse(
        request,
        "pipeline.html",
        {"active": "pipeline", "status": await controller(request).status()},
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
        },
    )


@router.get("/api/briefings/latest")
async def api_latest_briefing(request: Request) -> dict[str, object]:
    async with controller(request)._factory()() as session:
        briefing = await latest_briefing(session)
    return {"briefing": briefing.model_dump(mode="json") if briefing else None}


@router.get("/api/advices")
async def api_advices(request: Request) -> dict[str, object]:
    async with controller(request)._factory()() as session:
        advices = await list_advices(session)
    return {"advices": [advice.model_dump(mode="json") for advice in advices]}


@router.get("/api/advices/{advice_id}", response_model=None)
async def api_advice_detail(request: Request, advice_id: int) -> JSONResponse | dict[str, object]:
    async with controller(request)._factory()() as session:
        advice = await get_advice(session, advice_id)
        if advice is None:
            return error_response(404, "not_found", "advice not found")
        analyses = await analyses_for_advice(session, advice)
        raw_items = await raw_items_for_analyses(session, analyses)
    return {
        "advice": advice.model_dump(mode="json"),
        "analyses": [item.model_dump(mode="json") for item in analyses],
        "raw_items": [item.model_dump(mode="json") for item in raw_items],
    }


@router.get("/api/results")
async def api_results(request: Request) -> dict[str, object]:
    return await _result_summary(request)


@router.get("/api/pipeline/status")
async def api_pipeline_status(request: Request) -> dict[str, object]:
    return await controller(request).status()


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


async def _result_summary(request: Request) -> dict[str, Any]:
    async with controller(request)._factory()() as session:
        briefing = await latest_briefing(session)
        advices = await list_advices(session)
    failed_sources = {}
    if briefing is not None:
        failed_sources = briefing.metadata_.get("failed_sources", {})
    return {
        "briefing": briefing.model_dump(mode="json") if briefing else None,
        "advices": [advice.model_dump(mode="json") for advice in advices],
        "failed_sources": failed_sources,
    }


def _editor(config_path: Path) -> RuntimeConfigEditor:
    return RuntimeConfigEditor(config_path, config_path.parent / "skills")


def _kind(value: str) -> ConfigKind:
    if value not in {"system", "portfolio", "node", "dag", "skill"}:
        raise ConfigEditError(f"unsupported config kind: {value}")
    return cast(ConfigKind, value)
