from __future__ import annotations

import argparse
import json
from pathlib import Path

import edera_core.cli as _cli
from edera_core.cli._common import CommandHelp, _fmt_epilog

HELP = CommandHelp(
    description="Manage relations (关系) between entities.",
    help_line="Manage entity relations (关系)",
    epilog=_fmt_epilog(
        "A relation links two entities with a type and optional metadata.",
        [
            ("edera relation create --from stock:AAPL --to sector:tech --type belongs_to", "create a relation"),
            ("edera relation list --from stock:AAPL", "list outgoing relations"),
        ],
    ),
    subcommands={
        "list": "List relations, optionally filtered by endpoint or type.",
        "create": "Create a new typed relation between two entities.",
        "delete": "Delete a relation by id.",
        "import": "Import relations from a YAML/JSON file.",
        "export": "Export all relations to a file.",
    },
)


def add_parser(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="relation_command", required=True)
    sub = HELP.subcommands
    list_ = subparsers.add_parser("list", help=sub["list"])
    list_.add_argument("--from", dest="from_", help="Filter by source entity <type>:<id>.")
    list_.add_argument("--to", help="Filter by target entity <type>:<id>.")
    list_.add_argument("--type", help="Filter by relation type.")
    create = subparsers.add_parser("create", help=sub["create"])
    create.add_argument("--from", dest="from_", required=True, help="Source entity <type>:<id>.")
    create.add_argument("--to", required=True, help="Target entity <type>:<id>.")
    create.add_argument("--type", required=True, help="Relation type.")
    create.add_argument("--metadata", default="{}", help="JSON object of metadata.")
    delete = subparsers.add_parser("delete", help=sub["delete"])
    delete.add_argument("id", help="Relation ID.")
    import_ = subparsers.add_parser("import", help=sub["import"])
    import_.add_argument("path", nargs="?", type=Path, help="Path to YAML or JSON file.")
    import_.add_argument("--file", type=Path, help="Alias of path.")
    export = subparsers.add_parser("export", help=sub["export"])
    export.add_argument("-o", "--file", required=True, type=Path, help="Output file path.")


async def dispatch(args: argparse.Namespace) -> object:
    return await _grpc_relation(args)


async def _grpc_relation(args: argparse.Namespace) -> object:
    if args.relation_command == "list":
        filters = []
        if args.from_:
            filters.append(f"from_entity_id={args.from_}")
        if args.to:
            filters.append(f"to_entity_id={args.to}")
        if args.type:
            filters.append(f"relation_type={args.type}")
        return await _cli._grpc_entity(
            argparse.Namespace(
                server=args.server,
                identity=args.identity,
                entity_command="list",
                type="relation",
                filter=filters,
            )
        )
    if args.relation_command == "create":
        metadata = json.loads(args.metadata)
        if not isinstance(metadata, dict):
            raise ValueError("metadata must be a JSON object")
        attributes = {
            "from_entity_id": args.from_,
            "to_entity_id": args.to,
            "relation_type": args.type,
            "metadata": metadata,
        }
        return await _cli._grpc_entity(
            argparse.Namespace(
                server=args.server,
                identity=args.identity,
                entity_command="create",
                type="relation",
                id="",
                attributes=json.dumps(attributes, ensure_ascii=False, separators=(",", ":")),
            )
        )
    if args.relation_command == "delete":
        return await _cli._grpc_entity(
            argparse.Namespace(server=args.server, identity=args.identity, entity_command="delete", ref=args.id, force=False)
        )
    if args.relation_command == "import":
        return await _cli._grpc_entity(
            argparse.Namespace(
                server=args.server,
                identity=args.identity,
                entity_command="import",
                type="relation",
                path=getattr(args, "path", None),
                file=getattr(args, "file", None),
            )
        )
    if args.relation_command == "export":
        return await _cli._grpc_entity(
            argparse.Namespace(
                server=args.server,
                identity=args.identity,
                entity_command="export",
                type="relation",
                ref=None,
                file=args.file,
            )
        )
    raise ValueError(f"unknown relation command: {args.relation_command}")
