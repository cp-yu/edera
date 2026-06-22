from __future__ import annotations

import argparse
import json
from pathlib import Path

from edera_core.cli._common import _tail_arguments
import edera_core.cli as _cli
from edera_core.cli._common import CommandHelp, _fmt_epilog

HELP = CommandHelp(
    description="Operate on DAG node instances (节点实例) during a run.",
    help_line="Operate on DAG node instances (节点)",
    epilog=_fmt_epilog(
        "Node subcommands act on a single node instance within a DAG run.",
        [
            ("edera node status my-dag.node-1", "show runtime status"),
            ("edera node resume my-dag.node-1 --prompt retry", "resume a paused node"),
            ("edera node logs my-dag.node-1 --run-id r-001 --tail", "tail node logs"),
        ],
    ),
    subcommands={
        "status": "Show runtime status of a node instance.",
        "stop": "Stop a node instance.",
        "resume": "Resume a paused node instance with an optional prompt.",
        "output": "Read or write a node's output artifact.",
        "logs": "Read node logs (--tail to follow).",
    },
)


def add_parser(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="node_command", required=True)
    sub = HELP.subcommands
    status = subparsers.add_parser("status", help=sub["status"])
    status.add_argument("node_id", help="Node reference <dag>.<alias>.")
    stop = subparsers.add_parser("stop", help=sub["stop"])
    stop.add_argument("node_id", help="Node reference <dag>.<alias>.")
    resume = subparsers.add_parser("resume", help=sub["resume"])
    resume.add_argument("node_id", help="Node reference <dag>.<alias>.")
    resume.add_argument("--prompt", default="", help="Prompt text to inject on resume.")
    resume.add_argument("--run-id", help="Run ID (defaults to latest).")
    output = subparsers.add_parser("output", help=sub["output"])
    output.add_argument("output_args", nargs="*", help="Subcommand: export <node-id> [--out PATH] | query [node-id].")
    output.add_argument("--run-id", help="Run ID.")
    output.add_argument("--node", help="Node ID for export target.")
    output.add_argument("--out", type=Path, help="Output file path for export.")
    logs = subparsers.add_parser("logs", help=sub["logs"])
    logs.add_argument("node_id", help="Node reference <dag>.<alias>.")
    logs.add_argument("--run-id", required=True, help="Run ID.")
    _tail_arguments(logs)


async def dispatch(args: argparse.Namespace) -> object:
    if args.node_command == "output" and args.output_args[:1] == ["export"] and args.out is None:
        raise ValueError("Missing required parameter: --out")
    client = _cli.GrpcClient(args.server, identity=args.identity)
    try:
        if args.node_command == "status":
            return await client.node_status(args.node_id)
        if args.node_command == "stop":
            return await client.node_stop(args.node_id)
        if args.node_command == "resume":
            return await client.node_resume(args.node_id, args.run_id, args.prompt)
        if args.node_command == "output":
            if args.output_args[:1] == ["export"]:
                node_id = args.node or (args.output_args[1] if len(args.output_args) > 1 else None)
                if not node_id:
                    raise ValueError("node_id is required")
                outputs = await client.node_output(node_id, args.run_id)
                payloads = _node_output_payloads(outputs)
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_text(json.dumps(payloads, ensure_ascii=False, default=str), encoding="utf-8")
                return {"exported": node_id, "run_id": args.run_id, "file": str(args.out), "entries": len(payloads)}
            node_id = args.output_args[1] if args.output_args[:1] == ["query"] and len(args.output_args) > 1 else None
            node_id = node_id or (args.output_args[0] if args.output_args else None)
            if not node_id:
                raise ValueError("node_id is required")
            return await client.node_output(node_id, args.run_id)
        if args.node_command == "logs":
            return await client.query_node_logs(args.node_id, args.run_id)
    finally:
        await client.close()
    raise ValueError(f"unknown node command: {args.node_command}")


def _node_output_payloads(outputs: object) -> list[object]:
    records = outputs if isinstance(outputs, list) else [outputs]
    payloads: list[object] = []
    for record in records:
        if isinstance(record, dict):
            attributes = record.get("attributes")
            if isinstance(attributes, dict) and "payload" in attributes:
                payloads.append(attributes["payload"])
                continue
            if "payload" in record:
                payloads.append(record["payload"])
                continue
        payloads.append(record)
    return payloads
