from __future__ import annotations

import grpc
import pytest
from types import SimpleNamespace

from edera_core.config.entities import EntityStore
from edera_core.config.schema import EntitiesConfig, EntityConfig, EntityRelationsConfig, EntityTypeConfig
from edera_core.dag_controller import DagRunNotFoundError, RunAlreadyActiveError
from edera_core.event_service import _EventService
from edera_core.proto import edera_pb2 as pb2
from edera_core.server import _DagService, _SystemService

from service_fakes import AbortError, FakeContext, FakeDaemon


class Controller:
    def runtime_snapshot(self):
        return SimpleNamespace(config=SimpleNamespace(dags={"demo": object()}))

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
    def runtime_snapshot(self):
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
        return SimpleNamespace(entity_store=store)

    def _factory(self):
        return lambda: Session()


class RunController:
    async def emit(self, event: str, payload: object | None = None, *, source: str = "rpc", depth: int = 0) -> list[str]:
        assert event == "manual:dag:default"
        assert payload is None
        assert source == "dag-service"
        assert depth == 0
        return ["run-1"]


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
        "display_name: RSS\nbusiness_id_field: name\ndisplay_template: '{name}'\nschema:\n  properties:\n    name: {}\n",
        encoding="utf-8",
    )
    (root / "entities.yaml").write_text("entities:\n- id: s1\n  type: rss-source\n  attributes:\n    name: rss\n", encoding="utf-8")
    (root / "entity-relations.yaml").write_text("relations: []\n", encoding="utf-8")
