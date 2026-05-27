from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, Response

from edera_core.grpc_client import RigGrpcClient, bootstrap_address
from edera_core.pipeline import PipelineController
from edera_core.registry import HandlerRegistry
from edera_core.web.deps import error_response
from edera_core.web.routes import router


def create_app(
    config_dir: Path = Path("config"),
    controller: PipelineController | None = None,
    run_startup: bool = True,
    handler_registry: HandlerRegistry | None = None,
    grpc_client: RigGrpcClient | None = None,
) -> FastAPI:
    controller = controller or PipelineController(config_dir)
    owns_grpc_client = grpc_client is None and bool(os.environ.get("RIG_DAEMON_ADDR"))

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if owns_grpc_client:
            app.state.grpc_client = await _bff_grpc_client()
        await controller.start(run_startup=run_startup)
        try:
            yield
        finally:
            current_grpc_client = app.state.grpc_client
            if owns_grpc_client and current_grpc_client is not None:
                await current_grpc_client.close()
            await controller.shutdown()

    app = FastAPI(title="Edera", lifespan=lifespan)
    app.state.config_dir = config_dir
    app.state.controller = controller
    app.state.handler_registry = handler_registry
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
    static_dir = Path(os.environ.get("RIG_WEB_CONSOLE_DIR", "apps/web-console"))
    if (static_dir / "index.html").exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="web-console")


async def _token_auth_middleware(request: Request, call_next):
    token = os.environ.get("RIG_WEB_TOKEN")
    if os.environ.get("RIG_ENV") == "dev" or not token:
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


async def _bff_grpc_client() -> RigGrpcClient:
    data_dir = Path(os.environ.get("RIG_BFF_DIR", Path.home() / ".rig" / "bff"))
    if not (data_dir / "client.crt").exists():
        data_dir.mkdir(parents=True, exist_ok=True)
        daemon_addr = os.environ.get("RIG_DAEMON_ADDR")
        bootstrap = RigGrpcClient(bootstrap_address(daemon_addr) if daemon_addr else None, data_dir, force_insecure=True)
        try:
            certs = await bootstrap.init_client("bff:web-console")
            (data_dir / "client.crt").write_text(certs["client_cert_pem"], encoding="utf-8")
            (data_dir / "client.key").write_text(certs["client_key_pem"], encoding="utf-8")
            (data_dir / "ca.crt").write_text(certs["ca_cert_pem"], encoding="utf-8")
        finally:
            await bootstrap.close()
    os.environ["RIG_CLIENT_CERT"] = (data_dir / "client.crt").read_text(encoding="utf-8")
    os.environ["RIG_CLIENT_KEY"] = (data_dir / "client.key").read_text(encoding="utf-8")
    os.environ["RIG_CA_CERT"] = (data_dir / "ca.crt").read_text(encoding="utf-8")
    return RigGrpcClient(data_dir=data_dir)
