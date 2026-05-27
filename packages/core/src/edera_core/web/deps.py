from __future__ import annotations

from pathlib import Path
from typing import cast

from fastapi import Request
from fastapi.responses import JSONResponse

from edera_core.grpc_client import RigGrpcClient
from edera_core.pipeline import PipelineController
from edera_core.registry import HandlerRegistry


def error_response(status_code: int, error_type: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"type": error_type, "message": message}},
    )


def controller(request: Request) -> PipelineController:
    return cast(PipelineController, request.app.state.controller)


def config_dir(request: Request) -> Path:
    return cast(Path, request.app.state.config_dir)


def handler_registry(request: Request) -> HandlerRegistry | None:
    return cast(HandlerRegistry | None, request.app.state.handler_registry)


def grpc_client(request: Request) -> RigGrpcClient | None:
    return cast(RigGrpcClient | None, getattr(request.app.state, "grpc_client", None))
