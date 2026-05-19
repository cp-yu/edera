from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from stockimformation.config.loader import load_app_config
from stockimformation.config.entities import EntityStore
from stockimformation.config.schema import AppConfig, DagNodeInstance
from stockimformation.dag.loader import load_graph
from stockimformation.dag.runner import DagRunner
from stockimformation.models import create_engine, init_db, session_factory
from stockimformation.models.entities import Advice, AnalysisResult, Briefing, PipelineRun, RawItem
from stockimformation.models.repository import (
    create_pipeline_run,
    current_pipeline_run,
    finish_pipeline_run,
    mark_node_run,
    recent_pipeline_runs,
    store_cycle_outputs,
)
from stockimformation.node.executor import NodeExecutor
from stockimformation.node.models import NodeOutput
from stockimformation.services import (
    analyze_handler,
    make_advice_handler,
    make_briefing_handler,
    make_fetch_handler,
    make_notify_handler,
)


class RunAlreadyActiveError(Exception):
    def __init__(self, cycle_id: str) -> None:
        self.cycle_id = cycle_id
        super().__init__(f"pipeline run already active: {cycle_id}")


@dataclass
class DagRunContext:
    dag_name: str
    cycle_id: str
    task: asyncio.Task[object]
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class PipelineController:
    def __init__(
        self,
        config_dir: Path = Path("config"),
        scheduler: AsyncIOScheduler | None = None,
    ) -> None:
        self.config_dir = config_dir
        self.scheduler = scheduler or AsyncIOScheduler()
        self.engine: AsyncEngine | None = None
        self.factory: async_sessionmaker[AsyncSession] | None = None
        self.active_runs: dict[str, DagRunContext] = {}
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def start(self, run_startup: bool = True) -> None:
        config = load_app_config(self.config_dir)
        self.engine = create_engine(config.system.database_url)
        await init_db(self.engine)
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

    async def start_run(self, trigger: str = "manual", dag_name: str = "default") -> str:
        async with self._locks[dag_name]:
            cycle_id, task = self._start_run_locked(trigger, dag_name)
        task.add_done_callback(lambda t: self._clear_finished_task(t, dag_name))
        return cycle_id

    async def run_now(self, trigger: str = "manual", dag_name: str = "default") -> str:
        async with self._locks[dag_name]:
            cycle_id, task = self._start_run_locked(trigger, dag_name)
        try:
            await task
        finally:
            self._clear_finished_task(task, dag_name)
        return cycle_id

    def pause_scheduler(self) -> None:
        self.scheduler.pause()

    def resume_scheduler(self) -> None:
        self.scheduler.resume()

    async def stop_current(self, dag_name: str = "default") -> str | None:
        ctx = self.active_runs.get(dag_name)
        if ctx is None or ctx.task.done():
            return None
        ctx.task.cancel()
        try:
            await ctx.task
        except asyncio.CancelledError:
            pass
        return ctx.cycle_id

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

    async def _start_schedule_run(self, dag_name: str = "default") -> None:
        try:
            await self.start_run("schedule", dag_name)
        except RunAlreadyActiveError:
            return

    def _start_run_locked(self, trigger: str, dag_name: str) -> tuple[str, asyncio.Task[object]]:
        ctx = self.active_runs.get(dag_name)
        if ctx is not None and not ctx.task.done():
            raise RunAlreadyActiveError(ctx.cycle_id)
        cycle_id = uuid4().hex
        task = asyncio.create_task(self._run(cycle_id, trigger, dag_name))
        self.active_runs[dag_name] = DagRunContext(dag_name=dag_name, cycle_id=cycle_id, task=task)
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

    async def _run(self, cycle_id: str, trigger: str, dag_name: str = "default") -> object:
        config = load_app_config(self.config_dir)
        graph = load_graph(config.dags[dag_name], config.nodes)
        factory = self._factory()
        async with factory() as session:
            await create_pipeline_run(session, cycle_id, trigger, list(graph.nodes), dag_name)
            await session.commit()
        try:
            result = await DagRunner(
                _build_executor(config, graph.instances, self.config_dir),
                recorder=lambda node, status, error: self._record_node(cycle_id, node, status, error),
            ).run(graph, cycle_id, {"entities": _source_entity_refs(config)})
            await _record_source_runs(factory, cycle_id, result.node_outputs)
            await _persist_outputs(factory, result.node_outputs, graph.instances)
            status = "succeeded" if result.ok else "failed"
            error = "; ".join(f"{node}: {message}" for node, message in result.failures.items()) or None
            async with factory() as session:
                await finish_pipeline_run(session, cycle_id, status, error)
                await session.commit()
            return result.payload
        except asyncio.CancelledError:
            await self._finish_cancelled(cycle_id)
            raise
        except Exception as exc:
            async with factory() as session:
                await finish_pipeline_run(session, cycle_id, "failed", str(exc))
                await session.commit()
            raise

    async def _record_node(
        self,
        cycle_id: str,
        node: str,
        status: str,
        error: str | None,
    ) -> None:
        async with self._factory()() as session:
            await mark_node_run(session, cycle_id, node, status, error)
            await session.commit()

    async def _finish_cancelled(self, cycle_id: str) -> None:
        async with self._factory()() as session:
            await finish_pipeline_run(session, cycle_id, "cancelled")
            await session.commit()

    def _factory(self) -> async_sessionmaker[AsyncSession]:
        if self.factory is None:
            raise RuntimeError("pipeline controller has not been started")
        return self.factory


def build_executor(config_dir: Path = Path("config")) -> tuple[NodeExecutor, str]:
    return _build_executor(load_app_config(config_dir), config_dir=config_dir), "default"


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
    outputs: Mapping[str, NodeOutput],
    instances: Mapping[str, DagNodeInstance],
) -> None:
    raw_payload = _list_payload(outputs, _instance_id(instances, "rss-fetcher")) + _list_payload(outputs, _instance_id(instances, "web-scraper"))
    analyses_payload = _list_payload(outputs, _instance_id(instances, "reader"))
    advices_payload = _list_payload(outputs, _instance_id(instances, "advisor"))
    briefing_payload = _dict_payload(outputs, _instance_id(instances, "briefing-generator"))
    raw_items = [RawItem.model_validate(item) for item in raw_payload]
    analyses = [AnalysisResult.model_validate(item) for item in analyses_payload]
    advices = [Advice.model_validate(item) for item in advices_payload]
    briefing = Briefing.model_validate(briefing_payload) if briefing_payload else None
    async with factory() as session:
        await store_cycle_outputs(session, raw_items, analyses, advices, briefing)
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
    instances: Mapping[str, DagNodeInstance] | None = None,
    config_dir: Path | None = None,
) -> NodeExecutor:
    handlers = {
        "fetch-rss": make_fetch_handler(app_config.portfolio, "rss", app_config.system),
        "fetch-web": make_fetch_handler(app_config.portfolio, "web", app_config.system),
        "summarize": analyze_handler,
        "classify-sentiment": analyze_handler,
        "generate-advice": make_advice_handler(app_config.portfolio),
        "generate-briefing": make_briefing_handler(app_config.portfolio),
        "notify-ntfy": make_notify_handler(app_config.runtime),
    }
    entity_store = EntityStore(
        app_config.entities,
        app_config.entity_types,
        app_config.entity_relations,
        config_dir / "entities.yaml" if config_dir is not None else None,
    )
    return NodeExecutor(
        app_config.nodes,
        app_config.system,
        app_config.runtime,
        handlers,
        dict(instances or {}),
        entity_store,
    )


def _source_entity_refs(app_config: AppConfig) -> list[str]:
    refs: list[str] = []
    for entity in app_config.entities.entities:
        if entity.type not in {"rss-source", "web-source"}:
            continue
        name = entity.attributes.get("name")
        if isinstance(name, str):
            refs.append(f"{entity.type}:{name}")
    return refs


def _instance_id(instances: Mapping[str, DagNodeInstance], node_type: str) -> str:
    for instance_id, instance in instances.items():
        if instance.type == node_type:
            return instance_id
    return node_type


def _list_payload(outputs: Mapping[str, NodeOutput], node_name: str) -> list[object]:
    output = outputs.get(node_name)
    if output is None or not output.ok:
        return []
    return output.payload if isinstance(output.payload, list) else []


def _dict_payload(outputs: Mapping[str, NodeOutput], node_name: str) -> dict[str, object]:
    output = outputs.get(node_name)
    if output is None or not output.ok:
        return {}
    return output.payload if isinstance(output.payload, dict) else {}


def _source_recovery(outputs: Mapping[str, NodeOutput]) -> dict[str, object]:
    recovery: dict[str, object] = {}
    for output in outputs.values():
        recovery.update(output.metadata.get("source_recovery", {}))
    return recovery


def _run_dict(run: PipelineRun) -> dict[str, object]:
    return run.model_dump(mode="json")
