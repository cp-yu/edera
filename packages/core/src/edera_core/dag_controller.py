from __future__ import annotations

import asyncio
import hashlib
import json
import os
from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from edera_core.config.loader import _load_runtime_base_config, load_system_config, materialize_runtime_app_config
from edera_core.config.loader import _default_extensions_dirs
from edera_core.config.entities import EntityStore
from edera_core.config.git import commit_config_changes
from edera_core.config.schema import AppConfig, DagNodeInstance, RuntimeSettings, SystemConfig
from edera_core.bootstrap import BootstrapResult, create_extension_tables, load_installed_extensions
from edera_core.dag.loader import load_graph
from edera_core.dag.models import DagGraph
from edera_core.dag.runner import DagRunner, EdgeInputFact
from edera_core.errors import DagError
from edera_core.events import event_bus
from edera_core.storage import create_engine, init_db, session_factory
from edera_core.storage.entities import DagRun
from edera_core.storage.repository import (
    cleanup_node_output_entities,
    create_dag_run,
    finish_dag_run,
    get_dag_config,
    get_dag_run,
    get_node_config,
    latest_finished_dag_run,
    list_dag_configs,
    list_entity_type_configs,
    list_skill_configs,
    mark_node_run,
    delete_node_outputs_for_nodes,
    edge_inputs_for_run,
    query_node_output_entities,
    recent_dag_runs,
    record_log_index,
    restart_dag_run,
    list_core_entities,
    store_node_output_entities,
    upsert_edge_input,
    upsert_source_recovery,
)
from edera_core.node.executor import NodeExecutor
from edera_core.node.models import NodeOutput
from edera_core.skills.generator import refresh_all_skill_files
from edera_core.snapshot import DagExecutionSnapshot, build_dag_execution_closure
from edera_core.trigger import CronEmitter, TriggerExecutor


class RunAlreadyActiveError(Exception):
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        super().__init__(f"dag run already active: {run_id}")


class DagRunNotFoundError(Exception):
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        super().__init__(f"dag run not found: {run_id}")


@dataclass(frozen=True)
class RetryRunResult:
    run_id: str
    retry_of: str
    node_ids: list[str]
    mode: str
    retry_nodes: list[str]


@dataclass
class DagRunContext:
    dag_name: str
    run_id: str
    task: asyncio.Task[object]
    stop_event: asyncio.Event = field(default_factory=asyncio.Event)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    executor: NodeExecutor | None = None


@dataclass(frozen=True)
class RuntimeControlSnapshot:
    system: SystemConfig
    runtime: RuntimeSettings
    trigger_executor: TriggerExecutor
    cron_emitter: CronEmitter
    generation: int = 0


class DagController:
    def __init__(
        self,
        config_dir: Path = Path("config"),
        scheduler: object | None = None,
        extensions_dirs: list[Path] | None = None,
        agent_certificate_issuer: Callable[[str, int], object] | None = None,
        daemon_data_dir: Path | None = None,
    ) -> None:
        self.config_dir = config_dir
        self.extensions_dirs = extensions_dirs or _default_extensions_dirs(config_dir)
        self.handlers_dir = load_system_config(config_dir / "system.toml").handlers_dir
        self.scheduler = scheduler or _TriggerSchedulerState()
        self.engine: AsyncEngine | None = None
        self.factory: async_sessionmaker[AsyncSession] | None = None
        self.active_runs: dict[str, DagRunContext] = {}
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._db_write_lock = asyncio.Lock()
        self.agent_certificate_issuer = agent_certificate_issuer
        self.daemon_data_dir = daemon_data_dir
        self.trigger_executor: TriggerExecutor | None = None
        self.cron_emitter: CronEmitter | None = None
        self._cron_task: asyncio.Task[object] | None = None
        self._startup_window_task: asyncio.Task[object] | None = None
        self._snapshot: RuntimeControlSnapshot | None = None
        self._runtime_config: AppConfig | None = None
        self._bootstrap: BootstrapResult | None = None
        self._entity_store: EntityStore | None = None
        self._extension_table_names: dict[str, dict[str, str]] = {}
        self._snapshot_lock = asyncio.Lock()
        self._snapshot_generation = 0

    async def start(self) -> None:
        system = load_system_config(self.config_dir / "system.toml")
        self.engine = create_engine(_daemon_database_url(system.database_url, self.daemon_data_dir))
        await init_db(self.engine)
        config = _load_runtime_base_config(self.config_dir)
        self.factory = session_factory(self.engine)
        bootstrap = await self.load_bootstrap()
        await self.install_snapshot(config, bootstrap)
        self.scheduler.start()
        self._cron_task = asyncio.create_task(self._cron_loop())
        await self._open_startup_window(system.startup_window_seconds)

    async def shutdown(self) -> None:
        if self._cron_task is not None:
            self._cron_task.cancel()
            try:
                await self._cron_task
            except asyncio.CancelledError:
                pass
        if self._startup_window_task is not None:
            self._startup_window_task.cancel()
            try:
                await self._startup_window_task
            except asyncio.CancelledError:
                pass
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

    async def _open_startup_window(self, window_seconds: float) -> None:
        if self.trigger_executor is None:
            return
        await self.trigger_executor.events.clear("startup")
        await self.trigger_executor.emit("startup", source="startup")
        self._startup_window_task = asyncio.create_task(self._startup_window_loop(window_seconds))

    async def _startup_window_loop(self, window_seconds: float) -> None:
        try:
            await asyncio.sleep(window_seconds)
        except asyncio.CancelledError:
            raise
        if self.trigger_executor is not None:
            await self.trigger_executor.events.clear("startup")

    async def start_run(
        self,
        source: str = "manual",
        dag_name: str = "default",
        *,
        source_shared_inputs: object | None = None,
        node_inputs: dict[str, object] | None = None,
        append_nodes: set[str] | None = None,
    ) -> str:
        await self._wait_for_idle(dag_name, source_shared_inputs)
        async with self._locks[dag_name]:
            run_id, task = self._start_run_locked(
                source,
                dag_name,
                source_shared_inputs=source_shared_inputs,
                node_inputs=node_inputs,
                append_nodes=append_nodes,
            )
        task.add_done_callback(lambda t: self._clear_finished_task(t, dag_name))
        return run_id

    async def run_now(
        self,
        source: str = "manual",
        dag_name: str = "default",
        *,
        source_shared_inputs: object | None = None,
        node_inputs: dict[str, object] | None = None,
        append_nodes: set[str] | None = None,
    ) -> str:
        await self._wait_for_idle(dag_name, source_shared_inputs)
        async with self._locks[dag_name]:
            run_id, task = self._start_run_locked(
                source,
                dag_name,
                source_shared_inputs=source_shared_inputs,
                node_inputs=node_inputs,
                append_nodes=append_nodes,
            )
        try:
            await task
        finally:
            self._clear_finished_task(task, dag_name)
        return run_id

    async def emit(
        self,
        event: str,
        payload: object | None = None,
        *,
        source: str = "rpc",
        depth: int = 0,
    ) -> list[str]:
        snapshot = self.runtime_snapshot()
        return await snapshot.trigger_executor.emit(event, payload, source=source, depth=depth)

    async def _reload_triggers(self) -> None:
        if self.engine is None:
            raise RuntimeError("DAG controller has not been started")
        await self.install_snapshot(
            _load_runtime_base_config(self.config_dir),
            await self.load_bootstrap(),
        )

    async def load_bootstrap(self) -> BootstrapResult:
        if self.factory is None:
            raise RuntimeError("DAG controller has not been started")
        async with self.factory() as session:
            return await load_installed_extensions(session, self.handlers_dir)

    async def install_snapshot(self, config: AppConfig, bootstrap: BootstrapResult) -> RuntimeControlSnapshot:
        if self.engine is None:
            raise RuntimeError("DAG controller has not been started")
        async with self._snapshot_lock:
            config = await materialize_runtime_app_config(self.config_dir, config, self.engine)
            await create_extension_tables(self.engine, bootstrap.storage_tables)
            store = EntityStore(
                config.entities,
                config.entity_types,
                config.entity_relations,
                None,
            )
            async with self._factory()() as session:
                store.memory_entities[""] = {
                    entity.id: entity
                    for entity in await list_core_entities(session, "trigger")
                }
            trigger_executor = self._new_trigger_executor(config, store)
            await trigger_executor.load()
            cron_emitter = CronEmitter(trigger_executor)
            self._snapshot_generation += 1
            snapshot = RuntimeControlSnapshot(
                system=config.system,
                runtime=config.runtime,
                trigger_executor=trigger_executor,
                cron_emitter=cron_emitter,
                generation=self._snapshot_generation,
            )
            self._snapshot = snapshot
            self._runtime_config = config
            self._bootstrap = bootstrap
            self._entity_store = store
            self._extension_table_names = dict(bootstrap.table_names)
            self.trigger_executor = trigger_executor
            self.cron_emitter = cron_emitter
            _refresh_skills_dir(config.system.skills_dir, config.skills)
            return snapshot

    def runtime_snapshot(self) -> RuntimeControlSnapshot:
        if self._snapshot is None:
            raise RuntimeError("DAG controller has not been started")
        return self._snapshot

    def runtime_config(self) -> AppConfig:
        if self._runtime_config is None:
            raise RuntimeError("DAG controller has not been started")
        return self._runtime_config

    def bootstrap_result(self) -> BootstrapResult:
        if self._bootstrap is None:
            raise RuntimeError("DAG controller has not been started")
        return self._bootstrap

    def entity_store(self) -> EntityStore:
        if self._entity_store is None:
            raise RuntimeError("DAG controller has not been started")
        return self._entity_store

    def extension_table_names(self) -> dict[str, dict[str, str]]:
        return self._extension_table_names

    def _new_trigger_executor(self, config: AppConfig, store: EntityStore) -> TriggerExecutor:
        return TriggerExecutor(
            store,
            run_dag=lambda name, payload, source: self.start_run(source, name, source_shared_inputs=payload),
            run_node=lambda name, payload, source: self.run_node_trigger(name, payload, source),
            factory=self.factory,
            max_depth=config.system.max_trigger_depth,
        )

    async def run_node_trigger(
        self,
        target: str,
        payload: object | None = None,
        source: str = "manual",
        *,
        append: bool = False,
    ) -> str:
        dag_name, node_id = _parse_node_trigger_target(target)
        async with self._factory()() as session:
            _execution_snapshot, _instance = await self._node_trigger_target(session, dag_name, node_id)
        await self._wait_for_idle(dag_name, payload)
        async with self._locks[dag_name]:
            snapshot = self.runtime_snapshot()
            async with self._factory()() as session:
                execution_snapshot, instance = await self._node_trigger_target(session, dag_name, node_id)
            ctx = self.active_runs.get(dag_name)
            if ctx is not None and not ctx.task.done():
                raise RunAlreadyActiveError(ctx.run_id)
            run_id = uuid4().hex
            stop_event = asyncio.Event()
            task = asyncio.create_task(
                self._run_single_node(
                    run_id,
                    source,
                    dag_name,
                    instance,
                    stop_event,
                    snapshot,
                    execution_snapshot=execution_snapshot,
                    node_inputs={instance.id: payload} if payload is not None else None,
                    append_nodes={instance.id} if append else set(),
                )
            )
            self.active_runs[dag_name] = DagRunContext(dag_name=dag_name, run_id=run_id, task=task, stop_event=stop_event)
        task.add_done_callback(lambda t: self._clear_finished_task(t, dag_name))
        return run_id

    async def _node_trigger_target(self, session, dag_name: str, node_id: str) -> tuple[DagExecutionSnapshot, DagNodeInstance]:
        execution_snapshot = await self._dag_execution_snapshot(session, dag_name)
        dag = execution_snapshot.dag_config
        for instance in dag.nodes:
            if instance.id == node_id or instance.alias == node_id:
                return execution_snapshot, instance
        raise ValueError(f"node '{node_id}' not found in DAG '{dag_name}'")

    def pause_scheduler(self) -> None:
        self.scheduler.pause()

    def resume_scheduler(self) -> None:
        self.scheduler.resume()

    async def stop_current(self, dag_name: str = "default", force: bool = False, node_id: str | None = None) -> str | None:
        ctx = self.active_runs.get(dag_name)
        if ctx is None or ctx.task.done():
            return None
        if node_id is not None and ctx.executor is not None:
            ctx.executor.stop_agent(ctx.run_id, node_id)
        if force:
            ctx.task.cancel()
        else:
            ctx.stop_event.set()
        try:
            await ctx.task
        except asyncio.CancelledError:
            pass
        return ctx.run_id

    async def active_dag_for_node(self, node_id: str) -> str | None:
        active = [ctx.dag_name for ctx in self.active_runs.values() if not ctx.task.done()]
        if not active:
            return None
        async with self._factory()() as session:
            for dag_name in active:
                if _dag_has_node(await get_dag_config(session, dag_name), node_id):
                    return dag_name
        return None

    async def dag_for_run_node(self, run_id: str, node_id: str) -> str | None:
        async with self._factory()() as session:
            run = await get_dag_run(session, run_id)
            if run is None:
                raise DagRunNotFoundError(run_id)
            dag = await get_dag_config(session, run.dag_name)
        return run.dag_name if _dag_has_node(dag, node_id) else None

    async def retry_node(
        self,
        dag_name: str,
        run_id: str | None,
        node_ids: list[str],
        mode: str = "single",
        *,
        source_shared_inputs: object | None = None,
        node_inputs: dict[str, object] | None = None,
        append_nodes: set[str] | None = None,
    ) -> RetryRunResult:
        if mode not in {"single", "cascade"}:
            raise ValueError("mode must be single or cascade")
        if not node_ids:
            raise ValueError("node_ids is required")
        async with self._locks[dag_name]:
            ctx = self.active_runs.get(dag_name)
            if ctx is not None and not ctx.task.done():
                raise RunAlreadyActiveError(ctx.run_id)
            snapshot = self.runtime_snapshot()
            async with self._factory()() as session:
                execution_snapshot = await self._dag_execution_snapshot(session, dag_name)
            graph = load_graph(execution_snapshot.dag_config, execution_snapshot.node_configs, execution_snapshot.dag_closure.dags)
            missing = [node_id for node_id in node_ids if node_id not in graph.instances]
            if missing:
                raise ValueError(f"node_ids contain unknown nodes: {', '.join(missing)}")
            retry_nodes = set(node_ids) if mode == "single" else _downstream_union(graph, node_ids)
            original_run_id = run_id or await self._latest_finished_run_id(dag_name)
            if original_run_id is None:
                raise DagRunNotFoundError("latest finished run")
            prefilled = await self._prefilled_outputs(original_run_id, graph, retry_nodes)
            missing_inputs = _missing_prefilled_inputs(graph, retry_nodes, set(prefilled), set())
            if missing_inputs:
                raise ValueError(f"missing prefilled outputs: {', '.join(missing_inputs)}")
            retry_run_id = uuid4().hex
            stop_event = asyncio.Event()
            task = asyncio.create_task(
                self._run(
                    retry_run_id,
                    "retry",
                    dag_name,
                    stop_event=stop_event,
                    retry_of=original_run_id,
                    retry_nodes=retry_nodes,
                    prefilled_outputs=prefilled,
                    source_shared_inputs=source_shared_inputs,
                    node_inputs=node_inputs,
                    append_nodes=append_nodes,
                    snapshot=snapshot,
                    execution_snapshot=execution_snapshot,
                )
            )
            self.active_runs[dag_name] = DagRunContext(
                dag_name=dag_name,
                run_id=retry_run_id,
                task=task,
                stop_event=stop_event,
            )
        task.add_done_callback(lambda t: self._clear_finished_task(t, dag_name))
        return RetryRunResult(
            run_id=retry_run_id,
            retry_of=original_run_id,
            node_ids=node_ids,
            mode=mode,
            retry_nodes=_graph_ordered_nodes(graph, retry_nodes),
        )

    async def resume_node(self, dag_name: str, run_id: str, node_id: str, payload: object) -> str:
        async with self._locks[dag_name]:
            ctx = self.active_runs.get(dag_name)
            if ctx is not None and not ctx.task.done():
                raise RunAlreadyActiveError(ctx.run_id)
            snapshot = self.runtime_snapshot()
            async with self._factory()() as session:
                execution_snapshot = await self._dag_execution_snapshot(session, dag_name)
            graph = load_graph(execution_snapshot.dag_config, execution_snapshot.node_configs, execution_snapshot.dag_closure.dags)
            if node_id not in graph.instances:
                raise ValueError(f"node '{node_id}' not found")
            original = await self._dag_run(run_id)
            if original is None:
                raise DagRunNotFoundError(run_id)
            retry_nodes = _downstream_nodes(graph, node_id)
            prefilled = await self._prefilled_outputs(run_id, graph, retry_nodes)
            await self._delete_node_outputs(run_id, retry_nodes)
            stop_event = asyncio.Event()
            task = asyncio.create_task(
                self._run(
                    run_id,
                    "retry",
                    dag_name,
                    stop_event=stop_event,
                    retry_of=original.retry_of,
                    retry_nodes=retry_nodes,
                    prefilled_outputs=prefilled,
                    node_inputs={node_id: payload} if payload is not None else None,
                    replace_existing_run=True,
                    snapshot=snapshot,
                    execution_snapshot=execution_snapshot,
                )
            )
            self.active_runs[dag_name] = DagRunContext(
                dag_name=dag_name,
                run_id=run_id,
                task=task,
                stop_event=stop_event,
            )
        task.add_done_callback(lambda t: self._clear_finished_task(t, dag_name))
        return run_id

    async def status(self, dag_name: str | None = None) -> dict[str, object]:
        factory = self._factory()
        if dag_name is not None:
            async with factory() as session:
                recent = await recent_dag_runs(session, dag_name=dag_name)
            ctx = self.active_runs.get(dag_name)
            current_run_id = ctx.run_id if ctx is not None and not ctx.task.done() else None
            return {
                "scheduler_running": self.scheduler.running,
                "scheduler_paused": self.scheduler.state == 2,
                "dag_name": dag_name,
                "current_run_id": current_run_id,
                "recent_runs": [_run_dict(run) for run in recent],
            }
        async with factory() as session:
            recent = await recent_dag_runs(session)
        return {
            "scheduler_running": self.scheduler.running,
            "scheduler_paused": self.scheduler.state == 2,
            "active_dags": {name: ctx.run_id for name, ctx in self.active_runs.items() if not ctx.task.done()},
            "recent_runs": [_run_dict(run) for run in recent],
        }

    async def node_status(self, node_id: str) -> str:
        factory = self._factory()
        async with factory() as session:
            dags = await list_dag_configs(session)
            for ctx in self.active_runs.values():
                if not ctx.task.done() and _dag_has_node(dags.get(ctx.dag_name), node_id):
                    return "running"
            for dag in dags.values():
                if not _dag_has_node(dag, node_id):
                    continue
                recent = await recent_dag_runs(session, 1, dag.name)
                if recent and recent[0].status == "failed":
                    return "failed"
        return "idle"

    async def _cron_loop(self) -> None:
        while True:
            now = datetime.now(timezone.utc)
            await asyncio.sleep(max(0.0, 60.0 - now.second - now.microsecond / 1_000_000))
            if self.cron_emitter is not None:
                await self.cron_emitter.tick()

    async def _wait_for_idle(self, dag_name: str, inputs: object | None = None) -> None:
        factory = self._factory()
        async with factory() as session:
            dag = await get_dag_config(session, dag_name)
        target = _wait_for_idle_target(dag, inputs)
        if target is None:
            return
        while await self._active_dag_has_node(target):
            await asyncio.sleep(0.1)

    async def _active_dag_has_node(self, node_id: str) -> bool:
        active_dag_names = [ctx.dag_name for ctx in self.active_runs.values() if not ctx.task.done()]
        if not active_dag_names:
            return False
        async with self._factory()() as session:
            for dag_name in active_dag_names:
                dag = await get_dag_config(session, dag_name)
                if _dag_has_node(dag, node_id):
                    return True
        return False

    def _start_run_locked(
        self,
        source: str,
        dag_name: str,
        *,
        source_shared_inputs: object | None = None,
        node_inputs: dict[str, object] | None = None,
        append_nodes: set[str] | None = None,
    ) -> tuple[str, asyncio.Task[object]]:
        ctx = self.active_runs.get(dag_name)
        if ctx is not None and not ctx.task.done():
            raise RunAlreadyActiveError(ctx.run_id)
        run_id = uuid4().hex
        stop_event = asyncio.Event()
        task = asyncio.create_task(
            self._run(
                run_id,
                source,
                dag_name,
                stop_event=stop_event,
                source_shared_inputs=source_shared_inputs,
                node_inputs=node_inputs,
                append_nodes=append_nodes,
                snapshot=self.runtime_snapshot(),
            )
        )
        self.active_runs[dag_name] = DagRunContext(dag_name=dag_name, run_id=run_id, task=task, stop_event=stop_event)
        return run_id, task

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
        run_id: str,
        source: str,
        dag_name: str = "default",
        stop_event: asyncio.Event | None = None,
        retry_of: str | None = None,
        retry_nodes: set[str] | None = None,
        prefilled_outputs: dict[str, NodeOutput] | None = None,
        source_shared_inputs: object | None = None,
        node_inputs: dict[str, object] | None = None,
        append_nodes: set[str] | None = None,
        replace_existing_run: bool = False,
        snapshot: RuntimeControlSnapshot | None = None,
        execution_snapshot: DagExecutionSnapshot | None = None,
    ) -> object:
        snapshot = snapshot or self.runtime_snapshot()
        config = self.runtime_config()
        factory = self._factory()
        if execution_snapshot is None:
            async with factory() as session:
                execution_snapshot = await self._dag_execution_snapshot(session, dag_name)
        graph = load_graph(execution_snapshot.dag_config, execution_snapshot.node_configs, execution_snapshot.dag_closure.dags)
        run_store = EntityStore(config.entities, config.entity_types, config.entity_relations, None)
        run_store.default_dag_run_id = run_id
        executor: NodeExecutor | None = None
        if replace_existing_run:
            async with factory() as session:
                await restart_dag_run(session, run_id)
                await session.commit()
        else:
            async with factory() as session:
                await create_dag_run(session, run_id, source, list(graph.nodes), dag_name, retry_of)
                await session.commit()
        await event_bus.publish("dag.status", run_id=run_id, dag_name=dag_name, status="started")
        try:
            async with factory() as session:
                await run_store.preload_for_dag(
                    run_id,
                    _run_entity_refs([*execution_snapshot.dag_closure.dags.values()]),
                    session,
                )
                executor = await self._build_run_executor(snapshot, graph, session, entity_store=run_store, execution_snapshot=execution_snapshot)
                ctx = self.active_runs.get(dag_name)
                if ctx is not None and ctx.run_id == run_id:
                    ctx.executor = executor
                result = await DagRunner(
                    executor,
                    recorder=lambda output_run_id, node, status, error, failure_kind, metadata: self._record_node(
                        output_run_id, node, status, error, failure_kind, metadata
                    ),
                    edge_recorder=lambda fact: self._record_edge_input(fact),
                    emit=lambda event, event_payload: self.emit(event, event_payload, source=f"node:{dag_name}", depth=1),
                    dag_lifecycle=lambda child_run_id, child_dag_name, status, error: self._record_child_dag_run(
                        child_run_id, source, child_dag_name, status, error
                    ),
                    trigger_executor=snapshot.trigger_executor,
                    dags=execution_snapshot.dag_closure.dags,
                    nodes=execution_snapshot.node_configs,
                ).run(
                    graph,
                    run_id,
                    stop_event=stop_event,
                    retry_nodes=retry_nodes,
                    prefilled_outputs=prefilled_outputs,
                    source_shared_inputs=source_shared_inputs,
                    node_inputs=node_inputs,
                    append_nodes=append_nodes,
                )
            active_outputs = {
                node: output
                for node, output in result.node_outputs.items()
                if retry_nodes is None or node in retry_nodes
            }
            status = "cancelled" if stop_event is not None and stop_event.is_set() else _result_status(active_outputs)
            if retry_nodes is None and status == "succeeded":
                await _persist_outputs(
                    factory,
                    config.system.retention_count,
                    config.system.retention_hours,
                )
            error = "; ".join(
                f"{node}: {message}"
                for node, message in result.failures.items()
                if retry_nodes is None or node in retry_nodes
            ) or None
            async with factory() as session:
                await finish_dag_run(session, run_id, status, error)
                await session.commit()
            await event_bus.publish("dag.status", run_id=run_id, dag_name=dag_name, status=status, error=error)
            commit_config_changes(self.config_dir, run_id, config.system.config_git_commit)
            return result.payload
        except asyncio.CancelledError:
            await self._finish_cancelled(run_id, dag_name)
            commit_config_changes(self.config_dir, run_id, config.system.config_git_commit)
            raise
        except Exception as exc:
            await self._finish_failed(run_id, dag_name, exc)
            commit_config_changes(self.config_dir, run_id, config.system.config_git_commit)
            raise
        finally:
            run_store.clear_cache_for_dag(run_id)

    async def _run_single_node(
        self,
        run_id: str,
        source: str,
        dag_name: str,
        instance: DagNodeInstance,
        stop_event: asyncio.Event,
        snapshot: RuntimeControlSnapshot | None = None,
        execution_snapshot: DagExecutionSnapshot | None = None,
        node_inputs: dict[str, object] | None = None,
        append_nodes: set[str] | None = None,
    ) -> object:
        snapshot = snapshot or self.runtime_snapshot()
        config = self.runtime_config()
        factory = self._factory()
        if execution_snapshot is None:
            async with factory() as session:
                execution_snapshot = await self._dag_execution_snapshot(session, dag_name)
        graph = DagGraph(
            dag_name,
            [instance.id],
            {instance.id: instance},
            {instance.id: []},
            {instance.id: []},
        )
        run_store = EntityStore(config.entities, config.entity_types, config.entity_relations, None)
        run_store.default_dag_run_id = run_id
        executor: NodeExecutor | None = None
        async with factory() as session:
            await create_dag_run(session, run_id, source, [instance.id], dag_name)
            await session.commit()
        await event_bus.publish("dag.status", run_id=run_id, dag_name=dag_name, status="started")
        try:
            async with factory() as session:
                await run_store.preload_for_dag(run_id, _run_entity_refs(graph), session)
                executor = await self._build_run_executor(snapshot, graph, session, entity_store=run_store, execution_snapshot=execution_snapshot)
                ctx = self.active_runs.get(dag_name)
                if ctx is not None and ctx.run_id == run_id:
                    ctx.executor = executor
                result = await DagRunner(
                    executor,
                    recorder=lambda output_run_id, node, status, error, failure_kind, metadata: self._record_node(
                        output_run_id, node, status, error, failure_kind, metadata
                    ),
                    emit=lambda event, event_payload: self.emit(event, event_payload, source=f"node:{dag_name}", depth=1),
                    dag_lifecycle=lambda child_run_id, child_dag_name, status, error: self._record_child_dag_run(
                        child_run_id, source, child_dag_name, status, error
                    ),
                    trigger_executor=snapshot.trigger_executor,
                    dags=execution_snapshot.dag_closure.dags,
                    nodes=execution_snapshot.node_configs,
                ).run(
                    graph,
                    run_id,
                    stop_event=stop_event,
                    node_inputs=node_inputs,
                    append_nodes=append_nodes,
                )
            status = "cancelled" if stop_event.is_set() else _result_status(result.node_outputs)
            error = "; ".join(result.failures.values()) or None
            async with factory() as session:
                await finish_dag_run(session, run_id, status, error)
                await session.commit()
            await event_bus.publish("dag.status", run_id=run_id, dag_name=dag_name, status=status, error=error)
            commit_config_changes(self.config_dir, run_id, config.system.config_git_commit)
            return result.payload
        except asyncio.CancelledError:
            await self._finish_cancelled(run_id, dag_name)
            commit_config_changes(self.config_dir, run_id, config.system.config_git_commit)
            raise
        except Exception as exc:
            await self._finish_failed(run_id, dag_name, exc)
            commit_config_changes(self.config_dir, run_id, config.system.config_git_commit)
            raise
        finally:
            run_store.clear_cache_for_dag(run_id)

    async def _prefilled_outputs(
        self,
        original_run_id: str,
        graph,
        retry_nodes: set[str],
    ) -> dict[str, NodeOutput]:
        factory = self._factory()
        async with factory() as session:
            original = await get_dag_run(session, original_run_id)
            if original is None:
                raise DagRunNotFoundError(original_run_id)
            outputs = await query_node_output_entities(session, run_id=original_run_id, limit=10000)
            edge_facts = await edge_inputs_for_run(session, original_run_id)
        prefilled: dict[str, NodeOutput] = {}
        payloads: dict[str, list[object]] = defaultdict(list)
        for entity in outputs:
            node_id = str(entity.attributes.get("node_id") or "")
            if node_id in graph.instances and node_id not in retry_nodes:
                payloads[node_id].append(entity.attributes.get("payload"))
        for node_id, values in payloads.items():
            payload = values[0] if len(values) == 1 else list(reversed(values))
            prefilled[node_id] = NodeOutput(node_name=node_id, ok=True, payload=payload)
        for fact in edge_facts:
            if fact.from_node_id in graph.instances and fact.from_node_id not in retry_nodes and fact.from_node_id not in prefilled:
                prefilled[fact.from_node_id] = NodeOutput(
                    node_name=fact.from_node_id,
                    ok=False,
                    metadata={"runtime_status": fact.status},
                    error=fact.error_summary,
                )
        return prefilled

    async def _dag_run(self, run_id: str) -> DagRun | None:
        factory = self._factory()
        async with factory() as session:
            return await get_dag_run(session, run_id)

    async def _latest_finished_run_id(self, dag_name: str) -> str | None:
        factory = self._factory()
        async with factory() as session:
            run = await latest_finished_dag_run(session, dag_name)
        return run.run_id if run is not None else None

    async def _delete_node_outputs(self, run_id: str, node_ids: set[str]) -> None:
        factory = self._factory()
        async with factory() as session:
            await delete_node_outputs_for_nodes(session, run_id, node_ids)
            await session.commit()

    async def _record_node(
        self,
        run_id: str,
        node: str,
        status: str,
        error: str | None,
        failure_kind: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        async with self._db_write_lock:
            async with self._factory()() as session:
                await mark_node_run(session, run_id, node, status, error, failure_kind, metadata)
                await session.commit()

    async def _record_child_dag_run(
        self,
        run_id: str,
        source: str,
        dag_name: str,
        status: str,
        error: str | None,
    ) -> None:
        async with self._db_write_lock:
            async with self._factory()() as session:
                if status == "started":
                    await create_dag_run(session, run_id, source, dag_name=dag_name)
                else:
                    await finish_dag_run(session, run_id, status, error)
                await session.commit()

    async def _record_edge_input(self, fact: EdgeInputFact) -> None:
        async with self._db_write_lock:
            async with self._factory()() as session:
                await upsert_edge_input(
                    session,
                    fact.run_id,
                    fact.from_node_id,
                    fact.to_node_id,
                    fact.edge_optional,
                    fact.status,
                    fact.has_payload,
                    fact.error_summary,
                )
                await session.commit()

    async def _record_node_output(
        self,
        run_id: str,
        node_id: str,
        entity_type: str,
        payload: object,
        session_id: str | None,
    ) -> None:
        async with self._db_write_lock:
            await _record_node_output(self._factory(), run_id, node_id, entity_type, payload, session_id)

    async def _record_raw_log(
        self,
        run_id: str,
        node_id: str,
        path: str,
        digest: str,
        size: int,
    ) -> None:
        async with self._db_write_lock:
            await _record_raw_log(self._factory(), run_id, node_id, path, digest, size)

    async def _record_execution_summary(
        self,
        run_id: str,
        node_id: str,
        summary: dict[str, object],
        workspace_root: str,
    ) -> None:
        root = self.daemon_data_dir or Path(os.environ.get("EDERA_DATA_DIR", workspace_root))
        path = root / "sessions" / "summaries" / _safe_path_token(run_id) / f"{_safe_path_token(node_id)}.json"
        async with self._db_write_lock:
            await _record_summary_log(self._factory(), run_id, node_id, path, summary)

    async def _record_source_recovery(
        self,
        run_id: str,
        node_id: str,
        source_name: str,
        summary: dict[str, object],
    ) -> None:
        async with self._db_write_lock:
            async with self._factory()() as session:
                await upsert_source_recovery(session, run_id, node_id, source_name, summary)
                await session.commit()

    async def _finish_cancelled(self, run_id: str, dag_name: str) -> None:
        async with self._factory()() as session:
            await finish_dag_run(session, run_id, "cancelled")
            await session.commit()
        await event_bus.publish("dag.status", run_id=run_id, dag_name=dag_name, status="cancelled")

    async def _finish_failed(self, run_id: str, dag_name: str, exc: Exception) -> None:
        async with self._factory()() as session:
            await finish_dag_run(session, run_id, "failed", str(exc))
            await session.commit()
        await event_bus.publish("dag.status", run_id=run_id, dag_name=dag_name, status="failed", error=str(exc))

    def _factory(self) -> async_sessionmaker[AsyncSession]:
        if self.factory is None:
            raise RuntimeError("DAG controller has not been started")
        return self.factory

    async def _build_run_executor(
        self,
        snapshot: RuntimeControlSnapshot,
        graph,
        session,
        entity_store: EntityStore | None = None,
        execution_snapshot: DagExecutionSnapshot | None = None,
    ) -> NodeExecutor:
        execution_snapshot = execution_snapshot or await self._dag_execution_snapshot(session, graph.name)
        return _build_executor(
            self.runtime_config(),
            execution_snapshot,
            graph.instances,
            self.config_dir,
            entity_store=entity_store,
            extension_tables=execution_snapshot.extension_table_names,
            output_recorder=lambda output_run_id, node_id, entity_type, payload, session_id: self._record_node_output(
                output_run_id, node_id, entity_type, payload, session_id
            ),
            stdout_recorder=lambda output_run_id, node_id, line: event_bus.publish(
                "node.stdout",
                run_id=output_run_id,
                node_id=node_id,
                line=line,
            ),
            raw_log_recorder=lambda output_run_id, node_id, path, digest, size: self._record_raw_log(
                output_run_id, node_id, path, digest, size
            ),
            execution_summary_recorder=lambda output_run_id, node_id, summary: self._record_execution_summary(
                output_run_id, node_id, summary, self.runtime_config().system.workspace_root
            ),
            agent_certificate_issuer=self.agent_certificate_issuer,
            daemon_data_dir=self.daemon_data_dir,
            source_recovery_recorder=self._record_source_recovery,
        )

    async def _dag_execution_snapshot(self, session, dag_name: str) -> DagExecutionSnapshot:
        closure = await _load_dag_execution_closure(session, dag_name)
        return await DagExecutionSnapshot.from_closure(
            closure,
            await list_entity_type_configs(session),
            session,
            self.handlers_dir,
            self.extension_table_names(),
            await list_skill_configs(session),
        )


def build_executor(config_dir: Path = Path("config")) -> tuple[NodeExecutor, str]:
    async def _load() -> tuple[NodeExecutor, str]:
        controller = DagController(config_dir)
        await controller.start()
        try:
            config = controller.runtime_config()
            async with controller._factory()() as session:
                execution_snapshot = await controller._dag_execution_snapshot(session, "default")
                graph = load_graph(
                    execution_snapshot.dag_config,
                    execution_snapshot.node_configs,
                    execution_snapshot.dag_closure.dags,
                )
                return (
                    _build_executor(
                        config,
                        execution_snapshot,
                        graph.instances,
                        config_dir=config_dir,
                        extension_tables=controller.extension_table_names(),
                    ),
                    "default",
                )
        finally:
            await controller.shutdown()

    return asyncio.run(_load())


async def run_default_run(config_dir: Path = Path("config")) -> object:
    controller = DagController(config_dir)
    await controller.start()
    try:
        run_id = await controller.run_now("manual")
        async with controller._factory()() as session:
            current = await recent_dag_runs(session, 1)
        return current[0].run_id if current else run_id
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
    run_id: str,
    node_id: str,
    entity_type: str,
    payload: object,
    session_id: str | None,
) -> None:
    async with factory() as session:
        await store_node_output_entities(session, run_id, node_id, entity_type, payload, session_id)
        await session.commit()


async def _record_raw_log(
    factory: async_sessionmaker[AsyncSession],
    run_id: str,
    node_id: str,
    path: str,
    digest: str,
    size: int,
) -> None:
    async with factory() as session:
        await record_log_index(session, run_id, node_id, path, digest, size)
        await session.commit()


async def _record_summary_log(
    factory: async_sessionmaker[AsyncSession],
    run_id: str,
    node_id: str,
    path: Path,
    summary: dict[str, object],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(summary, ensure_ascii=False, sort_keys=True).encode("utf-8")
    path.write_bytes(data)
    async with factory() as session:
        await record_log_index(session, run_id, node_id, str(path), hashlib.sha256(data).hexdigest(), len(data), kind="summary")
        await session.commit()


async def _load_dag_execution_closure(session, root_dag_name: str):
    dags = {}
    nodes = {}

    async def visit(dag_name: str) -> None:
        if dag_name in dags:
            return
        dag = await get_dag_config(session, dag_name)
        if dag is None:
            raise DagError(f"missing DAG config: {dag_name}")
        dags[dag_name] = dag
        for instance in dag.nodes:
            sub_dag_name = instance.dag_ref if instance.type == "dag" and instance.dag_ref else None
            if sub_dag_name is None and await get_dag_config(session, instance.type) is not None:
                sub_dag_name = instance.type
            if sub_dag_name is not None:
                await visit(sub_dag_name)
                continue
            if instance.type in nodes:
                continue
            node = await get_node_config(session, instance.type)
            if node is not None:
                nodes[instance.type] = node

    await visit(root_dag_name)
    return build_dag_execution_closure(root_dag_name, dags, nodes)


def _refresh_skills_dir(skills_dir: Path, skills: dict[str, object]) -> None:
    skills_dir.mkdir(parents=True, exist_ok=True)
    refresh_all_skill_files(skills_dir, skills)


def _build_executor(
    app_config: AppConfig,
    execution_snapshot: DagExecutionSnapshot,
    instances: Mapping[str, DagNodeInstance] | None = None,
    config_dir: Path | None = None,
    entity_store: EntityStore | None = None,
    extension_tables: dict[str, dict[str, str]] | None = None,
    output_recorder=None,
    stdout_recorder=None,
    raw_log_recorder=None,
    execution_summary_recorder=None,
    agent_certificate_issuer=None,
    daemon_data_dir: Path | None = None,
    source_recovery_recorder=None,
) -> NodeExecutor:
    entity_store = entity_store or EntityStore(
        app_config.entities,
        execution_snapshot.entity_types,
        app_config.entity_relations,
        None,
    )
    entity_store.system = app_config.system
    entity_store.runtime = app_config.runtime
    return NodeExecutor(
        execution_snapshot.node_configs,
        app_config.system,
        app_config.runtime,
        execution_snapshot,
        dict(instances or {}),
        entity_store,
        output_recorder=output_recorder,
        stdout_recorder=stdout_recorder,
        raw_log_recorder=raw_log_recorder,
        execution_summary_recorder=execution_summary_recorder,
        agent_certificate_issuer=agent_certificate_issuer,
        extension_tables=extension_tables,
        daemon_data_dir=daemon_data_dir,
        source_recovery_recorder=source_recovery_recorder,
    )


def _run_entity_refs(dags_or_graph) -> list[str]:
    refs: list[str] = []
    if hasattr(dags_or_graph, "instances"):
        instances = list(dags_or_graph.instances.values())
    else:
        instances = [instance for dag in dags_or_graph for instance in dag.nodes]
    for instance in instances:
        if instance.resource:
            refs.append(instance.resource)
        raw = instance.config.get("entities")
        if isinstance(raw, list):
            refs.extend(str(item) for item in raw)
        source = instance.config.get("source")
        if isinstance(source, str):
            refs.append(source)
    return _dedupe_refs(refs)


def _dedupe_refs(refs: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for ref in refs:
        if ref in seen:
            continue
        seen.add(ref)
        result.append(ref)
    return result


def _safe_path_token(value: str) -> str:
    cleaned = "".join(item if item.isalnum() or item in {"-", "_", "."} else "_" for item in value)
    return cleaned or "default"


class _TriggerSchedulerState:
    running = False
    state = 0

    def start(self) -> None:
        self.running = True
        self.state = 1

    def shutdown(self, wait: bool = False) -> None:
        self.running = False
        self.state = 0

    def pause(self) -> None:
        self.state = 2

    def resume(self) -> None:
        self.state = 1

    def get_jobs(self) -> list[object]:
        return []

    def get_job(self, job_id: str) -> object | None:
        return None


def _run_dict(run: DagRun) -> dict[str, object]:
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


def _missing_prefilled_inputs(
    graph,
    retry_nodes: set[str],
    prefilled_nodes: set[str],
    allowed_missing: set[str],
) -> list[str]:
    missing: set[str] = set()
    for node_id in retry_nodes:
        for upstream in graph.reverse_edges[node_id]:
            if upstream not in retry_nodes and upstream not in prefilled_nodes and upstream not in allowed_missing:
                missing.add(upstream)
    return sorted(missing)


def _graph_ordered_nodes(graph, node_ids: set[str]) -> list[str]:
    return [node_id for node_id in graph.nodes if node_id in node_ids]


def _dag_has_node(dag, node_id: str) -> bool:
    if dag is None:
        return False
    return any(instance.id == node_id or instance.alias == node_id for instance in dag.nodes)


def _wait_for_idle_target(dag, inputs: object | None = None) -> str | None:
    if dag is None:
        return None
    wait_for = dag.ui.get("wait_for")
    if not isinstance(wait_for, dict) or wait_for.get("status") != "idle":
        return None
    target = wait_for.get("node")
    if target == "$payload.target" and isinstance(inputs, dict):
        target = inputs.get("target")
    return target if isinstance(target, str) and target else None


def _daemon_database_url(database_url: str, data_dir: Path | None) -> str:
    if data_dir is None:
        return database_url
    prefix = "sqlite+aiosqlite:///"
    if not database_url.startswith(prefix):
        return database_url
    path = database_url.removeprefix(prefix)
    if not path or path == ":memory:" or Path(path).is_absolute():
        return database_url
    db_path = data_dir / path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"{prefix}{db_path}"


def _parse_node_trigger_target(target: str) -> tuple[str, str]:
    dag_name, separator, node_id = target.partition("/")
    if not separator or not dag_name or not node_id:
        raise ValueError("node trigger target must be '<dag_name>/<node_id>'")
    return dag_name, node_id

