from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

import grpc
import yaml

from edera_core.errors import ConfigError
from edera_core.grpc_client import GrpcClient
from edera_core.handler_validator import validate_handler


def main() -> None:
    parser = argparse.ArgumentParser(prog="edera")
    parser.add_argument("--identity", default=os.environ.get("EDERA_IDENTITY", "human"))
    parser.add_argument("--server", default=os.environ.get("EDERA_SERVER_ADDR"))
    parser.add_argument("--version", action="version", version="edera 0.1.0")
    subparsers = parser.add_subparsers(dest="command", required=True)
    _entity_parser(subparsers.add_parser("entity"))
    _entity_type_parser(subparsers.add_parser("entity-type"))
    _node_parser(subparsers.add_parser("node"))
    _dag_parser(subparsers.add_parser("dag"))
    _event_parser(subparsers.add_parser("event"))
    _system_parser(subparsers.add_parser("system"))
    _client_parser(subparsers.add_parser("client"))
    handler_validate = subparsers.add_parser("handler-validate")
    handler_validate.add_argument("path", type=Path)
    args = parser.parse_args()
    try:
        if _should_inject_human_cert_env(args):
            _inject_human_cert_env()
        result = _dispatch(args)
    except PermissionError as exc:
        parser.exit(1, f"Permission denied: {exc}\n")
    except grpc.RpcError as exc:
        detail = exc.details() if hasattr(exc, "details") else str(exc)
        parser.exit(1, f"{detail}\n")
    except (ConfigError, ValueError, FileNotFoundError, yaml.YAMLError) as exc:
        parser.exit(1, f"{exc}\n")
    if result is not None:
        print(json.dumps(result, ensure_ascii=False, default=str))


def _entity_parser(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="entity_command", required=True)
    get = subparsers.add_parser("get")
    get.add_argument("ref")
    create = subparsers.add_parser("create")
    create.add_argument("--type", required=True)
    create.add_argument("--attributes", default="{}")
    import_ = subparsers.add_parser("import")
    import_.add_argument("--file", required=True, type=Path)
    export = subparsers.add_parser("export")
    export.add_argument("ref")
    export.add_argument("--file", required=True, type=Path)
    template = subparsers.add_parser("template")
    template.add_argument("--type", required=True)
    template.add_argument("--file", required=True, type=Path)
    list_ = subparsers.add_parser("list")
    list_.add_argument("--type")
    update = subparsers.add_parser("update")
    update.add_argument("ref")
    update.add_argument("--field", required=True)
    update.add_argument("--value", required=True)
    query = subparsers.add_parser("query")
    query.add_argument("expression")
    delete = subparsers.add_parser("delete")
    delete.add_argument("ref")


def _entity_type_parser(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="entity_type_command", required=True)
    materialize = subparsers.add_parser("materialize")
    materialize_sub = materialize.add_subparsers(dest="materialize_command", required=True)
    for command in ("plan", "apply"):
        item = materialize_sub.add_parser(command)
        item.add_argument("type")
        item.add_argument("--field", required=True)
        item.add_argument("--type", dest="field_type")
        item.add_argument("--index", action="store_true")
    inspect = materialize_sub.add_parser("inspect")
    inspect.add_argument("type")


def _node_parser(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="node_command", required=True)
    status = subparsers.add_parser("status")
    status.add_argument("node_id")
    stop = subparsers.add_parser("stop")
    stop.add_argument("node_id")
    resume = subparsers.add_parser("resume")
    resume.add_argument("node_id")
    resume.add_argument("--prompt", default="")
    resume.add_argument("--run-id")
    output = subparsers.add_parser("output")
    output.add_argument("output_args", nargs="*")
    output.add_argument("--run-id")


def _dag_parser(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="dag_command", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("dag_name")
    run.add_argument("--payload", default="{}")
    run.add_argument("--inputs", default="")
    run.add_argument("--input", action="append", default=[])
    status = subparsers.add_parser("status")
    status.add_argument("dag_name")
    stop = subparsers.add_parser("stop")
    stop.add_argument("dag_name")
    stop.add_argument("--force", action="store_true")
    retry = subparsers.add_parser("retry")
    retry.add_argument("dag_name")
    retry.add_argument("--run-id", default="")
    retry.add_argument("--nodes", default="")
    retry.add_argument("--mode", default="single")
    retry.add_argument("--payload", default="")
    edit = subparsers.add_parser("edit")
    edit.add_argument("dag_name")
    edit_sub = edit.add_subparsers(dest="edit_command", required=True)
    add_node = edit_sub.add_parser("add-node")
    add_node.add_argument("--id")
    add_node.add_argument("--alias")
    add_node.add_argument("--type", required=True)
    add_node.add_argument("--config", default="{}")
    add_edge = edit_sub.add_parser("add-edge")
    add_edge.add_argument("--from", dest="from_", required=True)
    add_edge.add_argument("--to", required=True)
    add_edge.add_argument("--optional", action="store_true")
    remove_edge = edit_sub.add_parser("remove-edge")
    remove_edge.add_argument("--from", dest="from_", required=True)
    remove_edge.add_argument("--to", required=True)


def _event_parser(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="event_command", required=True)
    emit = subparsers.add_parser("emit")
    emit.add_argument("event")
    emit.add_argument("--payload-json", default="")
    emit.add_argument("--source", default="cli")
    emit.add_argument("--depth", type=int, default=0)


def _system_parser(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="system_command", required=True)
    subparsers.add_parser("pause-scheduler")
    subparsers.add_parser("resume-scheduler")
    subparsers.add_parser("scheduler-status")


def _client_parser(parser: argparse.ArgumentParser) -> None:
    client_sub = parser.add_subparsers(dest="client_command", required=True)
    init = client_sub.add_parser("init")
    init.add_argument("--server", required=True)
    init.add_argument("--common-name", default=os.environ.get("EDERA_IDENTITY", "human:default"))


def _dispatch(args: argparse.Namespace) -> object:
    if args.command == "entity":
        return _run_grpc(_grpc_entity(args))
    if args.command == "entity-type":
        return _run_grpc(_grpc_entity_type(args))
    if args.command == "node":
        return _run_grpc(_grpc_node(args))
    if args.command == "dag":
        return _run_grpc(_grpc_dag(args))
    if args.command == "event":
        return _run_grpc(_grpc_event(args))
    if args.command == "system":
        return _run_grpc(_grpc_system(args))
    if args.command == "client":
        return _client(args)
    if args.command == "handler-validate":
        return _handler_validate(args.path)
    raise ValueError(f"unknown command: {args.command}")


def _should_inject_human_cert_env(args: argparse.Namespace) -> bool:
    return args.command not in {"client", "handler-validate"}


def _inject_human_cert_env() -> None:
    cert_dir = Path.home() / ".edera"
    for env_name, filename in (
        ("EDERA_CLIENT_CERT", "client.crt"),
        ("EDERA_CLIENT_KEY", "client.key"),
        ("EDERA_CA_CERT", "ca.crt"),
    ):
        if env_name in os.environ:
            continue
        path = cert_dir / filename
        if path.exists():
            os.environ[env_name] = path.read_text(encoding="utf-8")


async def _grpc_entity(args: argparse.Namespace) -> object:
    import_document = _read_entity_yaml(args.file) if args.entity_command == "import" else None
    client = GrpcClient(args.server, identity=args.identity)
    try:
        if args.entity_command == "get":
            return await client.entity_get(args.ref)
        if args.entity_command == "create":
            attributes = json.loads(args.attributes)
            if not isinstance(attributes, dict):
                raise ValueError("attributes must be a JSON object")
            return await client.entity_create(args.type, attributes)
        if args.entity_command == "import":
            document = import_document or _read_entity_yaml(args.file)
            return await client.entity_create(str(document["type"]), document["attributes"], entity_id=str(document["id"]))
        if args.entity_command == "export":
            entity = await client.entity_get(args.ref)
            _write_entity_yaml(args.file, _entity_document(entity))
            return {"exported": args.ref, "file": str(args.file)}
        if args.entity_command == "template":
            entity_type = await _entity_type(client, args.type)
            document = {"type": args.type, "id": "", "attributes": _template_attributes(entity_type)}
            _write_entity_yaml(args.file, document)
            return {"template": args.type, "file": str(args.file)}
        if args.entity_command == "list":
            return await client.entity_list(args.type)
        if args.entity_command == "update":
            return await client.entity_update(args.ref, args.field, _json_value(args.value))
        if args.entity_command == "query":
            return await client.entity_search(args.expression, args.identity)
        if args.entity_command == "delete":
            return await client.entity_delete(args.ref)
    finally:
        await client.close()
    raise ValueError(f"unknown entity command: {args.entity_command}")


async def _grpc_entity_type(args: argparse.Namespace) -> object:
    client = GrpcClient(args.server, identity=args.identity)
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


async def _grpc_node(args: argparse.Namespace) -> object:
    client = GrpcClient(args.server, identity=args.identity)
    try:
        if args.node_command == "status":
            return await client.node_status(args.node_id)
        if args.node_command == "stop":
            return await client.node_stop(args.node_id)
        if args.node_command == "resume":
            return await client.node_resume(args.node_id, args.run_id, args.prompt)
        if args.node_command == "output":
            node_id = args.output_args[1] if args.output_args[:1] == ["query"] and len(args.output_args) > 1 else None
            node_id = node_id or (args.output_args[0] if args.output_args else None)
            if not node_id:
                raise ValueError("node_id is required")
            return await client.node_output(node_id, args.run_id)
    finally:
        await client.close()
    raise ValueError(f"unknown node command: {args.node_command}")


async def _grpc_dag(args: argparse.Namespace) -> object:
    client = GrpcClient(args.server, identity=args.identity)
    try:
        if args.dag_command == "status":
            return await client.dag_status(args.dag_name)
        if args.dag_command == "stop":
            return await client.dag_stop(args.dag_name, args.force)
        if args.dag_command == "retry":
            return await client.dag_retry(args.dag_name, args.run_id, _node_ids(args.nodes), args.mode, _optional_json(args.payload))
        if args.dag_command == "edit":
            return await client.dag_edit(args.dag_name, args.edit_command, _dag_edit_payload(args))
        return await client.dag_run(args.dag_name, _dag_run_payload(args))
    finally:
        await client.close()


async def _grpc_event(args: argparse.Namespace) -> object:
    client = GrpcClient(args.server, identity=args.identity)
    try:
        if args.event_command == "emit":
            payload = json.loads(args.payload_json) if args.payload_json else None
            return await client.event_emit(args.event, payload, source=args.source, depth=args.depth)
    finally:
        await client.close()
    raise ValueError(f"unknown event command: {args.event_command}")


async def _grpc_system(args: argparse.Namespace) -> object:
    client = GrpcClient(args.server, identity=args.identity)
    try:
        if args.system_command == "pause-scheduler":
            return await client.system_pause_scheduler()
        if args.system_command == "resume-scheduler":
            return await client.system_resume_scheduler()
        if args.system_command == "scheduler-status":
            return await client.system_scheduler_status()
    finally:
        await client.close()
    raise ValueError(f"unknown system command: {args.system_command}")


def _dag_run_payload(args: argparse.Namespace) -> object:
    if args.input:
        payload: dict[str, str] = {}
        for item in args.input:
            key, sep, value = item.partition("=")
            if not sep or not key:
                raise ValueError("--input must be key=value")
            payload[key] = value
        return payload
    if args.inputs:
        return json.loads(args.inputs)
    return json.loads(args.payload)


def _node_ids(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _optional_json(value: str) -> object | None:
    return json.loads(value) if value else None


def _dag_edit_payload(args: argparse.Namespace) -> dict[str, object]:
    if args.edit_command == "add-node":
        node_id = args.id or args.alias
        if not node_id:
            raise ValueError("add-node requires --id or --alias")
        payload: dict[str, object] = {"id": node_id, "type": args.type, "config": json.loads(args.config)}
        if args.alias:
            payload["alias"] = args.alias
        return payload
    if args.edit_command == "add-edge":
        payload = {"from": args.from_, "to": args.to}
        if args.optional:
            payload["optional"] = True
        return payload
    if args.edit_command == "remove-edge":
        return {"from": args.from_, "to": args.to}
    raise ValueError(f"unknown dag edit command: {args.edit_command}")


def _client(args: argparse.Namespace) -> object:
    if args.client_command != "init":
        raise ValueError(f"unknown client command: {args.client_command}")
    target = Path.home() / ".edera"
    target.mkdir(parents=True, exist_ok=True)
    certs = _run_grpc(_grpc_client_init(args.server, args.common_name))
    (target / "client.crt").write_text(str(certs["client_cert_pem"]), encoding="utf-8")
    (target / "client.key").write_text(str(certs["client_key_pem"]), encoding="utf-8")
    (target / "ca.crt").write_text(str(certs["ca_cert_pem"]), encoding="utf-8")
    return {"configured": True, "server": args.server, "path": str(target / "client.crt")}


async def _grpc_client_init(server: str, common_name: str) -> dict[str, str]:
    client = GrpcClient(server, force_insecure=True)
    try:
        return await client.init_client(common_name)
    finally:
        await client.close()


def _handler_validate(path: Path) -> object:
    errors = validate_handler(path)
    if errors:
        raise ValueError("\n".join(errors))
    return {"ok": True}


def _run_grpc(coro):
    return asyncio.run(coro)


def _json_value(value: str) -> object:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _read_entity_yaml(path: Path) -> dict[str, object]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("entity YAML must be a mapping")
    type_name = data.get("type")
    attributes = data.get("attributes")
    if not isinstance(type_name, str) or not type_name:
        raise ValueError("entity YAML requires non-empty type")
    if "id" not in data or str(data["id"]) == "":
        raise ValueError("entity YAML requires non-empty id")
    if not isinstance(attributes, dict):
        raise ValueError("entity YAML requires attributes mapping")
    return {"type": type_name, "id": str(data["id"]), "attributes": attributes}


def _write_entity_yaml(path: Path, document: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _entity_document(entity: dict[str, object]) -> dict[str, object]:
    attributes = entity.get("attributes")
    if not isinstance(attributes, dict):
        raise ValueError("entity response missing attributes")
    return {
        "type": str(entity.get("type") or ""),
        "id": str(entity.get("id") or ""),
        "attributes": attributes,
    }


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


if __name__ == "__main__":
    main()
