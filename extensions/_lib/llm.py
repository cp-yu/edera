from __future__ import annotations

import asyncio
import json
import os
import shutil
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from edera_core.config.schema import NodeConfig, RuntimeSettings, SystemConfig
from edera_core.errors import NodeExecutionError
from edera_types import NodeInput


async def run_pi(
    config: NodeConfig,
    skills: list[str],
    node_input: NodeInput,
    cycle_id: str,
    instance_id: str,
    system: SystemConfig,
    runtime: RuntimeSettings,
    skills_dir: Path = Path("skills"),
) -> tuple[object, str]:
    session_ref = _session_ref(config, node_input)
    session_dir = resolve_session_dir(session_ref, system.workspace_root, instance_id, cycle_id)
    workspace = _workspace_for_session(session_dir, system.workspace_root, instance_id, cycle_id)
    workspace = prepare_workspace(config, workspace, session_dir)
    skill_paths = [str(skills_dir / skill) for skill in skills]
    args = [runtime.pi_bin, "-p", "--no-skills"]
    if config.tools:
        args.extend(["--tools", ",".join(config.tools)])
    else:
        args.append("--no-tools")
    for path in skill_paths:
        args.extend(["--skill", path])
    args.extend(["--no-extensions", "--no-prompt-templates", "--no-themes", "--session-dir", str(session_dir)])
    if _has_session(session_dir):
        args.append("--continue")
    args.append(_json(node_input))
    env = os.environ.copy()
    env["PI_CODING_AGENT_DIR"] = str(workspace / "pi-home")
    env["RIG_IDENTITY"] = f"node:{instance_id}"
    process = await asyncio.create_subprocess_exec(*args, cwd=workspace, env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise NodeExecutionError(f"pi failed for {config.name}: {stderr.decode(errors='replace').strip()}")
    try:
        return json.loads(stdout.decode()), str(session_dir)
    except json.JSONDecodeError as exc:
        raise NodeExecutionError(f"pi returned invalid JSON for {config.name}") from exc
    finally:
        (workspace / "pi-home" / "models.json").unlink(missing_ok=True)
        if system.retention_count == 0 and workspace.exists():
            shutil.rmtree(workspace)


def prepare_workspace(
    config: NodeConfig,
    workspace: Path,
    session_dir: Path | None = None,
) -> Path:
    (workspace / ".pi").mkdir(parents=True, exist_ok=True)
    (session_dir or workspace / "sessions").mkdir(parents=True, exist_ok=True)
    (workspace / "pi-home").mkdir(parents=True, exist_ok=True)
    (workspace / "AGENTS.md").write_text(f"{_agent_contract(config.input_type, config.output_type)}\n")
    (workspace / ".pi" / "SYSTEM.md").write_text("You are a JSON-only stock analysis agent.\n")
    model = config.parameters.get("model")
    if not isinstance(model, str) or not model:
        raise NodeExecutionError("model not configured for instance")
    (workspace / ".pi" / "settings.json").write_text(json.dumps({"defaultModel": model}))
    models_config = Path.home() / ".pi" / "agent" / "models.json"
    if models_config.exists():
        shutil.copy2(models_config, workspace / "pi-home" / "models.json")
    return workspace


def resolve_session_dir(ref: str | None, workspace_root: Path, instance_id: str, cycle_id: str) -> Path:
    if ref is None:
        return workspace_root / "sandbox" / instance_id / cycle_id / "sessions"
    if ref.startswith("/"):
        return Path(ref)
    parts = ref.split(":")
    if len(parts) != 3 or parts[0] != "sandbox":
        raise NodeExecutionError(f"invalid session_dir: {ref}")
    node_id, origin_cycle = parts[1], parts[2]
    if origin_cycle == "latest":
        origin_cycle = _latest_cycle(workspace_root / "sandbox" / node_id)
    sandbox = workspace_root / "sandbox" / node_id / origin_cycle
    if not sandbox.exists():
        raise NodeExecutionError(f"session sandbox not found: {sandbox}")
    return sandbox / "sessions"


def cleanup_sandboxes(system: SystemConfig, referenced: set[str] | None = None) -> None:
    root = system.workspace_root / "sandbox"
    if not root.exists():
        return
    referenced = referenced or set()
    now = time.time()
    for node_dir in root.iterdir():
        if not node_dir.is_dir():
            continue
        sandboxes = sorted((item for item in node_dir.iterdir() if item.is_dir()), key=lambda p: p.stat().st_mtime, reverse=True)
        for index, sandbox in enumerate(sandboxes):
            ref = f"sandbox:{node_dir.name}:{sandbox.name}"
            if ref in referenced:
                continue
            expired_by_count = system.retention_count > 0 and index >= system.retention_count
            expired_by_age = system.retention_hours > 0 and now - sandbox.stat().st_mtime > system.retention_hours * 3600
            expired_by_size = system.sandbox_max_bytes > 0 and _dir_size(sandbox) > system.sandbox_max_bytes
            if expired_by_count or expired_by_age or expired_by_size:
                shutil.rmtree(sandbox)


def _json(value: object) -> str:
    if isinstance(value, BaseModel):
        return value.model_dump_json()
    return json.dumps(value, default=str)


def _session_ref(config: NodeConfig, node_input: NodeInput) -> str | None:
    if isinstance(node_input.payload, dict) and isinstance(node_input.payload.get("resume_session"), str):
        return str(node_input.payload["resume_session"])
    value = config.parameters.get("session_dir")
    return value if isinstance(value, str) else None


def _has_session(session_dir: Path) -> bool:
    return session_dir.exists() and any(session_dir.glob("*.jsonl"))


def _latest_cycle(node_dir: Path) -> str:
    if not node_dir.exists():
        raise NodeExecutionError(f"session sandbox not found: {node_dir}")
    candidates = [item for item in node_dir.iterdir() if item.is_dir()]
    if not candidates:
        raise NodeExecutionError(f"session sandbox not found: {node_dir}")
    return max(candidates, key=lambda p: p.stat().st_mtime).name


def _dir_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _workspace_for_session(session_dir: Path, workspace_root: Path, instance_id: str, cycle_id: str) -> Path:
    default_workspace = workspace_root / "sandbox" / instance_id / cycle_id
    return session_dir.parent if session_dir.name == "sessions" else default_workspace


def _agent_contract(input_type: str, output_type: str) -> str:
    contract = [
        "Return JSON only.",
        "Do not wrap JSON in markdown fences.",
        f"Input type: {input_type}",
        f"Output type: {output_type}",
    ]
    if output_type == "list[AnalysisResult]":
        contract.append("Return an array of objects with raw_item_id, summary, keywords, sentiment, confidence, source_quote, source_url, rationale, contradiction.")
    return "\n".join(contract)
