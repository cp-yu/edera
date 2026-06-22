from __future__ import annotations

import argparse
import asyncio
import json
import tempfile
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class CommandHelp:
    description: str
    help_line: str
    epilog: str
    subcommands: dict[str, str] = field(default_factory=dict)


def _fmt_epilog(description: str, examples: list[tuple[str, str]]) -> str:
    header = description.strip()
    lines = ["EXAMPLES"]
    for invocation, note in examples:
        lines.append(f"  {invocation}")
        if note:
            lines.append(f"    # {note}")
    return header + "\n\n" + "\n".join(lines)


from edera_core.grpc_client import GrpcClient  # noqa: F401 - re-export for test monkeypatch


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


def _exit_error(parser: argparse.ArgumentParser, error: str, type_name: str, detail: str) -> None:
    parser.exit(1, json.dumps({"error": error, "type": type_name, "detail": detail}, ensure_ascii=False) + "\n")


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


def _entity_document(entity: dict[str, object]) -> dict[str, object]:
    attributes = entity.get("attributes")
    if not isinstance(attributes, dict):
        raise ValueError("entity response missing attributes")
    return {
        "type": str(entity.get("type") or ""),
        "id": str(entity.get("id") or ""),
        "attributes": attributes,
    }


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


def _watch_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--watch", action="store_true", help="Watch for changes, re-fetch on each interval.")
    parser.add_argument("--interval", type=float, default=1.0, help="Polling interval in seconds (default: 1.0).")
    parser.add_argument("--watch-count", type=int, help="Max watch iterations (unlimited if omitted).")


def _tail_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--tail", action="store_true", help="Follow output, printing new items as they arrive.")
    parser.add_argument("--interval", type=float, default=1.0, help="Polling interval in seconds (default: 1.0).")
    parser.add_argument("--watch-count", type=int, help="Max tail iterations (unlimited if omitted).")


def _offset_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--offset", type=int, default=0, help="Skip the first N results (default: 0).")


def _local_page_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--limit", type=int, help="Max number of results to return.")
    _offset_argument(parser)


def _created_range_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--created-from", default="", help="ISO-8601 start of creation time range.")
    parser.add_argument("--created-to", default="", help="ISO-8601 end of creation time range.")


def _time_range_arguments(parser: argparse.ArgumentParser) -> None:
    _created_range_args(parser)
    parser.add_argument("--limit", type=int, default=50, help="Max results (default: 50).")
    _offset_argument(parser)


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
