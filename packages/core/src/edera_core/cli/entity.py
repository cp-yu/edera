from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from edera_core.cli._common import (
    _arg_path,
    _entity_document,
    _json_value,
    _normalized_entity_import_yaml,
    _parse_filters,
    _write_entity_yaml,
)
import edera_core.cli as _cli
from edera_core.cli._common import CommandHelp, _fmt_epilog

HELP = CommandHelp(
    description="Manage entities (实体管理): the unified primitive of the kernel.",
    help_line="Manage entities (实体管理)",
    epilog=_fmt_epilog(
        "An entity is identified by `<type>:<id>` and stores typed attributes.",
        [
            ("edera entity create --type document --attributes title=\"Hello\"", "create a new entity"),
            ("edera entity list --type document --filter 'status=active'", "list with filters"),
            ("edera entity get stock:AAPL --output table", "render as a table"),
            ("edera entity import ./entities.yaml", "bulk import from YAML"),
        ],
    ),
    subcommands={
        "get": "Show a single entity by ref.",
        "show": "Show a single entity (alias of get).",
        "create": "Create a new entity.",
        "import": "Import entities from a YAML/JSON file.",
        "export": "Export a single entity to a file.",
        "template": "Emit a starter template for a given type.",
        "list": "List entities, optionally filtered.",
        "update": "Patch one field or full attributes on an entity.",
        "query": "Run an inline query expression against entities.",
        "delete": "Delete an entity (--force to bypass checks).",
    },
)


def add_parser(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="entity_command", required=True)
    sub = HELP.subcommands
    get = subparsers.add_parser("get", help=sub["get"])
    get.add_argument("ref", help="Entity reference in <type>:<id> form.")
    show = subparsers.add_parser("show", help=sub["show"])
    show.add_argument("ref", help="Entity reference in <type>:<id> form.")
    create = subparsers.add_parser("create", help=sub["create"])
    create.add_argument("--type", required=True, help="Entity type name.")
    create.add_argument("--id", default="", help="Entity ID (auto-generated if omitted).")
    create.add_argument("--attributes", help="JSON object of attribute key-value pairs.")
    import_ = subparsers.add_parser("import", help=sub["import"])
    import_.add_argument("path", nargs="?", type=Path, help="Path to YAML or JSON file.")
    import_.add_argument("--file", type=Path, help="Alias of path.")
    import_.add_argument("--type", help="Filter imports to this entity type.")
    export = subparsers.add_parser("export", help=sub["export"])
    export.add_argument("ref", nargs="?", help="Entity reference <type>:<id> (omit to export by type).")
    export.add_argument("-o", "--file", required=True, type=Path, help="Output file path.")
    export.add_argument("--type", help="Entity type to export (when ref omitted).")
    template = subparsers.add_parser("template", help=sub["template"])
    template.add_argument("--type", required=True, help="Entity type for the starter template.")
    template.add_argument("--file", required=True, type=Path, help="Output file path.")
    list_ = subparsers.add_parser("list", help=sub["list"])
    list_.add_argument("--type", help="Filter by entity type.")
    list_.add_argument("--filter", action="append", default=[], help="Filter in key=value form (repeatable).")
    update = subparsers.add_parser("update", help=sub["update"])
    update.add_argument("ref", help="Entity reference <type>:<id>.")
    update.add_argument("--field", help="Single field name to patch.")
    update.add_argument("--value", help="New value for --field (JSON literal or string).")
    update.add_argument("--attributes", help="JSON object to merge into attributes.")
    query = subparsers.add_parser("query", help=sub["query"])
    query.add_argument("expression", help="Inline query expression.")
    delete = subparsers.add_parser("delete", help=sub["delete"])
    delete.add_argument("ref", help="Entity reference <type>:<id>.")
    delete.add_argument("--force", action="store_true", help="Delete without confirmation.")


async def dispatch(args: argparse.Namespace) -> object:
    return await _grpc_entity(args)


async def _grpc_entity(args: argparse.Namespace) -> object:
    import_path = _arg_path(args) if args.entity_command == "import" else None
    normalized_import_path = import_path
    if import_path is not None and getattr(args, "type", None) != "relation":
        normalized_import_path = _normalized_entity_import_yaml(import_path)
    client = _cli.GrpcClient(args.server, identity=args.identity)
    try:
        if args.entity_command in {"get", "show"}:
            return await client.entity_get(args.ref)
        if args.entity_command == "create":
            if args.attributes is None:
                raise ValueError("Missing required parameter: --attributes")
            attributes = json.loads(args.attributes)
            if not isinstance(attributes, dict):
                raise ValueError("attributes must be a JSON object")
            return await client.entity_create(args.type, attributes, entity_id=args.id)
        if args.entity_command == "import":
            return await client.entity_import(str(normalized_import_path), getattr(args, "type", None))
        if args.entity_command == "export":
            if args.ref:
                entity = await client.entity_get(args.ref)
                _write_entity_yaml(args.file, _entity_document(entity))
                return {"exported": args.ref, "file": str(args.file)}
            result = await client.entity_export(getattr(args, "type", None))
            args.file.parent.mkdir(parents=True, exist_ok=True)
            args.file.write_text(str(result.get("content") or ""), encoding="utf-8")
            return {"exported": result.get("exported", 0), "file": str(args.file)}
        if args.entity_command == "template":
            entity_type = await _entity_type(client, args.type)
            document = {"type": args.type, "id": "", "attributes": _template_attributes(entity_type)}
            _write_entity_yaml(args.file, document)
            return {"template": args.type, "file": str(args.file)}
        if args.entity_command == "list":
            return await client.entity_list(args.type, _parse_filters(args.filter))
        if args.entity_command == "update":
            if getattr(args, "attributes", None):
                updates = json.loads(args.attributes)
                if not isinstance(updates, dict):
                    raise ValueError("attributes must be a JSON object")
                result = None
                for field, value in updates.items():
                    result = await client.entity_update(args.ref, str(field), value)
                return result or await client.entity_get(args.ref)
            if not args.field:
                raise ValueError("update requires --field or --attributes")
            return await client.entity_update(args.ref, args.field, _json_value(args.value))
        if args.entity_command == "query":
            return await client.entity_search(args.expression, args.identity)
        if args.entity_command == "delete":
            return await client.entity_delete(args.ref, getattr(args, "force", False))
    finally:
        await client.close()
    raise ValueError(f"unknown entity command: {args.entity_command}")


async def _entity_type(client: GrpcClient, type_name: str) -> dict[str, object]:
    for entity_type in await client.entity_list("entity_type"):
        attributes = entity_type.get("attributes")
        if entity_type.get("id") == type_name and isinstance(attributes, dict):
            return attributes
    raise ValueError(f"unknown entity type: {type_name}")


def _template_attributes(entity_type: dict[str, object]) -> dict[str, object]:
    schema = entity_type.get("schema")
    properties = schema.get("properties") if isinstance(schema, dict) else None
    required = schema.get("required") if isinstance(schema, dict) else None
    if not isinstance(properties, dict):
        return {}
    names = required if isinstance(required, list) else list(properties)
    return {str(name): _template_value(properties.get(name)) for name in names if isinstance(name, str)}


def _template_value(schema: object) -> object:
    if not isinstance(schema, dict):
        return ""
    if "default" in schema:
        return schema["default"]
    type_name = schema.get("type")
    if type_name == "integer":
        return 0
    if type_name == "number":
        return 0
    if type_name == "boolean":
        return False
    if type_name == "array":
        return []
    if type_name == "object":
        return {}
    return ""
