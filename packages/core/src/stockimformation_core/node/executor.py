from __future__ import annotations

import asyncio
import importlib.util
import re
from collections.abc import Awaitable, Callable
from types import ModuleType
from typing import Any, cast
from uuid import uuid4

from stockimformation_types import HandlerContext, NodeInput, NodeOutput

from stockimformation_core.config.entities import EntityStore
from stockimformation_core.config.schema import DagNodeInstance, EntityConfig, NodeConfig, RuntimeSettings, SystemConfig
from stockimformation_core.errors import ConfigError, NodeExecutionError
from stockimformation_core.node.models import NodeContext
from stockimformation_core.registry import HandlerRegistry

OutputRecorder = Callable[[str, str, str, object, str | None], Awaitable[None]]


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
        extension_tables: dict[str, dict[str, str]] | None = None,
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
        self.extension_tables = extension_tables or {}
        self._modules: dict[str, ModuleType] = {}

    async def execute(
        self,
        node_name: str,
        node_input: NodeInput,
        context: NodeContext | None = None,
    ) -> NodeOutput:
        instance = self.instances.get(node_name)
        context = context or NodeContext(node_input.cycle_id, node_name or uuid4().hex)
        type_name = instance.type if instance else context.node_type or node_name
        try:
            config = self._node(type_name)
        except NodeExecutionError as exc:
            return _failed(node_name, node_input, str(exc))
        handler_name = config.handler or config.name
        if handler_name not in self.handler_registry and handler_name not in self._memory_handlers:
            return _failed(node_name, node_input, f"handler not registered: {handler_name}")
        context = NodeContext(
            cycle_id=context.cycle_id,
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
        await self.output_recorder(
            node_input.cycle_id,
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
            if not asyncio.iscoroutine(result):
                raise NodeExecutionError(f"handler must be async: {handler_name}")
            return await asyncio.wait_for(result, timeout=timeout or None)
        ctx = HandlerContext(
            input=node_input,
            params=config.parameters,
            node_name=context.instance_id,
            node_type=config.name,
            cycle_id=node_input.cycle_id,
            entity_store=self.entity_store or _EmptyEntityStore(),
            storage=self._handler_storage(handler_name),
        )
        result = cast(Callable[[HandlerContext], object], handler)(ctx)
        if not asyncio.iscoroutine(result):
            raise NodeExecutionError(f"handler must be async: {handler_name}")
        return await asyncio.wait_for(result, timeout=timeout or None)

    def _node(self, node_name: str) -> NodeConfig:
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
            spec = importlib.util.spec_from_file_location(f"stockimformation_extension_{name}", entry.path)
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


def _failed(node_name: str, node_input: NodeInput, error: str) -> NodeOutput:
    return NodeOutput(node_name=node_name, ok=False, metadata=_output_metadata(node_input), error=error)


def _apply_instance_config(config: NodeConfig, instance: DagNodeInstance | None) -> NodeConfig:
    if instance is None:
        return config
    updates: dict[str, object] = {}
    model = instance.config.get("model")
    if model is not None:
        if not isinstance(model, str) or not model:
            raise NodeExecutionError("model must be a non-empty string")
        _update_parameters(updates, config.parameters, {"model": model})
    elif _uses_pi(config):
        raise NodeExecutionError("model not configured for instance")
    tools = instance.config.get("tools")
    if isinstance(tools, list):
        updates["tools"] = [str(item) for item in tools]
    source_names = instance.config.get("source_names")
    if isinstance(source_names, list):
        updates["source_names"] = [str(item) for item in source_names]
    raw_parameters = instance.config.get("parameters")
    if isinstance(raw_parameters, dict):
        _update_parameters(updates, config.parameters, raw_parameters)
    session_dir = instance.config.get("session_dir")
    if isinstance(session_dir, str):
        _update_parameters(updates, config.parameters, {"session_dir": session_dir})
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
    if not config.source_names and not entities:
        return node_input
    payload = dict(node_input.payload) if isinstance(node_input.payload, dict) else {}
    if isinstance(node_input.payload, dict) and "resume_session" in node_input.payload:
        payload["resume_session"] = node_input.payload["resume_session"]
    if entities:
        payload["entities"] = entities
        payload["source_names"] = _source_names(entities)
    else:
        payload["source_names"] = config.source_names
    return NodeInput(cycle_id=node_input.cycle_id, payload=payload, metadata=node_input.metadata)


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
    metadata: dict[str, object] = {"cycle_id": node_input.cycle_id}
    for key in ("failures", "source_recovery"):
        if key in node_input.metadata:
            metadata[key] = node_input.metadata[key]
    return metadata


def _node_from_entity(entity: EntityConfig) -> NodeConfig:
    attrs = dict(entity.attributes)
    attrs.setdefault("name", entity.id)
    if attrs.get("handler"):
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
