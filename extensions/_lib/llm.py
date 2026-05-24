from __future__ import annotations

import asyncio
import json
import os
import shutil
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from stockimformation_core.config.schema import NodeConfig, RuntimeSettings, SystemConfig
from stockimformation_core.errors import NodeExecutionError
from stockimformation_types import NodeInput


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
    workspace = prepare_workspace(config, cycle_id, instance_id, system)
    skill_paths = [str(skills_dir / skill) for skill in skills]
    args = [runtime.pi_bin, "-p", "--no-skills", "--no-tools"]
    for path in skill_paths:
        args.extend(["--skill", path])
    args.extend(["--no-extensions", "--no-prompt-templates", "--no-themes", "--session-dir", str(workspace / "sessions"), _json(node_input)])
    env = os.environ.copy()
    env["PI_CODING_AGENT_DIR"] = str(workspace / "pi-home")
    process = await asyncio.create_subprocess_exec(*args, cwd=workspace, env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise NodeExecutionError(f"pi failed for {config.name}: {stderr.decode(errors='replace').strip()}")
    try:
        return json.loads(stdout.decode()), str(workspace / "sessions")
    except json.JSONDecodeError as exc:
        raise NodeExecutionError(f"pi returned invalid JSON for {config.name}") from exc
    finally:
        (workspace / "pi-home" / "models.json").unlink(missing_ok=True)
        if system.retention_count == 0 and workspace.exists():
            shutil.rmtree(workspace)


def prepare_workspace(
    config: NodeConfig,
    cycle_id: str,
    instance_id: str,
    system: SystemConfig,
) -> Path:
    workspace = system.workspace_root / cycle_id / f"{config.name}-{instance_id}"
    (workspace / ".pi").mkdir(parents=True, exist_ok=True)
    (workspace / "sessions").mkdir(parents=True, exist_ok=True)
    (workspace / "pi-home").mkdir(parents=True, exist_ok=True)
    (workspace / "AGENTS.md").write_text(f"{_agent_contract(config.input_type, config.output_type)}\n")
    (workspace / ".pi" / "SYSTEM.md").write_text("You are a JSON-only stock analysis agent.\n")
    (workspace / ".pi" / "settings.json").write_text(json.dumps({"defaultModel": config.model}))
    models_config = Path.home() / ".pi" / "agent" / "models.json"
    if models_config.exists():
        shutil.copy2(models_config, workspace / "pi-home" / "models.json")
    return workspace


def _json(value: object) -> str:
    if isinstance(value, BaseModel):
        return value.model_dump_json()
    return json.dumps(value, default=str)


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
