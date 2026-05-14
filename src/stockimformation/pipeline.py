from __future__ import annotations

import asyncio
from collections.abc import Mapping
from pathlib import Path
from uuid import uuid4

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from stockimformation.config.loader import load_app_config
from stockimformation.config.schema import AppConfig
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
        self.current_task: asyncio.Task[object] | None = None
        self.current_cycle_id: str | None = None
        self._lock = asyncio.Lock()

    async def start(self, run_startup: bool = True) -> None:
        config = load_app_config(self.config_dir)
        self.engine = create_engine(config.system.database_url)
        await init_db(self.engine)
        self.factory = session_factory(self.engine)
        self.scheduler.add_job(
            self._start_schedule_run,
            "interval",
            minutes=config.system.schedule_minutes,
            id="default-dag",
            max_instances=1,
            coalesce=True,
        )
        self.scheduler.start()
        if run_startup:
            await self.start_run("startup")

    async def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        task = self.current_task
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        if self.engine is not None:
            await self.engine.dispose()

    async def start_run(self, trigger: str = "manual") -> str:
        async with self._lock:
            cycle_id, task = self._start_run_locked(trigger)
        task.add_done_callback(self._clear_finished_task)
        return cycle_id

    async def run_now(self, trigger: str = "manual") -> str:
        async with self._lock:
            cycle_id, task = self._start_run_locked(trigger)
        try:
            await task
        finally:
            self._clear_finished_task(task)
        return cycle_id

    def pause_scheduler(self) -> None:
        self.scheduler.pause()

    def resume_scheduler(self) -> None:
        self.scheduler.resume()

    async def stop_current(self) -> str | None:
        task = self.current_task
        cycle_id = self.current_cycle_id
        if task is None or task.done() or cycle_id is None:
            return None
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return cycle_id

    async def status(self) -> dict[str, object]:
        factory = self._factory()
        async with factory() as session:
            current = await current_pipeline_run(session)
            recent = await recent_pipeline_runs(session)
        return {
            "scheduler_running": self.scheduler.running,
            "scheduler_paused": self.scheduler.state == 2,
            "current_cycle_id": current.cycle_id if current else self.current_cycle_id,
            "recent_runs": [_run_dict(run) for run in recent],
        }

    async def _start_schedule_run(self) -> None:
        try:
            await self.start_run("schedule")
        except RunAlreadyActiveError:
            return

    def _start_run_locked(self, trigger: str) -> tuple[str, asyncio.Task[object]]:
        if self.current_task is not None and not self.current_task.done():
            if self.current_cycle_id is None:
                raise RunAlreadyActiveError("unknown")
            raise RunAlreadyActiveError(self.current_cycle_id)
        cycle_id = uuid4().hex
        self.current_cycle_id = cycle_id
        self.current_task = asyncio.create_task(self._run(cycle_id, trigger))
        return cycle_id, self.current_task

    def _clear_finished_task(self, task: asyncio.Task[object]) -> None:
        if task.done() and not task.cancelled():
            try:
                task.exception()
            except Exception:
                pass
        if self.current_task is task and task.done():
            self.current_task = None
            self.current_cycle_id = None

    async def _run(self, cycle_id: str, trigger: str) -> object:
        config = load_app_config(self.config_dir)
        graph = load_graph(config.dags["default"], config.nodes)
        factory = self._factory()
        async with factory() as session:
            await create_pipeline_run(session, cycle_id, trigger, list(graph.nodes))
            await session.commit()
        try:
            result = await DagRunner(
                _build_executor(config),
                recorder=lambda node, status, error: self._record_node(cycle_id, node, status, error),
            ).run(graph, cycle_id, {"source_names": [source.name for source in config.portfolio.sources]})
            await _persist_outputs(factory, result.node_outputs)
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
    return _build_executor(load_app_config(config_dir)), "default"


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
) -> None:
    raw_payload = _list_payload(outputs, "rss-fetcher") + _list_payload(outputs, "web-scraper")
    analyses_payload = _list_payload(outputs, "reader")
    advices_payload = _list_payload(outputs, "advisor")
    briefing_payload = _dict_payload(outputs, "briefing-generator")
    raw_items = [RawItem.model_validate(item) for item in raw_payload]
    analyses = [AnalysisResult.model_validate(item) for item in analyses_payload]
    advices = [Advice.model_validate(item) for item in advices_payload]
    briefing = Briefing.model_validate(briefing_payload) if briefing_payload else None
    async with factory() as session:
        await store_cycle_outputs(session, raw_items, analyses, advices, briefing)
        await session.commit()


def _build_executor(app_config: AppConfig) -> NodeExecutor:
    handlers = {
        "fetch-rss": make_fetch_handler(app_config.portfolio, "rss"),
        "fetch-web": make_fetch_handler(app_config.portfolio, "web"),
        "summarize": analyze_handler,
        "classify-sentiment": analyze_handler,
        "generate-advice": make_advice_handler(app_config.portfolio),
        "generate-briefing": make_briefing_handler(app_config.portfolio),
        "notify-ntfy": make_notify_handler(app_config.runtime),
    }
    return NodeExecutor(app_config.nodes, app_config.system, app_config.runtime, handlers)


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


def _run_dict(run: PipelineRun) -> dict[str, object]:
    return run.model_dump(mode="json")
