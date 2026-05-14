from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from stockimformation.models import create_engine, init_db, session_factory, sqlite_url
from stockimformation.models.repository import create_pipeline_run
from stockimformation.pipeline import PipelineController, RunAlreadyActiveError
from stockimformation.web.app import create_app


class FakeController(PipelineController):
    async def start(self, run_startup: bool = True) -> None:
        self.engine = create_engine(sqlite_url(self.config_dir / "web.db"))
        await init_db(self.engine)
        self.factory = session_factory(self.engine)
        self.scheduler.start()

    async def start_run(self, trigger: str = "manual") -> str:
        async with self._lock:
            if self.current_task is not None and not self.current_task.done():
                raise RunAlreadyActiveError(self.current_cycle_id or "unknown")
            cycle_id = "cycle-manual"
            self.current_cycle_id = cycle_id
            self.current_task = asyncio.create_task(self._fake_run(cycle_id, trigger))
            self.current_task.add_done_callback(self._clear_finished_task)
            return cycle_id

    async def _fake_run(self, cycle_id: str, trigger: str) -> None:
        async with self._factory()() as session:
            await create_pipeline_run(session, cycle_id, trigger)
            await session.commit()
        await asyncio.sleep(60)


@pytest.mark.asyncio
async def test_web_pipeline_api_run_conflict_pause_resume_stop(tmp_path: Path) -> None:
    app = create_app(tmp_path, FakeController(tmp_path), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            first = await client.post("/api/pipeline/run")
            second = await client.post("/api/pipeline/run")
            paused = await client.post("/api/pipeline/pause")
            resumed = await client.post("/api/pipeline/resume")
            stopped = await client.post("/api/pipeline/stop")
        finally:
            await app.state.controller.shutdown()
    assert first.status_code == 200
    assert first.json()["cycle_id"] == "cycle-manual"
    assert second.status_code == 409
    assert paused.json()["scheduler_paused"] is True
    assert resumed.json()["scheduler_paused"] is False
    assert stopped.json() == {"stopped": True, "cycle_id": "cycle-manual"}


@pytest.mark.asyncio
async def test_web_pipeline_stop_without_active_run(tmp_path: Path) -> None:
    app = create_app(tmp_path, FakeController(tmp_path), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            response = await client.post("/api/pipeline/stop")
        finally:
            await app.state.controller.shutdown()
    assert response.json() == {"stopped": False, "cycle_id": None}


@pytest.mark.asyncio
async def test_web_results_empty_state(tmp_path: Path) -> None:
    app = create_app(tmp_path, FakeController(tmp_path), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            response = await client.get("/api/results")
        finally:
            await app.state.controller.shutdown()
    assert response.json() == {"briefing": None, "advices": [], "failed_sources": {}}
