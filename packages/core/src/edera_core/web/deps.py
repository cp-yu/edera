from __future__ import annotations

from typing import cast

from fastapi import Request
from fastapi.responses import JSONResponse

from edera_core.grpc_client import GrpcClient


def error_response(status_code: int, error_type: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"type": error_type, "message": message}},
    )


def grpc_client(request: Request) -> GrpcClient | None:
    return cast(GrpcClient | None, getattr(request.app.state, "grpc_client", None))
