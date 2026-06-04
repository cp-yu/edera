from __future__ import annotations

import importlib
import inspect
import os
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from edera_types import HandlerContext, NodeOutput


async def run(ctx: HandlerContext) -> NodeOutput:
    module_path = _string(ctx.params.get("module_path"))
    function = _string(ctx.params.get("function")) or "main"
    if module_path is None:
        return _error(ctx, "missing module_path")
    try:
        result = await _call(ctx, module_path, function)
    except Exception as exc:
        return _error(ctx, str(exc))
    return NodeOutput(node_name=ctx.node_name, ok=True, payload=_json_safe(result))


async def _call(ctx: HandlerContext, module_path: str, function: str) -> Any:
    script_dir, import_name, import_paths = _module_target(module_path)
    old_cwd = os.getcwd()
    old_path = list(sys.path)
    old_env = _set_env(ctx)
    try:
        for path in reversed(import_paths):
            sys.path.insert(0, str(path))
        if script_dir is not None:
            os.chdir(script_dir)
        module = importlib.import_module(import_name)
        target = getattr(module, function)
        args = [_value(ctx, item) for item in _args_map(ctx)]
        result = target(*args)
        if inspect.isawaitable(result):
            return await result
        return result
    finally:
        os.chdir(old_cwd)
        sys.path[:] = old_path
        _restore_env(old_env)


def _module_target(module_path: str) -> tuple[Path | None, str, list[Path]]:
    path = Path(module_path)
    if path.suffix == ".py" or path.parent != Path("."):
        full = path.expanduser().resolve()
        script_dir = full.parent
        return script_dir, full.stem, _import_paths(script_dir)
    return None, module_path, []


def _import_paths(script_dir: Path) -> list[Path]:
    paths = [script_dir]
    for parent in (script_dir, *script_dir.parents):
        if (parent / "lib").is_dir() and parent not in paths:
            paths.append(parent)
            break
    return paths


def _args_map(ctx: HandlerContext) -> list[dict[str, Any]]:
    value = ctx.params.get("args_map")
    return value if isinstance(value, list) else []


def _set_env(ctx: HandlerContext) -> dict[str, str | None]:
    value = ctx.params.get("env")
    if not isinstance(value, dict):
        return {}
    old: dict[str, str | None] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key:
            continue
        old[key] = os.environ.get(key)
        if item is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = str(item)
    return old


def _restore_env(old: dict[str, str | None]) -> None:
    for key, value in old.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _value(ctx: HandlerContext, mapping: dict[str, Any]) -> Any:
    source = _string(mapping.get("source"))
    if source is None:
        return mapping.get("default")
    value = _lookup(_roots(ctx), source.split("."))
    if value is _MISSING:
        return mapping.get("default")
    return value


def _roots(ctx: HandlerContext) -> dict[str, Any]:
    return {
        "params": ctx.input.payload if isinstance(ctx.input.payload, dict) else {},
        "input": _input_payload(ctx),
        "metadata": ctx.input.metadata,
    }


def _input_payload(ctx: HandlerContext) -> Any:
    payload = ctx.input.payload
    upstreams = ctx.input.metadata.get("upstreams")
    if isinstance(payload, list) and isinstance(upstreams, list) and len(payload) == len(upstreams):
        return {str(name): item for name, item in zip(upstreams, payload)}
    return payload


def _lookup(value: Any, parts: list[str]) -> Any:
    current = value
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part, _MISSING)
        elif isinstance(current, list) and part.isdecimal():
            index = int(part)
            current = current[index] if index < len(current) else _MISSING
        else:
            current = getattr(current, part, _MISSING)
        if current is _MISSING:
            return _MISSING
    return current


def _string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _json_safe(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return _json_safe(asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return value


def _error(ctx: HandlerContext, message: str) -> NodeOutput:
    return NodeOutput(
        node_name=ctx.node_name,
        ok=True,
        payload={"quality": "ERROR", "error": message},
    )


_MISSING = object()


def aggregate_collection_results(payload: Any, fields: list[str], edge_inputs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if isinstance(payload, dict):
        return {field: payload.get(field) for field in fields}
    values = list(payload) if isinstance(payload, list) else [payload]
    status = {str(item.get("from_node_id")): item.get("status") for item in edge_inputs or [] if isinstance(item, dict)}
    result: dict[str, Any] = {}
    index = 0
    for field in fields:
        if status.get(field) == "failed":
            result[field] = None
            continue
        result[field] = values[index] if index < len(values) else None
        index += 1
    return result
