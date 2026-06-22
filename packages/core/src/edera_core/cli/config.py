from __future__ import annotations

import argparse
from pathlib import Path

import edera_core.cli as _cli
from edera_core.cli._common import CommandHelp, _fmt_epilog

HELP = CommandHelp(
    description="Inspect and edit effective configuration (配置).",
    help_line="Inspect and edit configuration (配置)",
    epilog=_fmt_epilog(
        "Config subcommands cover system config, named configs, and entity-type schemas managed via config.",
        [
            ("edera config list", "list top-level config kinds"),
            ("edera config system show", "show system.toml"),
            ("edera config save source my-src --file ./src.yaml", "save a named config from a file"),
            ("edera config entity-type create stock --file ./stock.yaml", "register an entity-type schema via config"),
        ],
    ),
    subcommands={
        "list": "List available config kinds.",
        "system": "Inspect or save system.toml (subcommands: show, save).",
        "system-show": "Show system.toml configuration.",
        "system-save": "Save system.toml from a file.",
        "read": "Read a named config item.",
        "save": "Save a named config from a file.",
        "entity-type": "Manage entity-type schemas via config (subcommands: list, show, create, save, delete).",
        "config-entity-type-list": "List entity-type schemas managed via config.",
        "config-entity-type-show": "Show a single entity-type schema by name.",
        "config-entity-type-create": "Register an entity-type schema from a YAML file.",
        "config-entity-type-save": "Replace an entity-type schema from a YAML file.",
        "config-entity-type-delete": "Delete an entity-type schema by name.",
    },
)


def add_parser(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="config_command", required=True)
    sub = HELP.subcommands
    subparsers.add_parser("list", help=sub["list"])
    system = subparsers.add_parser("system", help=sub["system"])
    system_sub = system.add_subparsers(dest="system_command", required=True)
    system_sub.add_parser("show", help=sub["system-show"])
    system_save = system_sub.add_parser("save", help=sub["system-save"])
    system_save.add_argument("--file", required=True, type=Path, help="TOML file path.")
    read = subparsers.add_parser("read", help=sub["read"])
    read.add_argument("kind", help="Config kind.")
    read.add_argument("name", help="Config name.")
    save = subparsers.add_parser("save", help=sub["save"])
    save.add_argument("kind", help="Config kind.")
    save.add_argument("name", help="Config name.")
    save.add_argument("--file", required=True, type=Path, help="Input file path.")
    entity_type = subparsers.add_parser("entity-type", help=sub["entity-type"])
    entity_type_sub = entity_type.add_subparsers(dest="entity_type_command", required=True)
    entity_type_sub.add_parser("list", help=sub["config-entity-type-list"])
    show = entity_type_sub.add_parser("show", help=sub["config-entity-type-show"])
    show.add_argument("name", help="Entity type name.")
    for command in ("create", "save"):
        item = entity_type_sub.add_parser(command, help=sub[f"config-entity-type-{command}"])
        item.add_argument("name", help="Entity type name.")
        item.add_argument("--file", required=True, type=Path, help="YAML file with entity-type schema.")
    delete = entity_type_sub.add_parser("delete", help=sub["config-entity-type-delete"])
    delete.add_argument("name", help="Entity type name.")
    delete.add_argument("--cascade", action="store_true", help="Cascade delete related entities.")


async def dispatch(args: argparse.Namespace) -> object:
    client = _cli.GrpcClient(args.server, identity=args.identity)
    try:
        if args.config_command == "list":
            return await client.config_list()
        if args.config_command == "system":
            if args.system_command == "show":
                return await client.config_read_system()
            if args.system_command == "save":
                return await client.config_save_system(args.file.read_text(encoding="utf-8"))
        if args.config_command == "read":
            return await client.config_read(args.kind, args.name)
        if args.config_command == "save":
            return await client.config_save(args.kind, args.name, args.file.read_text(encoding="utf-8"))
        if args.config_command == "entity-type":
            if args.entity_type_command == "list":
                return await client.config_list_entity_types()
            if args.entity_type_command == "show":
                return await client.config_get_entity_type(args.name)
            if args.entity_type_command == "create":
                return await client.config_create_entity_type(args.name, args.file.read_text(encoding="utf-8"))
            if args.entity_type_command == "save":
                return await client.config_save_entity_type(args.name, args.file.read_text(encoding="utf-8"))
            if args.entity_type_command == "delete":
                return await client.config_delete_entity_type(args.name, args.cascade)
    finally:
        await client.close()
    raise ValueError(f"unknown config command: {args.config_command}")
