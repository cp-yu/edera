from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import os
import re
from collections.abc import Awaitable, Callable, Iterable
from pathlib import Path
from types import ModuleType
from typing import Any, cast
from uuid import uuid4

from edera_types import HandlerContext, NodeInput, NodeOutput, RuntimeSourceRecoveryRecorder

from edera_core.config.entities import EntityStore
from edera_core.config.schema import (
    AgentNodeConfig,
    DagNodeConfig,
    DagNodeInstance,
    EntityConfig,
    NodeConfig,
    NodeConfigBase,
    RuntimeSettings,
    SystemConfig,
    WaitNodeConfig,
)
from edera_core.events import event_bus
from edera_core.errors import ConfigError, NodeExecutionError
from edera_core.node.models import NodeContext
from edera_core.registry import HandlerRegistry

OutputRecorder = Callable[[str, str, str, object, str | None], Awaitable[None]]
StdoutRecorder = Callable[[str, str, str], Awaitable[None]]
RawLogRecorder = Callable[[str, str, str, str, int], Awaitable[None]]
ExecutionSummaryRecorder = Callable[[str, str, dict[str, object]], Awaitable[None]]
DagExecutor = Callable[[DagNodeConfig, str, NodeInput, NodeContext], Awaitable[NodeOutput]]
AgentCertificateIssuer = Callable[[str, int], object]
WaitPayloadReader = Callable[[str], Awaitable[tuple[object | None, set[str]] | None]]
WaitRegister = Callable[[str, bool], asyncio.Future[object | None]]
WaitUnregister = Callable[[asyncio.Future[object | None]], None]
WaitMatchedTokens = Callable[[asyncio.Future[object | None]], set[str]]
WaitConsumer = Callable[[Iterable[str]], Awaitable[None]]
WaitRecorder = Callable[[str, str, str, str | None, str | None, dict[str, object] | None], Awaitable[None]]
_WAIT_TIMEOUT = object()
_WAIT_STOPPED = object()


class NodeExecutor:
    def __init__(
        self,
        nodes: dict[str, NodeConfig],
        system: SystemConfig,
        runtime: RuntimeSettings,
        handler_registry: HandlerRegistry | dict[str, object] | None = None,
        instances: dict[str, DagNodeInstance] | None = None,
        entity_store: EntityStore | None = None,
        output_recorder: OutputRecorder | None = None,
        stdout_recorder: StdoutRecorder | None = None,
        raw_log_recorder: RawLogRecorder | None = None,
        execution_summary_recorder: ExecutionSummaryRecorder | None = None,
        dag_executor: DagExecutor | None = None,
        agent_certificate_issuer: AgentCertificateIssuer | None = None,
        extension_tables: dict[str, dict[str, str]] | None = None,
        daemon_data_dir: Path | None = None,
        source_recovery_recorder: RuntimeSourceRecoveryRecorder | None = None,
        wait_payload_reader: WaitPayloadReader | None = None,
        wait_register: WaitRegister | None = None,
        wait_unregister: WaitUnregister | None = None,
        wait_matched_tokens: WaitMatchedTokens | None = None,
        wait_consumer: WaitConsumer | None = None,
        wait_recorder: WaitRecorder | None = None,
        wait_stop_event: asyncio.Event | None = None,
        **legacy_kwargs: object,
    ) -> None:
        if handler_registry is None:
            legacy_handlers = legacy_kwargs.get("handlers", {})
            handler_registry = legacy_handlers if isinstance(legacy_handlers, dict) else {}
        legacy_instances = legacy_kwargs.get("instances")
        if instances is None and isinstance(legacy_instances, dict):
            instances = {
                str(key): value
                for key, value in legacy_instances.items()
                if isinstance(value, DagNodeInstance)
            }
        self.nodes = nodes
        self.system = system
        self.runtime = runtime
        self.handler_registry = handler_registry if isinstance(handler_registry, HandlerRegistry) else HandlerRegistry()
        self._memory_handlers = handler_registry if isinstance(handler_registry, dict) else {}
        self.instances = instances or {}
        self.entity_store = entity_store
        self.output_recorder = output_recorder
        self.stdout_recorder = stdout_recorder
        self.raw_log_recorder = raw_log_recorder
        self.execution_summary_recorder = execution_summary_recorder
        self.dag_executor = dag_executor
        self.agent_certificate_issuer = agent_certificate_issuer
        self.extension_tables = extension_tables or {}
        self.daemon_data_dir = daemon_data_dir
        self.source_recovery_recorder = source_recovery_recorder
        self.wait_payload_reader = wait_payload_reader
        self.wait_register = wait_register
        self.wait_unregister = wait_unregister
        self.wait_matched_tokens = wait_matched_tokens
        self.wait_consumer = wait_consumer
        self.wait_recorder = wait_recorder
        self.wait_stop_event = wait_stop_event
        self._modules: dict[str, ModuleType] = {}
        self._agent_processes: dict[tuple[str, str], asyncio.subprocess.Process] = {}

    async def execute(
        self,
        node_name: str,
        node_input: NodeInput,
        context: NodeContext | None = None,
    ) -> NodeOutput:
        output = await self._execute(node_name, node_input, context)
        await self._record_execution_summary(node_name, node_input, output)
        return output

    async def _execute(
        self,
        node_name: str,
        node_input: NodeInput,
        context: NodeContext | None = None,
    ) -> NodeOutput:
        instance = self.instances.get(node_name)
        context = context or NodeContext(node_input.run_id, node_name or uuid4().hex)
        type_name = instance.type if instance else context.node_type or node_name
        try:
            config = self._node(type_name)
        except NodeExecutionError as exc:
            return _failed(node_name, node_input, str(exc))
        if isinstance(config, WaitNodeConfig):
            return await self._execute_wait(node_name, node_input, context, config)
        if isinstance(config, AgentNodeConfig):
            return await self._execute_agent(node_name, node_input, context, config, instance)
        if isinstance(config, DagNodeConfig):
            if self.dag_executor is None:
                return _failed(node_name, node_input, "dag executor not configured")
            return await self.dag_executor(config, node_name, node_input, context)
        handler_name = config.handler or config.name
        if handler_name not in self.handler_registry and handler_name not in self._memory_handlers:
            return _failed(node_name, node_input, f"handler not registered: {handler_name}")
        context = NodeContext(
            run_id=context.run_id,
            instance_id=context.instance_id,
            node_type=config.name,
            dag_name=context.dag_name,
            entity_store=self.entity_store,
            entity_permissions=_entity_permissions(instance),
        )
        try:
            effective = _apply_instance_config(config, instance)
            effective_input = _apply_instance_input(effective, node_input, instance, self.entity_store)
            payload = await self._execute_payload(handler_name, effective, effective_input, context)
        except Exception as exc:
            return _failed(node_name, node_input, str(exc))
        metadata = _output_metadata(effective_input)
        if isinstance(payload, NodeOutput):
            if payload.ok:
                await self._record_output(effective_input, node_name, effective, payload.payload, metadata)
            return payload
        await self._record_output(effective_input, node_name, effective, payload, metadata)
        return NodeOutput(node_name=node_name, ok=True, payload=payload, metadata=metadata)

    async def _execute_wait(
        self,
        node_name: str,
        node_input: NodeInput,
        context: NodeContext,
        config: WaitNodeConfig,
    ) -> NodeOutput:
        if (
            self.wait_payload_reader is None
            or self.wait_register is None
            or self.wait_unregister is None
            or self.wait_matched_tokens is None
            or self.wait_consumer is None
        ):
            return _failed(node_name, node_input, "wait executor not configured")
        metadata = _output_metadata(node_input)
        current = await self.wait_payload_reader(config.wait_for)
        if current is not None:
            payload, tokens = current
            await self._record_output(node_input, node_name, config, payload, metadata)
            if config.consume:
                await self.wait_consumer(tokens)
            return NodeOutput(node_name=node_name, ok=True, payload=payload, metadata=metadata)
        future = self.wait_register(config.wait_for, config.consume)
        try:
            current = await self.wait_payload_reader(config.wait_for)
            if current is not None:
                payload, tokens = current
                await self._record_output(node_input, node_name, config, payload, metadata)
                if config.consume:
                    await self.wait_consumer(tokens)
                return NodeOutput(node_name=node_name, ok=True, payload=payload, metadata=metadata)
            if self.wait_recorder is not None:
                await self.wait_recorder(node_input.run_id, node_name, "waiting", None, None, None)
            await event_bus.publish("node.waiting", run_id=node_input.run_id, node=node_name, node_id=node_name, wait_for=config.wait_for)
            payload = await self._await_waiter(future, config.timeout_seconds)
            if payload is _WAIT_STOPPED:
                return NodeOutput(node_name=node_name, ok=False, metadata={"runtime_status": "cancelled"}, error="cancelled")
            if payload is _WAIT_TIMEOUT:
                return NodeOutput(
                    node_name=node_name,
                    ok=False,
                    metadata={"failure_kind": "wait_timeout"},
                    error="wait timeout",
                )
            if self.wait_recorder is not None:
                await self.wait_recorder(node_input.run_id, node_name, "running", None, None, None)
            tokens = self.wait_matched_tokens(future)
            await self._record_output(node_input, node_name, config, payload, metadata)
            if config.consume:
                await self.wait_consumer(tokens)
            return NodeOutput(node_name=node_name, ok=True, payload=payload, metadata=metadata)
        finally:
            self.wait_unregister(future)

    async def _await_waiter(self, future: asyncio.Future[object | None], timeout: float | None) -> object:
        wait_items: set[asyncio.Future[object | None] | asyncio.Task[bool]] = {future}
        stop_task: asyncio.Task[bool] | None = None
        if self.wait_stop_event is not None:
            stop_task = asyncio.create_task(self.wait_stop_event.wait())
            wait_items.add(stop_task)
        done, pending = await asyncio.wait(wait_items, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            if task is stop_task:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        if not done:
            future.cancel()
            return _WAIT_TIMEOUT
        if stop_task is not None and stop_task in done:
            future.cancel()
            return _WAIT_STOPPED
        return future.result()

    async def _record_output(
        self,
        node_input: NodeInput,
        node_name: str,
        config: NodeConfig,
        payload: object,
        metadata: dict[str, object],
    ) -> None:
        if self.output_recorder is None:
            return
        if _payload_empty(payload):
            return
        await self.output_recorder(
            node_input.run_id,
            node_name,
            _entity_type_from_output(config.output_type),
            payload,
            str(metadata["session_id"]) if isinstance(metadata.get("session_id"), str) else None,
        )

    async def _execute_payload(
        self,
        handler_name: str,
        config: NodeConfig,
        node_input: NodeInput,
        context: NodeContext,
    ) -> object:
        handler = self._load_handler(handler_name)
        timeout = config.timeout_seconds if config.timeout_seconds is not None else self.system.llm_timeout_seconds
        if handler_name in self._memory_handlers:
            result = cast(Callable[[NodeInput], object], handler)(node_input)
            return await _await_handler_result(handler_name, result, timeout)
        ctx = HandlerContext(
            input=node_input,
            params=config.parameters,
            node_name=context.instance_id,
            node_type=config.name,
            run_id=node_input.run_id,
            entity_store=self.entity_store or _EmptyEntityStore(),
            storage=self._handler_storage(handler_name),
            runtime=_RuntimeContext(node_input.run_id, context.instance_id, self.source_recovery_recorder),
        )
        result = cast(Callable[[HandlerContext], object], handler)(ctx)
        return await _await_handler_result(handler_name, result, timeout)

    async def _execute_agent(
        self,
        node_name: str,
        node_input: NodeInput,
        context: NodeContext,
        config: AgentNodeConfig,
        instance: DagNodeInstance | None,
    ) -> NodeOutput:
        effective = _apply_agent_instance_config(config, instance)
        session_dir = _agent_session_dir(self._agent_data_dir(), context.dag_name, context.instance_id, node_input.run_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        runtime_context = _agent_runtime_context(node_input, context)
        (session_dir / "runtime-context.json").write_text(json.dumps(runtime_context, ensure_ascii=False), encoding="utf-8")
        cmd = [self.runtime.pi_bin, "--model", effective.model, "--session-dir", str(session_dir)]
        if any(session_dir.iterdir()):
            cmd.append("--continue")
        prompt = _agent_prompt(node_input.payload, runtime_context)
        if prompt:
            cmd.extend(["--prompt", prompt])
        env = os.environ.copy()
        env.update(_agent_env(context.instance_id))
        workdir = effective.workdir or session_dir.parent
        timeout = effective.timeout_seconds if effective.timeout_seconds is not None else self.system.llm_timeout_seconds
        cert = self.agent_certificate_issuer(context.instance_id, int(timeout or 3600)) if self.agent_certificate_issuer else None
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(workdir),
                env={**env, **_agent_cert_env(cert)} if cert is not None else env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            self._agent_processes[(node_input.run_id, node_name)] = process
            lines = await asyncio.wait_for(
                self._stream_stdout(process, node_input.run_id, node_name, session_dir / "stdout.log"),
                timeout=timeout or None,
            )
            code = await process.wait()
        except Exception as exc:
            return _failed(node_name, node_input, str(exc))
        finally:
            self._agent_processes.pop((node_input.run_id, node_name), None)
        metadata = _output_metadata(node_input)
        metadata["session_id"] = str(session_dir)
        metadata["raw_log_path"] = str(session_dir / "stdout.log")
        if code != 0:
            return NodeOutput(node_name=node_name, ok=False, metadata=metadata, error=f"pi exited with code {code}")
        payload = {"stdout": "\n".join(lines), "session_id": str(session_dir)}
        await self._record_output(node_input, node_name, config, payload, metadata)
        return NodeOutput(node_name=node_name, ok=True, payload=payload, metadata=metadata)

    def stop_agent(self, run_id: str, node_name: str) -> bool:
        process = self._agent_processes.get((run_id, node_name))
        if process is None or process.returncode is not None:
            return False
        process.terminate()
        return True

    def _agent_data_dir(self) -> Path:
        if self.daemon_data_dir is not None:
            return self.daemon_data_dir
        return Path(os.environ.get("EDERA_DATA_DIR", self.system.workspace_root))

    async def _stream_stdout(
        self,
        process: asyncio.subprocess.Process,
        run_id: str,
        node_name: str,
        log_path: Path,
    ) -> list[str]:
        lines: list[str] = []
        digest = hashlib.sha256()
        size = 0
        with log_path.open("wb") as raw_log:
            if process.stdout is not None:
                while True:
                    line = await process.stdout.readline()
                    if not line:
                        break
                    raw_log.write(line)
                    digest.update(line)
                    size += len(line)
                    text = line.decode(errors="replace").rstrip("\n")
                    lines.append(text)
                    if self.stdout_recorder is not None:
                        await self.stdout_recorder(run_id, node_name, text)
        if self.raw_log_recorder is not None:
            await self.raw_log_recorder(run_id, node_name, str(log_path), digest.hexdigest(), size)
        return lines

    async def _record_execution_summary(
        self,
        node_name: str,
        node_input: NodeInput,
        output: NodeOutput,
    ) -> None:
        if self.execution_summary_recorder is None:
            return
        summary = {
            "run_id": node_input.run_id,
            "node_id": node_name,
            "ok": output.ok,
            "status": "succeeded" if output.ok else "failed",
            "error": output.error,
            "failure_kind": _summary_failure_kind(output),
            "payload_empty": _payload_empty(output.payload),
            "session_id": output.metadata.get("session_id") if isinstance(output.metadata.get("session_id"), str) else None,
            "raw_log_path": output.metadata.get("raw_log_path") if isinstance(output.metadata.get("raw_log_path"), str) else None,
        }
        await self.execution_summary_recorder(node_input.run_id, node_name, summary)

    def _node(self, node_name: str) -> NodeConfigBase:
        if self.entity_store is not None and "node" in self.entity_store.entity_types:
            try:
                return _node_from_entity(self.entity_store.resolve(f"node:{node_name}"))
            except ConfigError:
                pass
        try:
            return self.nodes[node_name]
        except KeyError as exc:
            raise NodeExecutionError(f"missing node config: {node_name}") from exc

    def _load_handler(self, name: str) -> object:
        if name in self._memory_handlers:
            return self._memory_handlers[name]
        entry = self.handler_registry[name]
        module = self._modules.get(name)
        if module is None:
            spec = importlib.util.spec_from_file_location(f"edera_extension_{name}", entry.path)
            if spec is None or spec.loader is None:
                raise NodeExecutionError(f"cannot load handler: {name}")
            module = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(module)
            except SyntaxError as exc:
                raise NodeExecutionError(f"syntax error in handler {entry.path}: {exc}") from exc
            self._modules[name] = module
        handler = getattr(module, entry.function, None)
        if not callable(handler):
            raise NodeExecutionError(f"handler missing function {entry.function}: {name}")
        return handler

    def _handler_storage(self, handler_name: str) -> _ExtensionStorage | None:
        entry = self.handler_registry[handler_name] if handler_name in self.handler_registry else None
        tables = self.extension_tables.get(handler_name)
        if not tables and entry is not None:
            tables = self.extension_tables.get(entry.path.parent.name)
        return _ExtensionStorage(tables) if tables else None


async def _await_handler_result(handler_name: str, result: object, timeout: float | None) -> object:
    if not asyncio.iscoroutine(result):
        raise NodeExecutionError(f"handler must be async: {handler_name}")
    return await asyncio.wait_for(cast(Awaitable[object], result), timeout=timeout or None)


class _EmptyEntityStore:
    def query(self, type: str | None = None) -> list[object]:
        return []

    def resolve(self, ref: str) -> object:
        raise ConfigError(f"Entity not found: {ref}")

    def related_refs(self, ref: str) -> list[str]:
        return []


class _ExtensionStorage:
    def __init__(self, tables: dict[str, str]) -> None:
        self._tables = tables

    def table(self, name: str) -> str:
        try:
            return self._tables[name]
        except KeyError as exc:
            raise NodeExecutionError(f"extension table not declared: {name}") from exc


class _RuntimeContext:
    def __init__(
        self,
        run_id: str,
        node_id: str,
        recorder: RuntimeSourceRecoveryRecorder | None,
    ) -> None:
        self._run_id = run_id
        self._node_id = node_id
        self._recorder = recorder

    async def record_source_recovery(self, source_name: str, summary: dict[str, Any]) -> None:
        if self._recorder is None:
            return
        await self._recorder(self._run_id, self._node_id, source_name, summary)


def _failed(node_name: str, node_input: NodeInput, error: str) -> NodeOutput:
    return NodeOutput(node_name=node_name, ok=False, metadata=_output_metadata(node_input), error=error)


def _payload_empty(payload: object) -> bool:
    return payload is None or payload == [] or payload == {}


def _summary_failure_kind(output: NodeOutput) -> str | None:
    if output.ok:
        return None
    failure_kind = output.metadata.get("failure_kind")
    return failure_kind if isinstance(failure_kind, str) and failure_kind else "executor_error"


def _apply_instance_config(config: NodeConfigBase, instance: DagNodeInstance | None) -> NodeConfigBase:
    if instance is None:
        return config
    updates: dict[str, object] = {}
    model = instance.config.get("model")
    if model is not None:
        if not isinstance(model, str) or not model:
            raise NodeExecutionError("model must be a non-empty string")
        if isinstance(config, AgentNodeConfig):
            updates["model"] = model
        else:
            _update_parameters(updates, config.parameters, {"model": model})
    elif _uses_pi(config):
        raise NodeExecutionError("model not configured for instance")
    tools = instance.config.get("tools")
    if hasattr(config, "tools") and isinstance(tools, list):
        updates["tools"] = [str(item) for item in tools]
    source_names = instance.config.get("source_names")
    if hasattr(config, "source_names") and isinstance(source_names, list):
        updates["source_names"] = [str(item) for item in source_names]
    raw_parameters = instance.config.get("parameters")
    if hasattr(config, "parameters") and isinstance(raw_parameters, dict):
        _update_parameters(updates, config.parameters, raw_parameters)
    session_dir = instance.config.get("session_dir")
    if hasattr(config, "parameters") and isinstance(session_dir, str):
        _update_parameters(updates, config.parameters, {"session_dir": session_dir})
    return config.model_copy(update=updates)


def _apply_agent_instance_config(config: AgentNodeConfig, instance: DagNodeInstance | None) -> AgentNodeConfig:
    if instance is None:
        return config
    updates: dict[str, object] = {}
    model = instance.config.get("model")
    if isinstance(model, str) and model:
        updates["model"] = model
    tools = instance.config.get("tools")
    if isinstance(tools, list):
        updates["tools"] = [str(item) for item in tools]
    workdir = instance.config.get("workdir")
    if isinstance(workdir, str) and workdir:
        updates["workdir"] = Path(workdir)
    return config.model_copy(update=updates)


def _update_parameters(updates: dict[str, object], defaults: dict[str, Any], values: dict[str, Any]) -> None:
    current = updates.get("parameters")
    merged = dict(current) if isinstance(current, dict) else dict(defaults)
    merged.update(values)
    updates["parameters"] = merged


def _apply_instance_input(
    config: NodeConfig,
    node_input: NodeInput,
    instance: DagNodeInstance | None,
    entity_store: EntityStore | None,
) -> NodeInput:
    entities = _instance_entities(instance, entity_store)
    source_names = getattr(config, "source_names", [])
    if not source_names and not entities:
        return node_input
    payload = dict(node_input.payload) if isinstance(node_input.payload, dict) else {}
    if isinstance(node_input.payload, dict) and "resume_session" in node_input.payload:
        payload["resume_session"] = node_input.payload["resume_session"]
    if entities:
        payload["entities"] = entities
        payload["source_names"] = _source_names(entities)
    else:
        payload["source_names"] = source_names
    return NodeInput(run_id=node_input.run_id, payload=payload, metadata=node_input.metadata)


def _entity_permissions(instance: DagNodeInstance | None) -> dict[str, object]:
    if instance is None:
        return {}
    permissions = instance.config.get("entity_permissions")
    return permissions if isinstance(permissions, dict) else {}


def _instance_entities(
    instance: DagNodeInstance | None,
    entity_store: EntityStore | None,
) -> list[str]:
    if instance is None or entity_store is None:
        return []
    raw = instance.config.get("entities")
    if isinstance(raw, list):
        return [str(item) for item in raw]
    source = instance.config.get("source")
    if isinstance(source, str):
        return entity_store.related_refs(source)
    return []


def _source_names(entities: list[str]) -> list[str]:
    names: list[str] = []
    for ref in entities:
        if ref.startswith("rss-source:"):
            names.append(ref.removeprefix("rss-source:"))
        if ref.startswith("web-source:"):
            names.append(ref.removeprefix("web-source:"))
        if ref.startswith("api-source:"):
            names.append(ref.removeprefix("api-source:"))
    return names


def _output_metadata(node_input: NodeInput) -> dict[str, object]:
    return {"run_id": node_input.run_id}


def _node_from_entity(entity: EntityConfig) -> NodeConfig:
    attrs = dict(entity.attributes)
    attrs.setdefault("name", entity.id)
    if attrs.get("handler") or attrs.get("type") == "wait":
        return NodeConfig.model_validate(attrs)
    return NodeConfig.model_construct(
        name=str(attrs.get("name") or entity.id),
        type="function",
        role=attrs.get("role", "processor"),
        skills=[],
        handler=None,
        system_prompt_file=None,
        system_prompt=None,
        tools=[str(item) for item in attrs.get("tools", [])] if isinstance(attrs.get("tools"), list) else [],
        input_type=str(attrs.get("input_type") or ""),
        output_type=str(attrs.get("output_type") or ""),
        timeout_seconds=attrs.get("timeout_seconds") if isinstance(attrs.get("timeout_seconds"), int | float) else None,
        source_names=[str(item) for item in attrs.get("source_names", [])]
        if isinstance(attrs.get("source_names"), list)
        else [],
        parameters=attrs.get("parameters") if isinstance(attrs.get("parameters"), dict) else {},
        parameters_schema=attrs.get("parameters_schema") if isinstance(attrs.get("parameters_schema"), dict) else {},
    )


def _uses_pi(config: NodeConfig) -> bool:
    return config.handler in {"run-pi", "pi", "llm"}


def _agent_session_dir(root: Path, dag_name: str, instance_id: str, run_id: str) -> Path:
    return root / "sessions" / _safe_path_token(dag_name) / _safe_path_token(instance_id) / _safe_path_token(run_id)


def _safe_path_token(value: str) -> str:
    cleaned = "".join(item if item.isalnum() or item in {"-", "_", "."} else "_" for item in value)
    return cleaned or "default"


def _agent_prompt(payload: object, runtime_context: dict[str, object] | None = None) -> str:
    context = runtime_context or {}
    prefix = f"Runtime context: {json.dumps(context, ensure_ascii=False)}"
    if isinstance(payload, dict):
        prompt = payload.get("prompt")
        if isinstance(prompt, str):
            return f"{prefix}\n\n{prompt}"
    if isinstance(payload, str):
        return f"{prefix}\n\n{payload}"
    return prefix


def _agent_runtime_context(node_input: NodeInput, context: NodeContext) -> dict[str, object]:
    return {
        "run_id": node_input.run_id,
        "dag_name": context.dag_name,
        "node_id": context.instance_id,
        "edge_inputs": node_input.metadata.get("edge_inputs", []),
    }


def _agent_env(instance_id: str) -> dict[str, str]:
    return {
        "EDERA_SERVER_ADDR": os.environ.get("EDERA_SERVER_ADDR", "127.0.0.1:9090"),
        "EDERA_IDENTITY": f"node:{instance_id}",
    }


def _agent_cert_env(cert: object) -> dict[str, str]:
    return {
        "EDERA_CLIENT_CERT": str(getattr(cert, "cert_pem")),
        "EDERA_CLIENT_KEY": str(getattr(cert, "key_pem")),
        "EDERA_CA_CERT": str(getattr(cert, "ca_pem")),
    }


def _entity_type_from_output(output_type: str) -> str:
    name = output_type.strip()
    if name.startswith("list[") and name.endswith("]"):
        name = name[5:-1].strip()
    normalized = name.replace("_", "-").replace(" ", "-")
    mapped = {
        "rawitem": "raw-item",
        "raw-item": "raw-item",
        "analysisresult": "analysis",
        "analysis-result": "analysis",
        "advice": "advice",
        "briefing": "briefing",
    }
    key = re.sub(r"[^a-z0-9-]", "", _camel_to_kebab(normalized).lower())
    return mapped.get(key, key or "node-output")


def _camel_to_kebab(value: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "-", value)
