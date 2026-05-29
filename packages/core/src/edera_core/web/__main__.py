from __future__ import annotations

import argparse
import asyncio
import os

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
    bootstrap = GrpcClient("127.0.0.1:9091", force_insecure=True)
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


if __name__ == "__main__":
    main()
