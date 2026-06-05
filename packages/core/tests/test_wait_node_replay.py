from __future__ import annotations

import asyncio

import pytest

from edera_core.config.schema import DagConfig, NodeConfig, RuntimeSettings, SystemConfig
from edera_core.dag.loader import load_graph
from edera_core.dag.runner import DagRunner
from edera_core.node.executor import NodeExecutor
from edera_core.storage import create_engine, init_db, session_factory, sqlite_url
from edera_core.trigger import TriggerExecutor

from snapshot_fixtures import create_test_snapshot
from test_wait_registry import _store


@pytest.mark.asyncio
async def test_resume_passes_when_bit_is_set(tmp_path) -> None:
    graph, nodes = _graph()
    engine = create_engine(sqlite_url(tmp_path / "test.db"))
    await init_db(engine)
    factory = session_factory(engine)
    trigger = TriggerExecutor(_store(), factory=factory)
    await trigger.emit("event:approve:run", {"ok": True})
    restored = TriggerExecutor(_store(), factory=factory)
    await restored.load()

    try:
        result = await DagRunner(_executor(nodes, graph.instances), trigger_executor=restored).run(graph, "run", {})
    finally:
        await engine.dispose()

    assert result.node_outputs["gate"].payload == {"ok": True}


@pytest.mark.asyncio
async def test_resume_waits_when_bit_is_not_set() -> None:
    graph, nodes = _graph()
    trigger = TriggerExecutor(_store())
    task = asyncio.create_task(DagRunner(_executor(nodes, graph.instances), trigger_executor=trigger).run(graph, "run", {}))
    await asyncio.sleep(0.01)

    assert not task.done()
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


def _graph():
    nodes = {
        "gate": NodeConfig.model_validate(
            {
                "name": "gate",
                "type": "wait",
                "input_type": "Any",
                "output_type": "Any",
                "wait_for": "event:approve:run",
                "consume": False,
            }
        )
    }
    dag = DagConfig.model_validate({"name": "replay-test", "nodes": [{"id": "gate", "type": "gate"}], "edges": []})
    return load_graph(dag, nodes), nodes


def _executor(nodes, instances) -> NodeExecutor:
    return NodeExecutor(nodes, SystemConfig(), RuntimeSettings(), create_test_snapshot(nodes), instances)
