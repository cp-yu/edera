from __future__ import annotations

import argparse
import json

import edera_core.cli as _cli
from edera_core.cli._common import CommandHelp, _fmt_epilog

HELP = CommandHelp(
    description="Emit events into the event stream (事件).",
    help_line="Emit events into the stream (事件)",
    epilog=_fmt_epilog(
        "Events trigger registered handlers; payload is JSON.",
        [
            ("edera event emit my.event --payload-json '{\"k\":1}'", "emit a typed event"),
        ],
    ),
    subcommands={
        "emit": "Emit a typed event with optional payload and source.",
    },
)


def add_parser(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="event_command", required=True)
    sub = HELP.subcommands
    emit = subparsers.add_parser("emit", help=sub["emit"])
    emit.add_argument("event", help="Event name.")
    emit.add_argument("--payload-json", default="", help="JSON object payload.")
    emit.add_argument("--source", default="cli", help="Event source label (default: cli).")
    emit.add_argument("--depth", type=int, default=0, help="Trigger depth counter (default: 0).")


async def dispatch(args: argparse.Namespace) -> object:
    client = _cli.GrpcClient(args.server, identity=args.identity)
    try:
        if args.event_command == "emit":
            payload = json.loads(args.payload_json) if args.payload_json else None
            return await client.event_emit(args.event, payload, source=args.source, depth=args.depth)
    finally:
        await client.close()
    raise ValueError(f"unknown event command: {args.event_command}")
