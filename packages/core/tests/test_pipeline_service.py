from __future__ import annotations

import grpc
import pytest

from edera_core.pipeline import PipelineRunNotFoundError, RunAlreadyActiveError
from edera_core.pipeline_service import _PipelineService
from edera_core.proto import edera_pb2 as pb2

from service_fakes import AbortError, FakeContext, FakeDaemon


class Controller:
    async def start_run(self, trigger: str):
        raise RunAlreadyActiveError("active-cycle")

    async def retry_node(self, dag_name: str, cycle_id: str | None, node_ids: list[str], mode: str, payload: object):
        raise PipelineRunNotFoundError(cycle_id or "missing")


@pytest.mark.asyncio
async def test_run_already_active(tmp_path):
    service = _PipelineService(FakeDaemon(tmp_path, Controller()))

    with pytest.raises(AbortError) as exc:
        await service.Run(pb2.EmptyRequest(), FakeContext())

    assert exc.value.code == grpc.StatusCode.ALREADY_EXISTS
    assert exc.value.details == "active-cycle"


@pytest.mark.asyncio
async def test_retry_cycle_not_found(tmp_path):
    dag_dir = tmp_path / "dags"
    dag_dir.mkdir()
    (dag_dir / "demo.yaml").write_text("name: demo\nnodes: []\nedges: []\n", encoding="utf-8")
    service = _PipelineService(FakeDaemon(tmp_path, Controller()))

    with pytest.raises(AbortError) as exc:
        await service.DagRetry(pb2.DagRetryRequest(dag_name="demo", cycle_id="missing", node_ids=["n1"]), FakeContext())

    assert exc.value.code == grpc.StatusCode.NOT_FOUND


@pytest.mark.asyncio
async def test_repair_task_not_escalated(monkeypatch, tmp_path):
    _write_minimal_config(tmp_path)
    monkeypatch.setattr("edera_core.pipeline_service.source_health_summary", _health)
    monkeypatch.setattr("edera_core.pipeline_service.source_execution_logs", _logs)
    monkeypatch.setattr("edera_core.pipeline_service.latest_briefing", _briefing)
    service = _PipelineService(FakeDaemon(tmp_path, FactoryController()))

    with pytest.raises(AbortError) as exc:
        await service.CreateRepairTask(pb2.NameRequest(name="rss"), FakeContext())

    assert exc.value.code == grpc.StatusCode.FAILED_PRECONDITION


class FactoryController:
    def _factory(self):
        return lambda: Session()


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
