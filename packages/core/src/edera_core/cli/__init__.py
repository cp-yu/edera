from __future__ import annotations

import argparse
import asyncio
from edera_core.grpc_client import GrpcClient  # re-exported for test monkeypatch
from edera_core.cli.entity import _grpc_entity  # re-exported for test monkeypatch
from edera_core.handler_validator import validate_handler  # re-exported for test monkeypatch


# Re-exported for test compatibility — resolve at call time to avoid circular import
async def _grpc_relation(args):
    from edera_core.cli.relation import dispatch
    return await dispatch(args)
import importlib
import json
import os
import sys
import time
from pathlib import Path

import grpc
import yaml

from edera_core.cli._common import (
    _apply_output_page,
    _exit_error,
    _format_output,
    _normalize_global_output_arg,
    _run_grpc,
)
from edera_core.errors import ConfigError

COMMANDS: dict[str, tuple[str, str, str]] = {
    "entity":           ("edera_core.cli.entity",       "add_parser", "dispatch"),
    "relation":         ("edera_core.cli.relation",     "add_parser", "dispatch"),
    "entity-type":      ("edera_core.cli.entity_type",  "add_parser", "dispatch"),
    "node":             ("edera_core.cli.node",         "add_parser", "dispatch"),
    "node-type":        ("edera_core.cli.node_type",    "add_parser", "dispatch"),
    "skill":            ("edera_core.cli.skill",        "add_parser", "dispatch"),
    "dag":              ("edera_core.cli.dag",          "add_parser", "dispatch"),
    "event":            ("edera_core.cli.event",        "add_parser", "dispatch"),
    "system":           ("edera_core.cli.system",       "add_parser", "dispatch"),
    "client":           ("edera_core.cli.client",       "add_parser", "dispatch"),
    "config":           ("edera_core.cli.config",       "add_parser", "dispatch"),
    "query":            ("edera_core.cli.query",        "add_parser", "dispatch"),
    "source":           ("edera_core.cli.source",       "add_parser", "dispatch"),
    "handler":          ("edera_core.cli.handler",      "add_parser", "dispatch"),
    "extension":        ("edera_core.cli.extension",    "add_parser", "dispatch"),
    "handler-validate": ("edera_core.cli.handler_validate", "add_parser", "dispatch"),
}


def main() -> None:
    argv = _normalize_global_output_arg(sys.argv[1:])
    parser = argparse.ArgumentParser(
        prog="edera",
        description=(
            "Edera CLI — the unified entry point to the Edera control plane\n"
            "(Entity 原语 + DAG 执行模型的编排内核).\n\n"
            "Connects to a running `edera-server` over gRPC + mTLS and exposes\n"
            "every control capability (entities, DAGs, events, skills, ...)."
        ),
        epilog=(
            "EXAMPLES\n"
            "  edera entity list --type document    # list entities filtered by type\n"
            "  edera entity get doc-42 --output table    # render one entity as a table\n"
            "  EDERA_SERVER_ADDR=server.lan:9090 edera dag run my-dag    # run a DAG against a remote server\n"
            "  EDERA_IDENTITY=node:llm-analyze edera entity get stock:AAPL    # act as a specific node identity"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )
    connection = parser.add_argument_group("Connection")
    connection.add_argument(
        "--identity",
        default=os.environ.get("EDERA_IDENTITY", "human"),
        help="Caller identity sent to the server (env: EDERA_IDENTITY, default: human).",
    )
    connection.add_argument(
        "--server",
        default=os.environ.get("EDERA_SERVER_ADDR"),
        help="Server gRPC address host:port (env: EDERA_SERVER_ADDR).",
    )
    output_group = parser.add_argument_group("Output")
    output_group.add_argument(
        "--output",
        choices=["json", "yaml", "table"],
        default="json",
        help="Output format for results (default: json).",
    )
    common = parser.add_argument_group("Common")
    common.add_argument(
        "-h",
        "--help",
        action="help",
        default=argparse.SUPPRESS,
        help="show this help message and exit",
    )
    common.add_argument("--version", action="version", version="edera 0.1.0")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for cmd_name, (mod_path, add_fn, _) in COMMANDS.items():
        mod = importlib.import_module(mod_path)
        add_parser = getattr(mod, add_fn)
        add_parser(subparsers.add_parser(cmd_name, **_command_kwargs(cmd_name)))
    args = parser.parse_args(argv)
    try:
        if _should_inject_human_cert_env(args):
            _inject_human_cert_env()
        if _is_repeating(args):
            _dispatch_repeating(args)
            result = None
        else:
            result = _dispatch(args)
    except PermissionError as exc:
        _exit_error(parser, "Permission denied", "PermissionError", str(exc))
    except grpc.RpcError as exc:
        detail = exc.details() if hasattr(exc, "details") else str(exc)
        _exit_error(parser, "gRPC error", type(exc).__name__, str(detail))
    except (ConfigError, ValueError, FileNotFoundError, yaml.YAMLError) as exc:
        _exit_error(parser, str(exc), type(exc).__name__, str(exc))
    if result is not None:
        result = _apply_output_page(result, args)
        print(_format_output(result, args.output))


def _command_kwargs(name: str) -> dict[str, object]:
    mod_path = COMMANDS[name][0]
    mod = importlib.import_module(mod_path)
    help_meta = mod.HELP
    return {
        "help": help_meta.help_line,
        "description": help_meta.description,
        "epilog": help_meta.epilog,
        "formatter_class": argparse.RawDescriptionHelpFormatter,
    }


def _dispatch(args: argparse.Namespace) -> object:
    mod_path, _, dispatch_fn_name = COMMANDS[args.command]
    mod = importlib.import_module(mod_path)
    dispatch_fn = getattr(mod, dispatch_fn_name)
    if asyncio.iscoroutinefunction(dispatch_fn):
        return _run_grpc(dispatch_fn(args))
    return dispatch_fn(args)


def _is_repeating(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "watch", False) or getattr(args, "tail", False))


def _dispatch_repeating(args: argparse.Namespace) -> None:
    seen: set[str] = set()
    watch_count = getattr(args, "watch_count", None)
    iteration = 0
    while watch_count is None or iteration < watch_count:
        result = _dispatch(args)
        if getattr(args, "tail", False):
            result, has_items = _dedupe_tail_result(result, seen)
            if has_items:
                result = _apply_output_page(result, args)
                print(_format_output(result, args.output), flush=True)
        else:
            result = _apply_output_page(result, args)
            print(_format_output(result, args.output), flush=True)
        iteration += 1
        if watch_count is not None and iteration >= watch_count:
            break
        interval = getattr(args, "interval", 1.0)
        if interval > 0:
            time.sleep(interval)


def _dedupe_tail_result(result: object, seen: set[str]) -> tuple[object, bool]:
    if isinstance(result, dict):
        logs = result.get("logs")
        if isinstance(logs, list):
            new_logs = _new_tail_items(logs, seen)
            return {**result, "logs": new_logs}, bool(new_logs)
        single_list = _extract_single_list_value(result)
        if single_list is not None:
            key = next(k for k, v in result.items() if v is single_list)
            new_items = _new_tail_items(single_list, seen)
            return {**result, key: new_items}, bool(new_items)
    if isinstance(result, list):
        new_items = _new_tail_items(result, seen)
        return new_items, bool(new_items)
    key = _stable_tail_key(result)
    if key in seen:
        return result, False
    seen.add(key)
    return result, True


def _new_tail_items(items: list[object], seen: set[str]) -> list[object]:
    result = []
    for item in items:
        key = _stable_tail_key(item)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _stable_tail_key(item: object) -> str:
    return json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)


def _extract_single_list_value(result: dict[str, object]) -> list[object] | None:
    list_values = [(key, value) for key, value in result.items() if isinstance(value, list)]
    if len(list_values) == 1:
        return list_values[0][1]
    return None


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


if __name__ == "__main__":
    main()
