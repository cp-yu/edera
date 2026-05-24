from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from stockimformation_core.pipeline import PipelineController
from stockimformation_core.web.deps import error_response
from stockimformation_core.web.routes import router


def create_app(
    config_dir: Path = Path("config"),
    controller: PipelineController | None = None,
    run_startup: bool = True,
) -> FastAPI:
    controller = controller or PipelineController(config_dir)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await controller.start(run_startup=run_startup)
        try:
            yield
        finally:
            await controller.shutdown()

    app = FastAPI(title="stockImformation", lifespan=lifespan)
    app.state.config_dir = config_dir
    app.state.controller = controller
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(Exception, _unhandled_error)

    return app


async def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": {"type": "validation_error", "message": str(exc)}},
    )


async def _validation_error_handler(request: Request, exc: Exception) -> Response:
    if isinstance(exc, RequestValidationError):
        return await _validation_error(request, exc)
    return await _unhandled_error(request, exc)


async def _unhandled_error(_request: Request, exc: Exception) -> JSONResponse:
    return error_response(500, exc.__class__.__name__, str(exc))
