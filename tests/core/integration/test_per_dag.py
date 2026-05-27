from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from stockimformation_core.storage import create_engine, init_db, session_factory, sqlite_url
from stockimformation_core.storage.repository import (
    create_pipeline_run,
    finish_pipeline_run,
    get_pipeline_run,
    recent_pipeline_runs,
    store_node_output_entities,
)
from stockimformation_core.pipeline import DagRunContext, PipelineController, PipelineRunNotFoundError, RetryRunResult, RunAlreadyActiveError
from stockimformation_core.web.app import create_app


class FakeController(PipelineController):
    last_payload: object | None = None

    async def start(self, run_startup: bool = True) -> None:
        self.engine = create_engine(sqlite_url(self.config_dir / "test.db"))
        await init_db(self.engine)
        self.factory = session_factory(self.engine)
        self.scheduler.start()

    async def start_run(self, trigger: str = "manual", dag_name: str = "default", payload: object | None = None) -> str:
        self.last_payload = payload
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

    async def retry_node(
        self,
        dag_name: str,
        cycle_id: str | None,
        node_ids: list[str],
        mode: str = "single",
        payload: object | None = None,
    ) -> RetryRunResult:
        if not node_ids:
            raise ValueError("node_ids is required")
        if cycle_id is None:
            async with self._factory()() as session:
                recent = await recent_pipeline_runs(session, 10, dag_name)
            cycle_id = next((run.cycle_id for run in recent if run.status != "running"), None)
        if cycle_id is None:
            raise PipelineRunNotFoundError("latest finished run")
        if cycle_id == "missing-cycle":
            raise PipelineRunNotFoundError(cycle_id)
        retry_cycle_id = f"retry-{cycle_id}"
        async with self._factory()() as session:
            await create_pipeline_run(session, retry_cycle_id, "retry", dag_name=dag_name, retry_of=cycle_id)
            await session.commit()
        return RetryRunResult(retry_cycle_id, cycle_id, node_ids, mode, node_ids)

    async def resume_node(self, dag_name: str, cycle_id: str, node_id: str, payload: object) -> str:
        return await super().resume_node(dag_name, cycle_id, node_id, payload)


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
    dags_dir.joinpath("reflection.yaml").write_text(
        "name: reflection\n"
        "nodes: []\n"
        "edges: []\n"
        "ui:\n"
        "  wait_for:\n"
        "    node: $payload.target\n"
        "    status: idle\n"
    )
    nodes_dir = path / "nodes"
    nodes_dir.mkdir(exist_ok=True)
    nodes_dir.joinpath("node-a.yaml").write_text(
        "name: node-a\n"
        "type: function\n"
        "handler: node-a\n"
        "input_type: Any\n"
        "output_type: Any\n"
    )
    _write_entity_schemas(path)


def _write_entity_schemas(path: Path) -> None:
    schemas = path.parent / "schemas" / "entity-types"
    schemas.mkdir(parents=True, exist_ok=True)
    schemas.joinpath("stock.yaml").write_text(
        "display_name: Stock\nbusiness_id_field: code\ndisplay_template: '{code}'\nschema: {}\nfield_permissions: {}\n"
    )
    path.joinpath("entities.yaml").write_text("entities: []\n")
    path.joinpath("entity-relations.yaml").write_text("relations: []\n")


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
        stopped = await ctrl.stop_current("default", force=True)
        assert stopped == "cycle-default-manual"
        assert "default" not in ctrl.active_runs
        assert "realtime" in ctrl.active_runs
        assert not ctrl.active_runs["realtime"].task.done()
    finally:
        await ctrl.shutdown()


@pytest.mark.asyncio
async def test_dag_stop_api_accepts_force(tmp_path: Path) -> None:
    _write_dag_config(tmp_path)
    app = create_app(tmp_path, FakeController(tmp_path), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            await client.post("/api/pipeline/dag/default/run")
            response = await client.post("/api/pipeline/dag/default/stop", json={"force": True})
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 200
    assert response.json() == {"stopped": True, "cycle_id": "cycle-default-manual"}


@pytest.mark.asyncio
async def test_retry_api_records_retry_of(tmp_path: Path) -> None:
    _write_dag_config(tmp_path)
    app = create_app(tmp_path, FakeController(tmp_path), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            async with app.state.controller._factory()() as session:
                await create_pipeline_run(session, "cycle-original", "manual", dag_name="default")
                await session.commit()
            response = await client.post(
                "/api/pipeline/dag/default/retry",
                json={"cycle_id": "cycle-original", "node_ids": ["node-a"], "mode": "cascade"},
            )
            async with app.state.controller._factory()() as session:
                run = await get_pipeline_run(session, "retry-cycle-original")
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 200
    assert response.json() == {
        "cycle_id": "retry-cycle-original",
        "retry_of": "cycle-original",
        "node_ids": ["node-a"],
        "mode": "cascade",
        "retry_nodes": ["node-a"],
    }
    assert run is not None
    assert run.trigger == "retry"
    assert run.retry_of == "cycle-original"


@pytest.mark.asyncio
async def test_retry_api_defaults_to_latest_finished_run(tmp_path: Path) -> None:
    _write_dag_config(tmp_path)
    app = create_app(tmp_path, FakeController(tmp_path), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            async with app.state.controller._factory()() as session:
                await create_pipeline_run(session, "cycle-old", "manual", dag_name="default")
                await finish_pipeline_run(session, "cycle-old", "failed")
                await create_pipeline_run(session, "cycle-new", "manual", dag_name="default")
                await finish_pipeline_run(session, "cycle-new", "succeeded")
                await session.commit()
            response = await client.post(
                "/api/pipeline/dag/default/retry",
                json={"node_ids": ["node-a"], "mode": "single"},
            )
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 200
    assert response.json()["retry_of"] == "cycle-new"


@pytest.mark.asyncio
async def test_retry_api_missing_cycle_returns_404(tmp_path: Path) -> None:
    _write_dag_config(tmp_path)
    app = create_app(tmp_path, FakeController(tmp_path), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            response = await client.post(
                "/api/pipeline/dag/default/retry",
                json={"cycle_id": "missing-cycle", "node_ids": ["node-a"], "mode": "single"},
            )
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 404
    assert response.json()["error"]["type"] == "not_found"


@pytest.mark.asyncio
async def test_retry_node_missing_prefilled_upstream_returns_error(tmp_path: Path) -> None:
    _write_dag_config(tmp_path)
    (tmp_path / "nodes" / "node-b.yaml").write_text(
        "name: node-b\n"
        "type: function\n"
        "handler: node-b\n"
        "input_type: Any\n"
        "output_type: Any\n",
        encoding="utf-8",
    )
    (tmp_path / "dags" / "default.yaml").write_text(
        "name: default\n"
        "nodes:\n"
        "- id: node-a\n"
        "  type: node-a\n"
        "- id: node-b\n"
        "  type: node-b\n"
        "edges:\n"
        "- from: node-a\n"
        "  to: node-b\n",
        encoding="utf-8",
    )
    ctrl = PipelineController(tmp_path)
    await ctrl.start(run_startup=False)
    try:
        async with ctrl._factory()() as session:
            await create_pipeline_run(session, "cycle-original", "manual", ["node-a", "node-b"], dag_name="default")
            await finish_pipeline_run(session, "cycle-original", "failed")
            await session.commit()
        with pytest.raises(ValueError, match="missing prefilled outputs: node-a"):
            await ctrl.retry_node("default", "cycle-original", ["node-b"], "single")
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
async def test_dag_run_api_uses_direct_body_as_initial_payload(tmp_path: Path) -> None:
    _write_dag_config(tmp_path)
    app = create_app(tmp_path, FakeController(tmp_path), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            response = await client.post("/api/pipeline/dag/default/run", json={"ticker": "300470.SZ"})
            payload = app.state.controller.last_payload
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 200
    assert payload == {"ticker": "300470.SZ"}


@pytest.mark.asyncio
async def test_dag_run_api_unwraps_inputs_body(tmp_path: Path) -> None:
    _write_dag_config(tmp_path)
    app = create_app(tmp_path, FakeController(tmp_path), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            response = await client.post("/api/pipeline/dag/default/run", json={"inputs": {"ticker": "300470.SZ"}})
            payload = app.state.controller.last_payload
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 200
    assert payload == {"ticker": "300470.SZ"}


@pytest.mark.asyncio
async def test_web_token_auth(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_dag_config(tmp_path)
    app = create_app(tmp_path, FakeController(tmp_path), run_startup=False)
    monkeypatch.setenv("RIG_WEB_TOKEN", "secret")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            denied = await client.get("/api/pipeline/dag/default/status")
            allowed = await client.get("/api/pipeline/dag/default/status", headers={"Authorization": "Bearer secret"})
        finally:
            await app.state.controller.shutdown()
    assert denied.status_code == 401
    assert allowed.status_code == 200


@pytest.mark.asyncio
async def test_bff_dag_run_uses_grpc_client(tmp_path: Path) -> None:
    class FakeGrpcClient:
        payload: object | None = None

        async def dag_trigger(self, name: str, payload: object | None = None) -> dict[str, object]:
            assert name == "default"
            self.payload = payload
            return {"cycle_id": "grpc-cycle"}

    _write_dag_config(tmp_path)
    grpc = FakeGrpcClient()
    app = create_app(tmp_path, FakeController(tmp_path), run_startup=False, grpc_client=grpc)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            response = await client.post("/api/pipeline/dag/default/run", json={"inputs": {"ticker": "300470.SZ"}})
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 200
    assert response.json() == {"cycle_id": "grpc-cycle"}
    assert grpc.payload == {"ticker": "300470.SZ"}


@pytest.mark.asyncio
async def test_bff_grpc_client_initializes_web_console_certificate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from stockimformation_core.web import app as web_app

    calls: list[tuple[str | None, Path | None, bool, bool]] = []

    class FakeGrpcClient:
        def __init__(
            self,
            address: str | None = None,
            data_dir: Path | None = None,
            allow_insecure: bool = False,
            force_insecure: bool = False,
        ) -> None:
            calls.append((address, data_dir, allow_insecure, force_insecure))

        async def init_client(self, common_name: str) -> dict[str, str]:
            assert common_name == "bff:web-console"
            return {"client_cert_pem": "cert", "client_key_pem": "key", "ca_cert_pem": "ca"}

        async def close(self) -> None:
            return None

    monkeypatch.setenv("RIG_DAEMON_ADDR", "127.0.0.1:9090")
    monkeypatch.setenv("RIG_BFF_DIR", str(tmp_path / "bff"))
    monkeypatch.setattr(web_app, "RigGrpcClient", FakeGrpcClient)

    grpc = await web_app._bff_grpc_client()

    assert isinstance(grpc, FakeGrpcClient)
    assert calls[0] == ("127.0.0.1:9091", tmp_path / "bff", False, True)
    assert calls[-1] == (None, tmp_path / "bff", False, False)
    assert (tmp_path / "bff" / "client.crt").read_text(encoding="utf-8") == "cert"


@pytest.mark.asyncio
async def test_bff_lifespan_initializes_grpc_client_without_nested_event_loop(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from stockimformation_core.web import app as web_app

    _write_dag_config(tmp_path)
    closed = False

    class FakeGrpcClient:
        def __init__(
            self,
            address: str | None = None,
            data_dir: Path | None = None,
            allow_insecure: bool = False,
            force_insecure: bool = False,
        ) -> None:
            self.address = address
            self.data_dir = data_dir
            self.allow_insecure = allow_insecure
            self.force_insecure = force_insecure

        async def init_client(self, common_name: str) -> dict[str, str]:
            assert common_name == "bff:web-console"
            return {"client_cert_pem": "cert", "client_key_pem": "key", "ca_cert_pem": "ca"}

        async def dag_status(self, name: str) -> dict[str, object]:
            return {"dag_name": name, "grpc": True}

        async def close(self) -> None:
            nonlocal closed
            closed = True

    monkeypatch.setenv("RIG_DAEMON_ADDR", "127.0.0.1:9090")
    monkeypatch.setenv("RIG_BFF_DIR", str(tmp_path / "bff"))
    monkeypatch.setattr(web_app, "RigGrpcClient", FakeGrpcClient)
    app = create_app(tmp_path, FakeController(tmp_path), run_startup=False)

    async with app.router.lifespan_context(app):
        assert isinstance(app.state.grpc_client, FakeGrpcClient)
        assert app.state.grpc_client.address is None
        assert app.state.grpc_client.data_dir == tmp_path / "bff"
        assert app.state.grpc_client.allow_insecure is False

    assert closed


@pytest.mark.asyncio
async def test_bff_node_events_streams_from_grpc_client(tmp_path: Path) -> None:
    class FakeGrpcClient:
        async def subscribe_events(self, node_id: str = "", dag_name: str = ""):
            assert node_id == "reader"
            assert dag_name == ""
            yield {"type": "node.stdout", "payload": {"node_id": "reader", "line": "hello"}}

    _write_dag_config(tmp_path)
    app = create_app(tmp_path, FakeController(tmp_path), run_startup=False, grpc_client=FakeGrpcClient())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            async with client.stream("GET", "/api/events/node/reader") as response:
                text = await response.aread()
        finally:
            await app.state.controller.shutdown()
    assert b"event: node.stdout" in text
    assert b'"line": "hello"' in text


@pytest.mark.asyncio
async def test_bff_dag_events_streams_from_grpc_client(tmp_path: Path) -> None:
    class FakeGrpcClient:
        async def subscribe_events(self, node_id: str = "", dag_name: str = ""):
            assert node_id == ""
            assert dag_name == "default"
            yield {"type": "dag.status", "payload": {"dag_name": "default", "status": "started"}}

    _write_dag_config(tmp_path)
    app = create_app(tmp_path, FakeController(tmp_path), run_startup=False, grpc_client=FakeGrpcClient())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            async with client.stream("GET", "/api/events/dag/default") as response:
                text = await response.aread()
        finally:
            await app.state.controller.shutdown()
    assert b"event: dag.status" in text
    assert b'"status": "started"' in text


@pytest.mark.asyncio
async def test_resume_api_reuses_original_cycle(tmp_path: Path) -> None:
    _write_dag_config(tmp_path)
    dag_file = tmp_path / "dags" / "default.yaml"
    dag_file.write_text(
        "name: default\nnodes:\n- id: node-a\n  type: node-a\nedges: []\n",
        encoding="utf-8",
    )
    app = create_app(tmp_path, FakeController(tmp_path), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            async with app.state.controller._factory()() as session:
                await create_pipeline_run(session, "cycle-original", "manual", ["node-a"], dag_name="default")
                await store_node_output_entities(session, "cycle-original", "node-a", "analysis", {"summary": "old"}, "session-1")
                await session.commit()
            response = await client.post("/api/node/node-a/resume", json={"cycle_id": "cycle-original", "prompt": "adjust"})
            async with app.state.controller._factory()() as session:
                run = await get_pipeline_run(session, "cycle-original")
                recent = await recent_pipeline_runs(session, 5, "default")
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 200
    assert response.json()["cycle_id"] == "cycle-original"
    assert run is not None
    assert run.cycle_id == "cycle-original"
    assert all(item.cycle_id != "retry-cycle-original" for item in recent)


@pytest.mark.asyncio
async def test_reflection_run_waits_for_target_idle(tmp_path: Path) -> None:
    _write_dag_config(tmp_path)
    ctrl = PipelineController(tmp_path)
    await ctrl.start(run_startup=False)
    try:
        blocker = asyncio.create_task(asyncio.sleep(0.2))
        default_dag = tmp_path / "dags" / "default.yaml"
        default_dag.write_text("name: default\nnodes:\n- id: node-a\n  type: node-a\nedges: []\n", encoding="utf-8")
        ctrl.active_runs["default"] = DagRunContext("default", "cycle-default", blocker)
        pending = asyncio.create_task(ctrl.start_run("manual", "reflection", {"target": "node-a"}))
        await asyncio.sleep(0.05)
        assert not pending.done()
        await blocker
        ctrl._clear_finished_task(blocker, "default")
        cycle_id = await pending
        assert cycle_id
    finally:
        await ctrl.shutdown()


@pytest.mark.asyncio
async def test_pipeline_run_pi_session_dir_flows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_dag_config(tmp_path)
    extensions_dir = tmp_path / "extensions"
    _write_run_pi_extension(extensions_dir)
    fake_pi = _write_fake_pi(tmp_path)
    capture = tmp_path / "pi-calls.json"
    monkeypatch.setenv("STOCKIMFORMATION_PI_BIN", str(fake_pi))
    monkeypatch.setenv("CAPTURE", str(capture))
    session_dir = tmp_path / "persistent-session"
    session_dir.mkdir()
    (session_dir / "existing.jsonl").write_text("{}", encoding="utf-8")
    node_file = tmp_path / "nodes" / "llm-node.yaml"
    node_file.write_text(
        "name: llm-node\n"
        "type: function\n"
        "handler: run-pi\n"
        "input_type: Any\n"
        "output_type: Any\n",
        encoding="utf-8",
    )
    dag_file = tmp_path / "dags" / "default.yaml"
    dag_file.write_text(
        "name: default\n"
        "nodes:\n"
        "- id: llm-absolute\n"
        "  type: llm-node\n"
        "  config:\n"
        "    model: hf-share/deepseek-v4-flash\n"
        f"    session_dir: {session_dir}\n"
        "edges: []\n",
        encoding="utf-8",
    )
    ctrl = PipelineController(tmp_path, extensions_dirs=[extensions_dir, Path("extensions")])
    await ctrl.start(run_startup=False)
    try:
        await ctrl.run_now("manual", "default")
        configured = tmp_path / "workspace" / "sandbox" / "source" / "configured"
        override = tmp_path / "workspace" / "sandbox" / "source" / "override"
        (configured / "sessions").mkdir(parents=True)
        (override / "sessions").mkdir(parents=True)
        (override / "sessions" / "existing.jsonl").write_text("{}", encoding="utf-8")
        dag_file.write_text(
            "name: default\n"
            "nodes:\n"
            "- id: llm-override\n"
            "  type: llm-node\n"
            "  config:\n"
            "    model: hf-share/deepseek-v4-flash\n"
            "    session_dir: sandbox:source:configured\n"
            "edges: []\n",
            encoding="utf-8",
        )
        await ctrl.run_now("manual", "default", {"resume_session": "sandbox:source:override"})
    finally:
        await ctrl.shutdown()
    calls = json.loads(capture.read_text(encoding="utf-8"))
    first_args = calls[0]["args"]
    second_args = calls[1]["args"]
    assert first_args[first_args.index("--session-dir") + 1] == str(session_dir)
    assert "--continue" in first_args
    assert second_args[second_args.index("--session-dir") + 1] == str(override / "sessions")
    assert "--continue" in second_args


@pytest.mark.asyncio
async def test_scheduler_reflection_waits_and_edits_skill(tmp_path: Path) -> None:
    _write_dag_config(tmp_path)
    extensions_dir = tmp_path / "extensions"
    _write_reflection_extension(extensions_dir)
    skill_path = tmp_path / "skills" / "target-skill" / "skill.md"
    skill_path.parent.mkdir(parents=True)
    skill_path.write_text("initial\n", encoding="utf-8")
    (tmp_path / "nodes" / "reflection-editor.yaml").write_text(
        "name: reflection-editor\n"
        "type: function\n"
        "handler: reflection-editor\n"
        "input_type: Any\n"
        "output_type: Any\n",
        encoding="utf-8",
    )
    (tmp_path / "dags" / "default.yaml").write_text(
        "name: default\nnodes:\n- id: node-a\n  type: node-a\nedges: []\n",
        encoding="utf-8",
    )
    (tmp_path / "dags" / "reflection.yaml").write_text(
        "name: reflection\n"
        "nodes:\n"
        "- id: reflect\n"
        "  type: reflection-editor\n"
        "  config:\n"
        "    parameters:\n"
        f"      skill_path: {skill_path}\n"
        "      target: node-a\n"
        "edges: []\n"
        "ui:\n"
        "  wait_for:\n"
        "    node: node-a\n"
        "    status: idle\n",
        encoding="utf-8",
    )
    ctrl = PipelineController(tmp_path, extensions_dirs=[extensions_dir])
    await ctrl.start(run_startup=False)
    try:
        blocker = asyncio.create_task(asyncio.sleep(0.2))
        ctrl.active_runs["default"] = DagRunContext("default", "cycle-default", blocker)
        job = ctrl.scheduler.get_job("reflection-dag")
        assert job is not None
        pending = asyncio.create_task(job.func(*job.args, **job.kwargs))
        await asyncio.sleep(0.05)
        assert not pending.done()
        assert skill_path.read_text(encoding="utf-8") == "initial\n"
        await blocker
        ctrl._clear_finished_task(blocker, "default")
        await pending
        reflection = ctrl.active_runs.get("reflection")
        assert reflection is not None
        await reflection.task
        ctrl._clear_finished_task(reflection.task, "reflection")
    finally:
        await ctrl.shutdown()
    assert "reflected:node-a:" in skill_path.read_text(encoding="utf-8")


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
    assert index.status_code == 200
    assert results.status_code == 404
    assert pipeline.status_code == 404
    assert config.status_code == 404


@pytest.mark.asyncio
async def test_bff_serves_web_console_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_dag_config(tmp_path)
    web_dir = tmp_path / "web"
    web_dir.mkdir()
    (web_dir / "index.html").write_text("<html>console</html>", encoding="utf-8")
    monkeypatch.setenv("RIG_WEB_CONSOLE_DIR", str(web_dir))
    app = create_app(tmp_path, FakeController(tmp_path), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            response = await client.get("/")
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 200
    assert "console" in response.text


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
    (tmp_path / "dags" / "reflection.yaml").unlink()
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
    _write_entity_schemas(path)
    nodes_dir = path / "nodes"
    nodes_dir.mkdir(exist_ok=True)


def _write_run_pi_extension(path: Path) -> None:
    extension = path / "run-pi"
    extension.mkdir(parents=True)
    extension.joinpath("handler.py").write_text(
        "from _lib.llm import run_pi\n"
        "from stockimformation_core.config.schema import NodeConfig\n"
        "async def run(ctx):\n"
        "    config = NodeConfig(\n"
        "        name=ctx.node_type,\n"
        "        type='function',\n"
        "        handler='run-pi',\n"
        "        input_type='Any',\n"
        "        output_type='Any',\n"
        "        parameters=dict(ctx.params),\n"
        "    )\n"
        "    payload, _session_id = await run_pi(\n"
        "        config,\n"
        "        [],\n"
        "        ctx.input,\n"
        "        ctx.cycle_id,\n"
        "        ctx.node_name,\n"
        "        ctx.entity_store.system,\n"
        "        ctx.entity_store.runtime,\n"
        "    )\n"
        "    return payload\n",
        encoding="utf-8",
    )


def _write_reflection_extension(path: Path) -> None:
    extension = path / "reflection-editor"
    extension.mkdir(parents=True)
    extension.joinpath("handler.py").write_text(
        "from pathlib import Path\n"
        "async def run(ctx):\n"
        "    path = Path(ctx.params['skill_path'])\n"
        "    target = ctx.params['target']\n"
        "    text = path.read_text(encoding='utf-8')\n"
        "    path.write_text(text + f'reflected:{target}:{ctx.cycle_id}\\n', encoding='utf-8')\n"
        "    return {'target': target, 'edited': str(path)}\n",
        encoding="utf-8",
    )


def _write_fake_pi(path: Path) -> Path:
    fake_pi = path / "fake-pi"
    fake_pi.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, pathlib, sys\n"
        "capture = pathlib.Path(os.environ['CAPTURE'])\n"
        "calls = json.loads(capture.read_text(encoding='utf-8')) if capture.exists() else []\n"
        "calls.append({'args': sys.argv[1:], 'cwd': os.getcwd()})\n"
        "capture.write_text(json.dumps(calls), encoding='utf-8')\n"
        "print('{\"ok\": true}')\n",
        encoding="utf-8",
    )
    fake_pi.chmod(0o755)
    return fake_pi
