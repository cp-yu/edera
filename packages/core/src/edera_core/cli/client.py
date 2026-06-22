from __future__ import annotations

import argparse
import os
from pathlib import Path

import edera_core.cli as _cli
from edera_core.cli._common import CommandHelp, _fmt_epilog

HELP = CommandHelp(
    description="Manage the local client identity and certificates (客户端).",
    help_line="Manage client identity/certs (客户端)",
    epilog=_fmt_epilog(
        "client init runs against the server bootstrap port to mint a client certificate.",
        [
            ("edera client init --server 127.0.0.1:9091", "bootstrap a client cert over the bootstrap port"),
        ],
    ),
    subcommands={
        "init": "Bootstrap the local client against a server bootstrap port.",
    },
)


def add_parser(parser: argparse.ArgumentParser) -> None:
    client_sub = parser.add_subparsers(dest="client_command", required=True)
    sub = HELP.subcommands
    init = client_sub.add_parser("init", help=sub["init"])
    init.add_argument("--server", required=True, help="Server bootstrap address host:port.")
    init.add_argument("--common-name", default=os.environ.get("EDERA_IDENTITY", "human:default"), help="Client common name (env: EDERA_IDENTITY).")


def dispatch(args: argparse.Namespace) -> object:  # noqa: F811 - sync dispatch
    if args.client_command != "init":
        raise ValueError(f"unknown client command: {args.client_command}")
    target = Path.home() / ".edera"
    target.mkdir(parents=True, exist_ok=True)
    import asyncio
    certs = asyncio.run(_grpc_client_init(args.server, args.common_name))
    (target / "client.crt").write_text(str(certs["client_cert_pem"]), encoding="utf-8")
    (target / "client.key").write_text(str(certs["client_key_pem"]), encoding="utf-8")
    (target / "ca.crt").write_text(str(certs["ca_cert_pem"]), encoding="utf-8")
    return {"configured": True, "server": args.server, "path": str(target / "client.crt")}


async def _grpc_client_init(server: str, common_name: str) -> dict[str, str]:
    client = _cli.GrpcClient(server, force_insecure=True)
    try:
        return await client.init_client(common_name)
    finally:
        await client.close()
