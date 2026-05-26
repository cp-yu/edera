from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any, Coroutine
from urllib import request
from urllib.error import HTTPError, URLError

from stockimformation_core.config.entities import EntityStore, can_read, can_write, field_permission
from stockimformation_core.config.loader import load_app_config
from stockimformation_core.config.schema import AppConfig, EntityConfig, entity_ref
from stockimformation_core.errors import ConfigError
from stockimformation_core.grpc_client import RigGrpcClient, bootstrap_address
from stockimformation_core.storage import create_engine, init_db, session_factory
from stockimformation_core.storage.repository import query_node_output_entities


def main() -> None:
    parser = argparse.ArgumentParser(prog="rig")
    parser.add_argument("--identity", default=os.environ.get("RIG_IDENTITY", "human"))
    parser.add_argument("--config-dir", default="config")
    parser.add_argument("--api-url", default=os.environ.get("RIG_API_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--daemon-addr", default=os.environ.get("RIG_DAEMON_ADDR"))
    parser.add_argument("--version", action="version", version="rig 0.1.0")
    subparsers = parser.add_subparsers(dest="command", required=True)
    _entity_parser(subparsers.add_parser("entity"))
    _node_parser(subparsers.add_parser("node"))
    _dag_parser(subparsers.add_parser("dag"))
    _client_parser(subparsers.add_parser("client"))
    args = parser.parse_args()
    try:
        result = _dispatch(args)
    except PermissionError as exc:
        parser.exit(1, f"Permission denied: {exc}\n")
    except (ConfigError, ValueError, HTTPError, URLError) as exc:
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
    output.add_argument("node_id")
    output.add_argument("--cycle-id")


def _dag_parser(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="dag_command", required=True)
    trigger = subparsers.add_parser("trigger")
    trigger.add_argument("dag_name")
    trigger.add_argument("--payload", default="{}")
    status = subparsers.add_parser("status")
    status.add_argument("dag_name")
    edit = subparsers.add_parser("edit")
    edit.add_argument("dag_name")
    edit_sub = edit.add_subparsers(dest="edit_command", required=True)
    add_node = edit_sub.add_parser("add-node")
    add_node.add_argument("--id", required=True)
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
    init.add_argument("--common-name", default=os.environ.get("RIG_IDENTITY", "human:default"))


def _dispatch(args: argparse.Namespace) -> object:
    if args.command == "entity":
        return _entity(args)
    if args.command == "node":
        return _node(args)
    if args.command == "dag":
        return _dag(args)
    if args.command == "client":
        return _client(args)
    raise ValueError(f"unknown command: {args.command}")


def _entity(args: argparse.Namespace) -> object:
    if _use_grpc(args):
        return _run_grpc(_grpc_entity(args))
    app = load_app_config(Path(args.config_dir))
    store = EntityStore(app.entities, app.entity_types, app.entity_relations, Path(args.config_dir) / "entities.yaml")
    permissions = _identity_permissions(args.identity, app.dags)
    if args.entity_command == "get":
        return _entity_payload(store, _readable_entity(args.identity, store, permissions, store.resolve(args.ref)))
    if args.entity_command == "create":
        attributes = json.loads(args.attributes)
        if not isinstance(attributes, dict):
            raise ValueError("attributes must be a JSON object")
        return _entity_payload(store, store.create(args.type, attributes))
    if args.entity_command == "list":
        return [_entity_payload(store, entity) for entity in _readable_entities(args.identity, store, permissions, store.query(args.type))]
    if args.entity_command == "update":
        entity = store.resolve(args.ref)
        _check_write(args.identity, store, permissions, entity, args.field)
        updated = entity.model_copy(update={"attributes": {**entity.attributes, args.field: _json_value(args.value)}})
        return _entity_payload(store, store.save(updated, permissions))
    if args.entity_command == "query":
        return [_entity_payload(store, entity) for entity in _query(app, store, args.identity, permissions, args.expression)]
    if args.entity_command == "delete":
        return {"deleted": True, "relations_removed": store.delete(store.resolve(args.ref).id)}
    raise ValueError(f"unknown entity command: {args.entity_command}")


def _node(args: argparse.Namespace) -> object:
    if _use_grpc(args):
        return _run_grpc(_grpc_node(args))
    if args.node_command == "status":
        return _post(args.api_url, f"/api/node/{args.node_id}/status", None, method="GET")
    if args.node_command == "stop":
        return _post(args.api_url, f"/api/node/{args.node_id}/stop", {})
    if args.node_command == "resume":
        payload: dict[str, object] = {"prompt": args.prompt}
        if args.cycle_id:
            payload["cycle_id"] = args.cycle_id
        return _post(args.api_url, f"/api/node/{args.node_id}/resume", payload)
    if args.node_command == "output":
        expression = f"type=node-output AND node_id={args.node_id}"
        if args.cycle_id:
            expression = f"{expression} AND cycle_id={args.cycle_id}"
        args.entity_command = "query"
        args.expression = expression
        return _entity(args)
    raise ValueError(f"unknown node command: {args.node_command}")


def _dag(args: argparse.Namespace) -> object:
    if _use_grpc(args):
        return _run_grpc(_grpc_dag(args))
    if args.dag_command == "status":
        return _post(args.api_url, f"/api/pipeline/dag/{args.dag_name}/status", None, method="GET")
    if args.dag_command == "edit":
        return _edit_dag(Path(args.config_dir), args)
    payload = json.loads(args.payload)
    return _post(args.api_url, f"/api/pipeline/dag/{args.dag_name}/run", {"payload": payload})


def _edit_dag(config_dir: Path, args: argparse.Namespace) -> object:
    import yaml

    path = config_dir / "dags" / f"{args.dag_name}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    attrs = data.get("attributes") if data.get("type") == "dag" and isinstance(data.get("attributes"), dict) else data
    nodes = attrs.setdefault("nodes", [])
    edges = attrs.setdefault("edges", [])
    if args.edit_command == "add-node":
        nodes.append({"id": args.id, "type": args.type, "config": json.loads(args.config)})
    elif args.edit_command == "add-edge":
        edge = {"from": args.from_, "to": args.to}
        if args.optional:
            edge["optional"] = True
        edges.append(edge)
    elif args.edit_command == "remove-edge":
        attrs["edges"] = [edge for edge in edges if not (edge.get("from") == args.from_ and edge.get("to") == args.to)]
    else:
        raise ValueError(f"unknown dag edit command: {args.edit_command}")
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return {"updated": True, "dag": args.dag_name}


def _client(args: argparse.Namespace) -> object:
    if args.client_command != "init":
        raise ValueError(f"unknown client command: {args.client_command}")
    target = Path.home() / ".rig"
    target.mkdir(parents=True, exist_ok=True)
    certs = _run_grpc(_grpc_client_init(args.server, args.common_name))
    (target / "client.crt").write_text(str(certs["client_cert_pem"]), encoding="utf-8")
    (target / "client.key").write_text(str(certs["client_key_pem"]), encoding="utf-8")
    (target / "ca.crt").write_text(str(certs["ca_cert_pem"]), encoding="utf-8")
    (target / "config.json").write_text(json.dumps({"server": args.server}, ensure_ascii=False), encoding="utf-8")
    return {"configured": True, "server": args.server, "path": str(target / "config.json")}


def _use_grpc(args: argparse.Namespace) -> bool:
    return bool(args.daemon_addr or (Path.home() / ".rig" / "config.json").exists())


async def _grpc_entity(args: argparse.Namespace) -> object:
    client = RigGrpcClient(args.daemon_addr)
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
            return await client.entity_query(args.expression)
        if args.entity_command == "delete":
            return await client.entity_delete(args.ref)
    finally:
        await client.close()
    raise ValueError(f"unknown entity command: {args.entity_command}")


async def _grpc_node(args: argparse.Namespace) -> object:
    client = RigGrpcClient(args.daemon_addr)
    try:
        if args.node_command == "status":
            return await client.node_status(args.node_id)
        if args.node_command == "stop":
            return await client.node_stop(args.node_id)
        if args.node_command == "resume":
            return await client.node_resume(args.node_id, args.cycle_id, args.prompt)
        if args.node_command == "output":
            return await client.node_output(args.node_id, args.cycle_id)
    finally:
        await client.close()
    raise ValueError(f"unknown node command: {args.node_command}")


async def _grpc_dag(args: argparse.Namespace) -> object:
    client = RigGrpcClient(args.daemon_addr)
    try:
        if args.dag_command == "status":
            return await client.dag_status(args.dag_name)
        if args.dag_command == "edit":
            return await client.dag_edit(args.dag_name, args.edit_command, _dag_edit_payload(args))
        payload = json.loads(args.payload)
        return await client.dag_trigger(args.dag_name, payload)
    finally:
        await client.close()


def _dag_edit_payload(args: argparse.Namespace) -> dict[str, object]:
    if args.edit_command == "add-node":
        return {"id": args.id, "type": args.type, "config": json.loads(args.config)}
    if args.edit_command == "add-edge":
        payload: dict[str, object] = {"from": args.from_, "to": args.to}
        if args.optional:
            payload["optional"] = True
        return payload
    if args.edit_command == "remove-edge":
        return {"from": args.from_, "to": args.to}
    raise ValueError(f"unknown dag edit command: {args.edit_command}")


async def _grpc_client_init(server: str, common_name: str) -> dict[str, str]:
    client = RigGrpcClient(bootstrap_address(server), allow_insecure=True)
    try:
        return await client.init_client(common_name)
    finally:
        await client.close()


def _run_grpc(coro):
    return asyncio.run(coro)


def _post(api_url: str, path: str, payload: object, method: str = "POST") -> object:
    body = None if payload is None else json.dumps(payload).encode()
    req = request.Request(
        f"{api_url.rstrip('/')}{path}",
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode())


def _identity_permissions(identity: str, dags: dict[str, Any]) -> dict[str, Any] | None:
    if identity == "human":
        return None
    if not identity.startswith("node:"):
        return {}
    node_id = identity.removeprefix("node:")
    for dag in dags.values():
        for instance in dag.nodes:
            if instance.id == node_id or instance.alias == node_id or instance.type == node_id:
                permissions = instance.config.get("entity_permissions")
                return permissions if isinstance(permissions, dict) else {}
    return {}


def _check_write(
    identity: str,
    store: EntityStore,
    permissions: dict[str, Any] | None,
    entity: EntityConfig,
    field: str,
) -> None:
    if identity == "human":
        return
    overrides = permissions.get(entity.type) if isinstance(permissions, dict) else None
    allowed = can_write(field_permission(store.entity_types[entity.type], field, overrides if isinstance(overrides, dict) else None))
    if not allowed:
        raise PermissionError(f"{identity} cannot write {entity.type}.{field}")


def _query(
    app: AppConfig,
    store: EntityStore,
    identity: str,
    permissions: dict[str, Any] | None,
    expression: str,
) -> list[EntityConfig]:
    parts = [part.strip() for part in expression.split("AND")]
    relation_filters = _relation_filters(parts)
    if relation_filters:
        return _readable_entities(identity, store, permissions, _query_relations(store, relation_filters))
    node_output_filters = _node_output_filters(parts)
    if node_output_filters is not None:
        return _readable_entities(identity, store, permissions, asyncio_run(_query_node_outputs(app, node_output_filters)))
    result = store.query()
    for part in parts:
        if part.startswith("type="):
            wanted = part.removeprefix("type=").strip()
            result = [entity for entity in result if entity.type == wanted]
        elif ">" in part:
            field, raw = [item.strip() for item in part.split(">", 1)]
            threshold = float(raw)
            result = [entity for entity in result if float(entity.attributes.get(field, 0)) > threshold]
        elif "=" in part:
            field, raw = [item.strip() for item in part.split("=", 1)]
            result = [entity for entity in result if str(entity.attributes.get(field)) == raw]
    return _readable_entities(identity, store, permissions, result)


def _readable_entities(
    identity: str,
    store: EntityStore,
    permissions: dict[str, Any] | None,
    entities: list[EntityConfig],
) -> list[EntityConfig]:
    return [_readable_entity(identity, store, permissions, entity) for entity in entities]


def _readable_entity(
    identity: str,
    store: EntityStore,
    permissions: dict[str, Any] | None,
    entity: EntityConfig,
) -> EntityConfig:
    if identity == "human":
        return entity
    overrides = permissions.get(entity.type) if isinstance(permissions, dict) else None
    entity_type = store.entity_types.get(entity.type)
    if entity_type is None:
        return entity
    filtered = {
        field: value
        for field, value in entity.attributes.items()
        if can_read(field_permission(entity_type, field, overrides if isinstance(overrides, dict) else None))
    }
    return entity.model_copy(update={"attributes": filtered})


def _relation_filters(parts: list[str]) -> dict[str, str]:
    filters: dict[str, str] = {}
    for part in parts:
        if "=" not in part:
            continue
        key, value = [item.strip() for item in part.split("=", 1)]
        if key == "relation_type":
            filters["type"] = value
        elif key in {"from", "to"}:
            filters[key] = value
    return filters


def _query_relations(store: EntityStore, filters: dict[str, str]) -> list[EntityConfig]:
    entities: list[EntityConfig] = []
    for relation in store.relations.relations:
        if filters.get("type") and relation.type != filters["type"]:
            continue
        refs = relation.entities
        if filters.get("from") and filters["from"] not in refs:
            continue
        if filters.get("to") and filters["to"] not in refs:
            continue
        entities.append(
            EntityConfig(
                id=relation.id,
                type="relation",
                attributes={
                    "from": refs[0] if refs else "",
                    "to": refs[1] if len(refs) > 1 else "",
                    "relation_type": relation.type,
                    "entities": refs,
                    "metadata": relation.metadata,
                },
            )
        )
    return entities


def _node_output_filters(parts: list[str]) -> dict[str, str] | None:
    filters: dict[str, str] = {}
    for part in parts:
        if "=" not in part:
            continue
        key, value = [item.strip() for item in part.split("=", 1)]
        if key == "type":
            filters["type"] = value
        elif key in {"cycle_id", "node_id"}:
            filters[key] = value
    return filters if filters.get("type") == "node-output" or "node_id" in filters or "cycle_id" in filters else None


async def _query_node_outputs(app: AppConfig, filters: dict[str, str]) -> list[EntityConfig]:
    engine = create_engine(app.system.database_url)
    try:
        await init_db(engine)
        factory = session_factory(engine)
        async with factory() as session:
            return await query_node_output_entities(
                session,
                None if filters.get("type") == "node-output" else filters.get("type"),
                filters.get("cycle_id"),
                filters.get("node_id"),
                None,
                100,
            )
    finally:
        await engine.dispose()


def asyncio_run(coro: Coroutine[Any, Any, list[EntityConfig]]) -> list[EntityConfig]:
    import asyncio

    return asyncio.run(coro)


def _entity_payload(store: EntityStore, entity: EntityConfig) -> dict[str, object]:
    try:
        ref = entity_ref(entity, store.entity_types)
    except (KeyError, ValueError):
        ref = entity.id
    return {"ref": ref, **entity.model_dump(mode="json")}


def _json_value(value: str) -> object:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


if __name__ == "__main__":
    main()
