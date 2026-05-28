from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

import grpc

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
    _node_parser(subparsers.add_parser("node"))
    _dag_parser(subparsers.add_parser("dag"))
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
    except (ConfigError, ValueError, FileNotFoundError) as exc:
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


def _node_parser(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="node_command", required=True)
    status = subparsers.add_parser("status")
    status.add_argument("node_id")
    stop = subparsers.add_parser("stop")
    stop.add_argument("node_id")
    resume = subparsers.add_parser("resume")
    resume.add_argument("node_id")
    resume.add_argument("--prompt", default="")
    resume.add_argument("--cycle-id")
    output = subparsers.add_parser("output")
    output.add_argument("output_args", nargs="*")
    output.add_argument("--cycle-id")


def _dag_parser(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="dag_command", required=True)
    trigger = subparsers.add_parser("trigger")
    trigger.add_argument("dag_name")
    trigger.add_argument("--payload", default="{}")
    trigger.add_argument("--input", action="append", default=[])
    status = subparsers.add_parser("status")
    status.add_argument("dag_name")
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


def _client_parser(parser: argparse.ArgumentParser) -> None:
    client_sub = parser.add_subparsers(dest="client_command", required=True)
    init = client_sub.add_parser("init")
    init.add_argument("--server", required=True)
    init.add_argument("--common-name", default=os.environ.get("EDERA_IDENTITY", "human:default"))


def _dispatch(args: argparse.Namespace) -> object:
    if args.command == "entity":
        return _run_grpc(_grpc_entity(args))
    if args.command == "node":
        return _run_grpc(_grpc_node(args))
    if args.command == "dag":
        return _run_grpc(_grpc_dag(args))
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
    client = GrpcClient(args.server, identity=args.identity)
    try:
        if args.entity_command == "get":
            return await client.entity_get(args.ref)
        if args.entity_command == "create":
            attributes = json.loads(args.attributes)
            if not isinstance(attributes, dict):
                raise ValueError("attributes must be a JSON object")
            return await client.entity_create(args.type, attributes)
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


async def _grpc_node(args: argparse.Namespace) -> object:
    client = GrpcClient(args.server, identity=args.identity)
    try:
        if args.node_command == "status":
            return await client.node_status(args.node_id)
        if args.node_command == "stop":
            return await client.node_stop(args.node_id)
        if args.node_command == "resume":
            return await client.node_resume(args.node_id, args.cycle_id, args.prompt)
        if args.node_command == "output":
            node_id = args.output_args[1] if args.output_args[:1] == ["query"] and len(args.output_args) > 1 else None
            node_id = node_id or (args.output_args[0] if args.output_args else None)
            if not node_id:
                raise ValueError("node_id is required")
            return await client.node_output(node_id, args.cycle_id)
    finally:
        await client.close()
    raise ValueError(f"unknown node command: {args.node_command}")


async def _grpc_dag(args: argparse.Namespace) -> object:
    client = GrpcClient(args.server, identity=args.identity)
    try:
        if args.dag_command == "status":
            return await client.dag_status(args.dag_name)
        if args.dag_command == "edit":
            return await client.dag_edit(args.dag_name, args.edit_command, _dag_edit_payload(args))
        return await client.dag_trigger(args.dag_name, _dag_trigger_payload(args))
    finally:
        await client.close()


def _dag_trigger_payload(args: argparse.Namespace) -> object:
    if args.input:
        payload: dict[str, str] = {}
        for item in args.input:
            key, sep, value = item.partition("=")
            if not sep or not key:
                raise ValueError("--input must be key=value")
            payload[key] = value
        return payload
    return json.loads(args.payload)


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


if __name__ == "__main__":
    main()
