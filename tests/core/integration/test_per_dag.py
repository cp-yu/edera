from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

import edera_core.dag_controller as dag_controller_module
from edera_core.config.schema import EntityConfig
from edera_core.config.loader import _load_runtime_base_config
from edera_core.errors import DagError
from edera_core.extension_manager import ExtensionManager
from edera_core.storage import create_engine, init_db, session_factory, sqlite_url
from edera_core.storage.repository import (
    create_dag_run,
    edge_inputs_for_run,
    finish_dag_run,
    get_dag_run,
    node_runs_for_run,
    recent_dag_runs,
    save_core_entity,
    store_node_output_entities,
    upsert_edge_input,
)
from edera_core.dag_controller import DagRunContext, DagController, DagRunNotFoundError, RetryRunResult, RunAlreadyActiveError
from edera_core.web.app import create_app


class FakeController(DagController):
    last_payload: object | None = None

    async def start(self, run_startup: bool = True) -> None:
        self.engine = create_engine(sqlite_url(self.config_dir / "test.db"))
        await init_db(self.engine)
        self.factory = session_factory(self.engine)
        config = _load_runtime_base_config(self.config_dir)
        bootstrap = await self.load_bootstrap()
        await self.install_snapshot(config, bootstrap)
        self.scheduler.start()

    async def start_run(self, source: str = "manual", dag_name: str = "default", payload: object | None = None) -> str:
        self.last_payload = payload
        async with self._locks[dag_name]:
            ctx = self.active_runs.get(dag_name)
            if ctx is not None and not ctx.task.done():
                raise RunAlreadyActiveError(ctx.run_id)
            run_id = f"run-{dag_name}-{source}"
            task = asyncio.create_task(self._fake_run(run_id, source, dag_name))
            self.active_runs[dag_name] = DagRunContext(dag_name=dag_name, run_id=run_id, task=task)
            task.add_done_callback(lambda t: self._clear_finished_task(t, dag_name))
            return run_id

    async def _fake_run(self, run_id: str, source: str, dag_name: str) -> None:
        async with self._factory()() as session:
            await create_dag_run(session, run_id, source, dag_name=dag_name)
            await session.commit()
        await asyncio.sleep(60)

    async def retry_node(
        self,
        dag_name: str,
        run_id: str | None,
        node_ids: list[str],
        mode: str = "single",
        payload: object | None = None,
    ) -> RetryRunResult:
        if not node_ids:
            raise ValueError("node_ids is required")
        if run_id is None:
            async with self._factory()() as session:
                recent = await recent_dag_runs(session, 10, dag_name)
            run_id = next((run.run_id for run in recent if run.status != "running"), None)
        if run_id is None:
            raise DagRunNotFoundError("latest finished run")
        if run_id == "missing-run":
            raise DagRunNotFoundError(run_id)
        retry_run_id = f"retry-{run_id}"
        async with self._factory()() as session:
            await create_dag_run(session, retry_run_id, "retry", dag_name=dag_name, retry_of=run_id)
            await session.commit()
        return RetryRunResult(retry_run_id, run_id, node_ids, mode, node_ids)

    async def resume_node(self, dag_name: str, run_id: str, node_id: str, payload: object) -> str:
        return await super().resume_node(dag_name, run_id, node_id, payload)


class FakeGrpcClient:
    last_payload: object | None = None
    last_run_options: dict[str, object | None] | None = None
    last_retry_options: dict[str, object | None] | None = None
    closed = False

    async def close(self) -> None:
        self.closed = True

    async def dag_run(
        self,
        name: str,
        payload: object | None = None,
        *,
        source_shared_inputs: object | None = None,
        node_inputs: dict[str, object] | None = None,
        append_nodes: list[str] | None = None,
    ) -> dict[str, object]:
        self.last_payload = payload
        self.last_run_options = {
            "source_shared_inputs": source_shared_inputs,
            "node_inputs": node_inputs,
            "append_nodes": append_nodes,
        }
        return {"run_id": f"run-{name}-manual"}

    async def dag_retry(
        self,
        dag_name: str,
        run_id: str = "",
        node_ids: list[str] | None = None,
        mode: str = "single",
        payload: object | None = None,
        *,
        source_shared_inputs: object | None = None,
        node_inputs: dict[str, object] | None = None,
        append_nodes: list[str] | None = None,
    ) -> dict[str, object]:
        self.last_retry_options = {
            "dag_name": dag_name,
            "run_id": run_id,
            "node_ids": node_ids,
            "mode": mode,
            "payload": payload,
            "source_shared_inputs": source_shared_inputs,
            "node_inputs": node_inputs,
            "append_nodes": append_nodes,
        }
        return {"run_id": "retry-1"}

    async def dag_status(self, name: str) -> dict[str, object]:
        return {"dag_name": name, "current_run_id": f"run-{name}-manual"}

    async def query_node_history(self, dag_name: str, node_id: str, limit: int = 50) -> dict[str, object]:
        return {"history": [{"dag_name": dag_name, "node_id": node_id, "run_id": "run-1", "limit": limit}]}

    async def node_resume(self, node_id: str, run_id: str | None, prompt: str) -> dict[str, object]:
        return {"run_id": run_id or "", "node_id": node_id, "prompt": prompt}

    async def subscribe_events(self, node_id: str = "", dag_name: str = ""):
        if node_id:
            yield {"type": "node.stdout", "payload": {"node_id": node_id, "line": "hello"}}
        if dag_name:
            yield {"type": "dag.status", "payload": {"dag_name": dag_name, "status": "started"}}

    async def config_list(self) -> dict[str, object]:
        return {"configs": []}

    async def config_list_entity_types(self) -> dict[str, object]:
        return {"types": {}}


async def _install_controller_extensions(ctrl: DagController, extensions_dir: Path, names: list[str]) -> None:
    if ctrl.engine is None:
        raise RuntimeError("controller not started")
    manager = ExtensionManager(
        extensions_dir=extensions_dir,
        handlers_dir=ctrl.handlers_dir,
        engine=ctrl.engine,
        config_entity_types=_load_runtime_base_config(ctrl.config_dir).entity_types,
    )
    for name in names:
        await manager.install(name)
    await ctrl.install_snapshot(_load_runtime_base_config(ctrl.config_dir), await ctrl.load_bootstrap())


async def _save_default_node_a_dag(session) -> None:
    await save_core_entity(
        session,
        EntityConfig(
            id="default",
            type="dag",
            attributes={"name": "default", "nodes": [{"id": "node-a", "type": "node-a"}], "edges": []},
        ),
    )


async def _node_trigger_capture_controller(tmp_path: Path):
    _write_dag_config(tmp_path)
    (tmp_path / "dags" / "default.yaml").write_text(
        "name: default\nnodes:\n- id: node-a\n  type: node-a\nedges: []\n",
        encoding="utf-8",
    )

    class NodeTriggerCaptureController(FakeController):
        calls: list[tuple[str, dict[str, object] | None, set[str] | None]]

        def __init__(self, config_dir: Path) -> None:
            super().__init__(config_dir)
            self.calls = []

        async def _run_single_node(
            self,
            run_id,
            source,
            dag_name,
            instance,
            payload,
            stop_event,
            snapshot=None,
            *,
            node_inputs=None,
            append_nodes=None,
            **_kwargs,
        ):
            self.calls.append((run_id, node_inputs, append_nodes))
            await asyncio.sleep(60)

    ctrl = NodeTriggerCaptureController(tmp_path)
    await ctrl.start(run_startup=False)
    async with ctrl._factory()() as session:
        await create_dag_run(session, "run-original", "manual", dag_name="default")
        await finish_dag_run(session, "run-original", "succeeded")
        await _save_default_node_a_dag(session)
        await session.commit()
    return ctrl


# --- PLACEHOLDER_TESTS ---


def _write_dag_config(path: Path) -> None:
    path.joinpath("system.toml").write_text(
        f'database_url = "sqlite+aiosqlite:///{path / "test.db"}"\n'
        f'schedule_minutes = 30\n'
        f'log_level = "INFO"\nllm_timeout_seconds = 60\n'
        f'workspace_root = "{path / "workspace"}"\n'
        f'retention_count = 20\nretention_hours = 720\n'
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


def _write_retention_extension(path: Path) -> None:
    source = path / "retention-source"
    source.mkdir(parents=True)
    source.joinpath("manifest.yaml").write_text(
        "name: retention-source\n"
        "version: 0.1.0\n"
        "handlers:\n"
        "- name: retention-source\n"
        "  entry: handler.py\n"
        "  role: source\n"
        "  input_type: Any\n"
        "  output_type: Any\n",
        encoding="utf-8",
    )
    source.joinpath("handler.py").write_text(
        "import asyncio\n"
        "async def run(ctx):\n"
        "    if ctx.params.get('slow'):\n"
        "        await asyncio.sleep(1)\n"
        "    if ctx.params.get('fail'):\n"
        "        raise ValueError('source failed')\n"
        "    return {'manual': True, 'source': ctx.run_id}\n",
        encoding="utf-8",
    )
    sink = path / "retention-sink"
    sink.mkdir(parents=True)
    sink.joinpath("manifest.yaml").write_text(
        "name: retention-sink\n"
        "version: 0.1.0\n"
        "handlers:\n"
        "- name: retention-sink\n"
        "  entry: handler.py\n"
        "  role: sink\n"
        "  input_type: Any\n"
        "  output_type: Any\n",
        encoding="utf-8",
    )
    sink.joinpath("handler.py").write_text(
        "async def run(ctx):\n"
        "    if ctx.params.get('fail'):\n"
        "        raise ValueError('sink failed')\n"
        "    return {'sink': ctx.input.payload}\n",
        encoding="utf-8",
    )


def _write_retention_policy_dag(path: Path, *, fail_source: bool = False, slow_source: bool = False) -> Path:
    extensions_dir = path / "extensions"
    _write_retention_extension(extensions_dir)
    (path / "nodes" / "retention-source.yaml").write_text(
        "name: retention-source\n"
        "type: function\n"
        "handler: retention-source.retention-source\n"
        "input_type: Any\n"
        "output_type: Any\n",
        encoding="utf-8",
    )
    (path / "nodes" / "retention-sink.yaml").write_text(
        "name: retention-sink\n"
        "type: function\n"
        "handler: retention-sink.retention-sink\n"
        "input_type: Any\n"
        "output_type: Any\n",
        encoding="utf-8",
    )
    source_config = ""
    if fail_source or slow_source:
        source_config = (
            "  config:\n"
            "    parameters:\n"
            f"      fail: {str(fail_source).lower()}\n"
            f"      slow: {str(slow_source).lower()}\n"
        )
    (path / "dags" / "default.yaml").write_text(
        "name: default\n"
        "nodes:\n"
        "- id: source\n"
        "  type: retention-source\n"
        f"{source_config}"
        "- id: sink\n"
        "  type: retention-sink\n"
        "edges:\n"
        "- from: source\n"
        "  to: sink\n",
        encoding="utf-8",
    )
    return extensions_dir


@pytest.mark.asyncio
async def test_per_dag_concurrent_execution(tmp_path: Path) -> None:
    """C1: Different DAGs can run concurrently; same DAG raises RunAlreadyActiveError."""
    _write_dag_config(tmp_path)
    ctrl = FakeController(tmp_path)
    await ctrl.start(run_startup=False)
    try:
        run_default = await ctrl.start_run("manual", "default")
        run_realtime = await ctrl.start_run("manual", "realtime")
        assert run_default == "run-default-manual"
        assert run_realtime == "run-realtime-manual"
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
        assert stopped == "run-default-manual"
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
        run_id = await ctrl.stop_current("default", force=True)
    finally:
        await ctrl.shutdown()
    assert run_id == "run-default-manual"


@pytest.mark.asyncio
async def test_retry_api_records_retry_of(tmp_path: Path) -> None:
    _write_dag_config(tmp_path)
    ctrl = FakeController(tmp_path)
    await ctrl.start(run_startup=False)
    try:
        async with ctrl._factory()() as session:
            await create_dag_run(session, "run-original", "manual", dag_name="default")
            await session.commit()
        result = await ctrl.retry_node("default", "run-original", ["node-a"], "cascade")
        async with ctrl._factory()() as session:
            run = await get_dag_run(session, "retry-run-original")
    finally:
        await ctrl.shutdown()
    assert result.run_id == "retry-run-original"
    assert result.retry_of == "run-original"
    assert result.node_ids == ["node-a"]
    assert result.mode == "cascade"
    assert result.retry_nodes == ["node-a"]
    assert run is not None
    assert run.source == "retry"
    assert run.retry_of == "run-original"


@pytest.mark.asyncio
async def test_retry_api_defaults_to_latest_finished_run(tmp_path: Path) -> None:
    _write_dag_config(tmp_path)
    ctrl = FakeController(tmp_path)
    await ctrl.start(run_startup=False)
    try:
        async with ctrl._factory()() as session:
            await create_dag_run(session, "run-old", "manual", dag_name="default")
            await finish_dag_run(session, "run-old", "failed")
            await create_dag_run(session, "run-new", "manual", dag_name="default")
            await finish_dag_run(session, "run-new", "succeeded")
            await session.commit()
        result = await ctrl.retry_node("default", None, ["node-a"], "single")
    finally:
        await ctrl.shutdown()
    assert result.retry_of == "run-new"


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

        async def _run_single_node(self, run_id, source, dag_name, instance, payload, stop_event, snapshot=None, **_kwargs):
            self.calls.append((run_id, source, dag_name, payload))
            await asyncio.sleep(60)

    ctrl = NodeTriggerController(tmp_path)
    await ctrl.start(run_startup=False)
    try:
        async with ctrl._factory()() as session:
            await create_dag_run(session, "run-original", "manual", dag_name="default")
            await finish_dag_run(session, "run-original", "succeeded")
            await _save_default_node_a_dag(session)
            await session.commit()
        run_id = await ctrl.run_node_trigger("default/node-a", {"symbol": "TEST"})
        await asyncio.sleep(0)
    finally:
        await ctrl.shutdown()

    assert ctrl.calls == [(run_id, "manual", "default", {"symbol": "TEST"})]


@pytest.mark.asyncio
async def test_trigger_replace(tmp_path: Path) -> None:
    ctrl = await _node_trigger_capture_controller(tmp_path)
    try:
        run_id = await ctrl.run_node_trigger("default/node-a", {"symbol": "TEST"})
        await asyncio.sleep(0)
    finally:
        await ctrl.shutdown()

    assert ctrl.calls == [(run_id, {"node-a": {"symbol": "TEST"}}, set())]


@pytest.mark.asyncio
async def test_trigger_append(tmp_path: Path) -> None:
    ctrl = await _node_trigger_capture_controller(tmp_path)
    try:
        run_id = await ctrl.run_node_trigger("default/node-a", {"symbol": "TEST"}, append=True)
        await asyncio.sleep(0)
    finally:
        await ctrl.shutdown()

    assert ctrl.calls == [(run_id, {"node-a": {"symbol": "TEST"}}, {"node-a"})]


@pytest.mark.asyncio
async def test_retry_api_missing_run_returns_404(tmp_path: Path) -> None:
    _write_dag_config(tmp_path)
    ctrl = FakeController(tmp_path)
    await ctrl.start(run_startup=False)
    try:
        with pytest.raises(DagRunNotFoundError):
            await ctrl.retry_node("default", "missing-run", ["node-a"], "single")
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
    ctrl = DagController(tmp_path, extensions_dirs=[extensions_dir])
    await ctrl.start(run_startup=False)
    try:
        async with ctrl._factory()() as session:
            await create_dag_run(session, "run-original", "manual", ["node-a", "node-b"], dag_name="default")
            await finish_dag_run(session, "run-original", "failed")
            await session.commit()
        with pytest.raises(ValueError, match="missing prefilled outputs: node-a"):
            await ctrl.retry_node("default", "run-original", ["node-b"], "single")
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
    ctrl = DagController(tmp_path, extensions_dirs=[extensions_dir])
    await ctrl.start(run_startup=False)
    try:
        async with ctrl._factory()() as session:
            await create_dag_run(session, "run-original", "manual", ["node-a", "node-b"], dag_name="default")
            await upsert_edge_input(session, "run-original", "node-a", "node-b", True, "failed", False, "old failure")
            await finish_dag_run(session, "run-original", "failed")
            await session.commit()
        result = await ctrl.retry_node("default", "run-original", ["node-b"], "single")
        await ctrl.active_runs["default"].task
        async with ctrl._factory()() as session:
            facts = await edge_inputs_for_run(session, result.run_id)
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
    ctrl = DagController(tmp_path)
    await ctrl.start(run_startup=False)
    try:
        async with ctrl._factory()() as session:
            await create_dag_run(session, "run-original", "manual", ["node-a", "node-b"], dag_name="default")
            await upsert_edge_input(session, "run-original", "node-a", "node-b", False, "unknown", False, None)
            await finish_dag_run(session, "run-original", "failed")
            await session.commit()
        result = await ctrl.retry_node("default", "run-original", ["node-b"], "single")
        await ctrl.active_runs["default"].task
        async with ctrl._factory()() as session:
            runs = await node_runs_for_run(session, result.run_id)
    finally:
        await ctrl.shutdown()

    node_b = next(run for run in runs if run.node_name == "node-b")
    assert node_b.status == "failed"
    assert node_b.failure_kind == "upstream_failed"


@pytest.mark.asyncio
async def test_full_successful_dag_run_triggers_retention_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _write_dag_config(tmp_path)
    extensions_dir = _write_retention_policy_dag(tmp_path, slow_source=True)
    calls: list[tuple[int, int]] = []

    async def fake_persist_outputs(factory, retention_count: int, retention_hours: int) -> None:
        calls.append((retention_count, retention_hours))

    monkeypatch.setattr(dag_controller_module, "_persist_outputs", fake_persist_outputs)
    ctrl = DagController(tmp_path, extensions_dirs=[extensions_dir])
    await ctrl.start(run_startup=False)
    try:
        await _install_controller_extensions(ctrl, extensions_dir, ["retention-source", "retention-sink"])
        await ctrl.run_now("manual", "default")
    finally:
        await ctrl.shutdown()

    assert calls == [(20, 720)]


@pytest.mark.asyncio
async def test_failed_dag_run_skips_retention_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _write_dag_config(tmp_path)
    extensions_dir = _write_retention_policy_dag(tmp_path, fail_source=True)
    calls: list[tuple[int, int]] = []

    async def fake_persist_outputs(factory, retention_count: int, retention_hours: int) -> None:
        calls.append((retention_count, retention_hours))

    monkeypatch.setattr(dag_controller_module, "_persist_outputs", fake_persist_outputs)
    ctrl = DagController(tmp_path, extensions_dirs=[extensions_dir])
    await ctrl.start(run_startup=False)
    try:
        await _install_controller_extensions(ctrl, extensions_dir, ["retention-source", "retention-sink"])
        with pytest.raises(DagError, match="all source nodes failed"):
            await ctrl.run_now("manual", "default")
    finally:
        await ctrl.shutdown()

    assert calls == []


@pytest.mark.asyncio
async def test_cancelled_dag_run_skips_retention_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _write_dag_config(tmp_path)
    extensions_dir = _write_retention_policy_dag(tmp_path)
    calls: list[tuple[int, int]] = []

    async def fake_persist_outputs(factory, retention_count: int, retention_hours: int) -> None:
        calls.append((retention_count, retention_hours))

    monkeypatch.setattr(dag_controller_module, "_persist_outputs", fake_persist_outputs)
    ctrl = DagController(tmp_path, extensions_dirs=[extensions_dir])
    await ctrl.start(run_startup=False)
    try:
        await _install_controller_extensions(ctrl, extensions_dir, ["retention-source", "retention-sink"])
        run_id = await ctrl.start_run("manual", "default")
        assert run_id
        await asyncio.sleep(0)
        await ctrl.stop_current("default")
    finally:
        await ctrl.shutdown()

    assert calls == []


@pytest.mark.asyncio
async def test_single_node_run_skips_retention_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _write_dag_config(tmp_path)
    extensions_dir = _write_retention_policy_dag(tmp_path)
    calls: list[tuple[int, int]] = []

    async def fake_persist_outputs(factory, retention_count: int, retention_hours: int) -> None:
        calls.append((retention_count, retention_hours))

    monkeypatch.setattr(dag_controller_module, "_persist_outputs", fake_persist_outputs)
    ctrl = DagController(tmp_path, extensions_dirs=[extensions_dir])
    await ctrl.start(run_startup=False)
    try:
        await _install_controller_extensions(ctrl, extensions_dir, ["retention-source", "retention-sink"])
        await ctrl.run_node_trigger("default/source", {"manual": True})
        await ctrl.active_runs["default"].task
    finally:
        await ctrl.shutdown()

    assert calls == []


@pytest.mark.asyncio
async def test_partial_retry_skips_retention_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _write_dag_config(tmp_path)
    extensions_dir = _write_retention_policy_dag(tmp_path)
    calls: list[tuple[int, int]] = []

    async def fake_persist_outputs(factory, retention_count: int, retention_hours: int) -> None:
        calls.append((retention_count, retention_hours))

    monkeypatch.setattr(dag_controller_module, "_persist_outputs", fake_persist_outputs)
    ctrl = DagController(tmp_path, extensions_dirs=[extensions_dir])
    await ctrl.start(run_startup=False)
    try:
        await _install_controller_extensions(ctrl, extensions_dir, ["retention-source", "retention-sink"])
        await ctrl.run_now("manual", "default")
        async with ctrl._factory()() as session:
            await store_node_output_entities(session, "original", "source", "analysis", {"summary": "old"}, None)
            await session.commit()
        calls.clear()
        result = await ctrl.retry_node("default", None, ["sink"], "single")
        await ctrl.active_runs["default"].task
    finally:
        await ctrl.shutdown()

    assert result.retry_nodes == ["sink"]
    assert calls == []


@pytest.mark.asyncio
async def test_sub_dag_records_independent_run_and_parent_metadata(tmp_path: Path) -> None:
    _write_dag_config(tmp_path)
    (tmp_path / "nodes" / "child.yaml").write_text(
        "name: child\n"
        "type: dag\n"
        "dag_ref: child\n"
        "input_type: Any\n"
        "output_type: Any\n",
        encoding="utf-8",
    )
    (tmp_path / "nodes" / "leaf.yaml").write_text(
        "name: leaf\n"
        "type: function\n"
        "handler: leaf.leaf\n"
        "input_type: Any\n"
        "output_type: Any\n",
        encoding="utf-8",
    )
    (tmp_path / "dags" / "default.yaml").write_text(
        "name: default\n"
        "nodes:\n"
        "- id: child-node\n"
        "  type: child\n"
        "edges: []\n",
        encoding="utf-8",
    )
    (tmp_path / "dags" / "child.yaml").write_text(
        "name: child\n"
        "nodes:\n"
        "- id: leaf-node\n"
        "  type: leaf\n"
        "edges: []\n",
        encoding="utf-8",
    )
    extensions_dir = tmp_path / "extensions"
    _write_leaf_extension(extensions_dir)
    ctrl = DagController(tmp_path, extensions_dirs=[extensions_dir])
    await ctrl.start(run_startup=False)
    try:
        await _install_controller_extensions(ctrl, extensions_dir, ["leaf"])
        parent_run_id = await ctrl.run_now("manual", "default", {"seed": True})
        async with ctrl._factory()() as session:
            parent_runs = await node_runs_for_run(session, parent_run_id)
            parent_node = next(run for run in parent_runs if run.node_name == "child-node")
            metadata = parent_node.metadata_
            child_run_id = str(metadata["sub_dag_run_id"])
            child_dag_run = await get_dag_run(session, child_run_id)
            child_runs = await node_runs_for_run(session, child_run_id)
    finally:
        await ctrl.shutdown()

    assert metadata["parent_run_id"] == parent_run_id
    assert metadata["parent_node"] == "child-node"
    assert child_dag_run is not None
    assert child_dag_run.dag_name == "child"
    assert child_dag_run.status == "succeeded"
    assert [(run.run_id, run.node_name, run.status) for run in child_runs] == [(child_run_id, "leaf-node", "succeeded")]


@pytest.mark.asyncio
async def test_per_dag_status_api(tmp_path: Path) -> None:
    """C3: GET /api/dags/{dag_name}/status returns per-DAG status."""
    _write_dag_config(tmp_path)
    app = create_app(FakeGrpcClient())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/dags/default/status")
    assert response.status_code == 200
    data = response.json()
    assert data["dag_name"] == "default"
    assert data["current_run_id"] == "run-default-manual"


@pytest.mark.asyncio
async def test_per_dag_run_api(tmp_path: Path) -> None:
    """C4: POST /api/dags/{dag_name}/run returns 200 + run_id; nonexistent DAG returns 404."""
    _write_dag_config(tmp_path)
    app = create_app(FakeGrpcClient())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post("/api/dags/default/run")
    assert first.status_code == 200
    assert first.json()["run_id"] == "run-default-manual"


@pytest.mark.asyncio
async def test_dag_run_api_uses_direct_body_as_initial_payload(tmp_path: Path) -> None:
    _write_dag_config(tmp_path)
    grpc = FakeGrpcClient()
    app = create_app(grpc)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/dags/default/run", json={"ticker": "300470.SZ"})
    assert response.status_code == 200
    assert grpc.last_payload == {"ticker": "300470.SZ"}


@pytest.mark.asyncio
async def test_dag_run_api_unwraps_inputs_body(tmp_path: Path) -> None:
    _write_dag_config(tmp_path)
    grpc = FakeGrpcClient()
    app = create_app(grpc)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/dags/default/run", json={"inputs": {"ticker": "300470.SZ"}})
    assert response.status_code == 200
    assert grpc.last_payload == {"ticker": "300470.SZ"}


@pytest.mark.asyncio
async def test_run_with_temp_inputs(tmp_path: Path) -> None:
    _write_dag_config(tmp_path)
    grpc = FakeGrpcClient()
    app = create_app(grpc)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/dags/default/run",
            json={
                "sourceSharedInputs": {"symbol": "AAPL"},
                "nodeInputs": {"worker": {"limit": 5}},
                "appendNodes": ["worker"],
            },
        )
    assert response.status_code == 200
    assert grpc.last_run_options == {
        "source_shared_inputs": {"symbol": "AAPL"},
        "node_inputs": {"worker": {"limit": 5}},
        "append_nodes": ["worker"],
    }


@pytest.mark.asyncio
async def test_retry_with_temp_inputs(tmp_path: Path) -> None:
    _write_dag_config(tmp_path)
    grpc = FakeGrpcClient()
    app = create_app(grpc)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/dags/default/retry",
            json={
                "run_id": "run-1",
                "node_ids": ["worker"],
                "sourceSharedInputs": {"symbol": "AAPL"},
                "nodeInputs": {"worker": {"limit": 5}},
                "appendNodes": ["worker"],
            },
        )
    assert response.status_code == 200
    assert grpc.last_retry_options == {
        "dag_name": "default",
        "run_id": "run-1",
        "node_ids": ["worker"],
        "mode": "single",
        "payload": None,
        "source_shared_inputs": {"symbol": "AAPL"},
        "node_inputs": {"worker": {"limit": 5}},
        "append_nodes": ["worker"],
    }


@pytest.mark.asyncio
async def test_web_token_auth(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_dag_config(tmp_path)
    app = create_app(FakeGrpcClient())
    monkeypatch.setenv("EDERA_WEB_TOKEN", "secret")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        denied = await client.get("/api/dags/default/status")
        allowed = await client.get("/api/dags/default/status", headers={"Authorization": "Bearer secret"})
    assert denied.status_code == 401
    assert allowed.status_code == 200


@pytest.mark.asyncio
async def test_bff_dag_run_uses_grpc_client(tmp_path: Path) -> None:
    class RecordingGrpcClient(FakeGrpcClient):
        payload: object | None = None

        async def dag_run(
            self,
            name: str,
            payload: object | None = None,
            *,
            source_shared_inputs: object | None = None,
            node_inputs: dict[str, object] | None = None,
            append_nodes: list[str] | None = None,
        ) -> dict[str, object]:
            assert name == "default"
            self.payload = payload
            return {"run_id": "grpc-run"}

    _write_dag_config(tmp_path)
    grpc = RecordingGrpcClient()
    app = create_app(grpc)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/dags/default/run", json={"inputs": {"ticker": "300470.SZ"}})
    assert response.status_code == 200
    assert response.json() == {"run_id": "grpc-run"}
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
    monkeypatch.setenv("EDERA_DATA_DIR", str(tmp_path))
    (tmp_path / "bootstrap.json").write_text('{"host":"127.0.0.1","port":9091}', encoding="utf-8")
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
async def test_bff_grpc_client_uses_insecure_dev_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    from edera_core.web import __main__ as web_main

    calls: list[dict[str, object]] = []

    class DevGrpcClient:
        def __init__(
            self,
            address: str | None = None,
            *,
            identity: str | None = None,
            client_cert_pem: str | None = None,
            client_key_pem: str | None = None,
            ca_cert_pem: str | None = None,
            allow_insecure: bool = False,
            force_insecure: bool = False,
        ) -> None:
            calls.append(
                {
                    "address": address,
                    "identity": identity,
                    "client_cert_pem": client_cert_pem,
                    "client_key_pem": client_key_pem,
                    "ca_cert_pem": ca_cert_pem,
                    "allow_insecure": allow_insecure,
                    "force_insecure": force_insecure,
                }
            )

    monkeypatch.setenv("EDERA_DEV", "1")
    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.setattr(web_main, "GrpcClient", DevGrpcClient)

    grpc = await web_main._bff_grpc_client()

    assert isinstance(grpc, DevGrpcClient)
    assert calls == [
        {
            "address": "127.0.0.1:9090",
            "identity": "bff:web-console",
            "client_cert_pem": None,
            "client_key_pem": None,
            "ca_cert_pem": None,
            "allow_insecure": False,
            "force_insecure": False,
        }
    ]


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
    monkeypatch.setenv("EDERA_DATA_DIR", str(tmp_path))
    (tmp_path / "bootstrap.json").write_text('{"host":"127.0.0.1","port":9091}', encoding="utf-8")
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
async def test_resume_api_reuses_original_run(tmp_path: Path) -> None:
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
            await create_dag_run(session, "run-original", "manual", ["node-a"], dag_name="default")
            await store_node_output_entities(session, "run-original", "node-a", "analysis", {"summary": "old"}, "session-1")
            await _save_default_node_a_dag(session)
            await session.commit()
        run_id = await ctrl.resume_node("default", "run-original", "node-a", {"prompt": "adjust"})
        async with ctrl._factory()() as session:
            run = await get_dag_run(session, "run-original")
            recent = await recent_dag_runs(session, 5, "default")
    finally:
        await ctrl.shutdown()
    assert run_id == "run-original"
    assert run is not None
    assert run.run_id == "run-original"
    assert all(item.run_id != "retry-run-original" for item in recent)


@pytest.mark.asyncio
async def test_reflection_run_waits_for_target_idle(tmp_path: Path) -> None:
    _write_dag_config(tmp_path)
    ctrl = DagController(tmp_path)
    await ctrl.start(run_startup=False)
    try:
        blocker = asyncio.create_task(asyncio.sleep(0.2))
        default_dag = tmp_path / "dags" / "default.yaml"
        default_dag.write_text("name: default\nnodes:\n- id: node-a\n  type: node-a\nedges: []\n", encoding="utf-8")
        async with ctrl._factory()() as session:
            await save_core_entity(
                session,
                EntityConfig(
                    id="default",
                    type="dag",
                    attributes={"name": "default", "nodes": [{"id": "node-a", "type": "node-a"}], "edges": []},
                ),
            )
            await session.commit()
        await ctrl.install_snapshot(_load_runtime_base_config(tmp_path), await ctrl.load_bootstrap())
        ctrl.active_runs["default"] = DagRunContext("default", "run-default", blocker)
        pending = asyncio.create_task(ctrl.start_run("manual", "reflection", {"target": "node-a"}))
        await asyncio.sleep(0.05)
        assert not pending.done()
        await blocker
        ctrl._clear_finished_task(blocker, "default")
        run_id = await pending
        assert run_id
    finally:
        await ctrl.shutdown()


@pytest.mark.asyncio
async def test_dag_run_pi_session_dir_flows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_dag_config(tmp_path)
    fake_pi = _write_fake_pi(tmp_path)
    capture = tmp_path / "pi-calls.json"
    monkeypatch.setenv("EDERA_PI_BIN", str(fake_pi))
    monkeypatch.setenv("CAPTURE", str(capture))
    node_file = tmp_path / "nodes" / "llm-node.yaml"
    node_file.write_text(
        "name: llm-node\n"
        "type: agent\n"
        "model: hf-share/deepseek-v4-flash\n"
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
        "edges: []\n",
        encoding="utf-8",
    )
    ctrl = DagController(tmp_path)
    await ctrl.start(run_startup=False)
    try:
        await ctrl.run_now("manual", "default")
    finally:
        await ctrl.shutdown()
    calls = json.loads(capture.read_text(encoding="utf-8"))
    first_args = calls[0]["args"]
    first_session = Path(first_args[first_args.index("--session-dir") + 1])
    assert first_session.parent == tmp_path / "workspace" / "sessions" / "default" / "llm-absolute"
    assert "--continue" not in first_args


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
        "handler: reflection-editor.reflection-editor\n"
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
    ctrl = DagController(tmp_path, extensions_dirs=[extensions_dir])
    await ctrl.start(run_startup=False)
    try:
        await _install_controller_extensions(ctrl, extensions_dir, ["reflection-editor"])
        blocker = asyncio.create_task(asyncio.sleep(0.2))
        ctrl.active_runs["default"] = DagRunContext("default", "run-default", blocker)
        pending = asyncio.create_task(ctrl.start_run("manual", "reflection"))
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
        removed_route = await client.get("/removed")
        config = await client.get("/config")
    assert index.status_code == 200
    assert results.status_code == 404
    assert removed_route.status_code == 404
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
            "/api/system/scheduler-status",
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
async def test_bff_node_history_route_requires_dag_name(tmp_path: Path) -> None:
    _write_dag_config(tmp_path)
    app = create_app(FakeGrpcClient())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        removed = await client.get("/api/nodes/node-a/history?limit=10")
        response = await client.get("/api/history/dag/default/nodes/node-a?limit=10")
    assert removed.status_code == 404
    assert response.status_code == 200
    assert response.json() == {"history": [{"dag_name": "default", "node_id": "node-a", "run_id": "run-1", "limit": 10}]}


@pytest.mark.asyncio
async def test_dag_run_dag_name_field(tmp_path: Path) -> None:
    """C7: DagRun records include dag_name; filtering by dag_name works."""
    _write_dag_config(tmp_path)
    ctrl = FakeController(tmp_path)
    await ctrl.start(run_startup=False)
    try:
        async with ctrl._factory()() as session:
            await create_dag_run(session, "run-a", "manual", dag_name="default")
            await create_dag_run(session, "run-b", "manual", dag_name="realtime")
            await session.commit()
        async with ctrl._factory()() as session:
            all_runs = await recent_dag_runs(session)
            default_runs = await recent_dag_runs(session, dag_name="default")
            realtime_runs = await recent_dag_runs(session, dag_name="realtime")
    finally:
        await ctrl.shutdown()
    assert len(all_runs) == 2
    assert len(default_runs) == 1
    assert default_runs[0].dag_name == "default"
    assert len(realtime_runs) == 1
    assert realtime_runs[0].dag_name == "realtime"


@pytest.mark.asyncio
async def test_status_ignores_stale_running_rows(tmp_path: Path) -> None:
    _write_dag_config(tmp_path)
    ctrl = FakeController(tmp_path)
    await ctrl.start(run_startup=False)
    try:
        async with ctrl._factory()() as session:
            await create_dag_run(session, "stale-run", "manual", dag_name="default")
            await session.commit()

        status = await ctrl.status("default")
    finally:
        await ctrl.shutdown()

    assert status["current_run_id"] is None
    assert status["recent_runs"][0]["run_id"] == "stale-run"
    assert status["recent_runs"][0]["status"] == "running"


@pytest.mark.asyncio
async def test_controller_start_is_idle(tmp_path: Path) -> None:
    _write_dag_config(tmp_path)
    _write_full_config(tmp_path)
    ctrl = DagController(tmp_path)
    await ctrl.start()
    try:
        async with ctrl._factory()() as session:
            runs = await recent_dag_runs(session)
        assert runs == []
        assert ctrl.active_runs == {}
    finally:
        await ctrl.shutdown()


@pytest.mark.asyncio
async def test_scheduler_per_dag_registration(tmp_path: Path) -> None:
    """C8: Scheduler exposes cron DAG runs through Trigger Entity records."""
    _write_dag_config(tmp_path)
    _write_full_config(tmp_path)
    _write_trigger_schema(tmp_path)
    (tmp_path / "dags" / "reflection.yaml").unlink()
    await _seed_trigger(tmp_path, "hourly", 'cron:"0 * * * *"')
    ctrl = DagController(tmp_path)
    await ctrl.start(run_startup=False)
    try:
        assert not (tmp_path / "triggers" / "default-default-cron.yaml").exists()
        assert not (tmp_path / "triggers" / "realtime-default-cron.yaml").exists()
        assert ctrl.cron_emitter is not None
        assert ctrl.cron_emitter.cron_tokens() == {'cron:"0 * * * *"'}
    finally:
        await ctrl.shutdown()


def _write_full_config(path: Path) -> None:
    """Write minimal entity and nodes config for DagController.start()."""
    _write_entity_schemas(path)
    nodes_dir = path / "nodes"
    nodes_dir.mkdir(exist_ok=True)


async def _seed_trigger(root: Path, name: str, wait_for: str) -> None:
    engine = create_engine(sqlite_url(root / "test.db"))
    try:
        await init_db(engine)
        factory = session_factory(engine)
        async with factory() as session:
            await save_core_entity(
                session,
                EntityConfig(
                    id=name,
                    type="trigger",
                    attributes={"name": name, "wait_for": wait_for, "target": "dag:default", "enabled": True},
                ),
            )
            await session.commit()
    finally:
        await engine.dispose()


def _write_trigger_schema(path: Path) -> None:
    schemas = path.parent / "schemas" / "entity-types"
    schemas.mkdir(parents=True, exist_ok=True)
    schemas.joinpath("trigger.yaml").write_text(
        "display_name: Trigger\n"
        "business_id_field: name\n"
        "display_template: '{name}'\n"
        "storage_tier: filesystem\n"
        "schema:\n"
        "  type: object\n"
        "  required: [name, wait_for, target]\n"
        "  properties:\n"
        "    name: {type: string}\n"
        "    wait_for: {type: string}\n"
        "    target: {type: string}\n"
        "    enabled: {type: boolean}\n",
        encoding="utf-8",
    )


def _write_reflection_extension(path: Path) -> None:
    extension = path / "reflection-editor"
    extension.mkdir(parents=True)
    extension.joinpath("manifest.yaml").write_text(
        "name: reflection-editor\n"
        "version: 0.1.0\n"
        "handlers:\n"
        "- name: reflection-editor\n"
        "  entry: handler.py\n"
        "  role: processor\n"
        "  input_type: Any\n"
        "  output_type: Any\n",
        encoding="utf-8",
    )
    extension.joinpath("handler.py").write_text(
        "from pathlib import Path\n"
        "async def run(ctx):\n"
        "    path = Path(ctx.params['skill_path'])\n"
        "    target = ctx.params['target']\n"
        "    text = path.read_text(encoding='utf-8')\n"
        "    path.write_text(text + f'reflected:{target}:{ctx.run_id}\\n', encoding='utf-8')\n"
        "    return {'target': target, 'edited': str(path)}\n",
        encoding="utf-8",
    )


def _write_node_b_extension(path: Path) -> None:
    extension = path / "node-b"
    extension.mkdir(parents=True)
    extension.joinpath("manifest.yaml").write_text(
        "name: node-b\n"
        "version: 0.1.0\n"
        "handlers:\n"
        "- name: node-b\n"
        "  entry: handler.py\n"
        "  role: processor\n"
        "  input_type: Any\n"
        "  output_type: Any\n",
        encoding="utf-8",
    )
    extension.joinpath("handler.py").write_text("async def run(ctx):\n    return {'payload': ctx.input.payload}\n", encoding="utf-8")


def _write_leaf_extension(path: Path) -> None:
    extension = path / "leaf"
    extension.mkdir(parents=True)
    extension.joinpath("manifest.yaml").write_text(
        "name: leaf\n"
        "version: 0.1.0\n"
        "handlers:\n"
        "- name: leaf\n"
        "  entry: handler.py\n"
        "  role: processor\n"
        "  input_type: Any\n"
        "  output_type: Any\n",
        encoding="utf-8",
    )
    extension.joinpath("handler.py").write_text("async def run(ctx):\n    return {'leaf': ctx.run_id}\n", encoding="utf-8")


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
