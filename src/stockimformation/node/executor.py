from __future__ import annotations

import asyncio
import importlib.util
import inspect
import json
import os
import shutil
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel

from stockimformation.config.schema import DagNodeInstance, NodeConfig, RuntimeSettings, SystemConfig
from stockimformation.errors import NodeExecutionError
from stockimformation.node.models import FunctionHandler, NodeContext, NodeInput, NodeOutput
from stockimformation.node.skills import load_skill, load_skill_handler


class NodeExecutor:
    def __init__(
        self,
        nodes: dict[str, NodeConfig],
        system: SystemConfig,
        runtime: RuntimeSettings,
        handlers: dict[str, FunctionHandler] | None = None,
        instances: dict[str, DagNodeInstance] | None = None,
        handlers_dir: Path = Path("handlers"),
        skills_dir: Path = Path("skills"),
        skill_handlers_dir: Path = Path("skill_handlers"),
    ) -> None:
        self.nodes = nodes
        self.system = system
        self.runtime = runtime
        self.handlers = handlers or {}
        self.instances = instances or {}
        self.handlers_dir = handlers_dir
        self.skills_dir = skills_dir
        self.skill_handlers_dir = skill_handlers_dir

    async def execute(
        self,
        node_name: str,
        node_input: NodeInput,
        context: NodeContext | None = None,
    ) -> NodeOutput:
        instance = self.instances.get(node_name)
        context = context or NodeContext(node_input.cycle_id, node_name or uuid4().hex)
        type_name = instance.type if instance else context.node_type or node_name
        config = self._node(type_name)
        context = NodeContext(
            cycle_id=context.cycle_id,
            instance_id=context.instance_id,
            node_type=config.name,
            dag_name=context.dag_name,
        )
        effective = _apply_instance_config(config, instance)
        effective_input = _apply_instance_input(effective, node_input)
        try:
            payload = await self._execute_payload(effective, effective_input, context)
        except Exception as exc:
            return NodeOutput(
                node_name=node_name,
                ok=False,
                metadata=_output_metadata(effective_input),
                error=str(exc),
            )
        return NodeOutput(
            node_name=node_name,
            ok=True,
            payload=payload,
            metadata=_output_metadata(effective_input),
        )

    async def _execute_payload(
        self,
        config: NodeConfig,
        node_input: NodeInput,
        context: NodeContext,
    ) -> object:
        timeout = config.timeout_seconds or self.system.llm_timeout_seconds
        if config.type == "function":
            handler_name = config.handler or (config.skills[0] if config.skills else "")
            handler = self.handlers.get(handler_name) or self._load_handler(handler_name)
            if handler is None:
                raise NodeExecutionError(f"missing function handler: {handler_name}")
            return await asyncio.wait_for(
                _call_handler(handler, node_input, config.parameters, context),
                timeout=timeout,
            )
        for skill in config.skills:
            load_skill_handler(skill, self.skill_handlers_dir)
        return await asyncio.wait_for(
            self._run_pi(config, config.skills, node_input, context),
            timeout=timeout,
        )

    async def _run_pi(
        self,
        config: NodeConfig,
        skills: list[str],
        node_input: NodeInput,
        context: NodeContext,
    ) -> object:
        workspace = self._prepare_workspace(config, context)
        skill_paths = [str(load_skill(skill, self.skills_dir).path) for skill in skills]
        input_json = _json(node_input)
        args = [self.runtime.pi_bin, "-p", "--no-skills", "--no-tools"]
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
            (workspace / "pi-home" / "models.json").unlink(missing_ok=True)
            self._cleanup_success(workspace)

    def _prepare_workspace(self, config: NodeConfig, context: NodeContext) -> Path:
        workspace = self.system.workspace_root / context.cycle_id / f"{config.name}-{context.instance_id}"
        (workspace / ".pi").mkdir(parents=True, exist_ok=True)
        (workspace / "sessions").mkdir(parents=True, exist_ok=True)
        (workspace / "pi-home").mkdir(parents=True, exist_ok=True)
        (workspace / "AGENTS.md").write_text(
            f"{_agent_contract(config.input_type, config.output_type)}\n"
        )
        (workspace / ".pi" / "SYSTEM.md").write_text("You are a JSON-only stock analysis agent.\n")
        (workspace / ".pi" / "settings.json").write_text(json.dumps({"defaultModel": config.model}))
        models_config = Path.home() / ".pi" / "agent" / "models.json"
        if models_config.exists():
            shutil.copy2(models_config, workspace / "pi-home" / "models.json")
        return workspace

    def _cleanup_success(self, workspace: Path) -> None:
        if self.system.retention_count == 0 and workspace.exists():
            shutil.rmtree(workspace)

    def _node(self, node_name: str) -> NodeConfig:
        try:
            return self.nodes[node_name]
        except KeyError as exc:
            raise NodeExecutionError(f"missing node config: {node_name}") from exc

    def _load_handler(self, name: str) -> FunctionHandler | None:
        path = self.handlers_dir / f"{name}.py"
        if not path.exists():
            return None
        module_name = f"stockimformation_dynamic_handler_{name.replace('-', '_')}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        handler = getattr(module, "run", None)
        return handler if callable(handler) else None


async def _call_handler(
    handler: FunctionHandler,
    node_input: NodeInput,
    parameters: dict[str, object],
    context: NodeContext,
) -> object:
    if len(inspect.signature(handler).parameters) == 1:
        result = handler(node_input)
    else:
        result = handler(node_input.payload, parameters, context)
    if inspect.isawaitable(result):
        return await result
    return result


def _apply_instance_config(config: NodeConfig, instance: DagNodeInstance | None) -> NodeConfig:
    if instance is None:
        return config
    updates: dict[str, object] = {}
    if config.type == "llm":
        skills = instance.config.get("skills")
        if isinstance(skills, list):
            updates["skills"] = [str(item) for item in skills]
        model = instance.config.get("model")
        if isinstance(model, str):
            updates["model"] = model
    if config.type == "function":
        source_names = instance.config.get("source_names")
        if isinstance(source_names, list):
            updates["source_names"] = [str(item) for item in source_names]
    parameters = instance.config.get("parameters")
    if isinstance(parameters, dict):
        updates["parameters"] = parameters
    return config.model_copy(update=updates)


def _apply_instance_input(config: NodeConfig, node_input: NodeInput) -> NodeInput:
    if config.type != "function" or not config.source_names:
        return node_input
    payload = dict(node_input.payload) if isinstance(node_input.payload, dict) else {}
    payload["source_names"] = config.source_names
    return NodeInput(cycle_id=node_input.cycle_id, payload=payload, metadata=node_input.metadata)


def _json(value: object) -> str:
    if isinstance(value, BaseModel):
        return value.model_dump_json()
    return json.dumps(value, default=str)


def _output_metadata(node_input: NodeInput) -> dict[str, object]:
    metadata: dict[str, object] = {"cycle_id": node_input.cycle_id}
    for key in ("failures", "source_recovery"):
        if key in node_input.metadata:
            metadata[key] = node_input.metadata[key]
    return metadata


def _agent_contract(input_type: str, output_type: str) -> str:
    contract = [
        "Return JSON only.",
        "Do not wrap JSON in markdown fences.",
        f"Input type: {input_type}",
        f"Output type: {output_type}",
    ]
    if output_type == "list[AnalysisResult]":
        contract.append(
            "Return an array of objects with exactly these fields: "
            "raw_item_id, summary, keywords, sentiment, confidence, "
            "source_quote, source_url, rationale, contradiction."
        )
        contract.append("raw_item_id must be an integer; use the 1-based input item index when id is null.")
        contract.append("contradiction must be true or false; never null.")
        contract.append("sentiment must be bullish, bearish, or neutral.")
    return "\n".join(contract)
