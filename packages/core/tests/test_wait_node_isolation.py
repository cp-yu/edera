from __future__ import annotations

import asyncio

import pytest

from edera_core.config.schema import DagConfig, NodeConfig, RuntimeSettings, SystemConfig
from edera_core.dag.loader import load_graph
from edera_core.dag.runner import DagRunner
from edera_core.node.executor import NodeExecutor
from edera_core.trigger import TriggerExecutor

from snapshot_fixtures import create_test_snapshot
from test_wait_registry import _store


@pytest.mark.asyncio
async def test_consume_clears_oneshot_and_preserves_level_signal() -> None:
    trigger = TriggerExecutor(_store())
    consume_graph, consume_nodes = _graph("event:oneshot", consume=True)
    keep_graph, keep_nodes = _graph("event:level", consume=False)
    await trigger.emit("event:oneshot")
    await DagRunner(_executor(consume_nodes, consume_graph.instances), trigger_executor=trigger).run(consume_graph, "run", {})
    await trigger.emit("event:level")
    await DagRunner(_executor(keep_nodes, keep_graph.instances), trigger_executor=trigger).run(keep_graph, "run", {})

    assert "event:oneshot" not in trigger.events.events
    assert "event:level" in trigger.events.events


@pytest.mark.asyncio
async def test_isolation_wakes_only_matching_run() -> None:
    trigger = TriggerExecutor(_store())
    graph_a, nodes_a = _graph("event:approve:A")
    graph_b, nodes_b = _graph("event:approve:B")
    task_a = asyncio.create_task(DagRunner(_executor(nodes_a, graph_a.instances), trigger_executor=trigger).run(graph_a, "A", {}))
    task_b = asyncio.create_task(DagRunner(_executor(nodes_b, graph_b.instances), trigger_executor=trigger).run(graph_b, "B", {}))
    await asyncio.sleep(0.01)

    await trigger.emit("event:approve:A", {"run": "A"})
    result_a = await asyncio.wait_for(task_a, timeout=1)
    await asyncio.sleep(0.01)

    assert result_a.node_outputs["gate"].payload == {"run": "A"}
    assert not task_b.done()
    task_b.cancel()
    await asyncio.gather(task_b, return_exceptions=True)


def _graph(wait_for: str, consume: bool = True):
    nodes = {
        "gate": NodeConfig.model_validate(
            {
                "name": "gate",
                "type": "wait",
                "input_type": "Any",
                "output_type": "Any",
                "wait_for": wait_for,
                "consume": consume,
            }
        )
    }
    dag = DagConfig.model_validate({"name": "wait-test", "nodes": [{"id": "gate", "type": "gate"}], "edges": []})
    return load_graph(dag, nodes), nodes


def _executor(nodes, instances) -> NodeExecutor:
    return NodeExecutor(nodes, SystemConfig(), RuntimeSettings(), create_test_snapshot(nodes), instances)
