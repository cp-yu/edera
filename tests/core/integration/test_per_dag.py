from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from stockimformation_core.storage import create_engine, init_db, session_factory, sqlite_url
from stockimformation_core.storage.repository import create_pipeline_run, recent_pipeline_runs
from stockimformation_core.pipeline import DagRunContext, PipelineController, RunAlreadyActiveError
from stockimformation_core.web.app import create_app


class FakeController(PipelineController):
    async def start(self, run_startup: bool = True) -> None:
        self.engine = create_engine(sqlite_url(self.config_dir / "test.db"))
        await init_db(self.engine)
        self.factory = session_factory(self.engine)
        self.scheduler.start()

    async def start_run(self, trigger: str = "manual", dag_name: str = "default") -> str:
        async with self._locks[dag_name]:
            ctx = self.active_runs.get(dag_name)
            if ctx is not None and not ctx.task.done():
                raise RunAlreadyActiveError(ctx.cycle_id)
            cycle_id = f"cycle-{dag_name}-{trigger}"
            task = asyncio.create_task(self._fake_run(cycle_id, trigger, dag_name))
            self.active_runs[dag_name] = DagRunContext(dag_name=dag_name, cycle_id=cycle_id, task=task)
            task.add_done_callback(lambda t: self._clear_finished_task(t, dag_name))
            return cycle_id

    async def _fake_run(self, cycle_id: str, trigger: str, dag_name: str) -> None:
        async with self._factory()() as session:
            await create_pipeline_run(session, cycle_id, trigger, dag_name=dag_name)
            await session.commit()
        await asyncio.sleep(60)


# --- PLACEHOLDER_TESTS ---


def _write_dag_config(path: Path) -> None:
    path.joinpath("system.toml").write_text(
        f'database_url = "sqlite+aiosqlite:///{path / "test.db"}"\n'
        f'schedule_minutes = 30\nweb_host = "127.0.0.1"\nweb_port = 8000\n'
        f'log_level = "INFO"\nllm_timeout_seconds = 60\n'
        f'workspace_root = "{path / "workspace"}"\n'
        f'retention_count = 20\nretention_hours = 24\n'
    )
    dags_dir = path / "dags"
    dags_dir.mkdir(exist_ok=True)
    dags_dir.joinpath("default.yaml").write_text("name: default\nnodes: []\nedges: []\n")
    dags_dir.joinpath("realtime.yaml").write_text("name: realtime\nnodes: []\nedges: []\n")


@pytest.mark.asyncio
async def test_per_dag_concurrent_execution(tmp_path: Path) -> None:
    """C1: Different DAGs can run concurrently; same DAG raises RunAlreadyActiveError."""
    _write_dag_config(tmp_path)
    ctrl = FakeController(tmp_path)
    await ctrl.start(run_startup=False)
    try:
        cycle_default = await ctrl.start_run("manual", "default")
        cycle_realtime = await ctrl.start_run("manual", "realtime")
        assert cycle_default == "cycle-default-manual"
        assert cycle_realtime == "cycle-realtime-manual"
        assert "default" in ctrl.active_runs
        assert "realtime" in ctrl.active_runs
        with pytest.raises(RunAlreadyActiveError):
            await ctrl.start_run("manual", "default")
    finally:
        await ctrl.shutdown()


@pytest.mark.asyncio
async def test_per_dag_stop(tmp_path: Path) -> None:
    """C2: Stopping one DAG does not affect another running DAG."""
    _write_dag_config(tmp_path)
    ctrl = FakeController(tmp_path)
    await ctrl.start(run_startup=False)
    try:
        await ctrl.start_run("manual", "default")
        await ctrl.start_run("manual", "realtime")
        stopped = await ctrl.stop_current("default")
        assert stopped == "cycle-default-manual"
        assert "default" not in ctrl.active_runs
        assert "realtime" in ctrl.active_runs
        assert not ctrl.active_runs["realtime"].task.done()
    finally:
        await ctrl.shutdown()


@pytest.mark.asyncio
async def test_per_dag_status_api(tmp_path: Path) -> None:
    """C3: GET /api/pipeline/dag/{dag_name}/status returns per-DAG status."""
    _write_dag_config(tmp_path)
    app = create_app(tmp_path, FakeController(tmp_path), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            await client.post("/api/pipeline/dag/default/run")
            response = await client.get("/api/pipeline/dag/default/status")
            not_found = await client.get("/api/pipeline/dag/nonexistent/status")
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 200
    data = response.json()
    assert data["dag_name"] == "default"
    assert data["current_cycle_id"] == "cycle-default-manual"
    assert not_found.status_code == 404


@pytest.mark.asyncio
async def test_per_dag_run_api(tmp_path: Path) -> None:
    """C4: POST /api/pipeline/dag/{dag_name}/run returns 200 + cycle_id; nonexistent DAG returns 404."""
    _write_dag_config(tmp_path)
    app = create_app(tmp_path, FakeController(tmp_path), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            first = await client.post("/api/pipeline/dag/default/run")
            conflict = await client.post("/api/pipeline/dag/default/run")
            not_found = await client.post("/api/pipeline/dag/nonexistent/run")
        finally:
            await app.state.controller.shutdown()
    assert first.status_code == 200
    assert first.json()["cycle_id"] == "cycle-default-manual"
    assert conflict.status_code == 409
    assert not_found.status_code == 404


@pytest.mark.asyncio
async def test_ssr_routes_removed(tmp_path: Path) -> None:
    """C5: SSR routes no longer exist."""
    _write_dag_config(tmp_path)
    app = create_app(tmp_path, FakeController(tmp_path), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            index = await client.get("/")
            results = await client.get("/results")
            pipeline = await client.get("/pipeline")
            config = await client.get("/config")
        finally:
            await app.state.controller.shutdown()
    assert index.status_code == 404
    assert results.status_code == 404
    assert pipeline.status_code == 404
    assert config.status_code == 404


@pytest.mark.asyncio
async def test_cors_middleware(tmp_path: Path) -> None:
    """C6: CORS middleware allows localhost:5173."""
    _write_dag_config(tmp_path)
    app = create_app(tmp_path, FakeController(tmp_path), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            response = await client.options(
                "/api/pipeline/status",
                headers={
                    "Origin": "http://localhost:5173",
                    "Access-Control-Request-Method": "GET",
                },
            )
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


@pytest.mark.asyncio
async def test_pipeline_run_dag_name_field(tmp_path: Path) -> None:
    """C7: PipelineRun records include dag_name; filtering by dag_name works."""
    _write_dag_config(tmp_path)
    ctrl = FakeController(tmp_path)
    await ctrl.start(run_startup=False)
    try:
        async with ctrl._factory()() as session:
            await create_pipeline_run(session, "cycle-a", "manual", dag_name="default")
            await create_pipeline_run(session, "cycle-b", "manual", dag_name="realtime")
            await session.commit()
        async with ctrl._factory()() as session:
            all_runs = await recent_pipeline_runs(session)
            default_runs = await recent_pipeline_runs(session, dag_name="default")
            realtime_runs = await recent_pipeline_runs(session, dag_name="realtime")
    finally:
        await ctrl.shutdown()
    assert len(all_runs) == 2
    assert len(default_runs) == 1
    assert default_runs[0].dag_name == "default"
    assert len(realtime_runs) == 1
    assert realtime_runs[0].dag_name == "realtime"


@pytest.mark.asyncio
async def test_scheduler_per_dag_registration(tmp_path: Path) -> None:
    """C8: Scheduler registers one job per DAG config file."""
    _write_dag_config(tmp_path)
    _write_full_config(tmp_path)
    ctrl = PipelineController(tmp_path)
    await ctrl.start(run_startup=False)
    try:
        jobs = ctrl.scheduler.get_jobs()
        job_ids = {job.id for job in jobs}
        assert "default-dag" in job_ids
        assert "realtime-dag" in job_ids
        assert len(jobs) == 2
    finally:
        await ctrl.shutdown()


def _write_full_config(path: Path) -> None:
    """Write minimal entity and nodes config for PipelineController.start()."""
    schemas = path.parent / "schemas" / "entity-types"
    schemas.mkdir(parents=True, exist_ok=True)
    schemas.joinpath("stock.yaml").write_text(
        "display_name: Stock\nbusiness_id_field: code\ndisplay_template: '{code}'\nschema: {}\nfield_permissions: {}\n"
    )
    path.joinpath("entities.yaml").write_text("entities: []\n")
    path.joinpath("entity-relations.yaml").write_text("relations: []\n")
    nodes_dir = path / "nodes"
    nodes_dir.mkdir(exist_ok=True)
