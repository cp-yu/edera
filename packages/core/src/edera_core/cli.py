from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
import tarfile
import tempfile
import time
from pathlib import Path

import grpc
import yaml

from edera_core.cli_help import COMMANDS, TOP_DESCRIPTION, TOP_EPILOG
from edera_core.config.loader import load_system_config
from edera_core.errors import ConfigError
from edera_core.grpc_client import GrpcClient
from edera_core.handler_validator import validate_handler


def main() -> None:
    argv = _normalize_global_output_arg(sys.argv[1:])
    parser = argparse.ArgumentParser(
        prog="edera",
        description=TOP_DESCRIPTION,
        epilog=TOP_EPILOG,
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
    _entity_parser(subparsers.add_parser("entity", **_command_kwargs("entity")))
    _relation_parser(subparsers.add_parser("relation", **_command_kwargs("relation")))
    _entity_type_parser(subparsers.add_parser("entity-type", **_command_kwargs("entity-type")))
    _node_parser(subparsers.add_parser("node", **_command_kwargs("node")))
    _node_type_parser(subparsers.add_parser("node-type", **_command_kwargs("node-type")))
    _skill_parser(subparsers.add_parser("skill", **_command_kwargs("skill")))
    _dag_parser(subparsers.add_parser("dag", **_command_kwargs("dag")))
    _event_parser(subparsers.add_parser("event", **_command_kwargs("event")))
    _system_parser(subparsers.add_parser("system", **_command_kwargs("system")))
    _client_parser(subparsers.add_parser("client", **_command_kwargs("client")))
    _config_parser(subparsers.add_parser("config", **_command_kwargs("config")))
    _query_parser(subparsers.add_parser("query", **_command_kwargs("query")))
    _source_parser(subparsers.add_parser("source", **_command_kwargs("source")))
    _handler_parser(subparsers.add_parser("handler", **_command_kwargs("handler")))
    _extension_parser(subparsers.add_parser("extension", **_command_kwargs("extension")))
    handler_validate = subparsers.add_parser("handler-validate", **_command_kwargs("handler-validate"))
    handler_validate.add_argument("path", type=Path)
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
    help_meta = COMMANDS[name]
    return {
        "help": help_meta.help_line,
        "description": help_meta.description,
        "epilog": help_meta.epilog,
        "formatter_class": argparse.RawDescriptionHelpFormatter,
    }


def _normalize_global_output_arg(argv: list[str]) -> list[str]:
    output = "json"
    cleaned: list[str] = []
    index = 0
    while index < len(argv):
        item = argv[index]
        if item == "--output":
            if index + 1 >= len(argv):
                return argv
            output = argv[index + 1]
            index += 2
            continue
        if item.startswith("--output="):
            output = item.partition("=")[2]
            index += 1
            continue
        cleaned.append(item)
        index += 1
    return ["--output", output, *cleaned]


def _exit_error(parser: argparse.ArgumentParser, error: str, type_name: str, detail: str) -> None:
    parser.exit(1, json.dumps({"error": error, "type": type_name, "detail": detail}, ensure_ascii=False) + "\n")


def _format_output(result: object, output: str) -> str:
    if output == "json":
        return json.dumps(result, ensure_ascii=False, default=str)
    if output == "yaml":
        return yaml.safe_dump(result, allow_unicode=True, sort_keys=False).rstrip()
    if output == "table":
        return _format_table(result)
    raise ValueError(f"invalid output mode: {output}")


def _format_table(result: object) -> str:
    rows = _table_rows(result)
    if not rows:
        return ""
    keys = sorted({key for row in rows for key in row})
    rendered = [{key: _table_cell(row.get(key, "")) for key in keys} for row in rows]
    widths = {key: max(len(key), *(len(row[key]) for row in rendered)) for key in keys}
    header = "  ".join(key.ljust(widths[key]) for key in keys)
    separator = "  ".join("-" * widths[key] for key in keys)
    body = ["  ".join(row[key].ljust(widths[key]) for key in keys) for row in rendered]
    return "\n".join([header, separator, *body])


def _table_rows(result: object) -> list[dict[str, object]]:
    if isinstance(result, list):
        return [item if isinstance(item, dict) else {"value": item} for item in result]
    if isinstance(result, dict):
        single_list = _extract_single_list_value(result)
        if single_list is not None:
            return _table_rows(single_list)
        return [result]
    return [{"value": result}]


def _extract_single_list_value(result: dict[str, object]) -> list[object] | None:
    list_values = [(key, value) for key, value in result.items() if isinstance(value, list)]
    if len(list_values) == 1:
        return list_values[0][1]
    return None


def _table_cell(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


def _watch_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--watch-count", type=int)


def _tail_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--tail", action="store_true")
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--watch-count", type=int)


def _offset_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--offset", type=int, default=0)


def _local_page_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--limit", type=int)
    _offset_argument(parser)


def _entity_parser(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="entity_command", required=True)
    sub = COMMANDS["entity"].subcommands
    get = subparsers.add_parser("get", help=sub["get"])
    get.add_argument("ref", help="Entity reference in <type>:<id> form.")
    show = subparsers.add_parser("show", help=sub["show"])
    show.add_argument("ref", help="Entity reference in <type>:<id> form.")
    create = subparsers.add_parser("create", help=sub["create"])
    create.add_argument("--type", required=True)
    create.add_argument("--id", default="")
    create.add_argument("--attributes")
    import_ = subparsers.add_parser("import", help=sub["import"])
    import_.add_argument("path", nargs="?", type=Path)
    import_.add_argument("--file", type=Path)
    import_.add_argument("--type")
    export = subparsers.add_parser("export", help=sub["export"])
    export.add_argument("ref", nargs="?")
    export.add_argument("-o", "--file", required=True, type=Path)
    export.add_argument("--type")
    template = subparsers.add_parser("template", help=sub["template"])
    template.add_argument("--type", required=True)
    template.add_argument("--file", required=True, type=Path)
    list_ = subparsers.add_parser("list", help=sub["list"])
    list_.add_argument("--type")
    list_.add_argument("--filter", action="append", default=[])
    update = subparsers.add_parser("update", help=sub["update"])
    update.add_argument("ref")
    update.add_argument("--field")
    update.add_argument("--value")
    update.add_argument("--attributes")
    query = subparsers.add_parser("query", help=sub["query"])
    query.add_argument("expression")
    delete = subparsers.add_parser("delete", help=sub["delete"])
    delete.add_argument("ref")
    delete.add_argument("--force", action="store_true")


def _relation_parser(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="relation_command", required=True)
    sub = COMMANDS["relation"].subcommands
    list_ = subparsers.add_parser("list", help=sub["list"])
    list_.add_argument("--from", dest="from_")
    list_.add_argument("--to")
    list_.add_argument("--type")
    create = subparsers.add_parser("create", help=sub["create"])
    create.add_argument("--from", dest="from_", required=True)
    create.add_argument("--to", required=True)
    create.add_argument("--type", required=True)
    create.add_argument("--metadata", default="{}")
    delete = subparsers.add_parser("delete", help=sub["delete"])
    delete.add_argument("id")
    import_ = subparsers.add_parser("import", help=sub["import"])
    import_.add_argument("path", nargs="?", type=Path)
    import_.add_argument("--file", type=Path)
    export = subparsers.add_parser("export", help=sub["export"])
    export.add_argument("-o", "--file", required=True, type=Path)


def _entity_type_parser(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="entity_type_command", required=True)
    materialize = subparsers.add_parser("materialize", help=COMMANDS["entity-type"].subcommands["materialize"])
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
    sub = COMMANDS["node"].subcommands
    status = subparsers.add_parser("status", help=sub["status"])
    status.add_argument("node_id")
    stop = subparsers.add_parser("stop", help=sub["stop"])
    stop.add_argument("node_id")
    resume = subparsers.add_parser("resume", help=sub["resume"])
    resume.add_argument("node_id")
    resume.add_argument("--prompt", default="")
    resume.add_argument("--run-id")
    output = subparsers.add_parser("output", help=sub["output"])
    output.add_argument("output_args", nargs="*")
    output.add_argument("--run-id")
    output.add_argument("--node")
    output.add_argument("--out", type=Path)
    logs = subparsers.add_parser("logs", help=sub["logs"])
    logs.add_argument("node_id")
    logs.add_argument("--run-id", required=True)
    _tail_arguments(logs)


def _node_type_parser(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="node_type_command", required=True)
    sub = COMMANDS["node-type"].subcommands
    subparsers.add_parser("list", help=sub["list"])
    show = subparsers.add_parser("show", help=sub["show"])
    show.add_argument("name")
    for command in ("create", "save"):
        item = subparsers.add_parser(command, help=sub[command])
        item.add_argument("name")
        item.add_argument("--file", required=True, type=Path)
    delete = subparsers.add_parser("delete", help=sub["delete"])
    delete.add_argument("name")


def _skill_parser(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="skill_command", required=True)
    sub = COMMANDS["skill"].subcommands
    subparsers.add_parser("list", help=sub["list"])
    show = subparsers.add_parser("show", help=sub["show"])
    show.add_argument("name")
    create = subparsers.add_parser("create", help=sub["create"])
    create.add_argument("--from-dir", required=True, type=Path)
    update = subparsers.add_parser("update", help=sub["update"])
    update.add_argument("name")
    update.add_argument("--from-dir", required=True, type=Path)
    import_dir = subparsers.add_parser("import-dir", help=sub["import-dir"])
    import_dir.add_argument("path", type=Path)
    import_batch = subparsers.add_parser("import-batch", help=sub["import-batch"])
    import_batch.add_argument("path", type=Path)
    export = subparsers.add_parser("export", help=sub["export"])
    export.add_argument("name")
    export.add_argument("-o", "--output-dir", required=True, type=Path)
    delete = subparsers.add_parser("delete", help=sub["delete"])
    delete.add_argument("name")


def _dag_parser(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="dag_command", required=True)
    sub = COMMANDS["dag"].subcommands
    list_ = subparsers.add_parser("list", help=sub["list"])
    _local_page_arguments(list_)
    show = subparsers.add_parser("show", help=sub["show"])
    show.add_argument("dag_name")
    create = subparsers.add_parser("create", help=sub["create"])
    create.add_argument("dag_name")
    for command in ("save", "import"):
        item = subparsers.add_parser(command, help=sub[command])
        item.add_argument("dag_name")
        item.add_argument("--file", required=True, type=Path)
    export = subparsers.add_parser("export", help=sub["export"])
    export.add_argument("dag_name")
    export.add_argument("--file", required=True, type=Path)
    runtime_status = subparsers.add_parser("runtime-status", help=sub["runtime-status"])
    runtime_status.add_argument("--run-id", default="")
    _watch_arguments(runtime_status)
    run = subparsers.add_parser("run", help=sub["run"])
    run.add_argument("dag_name")
    run.add_argument("--source-shared-inputs", default="")
    run.add_argument("--node-inputs", default="")
    run.add_argument("--append-nodes", default="")
    status = subparsers.add_parser("status", help=sub["status"])
    status.add_argument("dag_name")
    _watch_arguments(status)
    stop = subparsers.add_parser("stop", help=sub["stop"])
    stop.add_argument("dag_name")
    stop.add_argument("--force", action="store_true")
    retry = subparsers.add_parser("retry", help=sub["retry"])
    retry.add_argument("dag_name")
    retry.add_argument("--run-id", default="")
    retry.add_argument("--nodes", default="")
    retry.add_argument("--mode", default="single")
    retry.add_argument("--source-shared-inputs", default="")
    retry.add_argument("--node-inputs", default="")
    retry.add_argument("--append-nodes", default="")
    edit = subparsers.add_parser("edit", help=sub["edit"])
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
    sub = COMMANDS["event"].subcommands
    emit = subparsers.add_parser("emit", help=sub["emit"])
    emit.add_argument("event")
    emit.add_argument("--payload-json", default="")
    emit.add_argument("--source", default="cli")
    emit.add_argument("--depth", type=int, default=0)


def _system_parser(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="system_command", required=True)
    sub = COMMANDS["system"].subcommands
    subparsers.add_parser("pause-scheduler", help=sub["pause-scheduler"])
    subparsers.add_parser("resume-scheduler", help=sub["resume-scheduler"])
    scheduler_status = subparsers.add_parser("scheduler-status", help=sub["scheduler-status"])
    _watch_arguments(scheduler_status)
    repair_source = subparsers.add_parser("repair-source", help=sub["repair-source"])
    repair_source.add_argument("source_name")


def _client_parser(parser: argparse.ArgumentParser) -> None:
    client_sub = parser.add_subparsers(dest="client_command", required=True)
    sub = COMMANDS["client"].subcommands
    init = client_sub.add_parser("init", help=sub["init"])
    init.add_argument("--server", required=True)
    init.add_argument("--common-name", default=os.environ.get("EDERA_IDENTITY", "human:default"))


def _config_parser(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="config_command", required=True)
    sub = COMMANDS["config"].subcommands
    subparsers.add_parser("list", help=sub["list"])
    system = subparsers.add_parser("system", help=sub["system"])
    system_sub = system.add_subparsers(dest="system_command", required=True)
    system_sub.add_parser("show")
    system_save = system_sub.add_parser("save")
    system_save.add_argument("--file", required=True, type=Path)
    read = subparsers.add_parser("read", help=sub["read"])
    read.add_argument("kind")
    read.add_argument("name")
    save = subparsers.add_parser("save", help=sub["save"])
    save.add_argument("kind")
    save.add_argument("name")
    save.add_argument("--file", required=True, type=Path)
    entity_type = subparsers.add_parser("entity-type", help=sub["entity-type"])
    entity_type_sub = entity_type.add_subparsers(dest="entity_type_command", required=True)
    entity_type_sub.add_parser("list")
    show = entity_type_sub.add_parser("show")
    show.add_argument("name")
    for command in ("create", "save"):
        item = entity_type_sub.add_parser(command)
        item.add_argument("name")
        item.add_argument("--file", required=True, type=Path)
    delete = entity_type_sub.add_parser("delete")
    delete.add_argument("name")
    delete.add_argument("--cascade", action="store_true")


def _handler_parser(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="handler_command", required=True)
    sub = COMMANDS["handler"].subcommands
    list_ = subparsers.add_parser("list", help=sub["list"])
    _local_page_arguments(list_)
    show = subparsers.add_parser("show", help=sub["show"])
    show.add_argument("name")
    save = subparsers.add_parser("save", help=sub["save"])
    save.add_argument("name")
    save.add_argument("--file", required=True, type=Path)


def _query_parser(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="query_command", required=True)
    sub = COMMANDS["query"].subcommands
    briefing = subparsers.add_parser("briefing", help=sub["briefing"])
    briefing_sub = briefing.add_subparsers(dest="briefing_command", required=True)
    briefing_sub.add_parser("latest")
    briefing_list = briefing_sub.add_parser("list")
    _time_range_arguments(briefing_list)
    show_briefing = briefing_sub.add_parser("show")
    show_briefing.add_argument("briefing_id")
    advice = subparsers.add_parser("advice", help=sub["advice"])
    advice_sub = advice.add_subparsers(dest="advice_command", required=True)
    advice_list = advice_sub.add_parser("list")
    advice_list.add_argument("--stock-code", default="")
    advice_list.add_argument("--direction", default="")
    _time_range_arguments(advice_list)
    show_advice = advice_sub.add_parser("show")
    show_advice.add_argument("advice_id")
    results = subparsers.add_parser("results", help=sub["results"])
    results_sub = results.add_subparsers(dest="results_command", required=True)
    summary = results_sub.add_parser("summary")
    summary.add_argument("--stock-code", default="")
    summary.add_argument("--direction", default="")
    summary.add_argument("--created-from", default="")
    summary.add_argument("--created-to", default="")
    node_outputs = subparsers.add_parser("node-outputs", help=sub["node-outputs"])
    node_outputs.add_argument("--node-id", default="")
    node_outputs.add_argument("--run-id", default="")
    node_outputs.add_argument("--limit", type=int, default=100)
    _offset_argument(node_outputs)
    node_history = subparsers.add_parser("node-history", help=sub["node-history"])
    node_history.add_argument("dag_name")
    node_history.add_argument("node_id")
    node_history.add_argument("--limit", type=int, default=50)
    child_run = subparsers.add_parser("child-run", help=sub["child-run"])
    child_run.add_argument("--parent-run-id", required=True)
    child_run.add_argument("--parent-node-id", required=True)


def _time_range_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--created-from", default="")
    parser.add_argument("--created-to", default="")
    parser.add_argument("--limit", type=int, default=50)
    _offset_argument(parser)


def _source_parser(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="source_command", required=True)
    sub = COMMANDS["source"].subcommands
    health = subparsers.add_parser("health", help=sub["health"])
    _watch_arguments(health)
    logs = subparsers.add_parser("logs", help=sub["logs"])
    logs.add_argument("--source-name", default="")
    logs.add_argument("--limit", type=int, default=50)
    _offset_argument(logs)
    _tail_arguments(logs)
    repair_task = subparsers.add_parser("repair-task", help=sub["repair-task"])
    repair_task.add_argument("source_name")


def _extension_parser(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="extension_command", required=True)
    sub = COMMANDS["extension"].subcommands
    list_ = subparsers.add_parser("list", help=sub["list"])
    list_.add_argument("--available", action="store_true")
    list_.add_argument("--installed", action="store_true")
    show = subparsers.add_parser("show", help=sub["show"])
    show.add_argument("name")
    show.add_argument("--extensions-dir", type=Path, default=Path("extensions"))
    install = subparsers.add_parser("install", help=sub["install"])
    install.add_argument("name")
    install.add_argument("--overwrite", action="store_true")
    delete = subparsers.add_parser("delete", help=sub["delete"])
    delete.add_argument("name")
    uninstall = subparsers.add_parser("uninstall", help=sub["uninstall"])
    uninstall.add_argument("name")
    uninstall.add_argument("--strategy", required=True, choices=["purge", "keep-modified", "deactivate"])
    reactivate = subparsers.add_parser("reactivate", help=sub["reactivate"])
    reactivate.add_argument("name")
    import_ = subparsers.add_parser("import", help=sub["import"])
    import_.add_argument("path", type=Path)
    import_.add_argument("--extensions-dir", type=Path, default=Path("extensions"))
    import_.add_argument("--install", action="store_true")
    import_.add_argument("--overwrite", action="store_true")
    export = subparsers.add_parser("export", help=sub["export"])
    export.add_argument("name")
    export.add_argument("-o", "--file", required=True, type=Path)
    export.add_argument("--handlers-dir", type=Path)
    import_entities = subparsers.add_parser("import-entities", help=sub["import-entities"])
    import_entities.add_argument("-f", "--file", required=True, type=Path)
    export_entities = subparsers.add_parser("export-entities", help=sub["export-entities"])
    export_entities.add_argument("-o", "--file", required=True, type=Path)
    export_entities.add_argument("--entities", required=True)
    export_entities.add_argument("--name", required=True)
    export_entities.add_argument("--version", required=True)


def _dispatch(args: argparse.Namespace) -> object:
    if args.command == "entity":
        return _run_grpc(_grpc_entity(args))
    if args.command == "relation":
        return _run_grpc(_grpc_relation(args))
    if args.command == "entity-type":
        return _run_grpc(_grpc_entity_type(args))
    if args.command == "node":
        return _run_grpc(_grpc_node(args))
    if args.command == "node-type":
        return _run_grpc(_grpc_node_type(args))
    if args.command == "skill":
        return _run_grpc(_grpc_skill(args))
    if args.command == "dag":
        return _run_grpc(_grpc_dag(args))
    if args.command == "event":
        return _run_grpc(_grpc_event(args))
    if args.command == "system":
        return _run_grpc(_grpc_system(args))
    if args.command == "extension":
        return _run_grpc(_grpc_extension(args))
    if args.command == "client":
        return _client(args)
    if args.command == "config":
        return _run_grpc(_grpc_config(args))
    if args.command == "query":
        return _run_grpc(_grpc_query(args))
    if args.command == "source":
        return _run_grpc(_grpc_source(args))
    if args.command == "handler":
        return _run_grpc(_grpc_handler(args))
    if args.command == "handler-validate":
        return _handler_validate(args.path)
    raise ValueError(f"unknown command: {args.command}")


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


def _apply_output_page(result: object, args: argparse.Namespace) -> object:
    if not hasattr(args, "offset"):
        return result
    offset = max(0, int(getattr(args, "offset", 0) or 0))
    limit = _local_output_limit(args)
    if offset == 0 and limit is None:
        return result
    return _page_result(result, offset, limit)


def _local_output_limit(args: argparse.Namespace) -> int | None:
    if args.command == "dag" and getattr(args, "dag_command", None) == "list":
        return max(0, int(args.limit)) if args.limit is not None else None
    if args.command == "handler" and getattr(args, "handler_command", None) == "list":
        return max(0, int(args.limit)) if args.limit is not None else None
    return None


def _page_result(result: object, offset: int, limit: int | None) -> object:
    if isinstance(result, list):
        return _page_list(result, offset, limit)
    if isinstance(result, dict):
        single_list = _extract_single_list_value(result)
        if single_list is not None:
            key = next(k for k, v in result.items() if v is single_list)
            return {**result, key: _page_list(single_list, offset, limit)}
    return result


def _page_list(items: list[object], offset: int, limit: int | None) -> list[object]:
    if limit is None:
        return items[offset:]
    return items[offset : offset + limit]


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
    import_path = _arg_path(args) if args.entity_command == "import" else None
    normalized_import_path = import_path
    if import_path is not None and getattr(args, "type", None) != "relation":
        normalized_import_path = _normalized_entity_import_yaml(import_path)
    client = GrpcClient(args.server, identity=args.identity)
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


async def _grpc_relation(args: argparse.Namespace) -> object:
    if args.relation_command == "list":
        filters = []
        if args.from_:
            filters.append(f"from_entity_id={args.from_}")
        if args.to:
            filters.append(f"to_entity_id={args.to}")
        if args.type:
            filters.append(f"relation_type={args.type}")
        return await _grpc_entity(
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
        return await _grpc_entity(
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
        return await _grpc_entity(
            argparse.Namespace(server=args.server, identity=args.identity, entity_command="delete", ref=args.id, force=False)
        )
    if args.relation_command == "import":
        return await _grpc_entity(
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
        return await _grpc_entity(
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
    if args.node_command == "output" and args.output_args[:1] == ["export"] and args.out is None:
        raise ValueError("Missing required parameter: --out")
    client = GrpcClient(args.server, identity=args.identity)
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


async def _grpc_node_type(args: argparse.Namespace) -> object:
    client = GrpcClient(args.server, identity=args.identity)
    try:
        if args.node_type_command == "list":
            return await client.graph_list_node_types()
        if args.node_type_command == "show":
            return await client.graph_get_node_type(args.name)
        if args.node_type_command == "create":
            return await client.graph_create_node_type(args.name, _read_json_object(args.file))
        if args.node_type_command == "save":
            return await client.graph_save_node_type(args.name, _read_json_object(args.file))
        if args.node_type_command == "delete":
            return await client.graph_delete_node_type(args.name)
    finally:
        await client.close()
    raise ValueError(f"unknown node-type command: {args.node_type_command}")


async def _grpc_skill(args: argparse.Namespace) -> object:
    client = GrpcClient(args.server, identity=args.identity)
    try:
        if args.skill_command == "list":
            return await client.graph_list_skills()
        if args.skill_command == "show":
            return _skill_from_list(await client.graph_list_skills(), args.name)
        if args.skill_command == "create":
            return await client.graph_create_skill(_skill_dir_payload(args.from_dir))
        if args.skill_command == "update":
            return await client.graph_save_skill(args.name, {**_skill_dir_payload(args.from_dir), "name": args.name})
        if args.skill_command == "import-dir":
            payload = _skill_dir_payload(args.path)
            return await client.graph_save_skill(str(payload["name"]), payload)
        if args.skill_command == "import-batch":
            imported = []
            for path in sorted(item for item in args.path.iterdir() if item.is_dir() and (item / "SKILL.md").is_file()):
                payload = _skill_dir_payload(path)
                result = await client.graph_save_skill(str(payload["name"]), payload)
                skill = result.get("skill") if isinstance(result, dict) else None
                if isinstance(skill, dict) and isinstance(skill.get("name"), str):
                    imported.append(skill["name"])
            return {"imported": imported}
        if args.skill_command == "export":
            skill = _skill_from_list(await client.graph_list_skills(), args.name)
            target = args.output_dir / args.name
            _write_skill_files(target, _skill_files_from_payload(skill))
            return {"exported": args.name, "path": str(target)}
        if args.skill_command == "delete":
            return await client.graph_delete_skill(args.name)
    finally:
        await client.close()
    raise ValueError(f"unknown skill command: {args.skill_command}")


async def _grpc_dag(args: argparse.Namespace) -> object:
    client = GrpcClient(args.server, identity=args.identity)
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
                args.dag_name,
                args.run_id,
                _node_ids(args.nodes),
                args.mode,
                **_dag_temporary_inputs(args),
            )
        if args.dag_command == "edit":
            return await client.dag_edit(args.dag_name, args.edit_command, _dag_edit_payload(args))
        if args.dag_command == "run":
            return await client.dag_run(
                args.dag_name,
                **_dag_temporary_inputs(args),
            )
    finally:
        await client.close()
    raise ValueError(f"unknown dag command: {args.dag_command}")


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
        if args.system_command == "repair-source":
            return await client.system_create_repair_task(args.source_name)
    finally:
        await client.close()
    raise ValueError(f"unknown system command: {args.system_command}")


async def _grpc_config(args: argparse.Namespace) -> object:
    client = GrpcClient(args.server, identity=args.identity)
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


async def _grpc_handler(args: argparse.Namespace) -> object:
    client = GrpcClient(args.server, identity=args.identity)
    try:
        if args.handler_command == "list":
            return await client.graph_list_handlers()
        if args.handler_command == "show":
            return await client.graph_get_handler(args.name)
        if args.handler_command == "save":
            return await client.graph_save_handler(args.name, args.file.read_text(encoding="utf-8"))
    finally:
        await client.close()
    raise ValueError(f"unknown handler command: {args.handler_command}")


async def _grpc_query(args: argparse.Namespace) -> object:
    client = GrpcClient(args.server, identity=args.identity)
    try:
        if args.query_command == "briefing":
            if args.briefing_command == "latest":
                return await client.query_latest_briefing()
            if args.briefing_command == "list":
                return await client.query_list_briefings(args.created_from, args.created_to, args.limit)
            if args.briefing_command == "show":
                return await client.query_get_briefing(args.briefing_id)
        if args.query_command == "advice":
            if args.advice_command == "list":
                return await client.query_list_advices(args.stock_code, args.direction, args.created_from, args.created_to, args.limit)
            if args.advice_command == "show":
                return await client.query_get_advice(args.advice_id)
        if args.query_command == "results":
            if args.results_command == "summary":
                return await client.query_results_summary(args.stock_code, args.direction, args.created_from, args.created_to)
        if args.query_command == "node-outputs":
            return await client.query_node_outputs(args.node_id, args.run_id, args.limit)
        if args.query_command == "node-history":
            return await client.query_node_history(args.dag_name, args.node_id, args.limit)
        if args.query_command == "child-run":
            return await client.query_child_run_for_parent(args.parent_run_id, args.parent_node_id)
    finally:
        await client.close()
    raise ValueError(f"unknown query command: {args.query_command}")


async def _grpc_source(args: argparse.Namespace) -> object:
    client = GrpcClient(args.server, identity=args.identity)
    try:
        if args.source_command == "health":
            return await client.query_source_health()
        if args.source_command == "logs":
            return await client.query_source_logs(args.source_name, args.limit)
        if args.source_command == "repair-task":
            return await client.system_create_repair_task(args.source_name)
    finally:
        await client.close()
    raise ValueError(f"unknown source command: {args.source_command}")


async def _grpc_extension(args: argparse.Namespace) -> object:
    if args.extension_command == "import":
        imported = _extension_import(args.path, args.extensions_dir, overwrite=args.overwrite)
        if not args.install:
            return imported
    client = GrpcClient(args.server, identity=args.identity)
    try:
        if args.extension_command == "list":
            if args.available and not args.installed:
                return await client.extension_list_available()
            if args.installed and not args.available:
                return await client.extension_list_installed()
            available = (await client.extension_list_available()).get("extensions", [])
            installed = (await client.extension_list_installed()).get("extensions", [])
            return {
                "available": _available_not_installed(available, installed),
                "installed": installed,
            }
        if args.extension_command == "show":
            try:
                return await client.extension_show(args.name)
            except grpc.RpcError:
                return _extension_show_available(args.extensions_dir, args.name)
        if args.extension_command == "install":
            return await client.extension_install(args.name, overwrite=args.overwrite)
        if args.extension_command == "delete":
            return await client.extension_delete(args.name)
        if args.extension_command == "uninstall":
            return await client.extension_uninstall(args.name, args.strategy)
        if args.extension_command == "reactivate":
            return await client.extension_reactivate(args.name)
        if args.extension_command == "import":
            return await client.extension_install(str(imported["name"]))
        if args.extension_command == "export":
            detail = await client.extension_show(args.name)
            exported_entities = []
            for record in _extension_import_records(detail):
                exported_entities.append(
                    {
                        "import_path": record["import_path"],
                        "entity": await client.entity_get(record["entity_ref"]),
                    }
                )
            handlers_dir = args.handlers_dir or load_system_config(Path("config") / "system.toml").handlers_dir
            warnings = _extension_export(args.file, handlers_dir, args.name, detail, exported_entities)
            return {"exported": args.name, "file": str(args.file), "warnings": warnings}
        if args.extension_command == "export-entities":
            refs = [item.strip() for item in args.entities.split(",") if item.strip()]
            entities = [await client.entity_get(ref) for ref in refs]
            _extension_export_entities(args.file, args.name, args.version, entities)
            return {"exported": args.name, "file": str(args.file), "entities": refs}
        if args.extension_command == "import-entities":
            return await client.extension_import_entities(str(args.file))
        raise ValueError(f"unknown extension command: {args.extension_command}")
    finally:
        await client.close()


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


def _extension_import(path: Path, extensions_dir: Path, *, overwrite: bool = False) -> dict[str, object]:
    from edera_core.manifest import parse_manifest

    if path.is_dir():
        source = path
        manifest_path = source / "manifest.yaml"
        if not manifest_path.exists():
            raise ValueError("extension import path must contain manifest.yaml")
        manifest = parse_manifest(manifest_path)
        target = extensions_dir / manifest.name
        if target.exists():
            if not overwrite:
                raise ValueError(f"extension already exists: {manifest.name}")
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target)
        return {"imported": True, "name": manifest.name, "path": str(target), "message": f"扩展已导入，使用 'edera extension install {manifest.name}' 安装"}
    with tempfile.TemporaryDirectory() as tmp:
        extract_dir = Path(tmp)
        _extract_tar(path, extract_dir)
        candidates = [item.parent for item in extract_dir.rglob("manifest.yaml")]
        if len(candidates) != 1:
            raise ValueError("extension package must contain exactly one manifest.yaml")
        return _extension_import(candidates[0], extensions_dir, overwrite=overwrite)


def _extension_show_available(extensions_dir: Path, name: str) -> dict[str, object]:
    manifest_path = extensions_dir / name / "manifest.yaml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"extension not found: {name}")
    return yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}


def _available_not_installed(available: object, installed: object) -> list[object]:
    if not isinstance(available, list):
        return []
    if not isinstance(installed, list):
        return available
    installed_names = {item.get("name") for item in installed if isinstance(item, dict)}
    return [item for item in available if not (isinstance(item, dict) and item.get("name") in installed_names)]


def _extension_import_records(detail: dict[str, object]) -> list[dict[str, str]]:
    records = detail.get("import_records")
    if not isinstance(records, list):
        return []
    result: list[dict[str, str]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        import_path = record.get("import_path")
        entity_ref = record.get("entity_ref")
        if isinstance(import_path, str) and import_path and isinstance(entity_ref, str) and entity_ref:
            result.append({"import_path": import_path, "entity_ref": entity_ref})
    return result


def _extension_export(
    path: Path,
    handlers_dir: Path,
    name: str,
    detail: dict[str, object],
    exported_entities: list[dict[str, object]] | None = None,
) -> list[str]:
    manifest = detail.get("manifest") if isinstance(detail.get("manifest"), dict) else detail
    warnings: list[str] = []
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / name
        root.mkdir()
        (root / "manifest.yaml").write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding="utf-8")
        if isinstance(manifest, dict) and manifest.get("type") == "workflow_extension":
            warnings.extend(_export_workflow_artifacts(root, handlers_dir, name, manifest))
        elif (handlers_dir / name).exists() and (handlers_dir / name).is_dir():
            shutil.copytree(handlers_dir / name, root, dirs_exist_ok=True)
        elif _manifest_handler_entries(manifest):
            warnings.append(f"handler code not included: {handlers_dir / name} is missing")
        for entry in _manifest_handler_entries(manifest):
            relative = Path(entry)
            if relative.is_absolute() or ".." in relative.parts:
                warnings.append(f"handler code not included: {entry} is outside handlers/")
        for item in exported_entities or []:
            import_path = item.get("import_path")
            entity = item.get("entity")
            if not isinstance(import_path, str) or not isinstance(entity, dict):
                continue
            _write_package_entity_yaml(root, import_path, _entity_document(entity))
        import_records = detail.get("import_records")
        if isinstance(import_records, list):
            (root / "import_records.json").write_text(json.dumps(import_records, ensure_ascii=False), encoding="utf-8")
        _write_tar(path, root)
    return warnings


def _export_workflow_artifacts(root: Path, handlers_dir: Path, name: str, manifest: dict[str, object]) -> list[str]:
    warnings: list[str] = []
    for handler in _workflow_provider_packages(manifest, name):
        package = handler["package"]
        source = handlers_dir / package
        provider = package.removeprefix(f"{name}.")
        if not source.exists():
            warnings.append(f"provider code not included: {source} is missing")
            continue
        target = root / "_providers" / provider
        shutil.copytree(source, target, dirs_exist_ok=True)
        manifest_path = target / "manifest.yaml"
        if not manifest_path.exists():
            provider_manifest = _provider_manifest(manifest, provider, package)
            manifest_path.write_text(yaml.safe_dump(provider_manifest, allow_unicode=True, sort_keys=False), encoding="utf-8")
    for item in _manifest_library_imports(manifest):
        library_name = Path(item).name
        source = _workflow_library_source(handlers_dir, name, library_name)
        if source is None:
            warnings.append(f"library code not included: {handlers_dir / '_libs' / f'{name}.{library_name}'} is missing")
            continue
        target = root / "_lib" / library_name
        if source.is_dir():
            shutil.copytree(source, target, dirs_exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    return warnings


def _workflow_provider_packages(manifest: dict[str, object], name: str) -> list[dict[str, str]]:
    packages = _manifest_handler_packages(manifest)
    providers = _manifest_provider_names(manifest)
    if not providers:
        return packages
    expected = {f"{name}.{provider}" for provider in providers}
    return [item for item in packages if item["package"] in expected]


def _manifest_provider_names(manifest: dict[str, object]) -> list[str]:
    imports = manifest.get("imports")
    providers = imports.get("providers") if isinstance(imports, dict) else None
    if not isinstance(providers, list):
        return []
    result: list[str] = []
    for item in providers:
        if not isinstance(item, str):
            continue
        parts = Path(item).parts
        if len(parts) >= 3 and parts[-1] == "manifest.yaml" and "*" not in parts[-2]:
            result.append(parts[-2])
    return result


def _provider_manifest(manifest: dict[str, object], provider: str, package: str) -> dict[str, object]:
    result: dict[str, object] = {
        "name": provider,
        "version": str(manifest.get("version") or ""),
        "handlers": [_provider_handler(handler, package) for handler in _manifest_provider_handlers(manifest, package)],
    }
    libraries = _manifest_library_imports(manifest)
    if libraries:
        result["depends"] = libraries
    return result


def _manifest_provider_handlers(manifest: dict[str, object], package: str) -> list[dict[str, object]]:
    handlers = manifest.get("handlers")
    if not isinstance(handlers, list):
        return []
    return [handler for handler in handlers if isinstance(handler, dict) and handler.get("package") == package]


def _provider_handler(handler: dict[str, object], package: str) -> dict[str, object]:
    prefix = f"{package}."
    name = str(handler.get("name") or "")
    result: dict[str, object] = {"name": name.removeprefix(prefix)}
    for key in ("entry", "role", "input_type", "output_type", "timeout_seconds"):
        if key in handler:
            result[key] = handler[key]
    return result


def _workflow_library_source(handlers_dir: Path, extension_name: str, library_name: str) -> Path | None:
    for source in (
        handlers_dir / "_libs" / f"{extension_name}.{library_name}",
        handlers_dir.parent / "libs" / f"{extension_name}.{library_name}",
    ):
        if source.exists():
            return source
    return None


def _manifest_handler_packages(manifest: dict[str, object]) -> list[dict[str, str]]:
    handlers = manifest.get("handlers")
    if not isinstance(handlers, list):
        return []
    packages: list[dict[str, str]] = []
    seen: set[str] = set()
    for handler in handlers:
        if not isinstance(handler, dict):
            continue
        package = handler.get("package")
        if not isinstance(package, str) or "." not in package or package in seen:
            continue
        seen.add(package)
        packages.append({"package": package})
    return packages


def _manifest_library_imports(manifest: dict[str, object]) -> list[str]:
    imports = manifest.get("imports")
    libraries = imports.get("libraries") if isinstance(imports, dict) else None
    return [item for item in libraries if isinstance(item, str)] if isinstance(libraries, list) else []


def _manifest_handler_entries(manifest: object) -> list[str]:
    if not isinstance(manifest, dict):
        return []
    handlers = manifest.get("handlers")
    if not isinstance(handlers, list):
        return []
    entries: list[str] = []
    for handler in handlers:
        if isinstance(handler, dict) and isinstance(handler.get("entry"), str):
            entries.append(str(handler["entry"]))
        elif isinstance(handler, str):
            entries.append(handler)
    return entries


def _write_package_entity_yaml(root: Path, import_path: str, document: dict[str, object]) -> None:
    relative = Path(import_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("unsafe extension import path")
    _write_entity_yaml(root / relative, document)


def _extension_export_entities(path: Path, name: str, version: str, entities: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / name
        entity_dir = root / "entities"
        entity_dir.mkdir(parents=True)
        imports: list[str] = []
        for entity in entities:
            entity_type = str(entity.get("type") or "")
            entity_id = str(entity.get("id") or "")
            if not entity_type or not entity_id:
                raise ValueError("entity response must include type and id")
            import_path = f"entities/{entity_type}-{entity_id}.yaml"
            imports.append(import_path)
            document = {"type": entity_type, "id": entity_id, "attributes": entity.get("attributes") or {}}
            (root / import_path).write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
        manifest = {"name": name, "version": version, "imports": {"entities": imports}}
        (root / "manifest.yaml").write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding="utf-8")
        _write_tar(path, root)


def _extract_tar(path: Path, target: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)
    with tarfile.open(path, "r:gz") as archive:
        for member in archive.getmembers():
            member_path = Path(member.name)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise ValueError("unsafe extension package path")
        archive.extractall(target)


def _write_tar(path: Path, root: Path) -> None:
    with tarfile.open(path, "w:gz") as archive:
        archive.add(root, arcname=root.name)


def _run_grpc(coro):
    return asyncio.run(coro)


def _json_value(value: str) -> object:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _read_json_object(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("JSON file must contain an object")
    return payload


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding="utf-8")


def _arg_path(args: argparse.Namespace) -> Path:
    path = getattr(args, "path", None) or getattr(args, "file", None)
    if path is None:
        raise ValueError("file path is required")
    return path


def _skill_dir_payload(path: Path) -> dict[str, object]:
    if not (path / "SKILL.md").is_file():
        raise ValueError("skill directory must contain SKILL.md")
    return {"name": path.name, "files": _read_skill_files(path)}


def _read_skill_files(root: Path) -> list[dict[str, str]]:
    return [
        {"path": item.relative_to(root).as_posix(), "content": item.read_text(encoding="utf-8")}
        for item in sorted(path for path in root.rglob("*") if path.is_file())
    ]


def _skill_from_list(payload: object, name: str) -> dict[str, object]:
    skills = payload.get("skills") if isinstance(payload, dict) else None
    if not isinstance(skills, list):
        raise ValueError("invalid skills response")
    for skill in skills:
        if isinstance(skill, dict) and skill.get("name") == name:
            return skill
    raise ValueError(f"skill not found: {name}")


def _skill_files_from_payload(skill: dict[str, object]) -> list[dict[str, str]]:
    files = skill.get("files")
    if not isinstance(files, list):
        raise ValueError("skill response missing files")
    return [
        {"path": str(item.get("path") or ""), "content": str(item.get("content") or "")}
        for item in files
        if isinstance(item, dict)
    ]


def _write_skill_files(root: Path, files: list[dict[str, str]]) -> None:
    for item in files:
        relative = Path(item["path"])
        if relative.is_absolute() or ".." in relative.parts or not item["path"]:
            raise ValueError(f"unsafe skill file path: {item['path']}")
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item["content"], encoding="utf-8")


def _parse_filters(filters: list[str]) -> dict[str, str]:
    return dict(_parse_filter(item) for item in filters)


def _parse_filter(value: str) -> tuple[str, str]:
    key, sep, item = value.partition("=")
    if not sep or not key:
        raise ValueError("--filter must be key=value")
    return key, item


def _write_entity_yaml(path: Path, document: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _normalized_entity_import_yaml(path: Path) -> Path:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError("entity YAML must be an object")
    if "entities" in payload:
        entities = payload["entities"]
        if not isinstance(entities, list):
            raise ValueError("entity YAML entities must be a list")
        for item in entities:
            _validate_entity_document(item)
        return path
    _validate_entity_document(payload)
    handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".yaml", delete=False)
    with handle:
        yaml.safe_dump({"entities": [payload]}, handle, allow_unicode=True, sort_keys=False)
    return Path(handle.name)


def _validate_entity_document(document: object) -> None:
    if not isinstance(document, dict):
        raise ValueError("entity YAML item must be an object")
    if not document.get("type"):
        raise ValueError("entity YAML requires non-empty type")
    if not isinstance(document.get("attributes"), dict):
        raise ValueError("entity YAML requires attributes object")


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
