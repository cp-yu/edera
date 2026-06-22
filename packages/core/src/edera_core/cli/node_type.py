from __future__ import annotations

import argparse
from pathlib import Path

from edera_core.cli._common import _read_json_object
import edera_core.cli as _cli
from edera_core.cli._common import CommandHelp, _fmt_epilog

HELP = CommandHelp(
    description="Manage node-type definitions (节点类型).",
    help_line="Manage node-type definitions (节点类型)",
    epilog=_fmt_epilog(
        "Node types are registered from YAML definitions and referenced by DAG nodes.",
        [
            ("edera node-type list", "list registered node types"),
            ("edera node-type create llm-analyze --file ./node-types/llm-analyze.yaml", "register a node type"),
            ("edera node-type delete llm-analyze", "remove a node type"),
        ],
    ),
    subcommands={
        "list": "List registered node types.",
        "show": "Show a single node type by name.",
        "create": "Register a node type from a YAML file.",
        "save": "Replace a node type from a YAML file.",
        "delete": "Delete a node type by name.",
    },
)


def add_parser(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="node_type_command", required=True)
    sub = HELP.subcommands
    subparsers.add_parser("list", help=sub["list"])
    show = subparsers.add_parser("show", help=sub["show"])
    show.add_argument("name", help="Node type name.")
    for command in ("create", "save"):
        item = subparsers.add_parser(command, help=sub[command])
        item.add_argument("name", help="Node type name.")
        item.add_argument("--file", required=True, type=Path, help="YAML file with node type definition.")
    delete = subparsers.add_parser("delete", help=sub["delete"])
    delete.add_argument("name", help="Node type name.")


async def dispatch(args: argparse.Namespace) -> object:
    client = _cli.GrpcClient(args.server, identity=args.identity)
    try:
        if args.node_type_command == "list":
            return await client.graph_list_node_types()
        if args.node_type_command == "show":
            return await client.graph_get_node_type(args.name)
        if args.node_type_command == "create":
            return await client.graph_create_node_type(args.name, _read_json_object(args.file))
        if args.node_type_command == "save":
            return await client.graph_save_node_type(args.name, _read_json_object(args.file))
        if args.node_type_command == "delete":
            return await client.graph_delete_node_type(args.name)
    finally:
        await client.close()
    raise ValueError(f"unknown node-type command: {args.node_type_command}")
