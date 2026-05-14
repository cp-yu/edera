from __future__ import annotations

import asyncio
import json
import os
import shutil
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel

from stockimformation.config.schema import NodeConfig, RuntimeSettings, SystemConfig
from stockimformation.errors import NodeExecutionError
from stockimformation.node.models import FunctionHandler, NodeContext, NodeInput, NodeOutput
from stockimformation.node.skills import load_skill


class NodeExecutor:
    def __init__(
        self,
        nodes: dict[str, NodeConfig],
        system: SystemConfig,
        runtime: RuntimeSettings,
        handlers: dict[str, FunctionHandler] | None = None,
        skills_dir: Path = Path("skills"),
    ) -> None:
        self.nodes = nodes
        self.system = system
        self.runtime = runtime
        self.handlers = handlers or {}
        self.skills_dir = skills_dir

    async def execute(
        self,
        node_name: str,
        node_input: NodeInput,
        context: NodeContext | None = None,
    ) -> NodeOutput:
        config = self._node(node_name)
        context = context or NodeContext(node_input.cycle_id, uuid4().hex)
        try:
            payload = await self._execute_payload(config, node_input, context)
        except Exception as exc:
            return NodeOutput(
                node_name=node_name,
                ok=False,
                metadata={"cycle_id": node_input.cycle_id},
                error=str(exc),
            )
        return NodeOutput(
            node_name=node_name,
            ok=True,
            payload=payload,
            metadata={"cycle_id": node_input.cycle_id},
        )

    async def _execute_payload(
        self,
        config: NodeConfig,
        node_input: NodeInput,
        context: NodeContext,
    ) -> object:
        for skill in config.skills:
            load_skill(skill.name, self.skills_dir)
        timeout = config.timeout_seconds or self.system.llm_timeout_seconds
        if config.type == "function":
            handler = self.handlers.get(config.skills[0].name)
            if handler is None:
                raise NodeExecutionError(f"missing function handler: {config.skills[0].name}")
            return await asyncio.wait_for(handler(node_input), timeout=timeout)
        return await asyncio.wait_for(self._run_pi(config, node_input, context), timeout=timeout)

    async def _run_pi(
        self,
        config: NodeConfig,
        node_input: NodeInput,
        context: NodeContext,
    ) -> object:
        workspace = self._prepare_workspace(config, context)
        skill_paths = [str(load_skill(skill.name, self.skills_dir).path) for skill in config.skills]
        input_json = _json(node_input)
        args = [self.runtime.pi_bin, "-p", "--no-skills"]
        for path in skill_paths:
            args.extend(["--skill", path])
        args.extend(
            [
                "--no-extensions",
                "--no-prompt-templates",
                "--no-themes",
                "--session-dir",
                str(workspace / "sessions"),
                input_json,
            ]
        )
        env = os.environ.copy()
        env["PI_CODING_AGENT_DIR"] = str(workspace / "pi-home")
        process = await asyncio.create_subprocess_exec(
            *args,
            cwd=workspace,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            raise NodeExecutionError(
                f"pi failed for {config.name}: {stderr.decode(errors='replace').strip()}"
            )
        try:
            return json.loads(stdout.decode())
        except json.JSONDecodeError as exc:
            raise NodeExecutionError(f"pi returned invalid JSON for {config.name}") from exc
        finally:
            self._cleanup_success(workspace)

    def _prepare_workspace(self, config: NodeConfig, context: NodeContext) -> Path:
        workspace = self.system.workspace_root / context.cycle_id / f"{config.name}-{context.instance_id}"
        (workspace / ".pi").mkdir(parents=True, exist_ok=True)
        (workspace / "sessions").mkdir(parents=True, exist_ok=True)
        (workspace / "pi-home").mkdir(parents=True, exist_ok=True)
        (workspace / "AGENTS.md").write_text(
            f"Return JSON only.\nInput type: {config.input_type}\nOutput type: {config.output_type}\n"
        )
        (workspace / ".pi" / "SYSTEM.md").write_text("You are a JSON-only stock analysis agent.\n")
        (workspace / ".pi" / "settings.json").write_text(json.dumps({"model": config.model}))
        return workspace

    def _cleanup_success(self, workspace: Path) -> None:
        if self.system.retention_count == 0 and workspace.exists():
            shutil.rmtree(workspace)

    def _node(self, node_name: str) -> NodeConfig:
        try:
            return self.nodes[node_name]
        except KeyError as exc:
            raise NodeExecutionError(f"missing node config: {node_name}") from exc


def _json(value: object) -> str:
    if isinstance(value, BaseModel):
        return value.model_dump_json()
    return json.dumps(value, default=str)
