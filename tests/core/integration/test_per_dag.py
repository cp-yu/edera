from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from edera_core.storage import create_engine, init_db, session_factory, sqlite_url
from edera_core.storage.repository import (
    create_pipeline_run,
    edge_inputs_for_cycle,
    finish_pipeline_run,
    get_pipeline_run,
    node_runs_for_cycle,
    recent_pipeline_runs,
    store_node_output_entities,
    upsert_edge_input,
)
from edera_core.pipeline import DagRunContext, PipelineController, PipelineRunNotFoundError, RetryRunResult, RunAlreadyActiveError
from edera_core.web.app import create_app


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


class FakeGrpcClient:
    last_payload: object | None = None
    closed = False

    async def close(self) -> None:
        self.closed = True

    async def dag_trigger(self, name: str, payload: object | None = None) -> dict[str, object]:
        self.last_payload = payload
        return {"cycle_id": f"cycle-{name}-manual"}

    async def dag_status(self, name: str) -> dict[str, object]:
        return {"dag_name": name, "current_cycle_id": f"cycle-{name}-manual"}

    async def node_resume(self, node_id: str, cycle_id: str | None, prompt: str) -> dict[str, object]:
        return {"cycle_id": cycle_id or "", "node_id": node_id, "prompt": prompt}

    async def subscribe_events(self, node_id: str = "", dag_name: str = ""):
        if node_id:
            yield {"type": "node.stdout", "payload": {"node_id": node_id, "line": "hello"}}
        if dag_name:
            yield {"type": "dag.status", "payload": {"dag_name": dag_name, "status": "started"}}

    async def config_list(self) -> dict[str, object]:
        return {"configs": []}

    async def config_list_entity_types(self) -> dict[str, object]:
        return {"types": {}}


# --- PLACEHOLDER_TESTS ---


def _write_dag_config(path: Path) -> None:
    path.joinpath("system.toml").write_text(
        f'database_url = "sqlite+aiosqlite:///{path / "test.db"}"\n'
        f'schedule_minutes = 30\n'
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
    ctrl = FakeController(tmp_path)
    await ctrl.start(run_startup=False)
    try:
        await ctrl.start_run("manual", "default")
        cycle_id = await ctrl.stop_current("default", force=True)
    finally:
        await ctrl.shutdown()
    assert cycle_id == "cycle-default-manual"


@pytest.mark.asyncio
async def test_retry_api_records_retry_of(tmp_path: Path) -> None:
    _write_dag_config(tmp_path)
    ctrl = FakeController(tmp_path)
    await ctrl.start(run_startup=False)
    try:
        async with ctrl._factory()() as session:
            await create_pipeline_run(session, "cycle-original", "manual", dag_name="default")
            await session.commit()
        result = await ctrl.retry_node("default", "cycle-original", ["node-a"], "cascade")
        async with ctrl._factory()() as session:
            run = await get_pipeline_run(session, "retry-cycle-original")
    finally:
        await ctrl.shutdown()
    assert result.cycle_id == "retry-cycle-original"
    assert result.retry_of == "cycle-original"
    assert result.node_ids == ["node-a"]
    assert result.mode == "cascade"
    assert result.retry_nodes == ["node-a"]
    assert run is not None
    assert run.trigger == "retry"
    assert run.retry_of == "cycle-original"


@pytest.mark.asyncio
async def test_retry_api_defaults_to_latest_finished_run(tmp_path: Path) -> None:
    _write_dag_config(tmp_path)
    ctrl = FakeController(tmp_path)
    await ctrl.start(run_startup=False)
    try:
        async with ctrl._factory()() as session:
            await create_pipeline_run(session, "cycle-old", "manual", dag_name="default")
            await finish_pipeline_run(session, "cycle-old", "failed")
            await create_pipeline_run(session, "cycle-new", "manual", dag_name="default")
            await finish_pipeline_run(session, "cycle-new", "succeeded")
            await session.commit()
        result = await ctrl.retry_node("default", None, ["node-a"], "single")
    finally:
        await ctrl.shutdown()
    assert result.retry_of == "cycle-new"


@pytest.mark.asyncio
async def test_trigger_node_target_uses_controller_node_path(tmp_path: Path) -> None:
    _write_dag_config(tmp_path)
    (tmp_path / "dags" / "default.yaml").write_text(
        "name: default\nnodes:\n- id: node-a\n  type: node-a\nedges: []\n",
        encoding="utf-8",
    )

    class NodeTriggerController(FakeController):
        calls: list[tuple[str, str, str, object | None]]

        def __init__(self, config_dir: Path) -> None:
            super().__init__(config_dir)
            self.calls = []

        async def _run_single_node(self, cycle_id, trigger, dag_name, instance, payload, stop_event):
            self.calls.append((cycle_id, trigger, dag_name, payload))
            await asyncio.sleep(60)

    ctrl = NodeTriggerController(tmp_path)
    await ctrl.start(run_startup=False)
    try:
        async with ctrl._factory()() as session:
            await create_pipeline_run(session, "cycle-original", "manual", dag_name="default")
            await finish_pipeline_run(session, "cycle-original", "succeeded")
            await session.commit()
        cycle_id = await ctrl.run_node_trigger("node-a", {"symbol": "TEST"})
        await asyncio.sleep(0)
    finally:
        await ctrl.shutdown()

    assert ctrl.calls == [(cycle_id, "trigger", "default", {"symbol": "TEST"})]


@pytest.mark.asyncio
async def test_retry_api_missing_cycle_returns_404(tmp_path: Path) -> None:
    _write_dag_config(tmp_path)
    ctrl = FakeController(tmp_path)
    await ctrl.start(run_startup=False)
    try:
        with pytest.raises(PipelineRunNotFoundError):
            await ctrl.retry_node("default", "missing-cycle", ["node-a"], "single")
    finally:
        await ctrl.shutdown()


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
    extensions_dir = tmp_path / "extensions"
    _write_node_b_extension(extensions_dir)
    ctrl = PipelineController(tmp_path, extensions_dirs=[extensions_dir])
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
async def test_retry_allows_missing_optional_historical_upstream(tmp_path: Path) -> None:
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
        "  to: node-b\n"
        "  optional: true\n",
        encoding="utf-8",
    )
    extensions_dir = tmp_path / "extensions"
    _write_node_b_extension(extensions_dir)
    ctrl = PipelineController(tmp_path, extensions_dirs=[extensions_dir])
    await ctrl.start(run_startup=False)
    try:
        async with ctrl._factory()() as session:
            await create_pipeline_run(session, "cycle-original", "manual", ["node-a", "node-b"], dag_name="default")
            await upsert_edge_input(session, "cycle-original", "node-a", "node-b", True, "failed", False, "old failure")
            await finish_pipeline_run(session, "cycle-original", "failed")
            await session.commit()
        result = await ctrl.retry_node("default", "cycle-original", ["node-b"], "single")
        await ctrl.active_runs["default"].task
        async with ctrl._factory()() as session:
            facts = await edge_inputs_for_cycle(session, result.cycle_id)
    finally:
        await ctrl.shutdown()

    assert result.retry_nodes == ["node-b"]
    assert [(fact.from_node_id, fact.to_node_id, fact.status, fact.error_summary) for fact in facts] == [
        ("node-a", "node-b", "failed", "old failure")
    ]


@pytest.mark.asyncio
async def test_retry_blocks_missing_required_historical_upstream(tmp_path: Path) -> None:
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
            await upsert_edge_input(session, "cycle-original", "node-a", "node-b", False, "unknown", False, None)
            await finish_pipeline_run(session, "cycle-original", "failed")
            await session.commit()
        result = await ctrl.retry_node("default", "cycle-original", ["node-b"], "single")
        await ctrl.active_runs["default"].task
        async with ctrl._factory()() as session:
            runs = await node_runs_for_cycle(session, result.cycle_id)
    finally:
        await ctrl.shutdown()

    node_b = next(run for run in runs if run.node_name == "node-b")
    assert node_b.status == "failed"
    assert node_b.failure_kind == "upstream_failed"


@pytest.mark.asyncio
async def test_per_dag_status_api(tmp_path: Path) -> None:
    """C3: GET /api/pipeline/dag/{dag_name}/status returns per-DAG status."""
    _write_dag_config(tmp_path)
    app = create_app(FakeGrpcClient())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/pipeline/dag/default/status")
    assert response.status_code == 200
    data = response.json()
    assert data["dag_name"] == "default"
    assert data["current_cycle_id"] == "cycle-default-manual"


@pytest.mark.asyncio
async def test_per_dag_run_api(tmp_path: Path) -> None:
    """C4: POST /api/pipeline/dag/{dag_name}/run returns 200 + cycle_id; nonexistent DAG returns 404."""
    _write_dag_config(tmp_path)
    app = create_app(FakeGrpcClient())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post("/api/pipeline/dag/default/run")
    assert first.status_code == 200
    assert first.json()["cycle_id"] == "cycle-default-manual"


@pytest.mark.asyncio
async def test_dag_run_api_uses_direct_body_as_initial_payload(tmp_path: Path) -> None:
    _write_dag_config(tmp_path)
    grpc = FakeGrpcClient()
    app = create_app(grpc)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/pipeline/dag/default/run", json={"ticker": "300470.SZ"})
    assert response.status_code == 200
    assert grpc.last_payload == {"ticker": "300470.SZ"}


@pytest.mark.asyncio
async def test_dag_run_api_unwraps_inputs_body(tmp_path: Path) -> None:
    _write_dag_config(tmp_path)
    grpc = FakeGrpcClient()
    app = create_app(grpc)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/pipeline/dag/default/run", json={"inputs": {"ticker": "300470.SZ"}})
    assert response.status_code == 200
    assert grpc.last_payload == {"ticker": "300470.SZ"}


@pytest.mark.asyncio
async def test_web_token_auth(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_dag_config(tmp_path)
    app = create_app(FakeGrpcClient())
    monkeypatch.setenv("EDERA_WEB_TOKEN", "secret")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        denied = await client.get("/api/pipeline/dag/default/status")
        allowed = await client.get("/api/pipeline/dag/default/status", headers={"Authorization": "Bearer secret"})
    assert denied.status_code == 401
    assert allowed.status_code == 200


@pytest.mark.asyncio
async def test_bff_dag_run_uses_grpc_client(tmp_path: Path) -> None:
    class RecordingGrpcClient(FakeGrpcClient):
        payload: object | None = None

        async def dag_trigger(self, name: str, payload: object | None = None) -> dict[str, object]:
            assert name == "default"
            self.payload = payload
            return {"cycle_id": "grpc-cycle"}

    _write_dag_config(tmp_path)
    grpc = RecordingGrpcClient()
    app = create_app(grpc)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/pipeline/dag/default/run", json={"inputs": {"ticker": "300470.SZ"}})
    assert response.status_code == 200
    assert response.json() == {"cycle_id": "grpc-cycle"}
    assert grpc.payload == {"ticker": "300470.SZ"}


@pytest.mark.asyncio
async def test_bff_grpc_client_initializes_web_console_certificate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from edera_core.web import __main__ as web_main

    calls: list[dict[str, object]] = []

    class CertGrpcClient:
        def __init__(
            self,
            address: str | None = None,
            *,
            client_cert_pem: str | None = None,
            client_key_pem: str | None = None,
            ca_cert_pem: str | None = None,
            allow_insecure: bool = False,
            force_insecure: bool = False,
        ) -> None:
            calls.append(
                {
                    "address": address,
                    "client_cert_pem": client_cert_pem,
                    "client_key_pem": client_key_pem,
                    "ca_cert_pem": ca_cert_pem,
                    "allow_insecure": allow_insecure,
                    "force_insecure": force_insecure,
                }
            )

        async def init_client(self, common_name: str) -> dict[str, str]:
            assert common_name == "bff:web-console"
            return {"client_cert_pem": "cert", "client_key_pem": "key", "ca_cert_pem": "ca"}

        async def close(self) -> None:
            return None

    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.setattr(web_main, "GrpcClient", CertGrpcClient)

    grpc = await web_main._bff_grpc_client()

    assert isinstance(grpc, CertGrpcClient)
    assert calls[0] == {
        "address": "127.0.0.1:9091",
        "client_cert_pem": None,
        "client_key_pem": None,
        "ca_cert_pem": None,
        "allow_insecure": False,
        "force_insecure": True,
    }
    assert calls[-1] == {
        "address": "127.0.0.1:9090",
        "client_cert_pem": "cert",
        "client_key_pem": "key",
        "ca_cert_pem": "ca",
        "allow_insecure": False,
        "force_insecure": False,
    }
    assert not (tmp_path / "bff").exists()


@pytest.mark.asyncio
async def test_bff_lifespan_initializes_grpc_client_without_nested_event_loop(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from edera_core.web import __main__ as web_main

    _write_dag_config(tmp_path)
    closed = False

    class CertGrpcClient:
        def __init__(
            self,
            address: str | None = None,
            *,
            client_cert_pem: str | None = None,
            client_key_pem: str | None = None,
            ca_cert_pem: str | None = None,
            allow_insecure: bool = False,
            force_insecure: bool = False,
        ) -> None:
            self.address = address
            self.client_cert_pem = client_cert_pem
            self.client_key_pem = client_key_pem
            self.ca_cert_pem = ca_cert_pem
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

    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.setattr(web_main, "GrpcClient", CertGrpcClient)
    app = create_app(await web_main._bff_grpc_client())

    async with app.router.lifespan_context(app):
        assert isinstance(app.state.grpc_client, CertGrpcClient)
        assert app.state.grpc_client.address == "127.0.0.1:9090"
        assert app.state.grpc_client.client_cert_pem == "cert"
        assert app.state.grpc_client.allow_insecure is False

    assert closed


@pytest.mark.asyncio
async def test_bff_node_events_streams_from_grpc_client(tmp_path: Path) -> None:
    class EventGrpcClient(FakeGrpcClient):
        async def subscribe_events(self, node_id: str = "", dag_name: str = ""):
            assert node_id == "reader"
            assert dag_name == ""
            yield {"type": "node.stdout", "payload": {"node_id": "reader", "line": "hello"}}

    _write_dag_config(tmp_path)
    app = create_app(EventGrpcClient())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        async with client.stream("GET", "/api/events/node/reader") as response:
            text = await response.aread()
    assert b"event: node.stdout" in text
    assert b'"line": "hello"' in text


@pytest.mark.asyncio
async def test_bff_dag_events_streams_from_grpc_client(tmp_path: Path) -> None:
    class EventGrpcClient(FakeGrpcClient):
        async def subscribe_events(self, node_id: str = "", dag_name: str = ""):
            assert node_id == ""
            assert dag_name == "default"
            yield {"type": "dag.status", "payload": {"dag_name": "default", "status": "started"}}

    _write_dag_config(tmp_path)
    app = create_app(EventGrpcClient())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        async with client.stream("GET", "/api/events/dag/default") as response:
            text = await response.aread()
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
    ctrl = FakeController(tmp_path)
    await ctrl.start(run_startup=False)
    try:
        async with ctrl._factory()() as session:
            await create_pipeline_run(session, "cycle-original", "manual", ["node-a"], dag_name="default")
            await store_node_output_entities(session, "cycle-original", "node-a", "analysis", {"summary": "old"}, "session-1")
            await session.commit()
        cycle_id = await ctrl.resume_node("default", "cycle-original", "node-a", {"prompt": "adjust"})
        async with ctrl._factory()() as session:
            run = await get_pipeline_run(session, "cycle-original")
            recent = await recent_pipeline_runs(session, 5, "default")
    finally:
        await ctrl.shutdown()
    assert cycle_id == "cycle-original"
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
    monkeypatch.setenv("EDERA_PI_BIN", str(fake_pi))
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
async def test_ssr_routes_removed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C5: SSR routes no longer exist."""
    _write_dag_config(tmp_path)
    web_dir = tmp_path / "web"
    web_dir.mkdir()
    (web_dir / "index.html").write_text("<html>console</html>", encoding="utf-8")
    monkeypatch.setenv("EDERA_WEB_CONSOLE_DIR", str(web_dir))
    app = create_app(FakeGrpcClient())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        index = await client.get("/")
        results = await client.get("/results")
        pipeline = await client.get("/pipeline")
        config = await client.get("/config")
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
    monkeypatch.setenv("EDERA_WEB_CONSOLE_DIR", str(web_dir))
    app = create_app(FakeGrpcClient())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")
    assert response.status_code == 200
    assert "console" in response.text


@pytest.mark.asyncio
async def test_cors_middleware(tmp_path: Path) -> None:
    """C6: CORS middleware allows localhost:5173."""
    _write_dag_config(tmp_path)
    app = create_app(FakeGrpcClient())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.options(
            "/api/pipeline/status",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


@pytest.mark.asyncio
async def test_bff_legacy_local_config_route_fails_closed(tmp_path: Path) -> None:
    _write_dag_config(tmp_path)
    app = create_app(FakeGrpcClient())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/config")
    assert response.status_code == 200
    assert response.json() == {"configs": []}


@pytest.mark.asyncio
async def test_bff_entity_types_route_uses_grpc(tmp_path: Path) -> None:
    class EntityTypesGrpcClient(FakeGrpcClient):
        async def config_list_entity_types(self) -> dict[str, object]:
            return {
                "types": {
                    "stock": {
                        "display_name": "Stock",
                        "business_id_field": "code",
                        "display_template": "{code}",
                        "storage_tier": "filesystem",
                        "system_protected": False,
                        "schema": {},
                        "field_permissions": {},
                        "validate": True,
                    }
                }
            }

    _write_dag_config(tmp_path)
    app = create_app(EntityTypesGrpcClient())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/config/entity-types")
    assert response.status_code == 200
    assert response.json()["types"]["stock"]["display_name"] == "Stock"


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
        "from edera_core.config.schema import NodeConfig\n"
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


def _write_node_b_extension(path: Path) -> None:
    extension = path / "node-b"
    extension.mkdir(parents=True)
    extension.joinpath("handler.py").write_text("async def run(ctx):\n    return {'payload': ctx.input.payload}\n", encoding="utf-8")


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
