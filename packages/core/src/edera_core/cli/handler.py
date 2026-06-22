from __future__ import annotations

import argparse
from pathlib import Path

from edera_core.cli._common import _local_page_arguments
import edera_core.cli as _cli
from edera_core.cli._common import CommandHelp, _fmt_epilog

HELP = CommandHelp(
    description="Manage event handlers (处理器).",
    help_line="Manage event handlers (处理器)",
    epilog=_fmt_epilog(
        "Handlers are named, versioned modules invoked by the event bus.",
        [
            ("edera handler list", "list registered handlers"),
            ("edera handler show my-handler", "show one handler"),
            ("edera handler save my-handler --file ./handler.yaml", "save a handler"),
        ],
    ),
    subcommands={
        "list": "List registered handlers.",
        "show": "Show a single handler by name.",
        "save": "Save a handler definition from a YAML file.",
    },
)


def add_parser(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="handler_command", required=True)
    sub = HELP.subcommands
    list_ = subparsers.add_parser("list", help=sub["list"])
    _local_page_arguments(list_)
    show = subparsers.add_parser("show", help=sub["show"])
    show.add_argument("name", help="Handler name.")
    save = subparsers.add_parser("save", help=sub["save"])
    save.add_argument("name", help="Handler name.")
    save.add_argument("--file", required=True, type=Path, help="YAML file with handler definition.")


async def dispatch(args: argparse.Namespace) -> object:
    client = _cli.GrpcClient(args.server, identity=args.identity)
    try:
        if args.handler_command == "list":
            return await client.graph_list_handlers()
        if args.handler_command == "show":
            return await client.graph_get_handler(args.name)
        if args.handler_command == "save":
            return await client.graph_save_handler(args.name, args.file.read_text(encoding="utf-8"))
    finally:
        await client.close()
    raise ValueError(f"unknown handler command: {args.handler_command}")
