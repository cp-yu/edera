from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from edera_core.config.loader import load_runtime_app_config, load_system_config, materialize_runtime_app_config
from edera_core.config.entities import EntityStore
from edera_core.config.git import commit_config_changes
from edera_core.config.schema import AppConfig, DagNodeInstance
from edera_core.bootstrap import BootstrapResult, create_extension_tables, scan_extensions
from edera_core.dag.loader import load_graph
from edera_core.dag.models import DagGraph
from edera_core.dag.runner import DagRunner, EdgeInputFact
from edera_core.events import event_bus
from edera_core.storage import create_engine, init_db, session_factory
from edera_core.storage.entities import DagRun
from edera_core.storage.repository import (
    cleanup_node_output_entities,
    create_dag_run,
    current_dag_run,
    finish_dag_run,
    get_dag_run,
    latest_finished_dag_run,
    mark_node_run,
    delete_node_outputs_for_nodes,
    edge_inputs_for_run,
    query_node_output_entities,
    recent_dag_runs,
    record_log_index,
    restart_dag_run,
    store_node_output_entities,
    upsert_edge_input,
    upsert_source_recovery,
)
from edera_core.node.executor import NodeExecutor
from edera_core.node.models import NodeOutput
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
class RuntimeSnapshot:
    config: AppConfig
    bootstrap: BootstrapResult
    entity_store: EntityStore
    trigger_executor: TriggerExecutor
    cron_emitter: CronEmitter
    extension_table_names: dict[str, dict[str, str]]


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
        self.extensions_dirs = extensions_dirs or [Path("extensions")]
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
        self._snapshot: RuntimeSnapshot | None = None
        self._snapshot_lock = asyncio.Lock()

    async def start(self, run_startup: bool = True) -> None:
        bootstrap = scan_extensions(self.extensions_dirs, self.config_dir)
        system = load_system_config(self.config_dir / "system.toml")
        self.engine = create_engine(system.database_url)
        await init_db(self.engine)
        config = await load_runtime_app_config(self.config_dir, self.engine)
        self.factory = session_factory(self.engine)
        await self.install_snapshot(config, bootstrap)
        self.scheduler.start()
        self._cron_task = asyncio.create_task(self._cron_loop())

    async def shutdown(self) -> None:
        if self._cron_task is not None:
            self._cron_task.cancel()
            try:
                await self._cron_task
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

    async def start_run(self, source: str = "manual", dag_name: str = "default", payload: object | None = None) -> str:
        await self._wait_for_idle(dag_name, payload)
        async with self._locks[dag_name]:
            run_id, task = self._start_run_locked(source, dag_name, payload)
        task.add_done_callback(lambda t: self._clear_finished_task(t, dag_name))
        return run_id

    async def run_now(self, source: str = "manual", dag_name: str = "default", payload: object | None = None) -> str:
        await self._wait_for_idle(dag_name, payload)
        async with self._locks[dag_name]:
            run_id, task = self._start_run_locked(source, dag_name, payload)
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
            await load_runtime_app_config(self.config_dir, self.engine),
            scan_extensions(self.extensions_dirs, self.config_dir),
        )

    async def install_snapshot(self, config: AppConfig, bootstrap: BootstrapResult) -> RuntimeSnapshot:
        if self.engine is None:
            raise RuntimeError("DAG controller has not been started")
        async with self._snapshot_lock:
            config.entity_types.update(bootstrap.entity_type_registry.as_dict())
            extension_imports = [
                (bootstrap.extension_roots[manifest.name], manifest)
                for manifest in bootstrap.manifests
                if manifest.entity_imports
            ]
            config = await materialize_runtime_app_config(self.config_dir, config, self.engine, extension_imports)
            await create_extension_tables(self.engine, bootstrap.storage_tables)
            store = EntityStore(
                config.entities,
                config.entity_types,
                config.entity_relations,
                None,
            )
            trigger_executor = self._new_trigger_executor(config, store)
            await trigger_executor.load()
            cron_emitter = CronEmitter(trigger_executor)
            snapshot = RuntimeSnapshot(
                config=config,
                bootstrap=bootstrap,
                entity_store=store,
                trigger_executor=trigger_executor,
                cron_emitter=cron_emitter,
                extension_table_names=dict(bootstrap.table_names),
            )
            self._snapshot = snapshot
            self.trigger_executor = trigger_executor
            self.cron_emitter = cron_emitter
            return snapshot

    def runtime_snapshot(self) -> RuntimeSnapshot:
        if self._snapshot is None:
            raise RuntimeError("DAG controller has not been started")
        return self._snapshot

    def _new_trigger_executor(self, config: AppConfig, store: EntityStore) -> TriggerExecutor:
        return TriggerExecutor(
            store,
            run_dag=lambda name, payload, source: self.start_run(source, name, payload),
            run_node=lambda name, payload, source: self.run_node_trigger(name, payload, source),
            factory=self.factory,
            max_depth=config.system.max_trigger_depth,
        )

    async def run_node_trigger(self, node_id: str, payload: object | None = None, source: str = "manual") -> str:
        dag_name, _instance = self._node_trigger_target(node_id, self.runtime_snapshot())
        await self._wait_for_idle(dag_name, payload)
        async with self._locks[dag_name]:
            snapshot = self.runtime_snapshot()
            dag_name, instance = self._node_trigger_target(node_id, snapshot)
            ctx = self.active_runs.get(dag_name)
            if ctx is not None and not ctx.task.done():
                raise RunAlreadyActiveError(ctx.run_id)
            run_id = uuid4().hex
            stop_event = asyncio.Event()
            task = asyncio.create_task(self._run_single_node(run_id, source, dag_name, instance, payload, stop_event, snapshot))
            self.active_runs[dag_name] = DagRunContext(dag_name=dag_name, run_id=run_id, task=task, stop_event=stop_event)
        task.add_done_callback(lambda t: self._clear_finished_task(t, dag_name))
        return run_id

    def _node_trigger_target(self, node_id: str, snapshot: RuntimeSnapshot) -> tuple[str, DagNodeInstance]:
        matches: list[tuple[str, DagNodeInstance]] = []
        for dag in snapshot.config.dags.values():
            for instance in dag.nodes:
                if instance.id == node_id or instance.alias == node_id:
                    matches.append((dag.name, instance))
        if not matches:
            raise ValueError(f"node '{node_id}' not found")
        if len(matches) > 1:
            dag_names = sorted(name for name, _instance in matches)
            raise ValueError(f"node '{node_id}' is ambiguous across DAGs: {', '.join(dag_names)}")
        return matches[0]

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

    async def retry_node(
        self,
        dag_name: str,
        run_id: str | None,
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
                raise RunAlreadyActiveError(ctx.run_id)
            snapshot = self.runtime_snapshot()
            config = snapshot.config
            graph = load_graph(config.dags[dag_name], config.nodes)
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
                    payload=payload,
                    snapshot=snapshot,
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
            config = snapshot.config
            graph = load_graph(config.dags[dag_name], config.nodes)
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
                    payload=payload,
                    replace_existing_run=True,
                    snapshot=snapshot,
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
                current = await current_dag_run(session, dag_name)
                recent = await recent_dag_runs(session, dag_name=dag_name)
            ctx = self.active_runs.get(dag_name)
            return {
                "scheduler_running": self.scheduler.running,
                "scheduler_paused": self.scheduler.state == 2,
                "dag_name": dag_name,
                "current_run_id": current.run_id if current else (ctx.run_id if ctx else None),
                "recent_runs": [_run_dict(run) for run in recent],
            }
        async with factory() as session:
            current = await current_dag_run(session)
            recent = await recent_dag_runs(session)
        return {
            "scheduler_running": self.scheduler.running,
            "scheduler_paused": self.scheduler.state == 2,
            "active_dags": {name: ctx.run_id for name, ctx in self.active_runs.items() if not ctx.task.done()},
            "recent_runs": [_run_dict(run) for run in recent],
        }

    async def node_status(self, node_id: str) -> str:
        for ctx in self.active_runs.values():
            if not ctx.task.done() and _dag_has_node(self.runtime_snapshot().config, ctx.dag_name, node_id):
                return "running"
        config = self.runtime_snapshot().config
        factory = self._factory()
        async with factory() as session:
            for dag in config.dags.values():
                if not any(instance.id == node_id or instance.alias == node_id for instance in dag.nodes):
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

    async def _wait_for_idle(self, dag_name: str, payload: object | None) -> None:
        target = _wait_for_idle_target(self.runtime_snapshot().config, dag_name, payload)
        if target is None:
            return
        while any(not ctx.task.done() and _dag_has_node(self.runtime_snapshot().config, ctx.dag_name, target) for ctx in self.active_runs.values()):
            await asyncio.sleep(0.1)

    def _start_run_locked(self, source: str, dag_name: str, payload: object | None = None) -> tuple[str, asyncio.Task[object]]:
        ctx = self.active_runs.get(dag_name)
        if ctx is not None and not ctx.task.done():
            raise RunAlreadyActiveError(ctx.run_id)
        run_id = uuid4().hex
        stop_event = asyncio.Event()
        task = asyncio.create_task(self._run(run_id, source, dag_name, stop_event=stop_event, payload=payload, snapshot=self.runtime_snapshot()))
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
        payload: object | None = None,
        replace_existing_run: bool = False,
        snapshot: RuntimeSnapshot | None = None,
    ) -> object:
        snapshot = snapshot or self.runtime_snapshot()
        config = snapshot.config
        graph = load_graph(config.dags[dag_name], config.nodes)
        factory = self._factory()
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
            executor = self._build_run_executor(snapshot, graph)
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
                dags=config.dags,
                nodes=config.nodes,
            ).run(
                graph,
                run_id,
                payload if payload is not None else {"entities": _source_entity_refs(config)},
                stop_event=stop_event,
                retry_nodes=retry_nodes,
                prefilled_outputs=prefilled_outputs,
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
            _cleanup_sandboxes(config)
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

    async def _run_single_node(
        self,
        run_id: str,
        source: str,
        dag_name: str,
        instance: DagNodeInstance,
        payload: object | None,
        stop_event: asyncio.Event,
        snapshot: RuntimeSnapshot | None = None,
    ) -> object:
        snapshot = snapshot or self.runtime_snapshot()
        config = snapshot.config
        graph = DagGraph(
            dag_name,
            [instance.id],
            {instance.id: instance},
            {instance.id: []},
            {instance.id: []},
        )
        factory = self._factory()
        async with factory() as session:
            await create_dag_run(session, run_id, source, [instance.id], dag_name)
            await session.commit()
        await event_bus.publish("dag.status", run_id=run_id, dag_name=dag_name, status="started")
        try:
            executor = self._build_run_executor(snapshot, graph)
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
                dags=config.dags,
                nodes=config.nodes,
            ).run(
                graph,
                run_id,
                payload if payload is not None else {"entities": _source_entity_refs(config)},
                stop_event=stop_event,
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

    def _build_run_executor(self, snapshot: RuntimeSnapshot, graph) -> NodeExecutor:
        return _build_executor(
            snapshot.config,
            snapshot.bootstrap.handler_registry,
            graph.instances,
            self.config_dir,
            extension_tables=snapshot.extension_table_names,
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
            agent_certificate_issuer=self.agent_certificate_issuer,
            daemon_data_dir=self.daemon_data_dir,
            source_recovery_recorder=self._record_source_recovery,
        )


def build_executor(config_dir: Path = Path("config")) -> tuple[NodeExecutor, str]:
    async def _load() -> tuple[NodeExecutor, str]:
        controller = DagController(config_dir)
        await controller.start(run_startup=False)
        try:
            snapshot = controller.runtime_snapshot()
            graph = load_graph(snapshot.config.dags["default"], snapshot.config.nodes)
            return (
                _build_executor(
                    snapshot.config,
                    snapshot.bootstrap.handler_registry,
                    graph.instances,
                    config_dir=config_dir,
                    extension_tables=snapshot.extension_table_names,
                ),
                "default",
            )
        finally:
            await controller.shutdown()

    return asyncio.run(_load())


async def run_default_run(config_dir: Path = Path("config")) -> object:
    controller = DagController(config_dir)
    await controller.start(run_startup=False)
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


def _build_executor(
    app_config: AppConfig,
    handler_registry,
    instances: Mapping[str, DagNodeInstance] | None = None,
    config_dir: Path | None = None,
    extension_tables: dict[str, dict[str, str]] | None = None,
    output_recorder=None,
    stdout_recorder=None,
    raw_log_recorder=None,
    agent_certificate_issuer=None,
    daemon_data_dir: Path | None = None,
    source_recovery_recorder=None,
) -> NodeExecutor:
    entity_store = EntityStore(
        app_config.entities,
        app_config.entity_types,
        app_config.entity_relations,
        None,
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
        raw_log_recorder=raw_log_recorder,
        agent_certificate_issuer=agent_certificate_issuer,
        extension_tables=extension_tables,
        daemon_data_dir=daemon_data_dir,
        source_recovery_recorder=source_recovery_recorder,
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


def _dag_has_node(config: AppConfig, dag_name: str, node_id: str) -> bool:
    dag = config.dags.get(dag_name)
    if dag is None:
        return False
    return any(instance.id == node_id or instance.alias == node_id for instance in dag.nodes)


def _wait_for_idle_target(config: AppConfig, dag_name: str, payload: object | None) -> str | None:
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
