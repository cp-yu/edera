from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from stockimformation_core.config.loader import load_app_config
from stockimformation_core.config.entities import EntityStore
from stockimformation_core.config.git import commit_config_changes
from stockimformation_core.config.schema import AppConfig, DagNodeInstance
from stockimformation_core.bootstrap import create_extension_tables, scan_extensions
from stockimformation_core.dag.loader import load_graph
from stockimformation_core.dag.runner import DagRunner
from stockimformation_core.events import event_bus
from stockimformation_core.storage import create_engine, init_db, session_factory
from stockimformation_core.storage.entities import PipelineRun
from stockimformation_core.storage.repository import (
    cleanup_node_output_entities,
    create_pipeline_run,
    current_pipeline_run,
    finish_pipeline_run,
    get_pipeline_run,
    latest_finished_pipeline_run,
    mark_node_run,
    delete_node_outputs_for_nodes,
    query_node_output_entities,
    recent_pipeline_runs,
    restart_pipeline_run,
    store_node_output_entities,
)
from stockimformation_core.node.executor import NodeExecutor
from stockimformation_core.node.models import NodeOutput


class RunAlreadyActiveError(Exception):
    def __init__(self, cycle_id: str) -> None:
        self.cycle_id = cycle_id
        super().__init__(f"pipeline run already active: {cycle_id}")


class PipelineRunNotFoundError(Exception):
    def __init__(self, cycle_id: str) -> None:
        self.cycle_id = cycle_id
        super().__init__(f"pipeline run not found: {cycle_id}")


@dataclass(frozen=True)
class RetryRunResult:
    cycle_id: str
    retry_of: str
    node_ids: list[str]
    mode: str
    retry_nodes: list[str]


@dataclass
class DagRunContext:
    dag_name: str
    cycle_id: str
    task: asyncio.Task[object]
    stop_event: asyncio.Event = field(default_factory=asyncio.Event)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    executor: NodeExecutor | None = None


class PipelineController:
    def __init__(
        self,
        config_dir: Path = Path("config"),
        scheduler: AsyncIOScheduler | None = None,
        extensions_dirs: list[Path] | None = None,
        agent_certificate_issuer: Callable[[str, int], object] | None = None,
    ) -> None:
        self.config_dir = config_dir
        self.extensions_dirs = extensions_dirs or [Path("extensions")]
        self.scheduler = scheduler or AsyncIOScheduler()
        self.engine: AsyncEngine | None = None
        self.factory: async_sessionmaker[AsyncSession] | None = None
        self.active_runs: dict[str, DagRunContext] = {}
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._db_write_lock = asyncio.Lock()
        self.agent_certificate_issuer = agent_certificate_issuer

    async def start(self, run_startup: bool = True) -> None:
        config = load_app_config(self.config_dir)
        bootstrap = scan_extensions(self.extensions_dirs, self.config_dir)
        config.entity_types.update(bootstrap.entity_type_registry.as_dict())
        self.engine = create_engine(config.system.database_url)
        await init_db(self.engine)
        await create_extension_tables(self.engine, bootstrap.storage_tables)
        self.factory = session_factory(self.engine)
        for dag_name, dag_config in config.dags.items():
            self.scheduler.add_job(
                self._start_schedule_run,
                "interval",
                minutes=config.system.schedule_minutes,
                id=f"{dag_name}-dag",
                max_instances=1,
                coalesce=True,
                args=[dag_name],
            )
        self.scheduler.start()
        if run_startup:
            await self.start_run("startup")

    async def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        for ctx in list(self.active_runs.values()):
            if not ctx.task.done():
                ctx.task.cancel()
                try:
                    await ctx.task
                except asyncio.CancelledError:
                    pass
        if self.engine is not None:
            await self.engine.dispose()

    async def start_run(self, trigger: str = "manual", dag_name: str = "default", payload: object | None = None) -> str:
        await self._wait_for_idle(dag_name, payload)
        async with self._locks[dag_name]:
            cycle_id, task = self._start_run_locked(trigger, dag_name, payload)
        task.add_done_callback(lambda t: self._clear_finished_task(t, dag_name))
        return cycle_id

    async def run_now(self, trigger: str = "manual", dag_name: str = "default", payload: object | None = None) -> str:
        await self._wait_for_idle(dag_name, payload)
        async with self._locks[dag_name]:
            cycle_id, task = self._start_run_locked(trigger, dag_name, payload)
        try:
            await task
        finally:
            self._clear_finished_task(task, dag_name)
        return cycle_id

    def pause_scheduler(self) -> None:
        self.scheduler.pause()

    def resume_scheduler(self) -> None:
        self.scheduler.resume()

    async def stop_current(self, dag_name: str = "default", force: bool = False, node_id: str | None = None) -> str | None:
        ctx = self.active_runs.get(dag_name)
        if ctx is None or ctx.task.done():
            return None
        if node_id is not None and ctx.executor is not None:
            ctx.executor.stop_agent(ctx.cycle_id, node_id)
        if force:
            ctx.task.cancel()
        else:
            ctx.stop_event.set()
        try:
            await ctx.task
        except asyncio.CancelledError:
            pass
        return ctx.cycle_id

    async def retry_node(
        self,
        dag_name: str,
        cycle_id: str | None,
        node_ids: list[str],
        mode: str = "single",
        payload: object | None = None,
    ) -> RetryRunResult:
        if mode not in {"single", "cascade"}:
            raise ValueError("mode must be single or cascade")
        if not node_ids:
            raise ValueError("node_ids is required")
        async with self._locks[dag_name]:
            ctx = self.active_runs.get(dag_name)
            if ctx is not None and not ctx.task.done():
                raise RunAlreadyActiveError(ctx.cycle_id)
            config = load_app_config(self.config_dir)
            graph = load_graph(config.dags[dag_name], config.nodes)
            missing = [node_id for node_id in node_ids if node_id not in graph.instances]
            if missing:
                raise ValueError(f"node_ids contain unknown nodes: {', '.join(missing)}")
            retry_nodes = set(node_ids) if mode == "single" else _downstream_union(graph, node_ids)
            original_cycle_id = cycle_id or await self._latest_finished_cycle_id(dag_name)
            if original_cycle_id is None:
                raise PipelineRunNotFoundError("latest finished run")
            prefilled = await self._prefilled_outputs(original_cycle_id, graph, retry_nodes)
            missing_inputs = _missing_prefilled_inputs(graph, retry_nodes, set(prefilled))
            if missing_inputs:
                raise ValueError(f"missing prefilled outputs: {', '.join(missing_inputs)}")
            retry_cycle_id = uuid4().hex
            stop_event = asyncio.Event()
            task = asyncio.create_task(
                self._run(
                    retry_cycle_id,
                    "retry",
                    dag_name,
                    stop_event=stop_event,
                    retry_of=original_cycle_id,
                    retry_nodes=retry_nodes,
                    prefilled_outputs=prefilled,
                    payload=payload,
                )
            )
            self.active_runs[dag_name] = DagRunContext(
                dag_name=dag_name,
                cycle_id=retry_cycle_id,
                task=task,
                stop_event=stop_event,
            )
        task.add_done_callback(lambda t: self._clear_finished_task(t, dag_name))
        return RetryRunResult(
            cycle_id=retry_cycle_id,
            retry_of=original_cycle_id,
            node_ids=node_ids,
            mode=mode,
            retry_nodes=_graph_ordered_nodes(graph, retry_nodes),
        )

    async def resume_node(self, dag_name: str, cycle_id: str, node_id: str, payload: object) -> str:
        async with self._locks[dag_name]:
            ctx = self.active_runs.get(dag_name)
            if ctx is not None and not ctx.task.done():
                raise RunAlreadyActiveError(ctx.cycle_id)
            config = load_app_config(self.config_dir)
            graph = load_graph(config.dags[dag_name], config.nodes)
            if node_id not in graph.instances:
                raise ValueError(f"node '{node_id}' not found")
            original = await self._pipeline_run(cycle_id)
            if original is None:
                raise PipelineRunNotFoundError(cycle_id)
            retry_nodes = _downstream_nodes(graph, node_id)
            prefilled = await self._prefilled_outputs(cycle_id, graph, retry_nodes)
            await self._delete_node_outputs(cycle_id, retry_nodes)
            stop_event = asyncio.Event()
            task = asyncio.create_task(
                self._run(
                    cycle_id,
                    "retry",
                    dag_name,
                    stop_event=stop_event,
                    retry_of=original.retry_of,
                    retry_nodes=retry_nodes,
                    prefilled_outputs=prefilled,
                    payload=payload,
                    replace_existing_run=True,
                )
            )
            self.active_runs[dag_name] = DagRunContext(
                dag_name=dag_name,
                cycle_id=cycle_id,
                task=task,
                stop_event=stop_event,
            )
        task.add_done_callback(lambda t: self._clear_finished_task(t, dag_name))
        return cycle_id

    async def status(self, dag_name: str | None = None) -> dict[str, object]:
        factory = self._factory()
        if dag_name is not None:
            async with factory() as session:
                current = await current_pipeline_run(session, dag_name)
                recent = await recent_pipeline_runs(session, dag_name=dag_name)
            ctx = self.active_runs.get(dag_name)
            return {
                "scheduler_running": self.scheduler.running,
                "scheduler_paused": self.scheduler.state == 2,
                "dag_name": dag_name,
                "current_cycle_id": current.cycle_id if current else (ctx.cycle_id if ctx else None),
                "recent_runs": [_run_dict(run) for run in recent],
            }
        async with factory() as session:
            current = await current_pipeline_run(session)
            recent = await recent_pipeline_runs(session)
        return {
            "scheduler_running": self.scheduler.running,
            "scheduler_paused": self.scheduler.state == 2,
            "active_dags": {name: ctx.cycle_id for name, ctx in self.active_runs.items() if not ctx.task.done()},
            "recent_runs": [_run_dict(run) for run in recent],
        }

    async def node_status(self, node_id: str) -> str:
        for ctx in self.active_runs.values():
            if not ctx.task.done() and _dag_has_node(self.config_dir, ctx.dag_name, node_id):
                return "running"
        config = load_app_config(self.config_dir)
        factory = self._factory()
        async with factory() as session:
            for dag in config.dags.values():
                if not any(instance.id == node_id or instance.alias == node_id for instance in dag.nodes):
                    continue
                recent = await recent_pipeline_runs(session, 1, dag.name)
                if recent and recent[0].status == "failed":
                    return "failed"
        return "idle"

    async def _start_schedule_run(self, dag_name: str = "default") -> None:
        try:
            await self.start_run("schedule", dag_name)
        except RunAlreadyActiveError:
            return

    async def _wait_for_idle(self, dag_name: str, payload: object | None) -> None:
        target = _wait_for_idle_target(self.config_dir, dag_name, payload)
        if target is None:
            return
        while any(not ctx.task.done() and _dag_has_node(self.config_dir, ctx.dag_name, target) for ctx in self.active_runs.values()):
            await asyncio.sleep(0.1)

    def _start_run_locked(self, trigger: str, dag_name: str, payload: object | None = None) -> tuple[str, asyncio.Task[object]]:
        ctx = self.active_runs.get(dag_name)
        if ctx is not None and not ctx.task.done():
            raise RunAlreadyActiveError(ctx.cycle_id)
        cycle_id = uuid4().hex
        stop_event = asyncio.Event()
        task = asyncio.create_task(self._run(cycle_id, trigger, dag_name, stop_event=stop_event, payload=payload))
        self.active_runs[dag_name] = DagRunContext(dag_name=dag_name, cycle_id=cycle_id, task=task, stop_event=stop_event)
        return cycle_id, task

    def _clear_finished_task(self, task: asyncio.Task[object], dag_name: str) -> None:
        if task.done() and not task.cancelled():
            try:
                task.exception()
            except Exception:
                pass
        ctx = self.active_runs.get(dag_name)
        if ctx is not None and ctx.task is task and task.done():
            del self.active_runs[dag_name]

    async def _run(
        self,
        cycle_id: str,
        trigger: str,
        dag_name: str = "default",
        stop_event: asyncio.Event | None = None,
        retry_of: str | None = None,
        retry_nodes: set[str] | None = None,
        prefilled_outputs: dict[str, NodeOutput] | None = None,
        payload: object | None = None,
        replace_existing_run: bool = False,
    ) -> object:
        config = load_app_config(self.config_dir)
        bootstrap = scan_extensions(self.extensions_dirs, self.config_dir)
        config.entity_types.update(bootstrap.entity_type_registry.as_dict())
        graph = load_graph(config.dags[dag_name], config.nodes)
        factory = self._factory()
        if replace_existing_run:
            async with factory() as session:
                await restart_pipeline_run(session, cycle_id)
                await session.commit()
        else:
            async with factory() as session:
                await create_pipeline_run(session, cycle_id, trigger, list(graph.nodes), dag_name, retry_of)
                await session.commit()
        await event_bus.publish("dag.status", cycle_id=cycle_id, dag_name=dag_name, status="started")
        try:
            executor = _build_executor(
                config,
                bootstrap.handler_registry,
                graph.instances,
                self.config_dir,
                extension_tables=bootstrap.table_names,
                output_recorder=lambda output_cycle_id, node_id, entity_type, payload, session_id: self._record_node_output(
                    output_cycle_id, node_id, entity_type, payload, session_id
                ),
                stdout_recorder=lambda output_cycle_id, node_id, line: event_bus.publish(
                    "node.stdout",
                    cycle_id=output_cycle_id,
                    node_id=node_id,
                    line=line,
                ),
                agent_certificate_issuer=self.agent_certificate_issuer,
            )
            ctx = self.active_runs.get(dag_name)
            if ctx is not None and ctx.cycle_id == cycle_id:
                ctx.executor = executor
            result = await DagRunner(
                executor,
                recorder=lambda node, status, error: self._record_node(cycle_id, node, status, error),
            ).run(
                graph,
                cycle_id,
                payload if payload is not None else {"entities": _source_entity_refs(config)},
                stop_event=stop_event,
                retry_nodes=retry_nodes,
                prefilled_outputs=prefilled_outputs,
            )
            await _record_source_runs(factory, cycle_id, result.node_outputs)
            await _persist_outputs(
                factory,
                config.system.retention_count,
                config.system.retention_hours,
            )
            _cleanup_sandboxes(config)
            active_outputs = {
                node: output
                for node, output in result.node_outputs.items()
                if retry_nodes is None or node in retry_nodes
            }
            status = "cancelled" if stop_event is not None and stop_event.is_set() else _result_status(active_outputs)
            error = "; ".join(
                f"{node}: {message}"
                for node, message in result.failures.items()
                if retry_nodes is None or node in retry_nodes
            ) or None
            async with factory() as session:
                await finish_pipeline_run(session, cycle_id, status, error)
                await session.commit()
            await event_bus.publish("dag.status", cycle_id=cycle_id, dag_name=dag_name, status=status, error=error)
            commit_config_changes(self.config_dir, cycle_id, config.system.config_git_commit)
            return result.payload
        except asyncio.CancelledError:
            await self._finish_cancelled(cycle_id, dag_name)
            commit_config_changes(self.config_dir, cycle_id, config.system.config_git_commit)
            raise
        except Exception as exc:
            async with factory() as session:
                await finish_pipeline_run(session, cycle_id, "failed", str(exc))
                await session.commit()
            await event_bus.publish("dag.status", cycle_id=cycle_id, dag_name=dag_name, status="failed", error=str(exc))
            commit_config_changes(self.config_dir, cycle_id, config.system.config_git_commit)
            raise

    async def _prefilled_outputs(
        self,
        original_cycle_id: str,
        graph,
        retry_nodes: set[str],
    ) -> dict[str, NodeOutput]:
        factory = self._factory()
        async with factory() as session:
            original = await get_pipeline_run(session, original_cycle_id)
            if original is None:
                raise PipelineRunNotFoundError(original_cycle_id)
            outputs = await query_node_output_entities(session, cycle_id=original_cycle_id, limit=10000)
        prefilled: dict[str, NodeOutput] = {}
        payloads: dict[str, list[object]] = defaultdict(list)
        for entity in outputs:
            node_id = str(entity.attributes.get("node_id") or "")
            if node_id in graph.instances and node_id not in retry_nodes:
                payloads[node_id].append(entity.attributes.get("payload"))
        for node_id, values in payloads.items():
            payload = values[0] if len(values) == 1 else list(reversed(values))
            prefilled[node_id] = NodeOutput(node_name=node_id, ok=True, payload=payload)
        return prefilled

    async def _pipeline_run(self, cycle_id: str) -> PipelineRun | None:
        factory = self._factory()
        async with factory() as session:
            return await get_pipeline_run(session, cycle_id)

    async def _latest_finished_cycle_id(self, dag_name: str) -> str | None:
        factory = self._factory()
        async with factory() as session:
            run = await latest_finished_pipeline_run(session, dag_name)
        return run.cycle_id if run is not None else None

    async def _delete_node_outputs(self, cycle_id: str, node_ids: set[str]) -> None:
        factory = self._factory()
        async with factory() as session:
            await delete_node_outputs_for_nodes(session, cycle_id, node_ids)
            await session.commit()

    async def _record_node(
        self,
        cycle_id: str,
        node: str,
        status: str,
        error: str | None,
    ) -> None:
        async with self._db_write_lock:
            async with self._factory()() as session:
                await mark_node_run(session, cycle_id, node, status, error)
                await session.commit()

    async def _record_node_output(
        self,
        cycle_id: str,
        node_id: str,
        entity_type: str,
        payload: object,
        session_id: str | None,
    ) -> None:
        async with self._db_write_lock:
            await _record_node_output(self._factory(), cycle_id, node_id, entity_type, payload, session_id)

    async def _finish_cancelled(self, cycle_id: str, dag_name: str) -> None:
        async with self._factory()() as session:
            await finish_pipeline_run(session, cycle_id, "cancelled")
            await session.commit()
        await event_bus.publish("dag.status", cycle_id=cycle_id, dag_name=dag_name, status="cancelled")

    def _factory(self) -> async_sessionmaker[AsyncSession]:
        if self.factory is None:
            raise RuntimeError("pipeline controller has not been started")
        return self.factory


def build_executor(config_dir: Path = Path("config")) -> tuple[NodeExecutor, str]:
    bootstrap = scan_extensions([Path("extensions")], config_dir)
    config = load_app_config(config_dir)
    config.entity_types.update(bootstrap.entity_type_registry.as_dict())
    return _build_executor(config, bootstrap.handler_registry, config_dir=config_dir, extension_tables=bootstrap.table_names), "default"


async def run_default_cycle(config_dir: Path = Path("config")) -> object:
    controller = PipelineController(config_dir)
    await controller.start(run_startup=False)
    try:
        cycle_id = await controller.run_now("manual")
        async with controller._factory()() as session:
            current = await recent_pipeline_runs(session, 1)
        return current[0].cycle_id if current else cycle_id
    finally:
        await controller.shutdown()


async def _persist_outputs(
    factory: async_sessionmaker[AsyncSession],
    retention_count: int,
    retention_hours: int,
) -> None:
    async with factory() as session:
        await cleanup_node_output_entities(session, retention_count, retention_hours)
        await session.commit()


async def _record_node_output(
    factory: async_sessionmaker[AsyncSession],
    cycle_id: str,
    node_id: str,
    entity_type: str,
    payload: object,
    session_id: str | None,
) -> None:
    async with factory() as session:
        await store_node_output_entities(session, cycle_id, node_id, entity_type, payload, session_id)
        await session.commit()


async def _record_source_runs(
    factory: async_sessionmaker[AsyncSession],
    cycle_id: str,
    outputs: Mapping[str, NodeOutput],
) -> None:
    recovery = _source_recovery(outputs)
    if not recovery:
        return
    async with factory() as session:
        for source_name, summary in recovery.items():
            if not isinstance(summary, dict):
                continue
            status = "failed" if summary.get("recovery_status") == "escalated" else "succeeded"
            error = str(summary.get("latest_failure_reason") or "") or None
            await mark_node_run(session, cycle_id, source_name, status, error)
        await session.commit()


def _build_executor(
    app_config: AppConfig,
    handler_registry,
    instances: Mapping[str, DagNodeInstance] | None = None,
    config_dir: Path | None = None,
    extension_tables: dict[str, dict[str, str]] | None = None,
    output_recorder=None,
    stdout_recorder=None,
    agent_certificate_issuer=None,
) -> NodeExecutor:
    entity_store = EntityStore(
        app_config.entities,
        app_config.entity_types,
        app_config.entity_relations,
        config_dir / "entities.yaml" if config_dir is not None else None,
    )
    entity_store.system = app_config.system
    entity_store.runtime = app_config.runtime
    return NodeExecutor(
        app_config.nodes,
        app_config.system,
        app_config.runtime,
        handler_registry,
        dict(instances or {}),
        entity_store,
        output_recorder=output_recorder,
        stdout_recorder=stdout_recorder,
        agent_certificate_issuer=agent_certificate_issuer,
        extension_tables=extension_tables,
    )


def _source_entity_refs(app_config: AppConfig) -> list[str]:
    refs: list[str] = []
    for entity in app_config.entities.entities:
        if entity.type not in {"rss-source", "web-source", "api-source"}:
            continue
        name = entity.attributes.get("name")
        if isinstance(name, str):
            refs.append(f"{entity.type}:{name}")
    return refs


def _source_recovery(outputs: Mapping[str, NodeOutput]) -> dict[str, object]:
    recovery: dict[str, object] = {}
    for output in outputs.values():
        recovery.update(output.metadata.get("source_recovery", {}))
    return recovery


def _run_dict(run: PipelineRun) -> dict[str, object]:
    return run.model_dump(mode="json")


def _result_status(outputs: Mapping[str, NodeOutput]) -> str:
    if outputs and not all(not output.ok for output in outputs.values()):
        return "succeeded"
    return "failed"


def _downstream_nodes(graph, node_id: str) -> set[str]:
    found: set[str] = set()
    stack = [node_id]
    while stack:
        node = stack.pop()
        if node in found:
            continue
        found.add(node)
        stack.extend(graph.edges[node])
    return found


def _downstream_union(graph, node_ids: list[str]) -> set[str]:
    retry_nodes: set[str] = set()
    for node_id in node_ids:
        retry_nodes.update(_downstream_nodes(graph, node_id))
    return retry_nodes


def _missing_prefilled_inputs(graph, retry_nodes: set[str], prefilled_nodes: set[str]) -> list[str]:
    missing: set[str] = set()
    for node_id in retry_nodes:
        for upstream in graph.reverse_edges[node_id]:
            if upstream not in retry_nodes and upstream not in prefilled_nodes:
                missing.add(upstream)
    return sorted(missing)


def _graph_ordered_nodes(graph, node_ids: set[str]) -> list[str]:
    return [node_id for node_id in graph.nodes if node_id in node_ids]


def _dag_has_node(config_dir: Path, dag_name: str, node_id: str) -> bool:
    config = load_app_config(config_dir)
    dag = config.dags.get(dag_name)
    if dag is None:
        return False
    return any(instance.id == node_id or instance.alias == node_id for instance in dag.nodes)


def _wait_for_idle_target(config_dir: Path, dag_name: str, payload: object | None) -> str | None:
    config = load_app_config(config_dir)
    dag = config.dags.get(dag_name)
    if dag is None:
        return None
    wait_for = dag.ui.get("wait_for")
    if not isinstance(wait_for, dict) or wait_for.get("status") != "idle":
        return None
    target = wait_for.get("node")
    if target == "$payload.target" and isinstance(payload, dict):
        target = payload.get("target")
    return target if isinstance(target, str) and target else None


def _cleanup_sandboxes(config: AppConfig) -> None:
    try:
        from extensions._lib.llm import cleanup_sandboxes
    except ImportError:
        return
    cleanup_sandboxes(config.system, _referenced_sandboxes(config))


def _referenced_sandboxes(config: AppConfig) -> set[str]:
    refs: set[str] = set()
    for dag in config.dags.values():
        for instance in dag.nodes:
            value = instance.config.get("session_dir")
            if isinstance(value, str) and value.startswith("sandbox:") and not value.endswith(":latest"):
                refs.add(value)
    return refs
