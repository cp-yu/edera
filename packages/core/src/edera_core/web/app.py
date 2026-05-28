from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from edera_core.grpc_client import GrpcClient
from edera_core.web.deps import error_response
from edera_core.web.routes import router


def create_app(grpc_client: GrpcClient) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await app.state.grpc_client.close()

    app = FastAPI(title="Edera", lifespan=lifespan)
    app.state.grpc_client = grpc_client
    app.middleware("http")(_token_auth_middleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    _mount_web_console(app)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(Exception, _unhandled_error)
    return app


def _mount_web_console(app: FastAPI) -> None:
    static_dir = Path(os.environ.get("EDERA_WEB_CONSOLE_DIR", "apps/web-console"))
    if (static_dir / "index.html").exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="web-console")


async def _token_auth_middleware(request: Request, call_next):
    token = os.environ.get("EDERA_WEB_TOKEN")
    if os.environ.get("EDERA_DEV") == "1" or not token:
        return await call_next(request)
    if request.headers.get("authorization") != f"Bearer {token}":
        return error_response(401, "unauthorized", "invalid token")
    return await call_next(request)


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
