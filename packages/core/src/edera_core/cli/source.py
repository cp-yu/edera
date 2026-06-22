from __future__ import annotations

import argparse

from edera_core.cli._common import _offset_argument, _tail_arguments, _watch_arguments
import edera_core.cli as _cli
from edera_core.cli._common import CommandHelp, _fmt_epilog

HELP = CommandHelp(
    description="Inspect information-source health and logs (信息源).",
    help_line="Inspect info sources (信息源)",
    epilog=_fmt_epilog(
        "Source subcommands expose runtime diagnostics for information sources.",
        [
            ("edera source health", "watch source health"),
            ("edera source logs --source-name minimax-docs --tail", "tail a source's logs"),
            ("edera source repair-task minimax-docs", "repair a single source task"),
        ],
    ),
    subcommands={
        "health": "Show source health (--watch).",
        "logs": "Read source logs with pagination and optional --tail.",
        "repair-task": "Repair a single source task by source name.",
    },
)


def add_parser(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="source_command", required=True)
    sub = HELP.subcommands
    health = subparsers.add_parser("health", help=sub["health"])
    _watch_arguments(health)
    logs = subparsers.add_parser("logs", help=sub["logs"])
    logs.add_argument("--source-name", default="", help="Filter by source name.")
    logs.add_argument("--limit", type=int, default=50, help="Max results (default: 50).")
    _offset_argument(logs)
    _tail_arguments(logs)
    repair_task = subparsers.add_parser("repair-task", help=sub["repair-task"])
    repair_task.add_argument("source_name", help="Source name to repair.")


async def dispatch(args: argparse.Namespace) -> object:
    client = _cli.GrpcClient(args.server, identity=args.identity)
    try:
        if args.source_command == "health":
            return await client.query_source_health()
        if args.source_command == "logs":
            return await client.query_source_logs(args.source_name, args.limit)
        if args.source_command == "repair-task":
            return await client.system_create_repair_task(args.source_name)
    finally:
        await client.close()
    raise ValueError(f"unknown source command: {args.source_command}")
