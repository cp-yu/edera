from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from edera_core.grpc_client import GrpcClient
from edera_core.web.app import create_app


def main() -> None:
    parser = argparse.ArgumentParser(prog="edera-web")
    parser.add_argument("--bind", default=os.environ.get("EDERA_WEB_BIND", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("EDERA_WEB_PORT", "8000")))
    args = parser.parse_args()
    asyncio.run(_serve(args.bind, args.port))


async def _serve(bind: str, port: int) -> None:
    import uvicorn

    grpc_client = await _bff_grpc_client()
    config = uvicorn.Config(
        create_app(grpc_client),
        host=bind,
        port=port,
        log_level=os.environ.get("EDERA_LOG_LEVEL", "info").lower(),
    )
    await uvicorn.Server(config).serve()


async def _bff_grpc_client() -> GrpcClient:
    server_addr = os.environ.get("EDERA_SERVER_ADDR")
    if not server_addr:
        raise ValueError("EDERA_SERVER_ADDR not set")
    if os.environ.get("EDERA_DEV") == "1":
        return GrpcClient(server_addr, identity="bff:web-console")
    bootstrap = GrpcClient(_bootstrap_address(), force_insecure=True)
    try:
        certs = await bootstrap.init_client("bff:web-console")
    finally:
        await bootstrap.close()
    return GrpcClient(
        server_addr,
        client_cert_pem=certs["client_cert_pem"],
        client_key_pem=certs["client_key_pem"],
        ca_cert_pem=certs["ca_cert_pem"],
    )


def _bootstrap_address() -> str:
    path = _data_dir() / "bootstrap.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"bootstrap status unavailable: {path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"bootstrap status unavailable: {path}")
    host = payload.get("host")
    port = payload.get("port")
    if not isinstance(host, str) or host != "127.0.0.1" or not isinstance(port, int):
        raise RuntimeError(f"bootstrap status unavailable: {path}")
    return f"{host}:{port}"


def _data_dir() -> Path:
    value = os.environ.get("EDERA_DATA_DIR")
    return Path(value) if value else Path.home() / ".local" / "share" / "edera-server"


if __name__ == "__main__":
    main()
