from __future__ import annotations

import importlib
import inspect
import os
import sys
import asyncio
import html as html_lib
import json
import tempfile
import threading
from dataclasses import asdict, is_dataclass
from datetime import date
from pathlib import Path
from typing import Any

from edera_types import HandlerContext, NodeInput, NodeOutput


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
    timeout = _float(ctx.params.get("timeout_seconds"))
    if timeout is not None:
        return await _call_subprocess(ctx, module_path, function, timeout)
    return await asyncio.to_thread(_call_sync, ctx, module_path, function)


async def _call_subprocess(ctx: HandlerContext, module_path: str, function: str, timeout: float) -> Any:
    with tempfile.TemporaryDirectory(prefix="uzi-adapter-") as tmp:
        input_path = Path(tmp) / "input.json"
        output_path = Path(tmp) / "output.json"
        input_path.write_text(
            json.dumps(
                {
                    "params": _json_safe(ctx.params),
                    "input_payload": _json_safe(ctx.input.payload),
                    "input_metadata": _json_safe(ctx.input.metadata),
                    "node_name": ctx.node_name,
                    "node_type": ctx.node_type,
                    "run_id": ctx.run_id,
                    "module_path": module_path,
                    "function": function,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            str(Path(__file__).resolve()),
            "--worker",
            str(input_path),
            str(output_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except asyncio.TimeoutError as exc:
            process.kill()
            await process.communicate()
            raise TimeoutError(f"legacy script timeout > {timeout:g}s") from exc
        if process.returncode != 0:
            detail = (stderr or stdout).decode(errors="replace").strip()
            raise RuntimeError(detail or f"legacy script worker exited with code {process.returncode}")
        try:
            payload = json.loads(output_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            detail = (stderr or stdout).decode(errors="replace").strip()
            raise RuntimeError(detail or "legacy script worker produced no output") from exc
        if not payload.get("ok"):
            raise RuntimeError(str(payload.get("error") or "legacy script worker failed"))
        return payload.get("result")


def _call_sync(ctx: HandlerContext, module_path: str, function: str) -> Any:
    with _CALL_LOCK:
        script_dir, import_name, import_paths = _module_target(module_path)
        old_cwd = os.getcwd()
        old_path = list(sys.path)
        old_env = _set_env(ctx)
        old_modules = _stash_modules(import_name)
        try:
            for path in reversed(import_paths):
                sys.path.insert(0, str(path))
            if script_dir is not None:
                os.chdir(script_dir)
            module = importlib.import_module(import_name)
            target = _target(module, function)
            args = [_value(ctx, item) for item in _args_map(ctx)]
            result = target(*args)
            if inspect.isawaitable(result):
                return asyncio.run(result)
            return result
        finally:
            os.chdir(old_cwd)
            sys.path[:] = old_path
            _restore_modules(old_modules)
            _restore_env(old_env)


def _module_target(module_path: str) -> tuple[Path | None, str, list[Path]]:
    path = Path(module_path)
    if path.suffix == ".py" or path.parent != Path("."):
        full = path.expanduser().resolve()
        script_dir = full.parent
        return script_dir, _import_name(full), _import_paths(script_dir)
    return None, module_path, []


def _import_name(path: Path) -> str:
    parts = [path.stem]
    current = path.parent
    while (current / "__init__.py").exists():
        parts.append(current.name)
        current = current.parent
    return ".".join(reversed(parts))


def _import_paths(script_dir: Path) -> list[Path]:
    paths = [script_dir]
    for parent in (script_dir, *script_dir.parents):
        if (parent / "lib").is_dir() and parent not in paths:
            paths.append(parent)
            break
    return paths


def _stash_modules(import_name: str) -> dict[str, Any]:
    root = import_name.split(".", 1)[0]
    if root in sys.builtin_module_names:
        return {}
    prefix = f"{root}."
    names = [name for name in sys.modules if name == root or name.startswith(prefix)]
    return {name: sys.modules.pop(name) for name in names}


def _restore_modules(modules: dict[str, Any]) -> None:
    for name in list(sys.modules):
        root = name.split(".", 1)[0]
        if root in {module_name.split(".", 1)[0] for module_name in modules}:
            sys.modules.pop(name)
    sys.modules.update(modules)


def _target(module: Any, function: str) -> Any:
    if hasattr(module, function):
        return getattr(module, function)
    if function != "render":
        raise AttributeError(f"module {module.__name__!r} has no attribute {function!r}")
    return lambda payload: _render_section(module, payload)


def _render_section(module: Any, payload: Any) -> dict[str, Any]:
    renderer = _renderer(module)
    context_cls = getattr(importlib.import_module("lib.pipeline.renderer.base"), "RenderContext")
    raw = payload.get("raw", {}) if isinstance(payload, dict) else {}
    synthesis = payload.get("synthesis", {}) if isinstance(payload, dict) else {}
    data = _section_data(raw, renderer.section_id)
    basic = _section_data(raw, "basic_header")
    ctx = context_cls(
        ticker=str(synthesis.get("ticker") or raw.get("ticker") or ""),
        name=str(synthesis.get("name") or basic.get("name") or ""),
        market=str(raw.get("market") or "A"),
        data=data,
        meta=raw,
        quality=_quality(data),
    )
    return {"section_id": renderer.section_id, "html": renderer.render(ctx)}


def _renderer(module: Any) -> Any:
    base = importlib.import_module("lib.pipeline.renderer.base")
    section_renderer = getattr(base, "SectionRenderer")
    candidates = [
        value
        for value in vars(module).values()
        if isinstance(value, type) and issubclass(value, section_renderer) and value is not section_renderer
    ]
    if len(candidates) != 1:
        raise AttributeError(f"module {module.__name__!r} has no module render function")
    return candidates[0]()


def _section_data(raw: Any, section_id: str) -> dict[str, Any]:
    dimensions = raw.get("dimensions", {}) if isinstance(raw, dict) else {}
    dim_key = _SECTION_DIMENSIONS.get(section_id, section_id)
    value = dimensions.get(dim_key)
    if isinstance(value, dict):
        data = value.get("data")
        return data if isinstance(data, dict) else value
    return {}


def _quality(data: dict[str, Any]) -> str:
    if data.get("quality") == "ERROR" or data.get("error"):
        return "error"
    return "full" if data else "missing"


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
        "run_id": ctx.input.run_id,
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


def _float(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) and value > 0 else None


def _json_safe(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return _json_safe(asdict(value))
    if isinstance(value, date):
        return value.isoformat()
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
_CALL_LOCK = threading.RLock()

_SECTION_DIMENSIONS = {
    "basic_header": "0_basic",
    "financials": "1_financials",
    "kline": "4_market",
    "research": "2_news",
    "fund_managers": "5_shareholder",
    "industry": "7_industry",
    "sentiment": "8_sentiment",
    "futures": "9_futures",
    "valuation": "10_valuation",
    "lhb": "11_moneyflow",
    "capital_flow": "12_capital_flow",
    "policy": "13_policy",
    "events": "14_events",
    "peers": "15_competitors",
    "trap": "16_risk",
    "governance": "18_insider",
}


def score_dimensions_from_raw(raw: dict[str, Any]) -> dict[str, Any]:
    raw = _collection_to_raw(raw)
    return {"raw": raw, "dims_scored": _call_run_real_test("score_dimensions", raw)}


def generate_panel_from_scored(payload: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get("raw", {})
    dims_scored = payload.get("dims_scored", {})
    panel = _call_run_real_test("generate_panel", dims_scored, raw)
    return {"raw": raw, "dims_scored": dims_scored, "panel": panel}


def generate_synthesis_from_panel(payload: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get("raw", {})
    dims_scored = payload.get("dims_scored", {})
    panel = payload.get("panel", {})
    synthesis = _call_run_real_test("generate_synthesis", raw, dims_scored, panel)
    return {"raw": raw, "dims_scored": dims_scored, "panel": panel, "synthesis": synthesis}


def assemble_rendered_report(payload: Any, run_id: str | None = None, edge_inputs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    sections = _rendered_sections(payload, edge_inputs)
    html = _report_html(sections)
    reports_dir = Path(__file__).resolve().parents[2] / "data" / "uzi-reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    safe_run_id = "".join(ch for ch in str(run_id or "manual") if ch.isalnum() or ch in "-_") or "manual"
    report_path = reports_dir / f"{safe_run_id}.html"
    report_path.write_text(html, encoding="utf-8")
    return {"report_path": str(report_path), "section_count": len(sections), "html": html}


def _rendered_sections(payload: Any, edge_inputs: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    values = _rendered_values(payload, edge_inputs)
    if not edge_inputs:
        sections: list[dict[str, str]] = []
        for item in values:
            section = _rendered_section(item)
            if section:
                sections.append(section)
        return sections
    sections: list[dict[str, str]] = []
    index = 0
    for edge in edge_inputs:
        if not isinstance(edge, dict) or edge.get("status") not in {"available", "succeeded"} or not edge.get("has_payload"):
            continue
        if index >= len(values):
            break
        section = _rendered_section(values[index])
        index += 1
        if section:
            sections.append(section)
    return sections


def _rendered_values(payload: Any, edge_inputs: list[dict[str, Any]] | None) -> list[Any]:
    if not isinstance(payload, dict) or "html" in payload:
        return payload if isinstance(payload, list) else [payload]
    if edge_inputs:
        ordered = []
        for edge in edge_inputs:
            if isinstance(edge, dict) and edge.get("from_node_id") in payload:
                ordered.append(payload[edge["from_node_id"]])
        return ordered
    return list(payload.values())


def _rendered_section(value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    html = value.get("html")
    if not isinstance(html, str) or not html:
        return None
    section_id = value.get("section_id")
    return {"section_id": str(section_id or ""), "html": html}


def _report_html(sections: list[dict[str, str]]) -> str:
    body = "\n".join(section["html"] for section in sections)
    title = "UZI Skill Report"
    return (
        "<!doctype html>\n"
        "<html lang=\"zh-CN\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\">\n"
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"  <title>{html_lib.escape(title)}</title>\n"
        "  <style>\n"
        "    body{margin:0;background:#f8fafc;color:#0f172a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;}\n"
        "    main{max-width:1180px;margin:0 auto;padding:24px;}\n"
        "    section{background:#fff;border:1px solid #e2e8f0;border-radius:8px;margin:0 0 16px;padding:18px;}\n"
        "    h1,h2,h3{margin-top:0;letter-spacing:0;}\n"
        "    table{width:100%;border-collapse:collapse;}th,td{border-bottom:1px solid #e2e8f0;padding:8px;text-align:left;}\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        f"<main>\n{body}\n</main>\n"
        "</body>\n"
        "</html>\n"
    )


def autofill_qualitative_from_basic(basic: dict[str, Any]) -> dict[str, Any]:
    raw = {"ticker": basic.get("ticker"), "dimensions": {"0_basic": basic}}
    ticker = str(basic.get("ticker") or "")
    _call_run_real_test("_autofill_qualitative_via_mx", raw, ticker)
    return raw["dimensions"].get("0_basic", basic)


def _call_run_real_test(name: str, *args: Any) -> Any:
    scripts = Path("/home/yunxin/Software/skills/UZI-Skill-instance/skills/deep-analysis/scripts")
    old_path = list(sys.path)
    try:
        sys.path.insert(0, str(scripts))
        module = importlib.import_module("run_real_test")
        return getattr(module, name)(*args)
    finally:
        sys.path[:] = old_path


def _collection_to_raw(payload: dict[str, Any]) -> dict[str, Any]:
    if "dimensions" in payload:
        return payload
    dimensions = {key: value for key, value in payload.items() if key[0:1].isdigit() and "_" in key}
    for source, target in _SCORE_DIMENSION_ALIASES.items():
        if source in dimensions and target not in dimensions:
            dimensions[target] = dimensions[source]
    basic = dimensions.get("0_basic") if isinstance(dimensions.get("0_basic"), dict) else {}
    basic_data = basic.get("data") if isinstance(basic, dict) else {}
    return {
        "ticker": payload.get("ticker") or basic.get("ticker") or basic_data.get("ticker"),
        "market": payload.get("market") or basic.get("market") or basic_data.get("market") or "A",
        "dimensions": dimensions,
    }


_SCORE_DIMENSION_ALIASES = {
    "2_news": "6_research",
    "4_market": "2_kline",
    "6_technical": "2_kline",
    "8_sentiment": "17_sentiment",
    "11_moneyflow": "16_lhb",
    "14_events": "15_events",
    "15_competitors": "4_peers",
    "16_risk": "18_trap",
    "18_insider": "11_governance",
}


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


def _worker_main(argv: list[str]) -> int:
    if len(argv) != 4 or argv[1] != "--worker":
        return 2
    input_path = Path(argv[2])
    output_path = Path(argv[3])
    data = json.loads(input_path.read_text(encoding="utf-8"))
    ctx = HandlerContext(
        input=NodeInput(
            run_id=str(data.get("run_id") or ""),
            payload=data.get("input_payload"),
            metadata=data.get("input_metadata") if isinstance(data.get("input_metadata"), dict) else {},
        ),
        params=data.get("params") if isinstance(data.get("params"), dict) else {},
        node_name=str(data.get("node_name") or ""),
        node_type=str(data.get("node_type") or ""),
        run_id=str(data.get("run_id") or ""),
        entity_store=_WorkerEntityStore(),
    )
    try:
        result = _call_sync(ctx, str(data["module_path"]), str(data["function"]))
    except Exception as exc:
        output = {"ok": False, "error": str(exc)}
    else:
        output = {"ok": True, "result": _json_safe(result)}
    output_path.write_text(json.dumps(output, ensure_ascii=False), encoding="utf-8")
    return 0


class _WorkerEntityStore:
    def query(self, type: str | None = None) -> list[object]:
        return []

    def resolve(self, ref: str) -> object:
        raise KeyError(ref)

    def related_refs(self, ref: str) -> list[str]:
        return []


if __name__ == "__main__":
    raise SystemExit(_worker_main(sys.argv))
