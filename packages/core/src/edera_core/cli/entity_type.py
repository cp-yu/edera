from __future__ import annotations

import argparse

import edera_core.cli as _cli
from edera_core.cli._common import CommandHelp, _fmt_epilog

HELP = CommandHelp(
    description="Inspect and materialize entity-type schemas (实体类型).",
    help_line="Manage entity-type schemas (实体类型)",
    epilog=_fmt_epilog(
        "Entity types describe attribute schemas; materialize promotes a field to a typed column.",
        [
            ("edera entity-type materialize plan stock --field sentiment --type string", "preview materialization"),
            ("edera entity-type materialize apply stock --field sentiment --type string", "apply materialization"),
            ("edera entity-type materialize inspect stock", "inspect current materialization state"),
        ],
    ),
    subcommands={
        "materialize": "Promote a field into a typed, indexed column (subcommands: plan, apply, inspect).",
        "materialize-plan": "Preview the materialization plan for a field.",
        "materialize-apply": "Apply a field materialization.",
        "materialize-inspect": "Inspect current materialization state.",
    },
)


def add_parser(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="entity_type_command", required=True)
    materialize = subparsers.add_parser("materialize", help=HELP.subcommands["materialize"])
    materialize_sub = materialize.add_subparsers(dest="materialize_command", required=True)
    et_sub = HELP.subcommands
    for command in ("plan", "apply"):
        item = materialize_sub.add_parser(command, help=et_sub[f"materialize-{command}"])
        item.add_argument("type", help="Entity type name.")
        item.add_argument("--field", required=True, help="Attribute field name to materialize.")
        item.add_argument("--type", dest="field_type", help="Target column type (e.g. string, integer).")
        item.add_argument("--index", action="store_true", help="Create a database index on the column.")
    inspect = materialize_sub.add_parser("inspect", help=et_sub["materialize-inspect"])
    inspect.add_argument("type", help="Entity type name to inspect.")


async def dispatch(args: argparse.Namespace) -> object:
    client = _cli.GrpcClient(args.server, identity=args.identity)
    try:
        if args.entity_type_command != "materialize":
            raise ValueError(f"unknown entity-type command: {args.entity_type_command}")
        payload: dict[str, object] = {
            "operation": args.materialize_command,
            "entity_type": args.type,
        }
        if args.materialize_command in {"plan", "apply"}:
            payload["field"] = args.field
            if args.field_type:
                payload["type"] = args.field_type
            if args.index:
                payload["index"] = True
        return await client.entity_materialize(payload)
    finally:
        await client.close()
