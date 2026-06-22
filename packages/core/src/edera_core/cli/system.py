from __future__ import annotations

import argparse

from edera_core.cli._common import _watch_arguments
import edera_core.cli as _cli
from edera_core.cli._common import CommandHelp, _fmt_epilog

HELP = CommandHelp(
    description="Inspect and control server runtime state (系统).",
    help_line="Control server runtime (系统)",
    epilog=_fmt_epilog(
        "System subcommands control the scheduler and repair sources.",
        [
            ("edera system scheduler-status", "show scheduler status"),
            ("edera system pause-scheduler", "pause the scheduler"),
            ("edera system repair-source my-source", "repair a stalled source"),
        ],
    ),
    subcommands={
        "pause-scheduler": "Pause the global scheduler.",
        "resume-scheduler": "Resume the global scheduler.",
        "scheduler-status": "Show scheduler status (--watch).",
        "repair-source": "Trigger repair for a specific source.",
    },
)


def add_parser(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="system_command", required=True)
    sub = HELP.subcommands
    subparsers.add_parser("pause-scheduler", help=sub["pause-scheduler"])
    subparsers.add_parser("resume-scheduler", help=sub["resume-scheduler"])
    scheduler_status = subparsers.add_parser("scheduler-status", help=sub["scheduler-status"])
    _watch_arguments(scheduler_status)
    repair_source = subparsers.add_parser("repair-source", help=sub["repair-source"])
    repair_source.add_argument("source_name", help="Source name to repair.")


async def dispatch(args: argparse.Namespace) -> object:
    client = _cli.GrpcClient(args.server, identity=args.identity)
    try:
        if args.system_command == "pause-scheduler":
            return await client.system_pause_scheduler()
        if args.system_command == "resume-scheduler":
            return await client.system_resume_scheduler()
        if args.system_command == "scheduler-status":
            return await client.system_scheduler_status()
        if args.system_command == "repair-source":
            return await client.system_create_repair_task(args.source_name)
    finally:
        await client.close()
    raise ValueError(f"unknown system command: {args.system_command}")
