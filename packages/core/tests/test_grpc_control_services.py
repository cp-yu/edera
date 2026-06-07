from __future__ import annotations

import grpc
import pytest
from types import SimpleNamespace

from edera_core.config.entities import EntityStore
from edera_core.config.schema import EntitiesConfig, EntityConfig, EntityRelationsConfig, EntityTypeConfig, SystemConfig
from edera_core.dag_controller import DagController, DagRunNotFoundError, RunAlreadyActiveError
from edera_core.event_service import _EventService
from edera_core.proto import edera_pb2 as pb2
from edera_core.server import _DagService, _NodeService, _SystemService
from edera_core.storage import create_engine, init_db, session_factory
from edera_core.storage.repository import create_dag_run, get_dag_config, save_core_entity

from service_fakes import AbortError, FakeContext, FakeDaemon


class Controller:
    def runtime_config(self):
        return SimpleNamespace(dags={"demo": object()})

    async def emit(self, event: str, payload: object | None = None, *, source: str = "rpc", depth: int = 0):
        raise RunAlreadyActiveError("active-run")

    async def retry_node(self, dag_name: str, run_id: str | None, node_ids: list[str], mode: str, payload: object):
        raise DagRunNotFoundError(run_id or "missing")


class EmitController:
    async def emit(self, event: str, payload: object | None, *, source: str, depth: int) -> list[str]:
        assert event == "event:price-drop"
        assert payload == {"symbol": "TEST"}
        assert source == "test"
        assert depth == 1
        return ["dag:default"]


@pytest.mark.asyncio
async def test_emit_rpc(tmp_path):
    service = _EventService(FakeDaemon(tmp_path, EmitController()))

    response = await service.Emit(
        pb2.EmitRequest(
            event="event:price-drop",
            payload_json='{"symbol":"TEST"}',
            source="test",
            depth=1,
        ),
        FakeContext(),
    )

    assert response.json == '{"event": "event:price-drop", "fired": ["dag:default"]}'


@pytest.mark.asyncio
async def test_run_already_active(tmp_path):
    service = _DagService(FakeDaemon(tmp_path, Controller()))

    with pytest.raises(AbortError) as exc:
        await service.Run(pb2.DagRunRequest(name="default"), FakeContext())

    assert exc.value.code == grpc.StatusCode.ALREADY_EXISTS
    assert exc.value.details == "active-run"


@pytest.mark.asyncio
async def test_run_uses_manual_emit(tmp_path):
    service = _DagService(FakeDaemon(tmp_path, RunController()))

    response = await service.Run(pb2.DagRunRequest(name="default"), FakeContext())

    assert response.run_id == "run-1"


@pytest.mark.asyncio
async def test_retry_run_not_found(tmp_path):
    dag_dir = tmp_path / "dags"
    dag_dir.mkdir()
    (dag_dir / "demo.yaml").write_text("name: demo\nnodes: []\nedges: []\n", encoding="utf-8")
    service = _DagService(FakeDaemon(tmp_path, Controller()))

    with pytest.raises(AbortError) as exc:
        await service.Retry(pb2.DagRetryRequest(dag_name="demo", run_id="missing", node_ids=["n1"]), FakeContext())

    assert exc.value.code == grpc.StatusCode.NOT_FOUND


@pytest.mark.asyncio
async def test_dag_edit_sub_dag_cycle_rejected(tmp_path):
    controller = await EditController.create(tmp_path)
    service = _DagService(FakeDaemon(tmp_path, controller))

    try:
        with pytest.raises(AbortError) as exc:
            await service.Edit(
                pb2.DagEditRequest(
                    name="demo",
                    operation="add-node",
                    json='{"id":"self","type":"demo","config":{}}',
                ),
                FakeContext(),
            )
    finally:
        await controller.engine.dispose()

    assert exc.value.code == grpc.StatusCode.INVALID_ARGUMENT
    assert "Sub DAG cycle detected" in exc.value.details
    assert "节点 'self'" in exc.value.details
    assert "修复建议" in exc.value.details


@pytest.mark.asyncio
async def test_dag_edit_writes_database_and_emits_without_snapshot_rebuild(tmp_path):
    controller = await EditController.create(tmp_path)
    service = _DagService(FakeDaemon(tmp_path, controller))

    try:
        response = await service.Edit(
            pb2.DagEditRequest(
                name="demo",
                operation="add-node",
                json='{"id":"n2","type":"source","config":{}}',
            ),
            FakeContext(),
        )
        async with controller._factory()() as session:
            stored = await get_dag_config(session, "demo")
    finally:
        await controller.engine.dispose()

    assert response.name == "demo"
    assert stored is not None
    assert [node.id for node in stored.nodes] == ["n1", "n2"]
    assert controller.emitted == ["event:config-changed"]


@pytest.mark.asyncio
async def test_dag_stop_checks_dag_from_database(tmp_path):
    controller = await EditController.create(tmp_path)
    service = _DagService(FakeDaemon(tmp_path, controller))

    try:
        response = await service.Stop(pb2.DagStopRequest(dag_name="demo"), FakeContext())
    finally:
        await controller.engine.dispose()

    assert response.json == '{"stopped": false, "run_id": null}'


@pytest.mark.asyncio
async def test_node_stop_resolves_active_dag_from_database(tmp_path, monkeypatch):
    controller = await _node_controller(tmp_path)
    service = _NodeService(FakeDaemon(tmp_path, controller))
    captured: dict[str, str | None] = {}

    async def stop_current(dag_name: str, force: bool = False, node_id: str | None = None):
        captured["dag_name"] = dag_name
        captured["node_id"] = node_id
        return "run-1"

    controller.active_runs["demo"] = SimpleNamespace(dag_name="demo", task=SimpleNamespace(done=lambda: False))
    monkeypatch.setattr(controller, "stop_current", stop_current)

    try:
        response = await service.Stop(pb2.NodeRef(id="n1"), FakeContext())
    finally:
        await controller.engine.dispose()

    assert response.status == "stopped"
    assert captured == {"dag_name": "demo", "node_id": "n1"}


@pytest.mark.asyncio
async def test_node_resume_resolves_dag_from_run_record(tmp_path, monkeypatch):
    controller = await _node_controller(tmp_path)
    service = _NodeService(FakeDaemon(tmp_path, controller))
    captured: dict[str, object] = {}

    async def resume_node(dag_name: str, run_id: str, node_id: str, payload: object):
        captured.update({"dag_name": dag_name, "run_id": run_id, "node_id": node_id, "payload": payload})
        return "run-1"

    async with controller._factory()() as session:
        await create_dag_run(session, "run-1", "manual", ["n1"], "demo")
        await session.commit()
    monkeypatch.setattr(controller, "resume_node", resume_node)

    try:
        response = await service.Resume(pb2.NodeResumeRequest(id="n1", run_id="run-1", prompt="continue"), FakeContext())
    finally:
        await controller.engine.dispose()

    assert response.run_id == "run-1"
    assert captured == {
        "dag_name": "demo",
        "run_id": "run-1",
        "node_id": "n1",
        "payload": {"resume_session": "sandbox:n1:run-1", "prompt": "continue"},
    }


@pytest.mark.asyncio
async def test_repair_task_not_escalated(monkeypatch, tmp_path):
    _write_minimal_config(tmp_path)
    monkeypatch.setattr("edera_core.server.source_health_summary", _health)
    monkeypatch.setattr("edera_core.server.source_execution_logs", _logs)
    monkeypatch.setattr("edera_core.server.latest_briefing", _briefing)
    service = _SystemService(FakeDaemon(tmp_path, FactoryController()), bootstrap=False)

    with pytest.raises(AbortError) as exc:
        await service.CreateRepairTask(pb2.NameRequest(name="rss"), FakeContext())

    assert exc.value.code == grpc.StatusCode.FAILED_PRECONDITION


class FactoryController:
    def entity_store(self):
        entity_type = EntityTypeConfig(
            display_name="RSS",
            business_id_field="name",
            display_template="{name}",
            schema_={"properties": {"name": {}}},
        )
        store = EntityStore(
            EntitiesConfig(entities=[EntityConfig(id="s1", type="rss-source", attributes={"name": "rss"})]),
            {"rss-source": entity_type},
            EntityRelationsConfig(),
            None,
        )
        return store

    def _factory(self):
        return lambda: Session()


class EditController:
    def __init__(self, engine, factory):
        self.engine = engine
        self.factory = factory
        self.emitted: list[str] = []

    @classmethod
    async def create(cls, tmp_path):
        engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'edera.db'}")
        await init_db(engine)
        factory = session_factory(engine)
        async with factory() as session:
            await save_core_entity(
                session,
                EntityConfig(
                    id="node:source",
                    type="node",
                    attributes={
                        "name": "source",
                        "type": "function",
                        "handler": "source",
                        "input_type": "Any",
                        "output_type": "Any",
                    },
                ),
            )
            await save_core_entity(
                session,
                EntityConfig(
                    id="dag:demo",
                    type="dag",
                    attributes={"name": "demo", "nodes": [{"id": "n1", "type": "source"}], "edges": [], "ui": {}},
                ),
            )
            await session.commit()
        return cls(engine, factory)

    def _factory(self):
        return self.factory

    def runtime_config(self):
        return SimpleNamespace(dags={}, system=SystemConfig())

    async def emit(self, event: str, payload: object | None = None, *, source: str = "rpc", depth: int = 0):
        self.emitted.append(event)
        return []

    async def install_snapshot(self, *_args, **_kwargs):
        raise AssertionError("DAG edit must not rebuild RuntimeControlSnapshot")

    async def stop_current(self, dag_name: str, force: bool = False):
        return None


class RunController:
    async def emit(self, event: str, payload: object | None = None, *, source: str = "rpc", depth: int = 0) -> list[str]:
        assert event == "manual:dag:default"
        assert payload is None
        assert source == "dag-service"
        assert depth == 0
        return ["run-1"]


async def _node_controller(tmp_path) -> DagController:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'edera.db'}")
    await init_db(engine)
    factory = session_factory(engine)
    async with factory() as session:
        await save_core_entity(
            session,
            EntityConfig(
                id="node:source",
                type="node",
                attributes={
                    "name": "source",
                    "type": "function",
                    "handler": "source",
                    "input_type": "Any",
                    "output_type": "Any",
                },
            ),
        )
        await save_core_entity(
            session,
            EntityConfig(
                id="dag:demo",
                type="dag",
                attributes={"name": "demo", "nodes": [{"id": "n1", "type": "source"}], "edges": [], "ui": {}},
            ),
        )
        await session.commit()
    controller = DagController(tmp_path / "config")
    controller.engine = engine
    controller.factory = factory
    controller._runtime_config = SimpleNamespace(dags={}, system=SystemConfig())
    return controller


class Session:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


async def _health(session, source_names):
    return [{"source_name": source_names[0], "escalated": False}]


async def _logs(session, source_name, limit):
    return []


async def _briefing(session):
    return None


def _write_minimal_config(root):
    (root / "dags").mkdir()
    (root / "nodes").mkdir()
    (root / "skills").mkdir()
    (root.parent / "schemas" / "entity-types").mkdir(parents=True, exist_ok=True)
    (root.parent / "schemas" / "entity-types" / "rss-source.yaml").write_text(
        "display_name: RSS\nbusiness_id_field: name\ndisplay_template: '{name}'\nstorage_tier: database\nschema:\n  properties:\n    name: {}\n",
        encoding="utf-8",
    )
