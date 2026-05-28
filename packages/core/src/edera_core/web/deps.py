from __future__ import annotations

from typing import NoReturn, cast

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from edera_core.grpc_client import GrpcClient

_UNSUPPORTED_ROUTE = "route requires edera-server gRPC API"


def error_response(status_code: int, error_type: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"type": error_type, "message": message}},
    )


def _unsupported_route() -> NoReturn:
    raise HTTPException(status_code=501, detail=_UNSUPPORTED_ROUTE)


def controller(_request: Request) -> NoReturn:
    _unsupported_route()


def config_dir(_request: Request) -> NoReturn:
    _unsupported_route()


def handler_registry(_request: Request) -> NoReturn:
    _unsupported_route()


def grpc_client(request: Request) -> GrpcClient | None:
    return cast(GrpcClient | None, getattr(request.app.state, "grpc_client", None))
