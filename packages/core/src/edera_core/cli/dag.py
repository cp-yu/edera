from __future__ import annotations

import argparse
import json
from pathlib import Path

from edera_core.cli._common import (
    _local_page_arguments,
    _read_json_object,
    _watch_arguments,
    _write_json,
)
import edera_core.cli as _cli
from edera_core.cli._common import CommandHelp, _fmt_epilog

HELP = CommandHelp(
    description="Submit, watch, edit and inspect DAG runs (DAG 运行).",
    help_line="Submit and inspect DAG runs (DAG)",
    epilog=_fmt_epilog(
        "A DAG is the unit of execution; edit subcommands mutate a saved DAG definition.",
        [
            ("edera dag run my-dag", "start a new run"),
            ("edera dag status my-dag --watch", "watch run status"),
            ("edera dag retry my-dag --nodes node-1", "retry specific nodes"),
            ("edera dag edit my-dag add-node --type llm-analyze --alias n2", "mutate definition"),
        ],
    ),
    subcommands={
        "list": "List saved DAG definitions.",
        "show": "Show a saved DAG definition.",
        "create": "Create an empty DAG definition.",
        "save": "Replace a DAG definition from a YAML file.",
        "import": "Import a DAG definition from a YAML file (alias of save).",
        "export": "Export a DAG definition to a YAML file.",
        "runtime-status": "Show runtime status of one or all runs (--watch).",
        "run": "Start a new DAG run with optional input overrides.",
        "status": "Show status of the latest or a specific run (--watch).",
        "stop": "Stop a running DAG.",
        "retry": "Retry failed nodes of a DAG run.",
        "edit": "Edit a saved DAG definition (subcommands: add-node, add-edge, remove-edge).",
        "add-node": "Add a node to the DAG definition.",
        "add-edge": "Add an edge between two nodes.",
        "remove-edge": "Remove an edge between two nodes.",
    },
)


def add_parser(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="dag_command", required=True)
    sub = HELP.subcommands
    list_ = subparsers.add_parser("list", help=sub["list"])
    _local_page_arguments(list_)
    show = subparsers.add_parser("show", help=sub["show"])
    show.add_argument("dag_name", help="DAG name.")
    create = subparsers.add_parser("create", help=sub["create"])
    create.add_argument("dag_name", help="DAG name.")
    for command in ("save", "import"):
        item = subparsers.add_parser(command, help=sub[command])
        item.add_argument("dag_name", help="DAG name.")
        item.add_argument("--file", required=True, type=Path, help="YAML file with DAG definition.")
    export = subparsers.add_parser("export", help=sub["export"])
    export.add_argument("dag_name", help="DAG name.")
    export.add_argument("--file", required=True, type=Path, help="Output file path.")
    runtime_status = subparsers.add_parser("runtime-status", help=sub["runtime-status"])
    runtime_status.add_argument("--run-id", default="", help="Run ID (empty for all runs).")
    _watch_arguments(runtime_status)
    run = subparsers.add_parser("run", help=sub["run"])
    run.add_argument("dag_name", help="DAG name.")
    run.add_argument("--source-shared-inputs", default="", help="JSON object of shared inputs for all nodes.")
    run.add_argument("--node-inputs", default="", help="JSON object mapping node IDs to their inputs.")
    run.add_argument("--append-nodes", default="", help="Comma-separated node IDs to append.")
    status = subparsers.add_parser("status", help=sub["status"])
    status.add_argument("dag_name", help="DAG name.")
    _watch_arguments(status)
    stop = subparsers.add_parser("stop", help=sub["stop"])
    stop.add_argument("dag_name", help="DAG name.")
    stop.add_argument("--force", action="store_true", help="Force stop without graceful shutdown.")
    retry = subparsers.add_parser("retry", help=sub["retry"])
    retry.add_argument("dag_name", help="DAG name.")
    retry.add_argument("--run-id", default="", help="Run ID (defaults to latest).")
    retry.add_argument("--nodes", default="", help="Comma-separated node IDs to retry.")
    retry.add_argument("--mode", default="single", help="Retry strategy: single, cascade, or downstream (default: single).")
    retry.add_argument("--source-shared-inputs", default="", help="JSON object of shared inputs.")
    retry.add_argument("--node-inputs", default="", help="JSON object mapping node IDs to inputs.")
    retry.add_argument("--append-nodes", default="", help="Comma-separated node IDs to append.")
    edit = subparsers.add_parser("edit", help=sub["edit"])
    edit.add_argument("dag_name", help="DAG name.")
    edit_sub = edit.add_subparsers(dest="edit_command", required=True)
    add_node = edit_sub.add_parser("add-node", help=sub["add-node"])
    add_node.add_argument("--id", help="Node ID (defaults to alias).")
    add_node.add_argument("--alias", help="Node alias for referencing within the DAG.")
    add_node.add_argument("--type", required=True, help="Node type name.")
    add_node.add_argument("--config", default="{}", help="JSON object of node configuration.")
    add_edge = edit_sub.add_parser("add-edge", help=sub["add-edge"])
    add_edge.add_argument("--from", dest="from_", required=True, help="Source node alias.")
    add_edge.add_argument("--to", required=True, help="Target node alias.")
    add_edge.add_argument("--optional", action="store_true", help="Mark this edge as optional.")
    remove_edge = edit_sub.add_parser("remove-edge", help=sub["remove-edge"])
    remove_edge.add_argument("--from", dest="from_", required=True, help="Source node alias.")
    remove_edge.add_argument("--to", required=True, help="Target node alias.")


async def dispatch(args: argparse.Namespace) -> object:
    client = _cli.GrpcClient(args.server, identity=args.identity)
    try:
        if args.dag_command == "list":
            return await client.graph_list_dags()
        if args.dag_command == "show":
            return await client.graph_get_dag(args.dag_name)
        if args.dag_command == "create":
            return await client.graph_create_dag(args.dag_name)
        if args.dag_command in {"save", "import"}:
            return await client.graph_save_dag(args.dag_name, _read_json_object(args.file))
        if args.dag_command == "export":
            payload = await client.graph_get_dag(args.dag_name)
            _write_json(args.file, payload)
            return {"exported": args.dag_name, "file": str(args.file)}
        if args.dag_command == "runtime-status":
            return await client.graph_runtime_status(args.run_id)
        if args.dag_command == "status":
            return await client.dag_status(args.dag_name)
        if args.dag_command == "stop":
            return await client.dag_stop(args.dag_name, args.force)
        if args.dag_command == "retry":
            return await client.dag_retry(
                args.dag_name, args.run_id, _node_ids(args.nodes), args.mode,
                **_dag_temporary_inputs(args),
            )
        if args.dag_command == "edit":
            return await client.dag_edit(args.dag_name, args.edit_command, _dag_edit_payload(args))
        if args.dag_command == "run":
            return await client.dag_run(args.dag_name, **_dag_temporary_inputs(args))
    finally:
        await client.close()
    raise ValueError(f"unknown dag command: {args.dag_command}")


def _node_ids(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _optional_json(value: str) -> object | None:
    return json.loads(value) if value else None


def _dag_temporary_inputs(args: argparse.Namespace) -> dict[str, object]:
    return {
        "source_shared_inputs": _optional_json(args.source_shared_inputs),
        "node_inputs": _optional_json(args.node_inputs),
        "append_nodes": _node_ids(args.append_nodes) if args.append_nodes else None,
    }


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
