from __future__ import annotations

import asyncio

import pytest

from edera_core.config.schema import DagConfig, NodeConfig, RuntimeSettings, SystemConfig
from edera_core.dag.loader import load_graph
from edera_core.dag.runner import DagRunner
from edera_core.node.executor import NodeExecutor
from edera_core.node.models import NodeInput
from edera_core.trigger import TriggerExecutor

from test_wait_registry import _store


@pytest.mark.asyncio
async def test_independent_path_runs_while_wait_node_is_waiting() -> None:
    graph, nodes = _graph(include_sink=False)
    trigger = TriggerExecutor(_store())
    records: list[str] = []

    async def worker(_input: NodeInput) -> object:
        records.append("worker")
        return "done"

    task = asyncio.create_task(DagRunner(_executor(nodes, graph.instances, worker), trigger_executor=trigger).run(graph, "run", {}))
    await _until(lambda: "worker" in records)

    assert not task.done()
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_resume_starts_downstream_after_wait_node_wakes() -> None:
    graph, nodes = _graph(include_sink=True)
    trigger = TriggerExecutor(_store())
    records: list[str] = []

    async def sink(node_input: NodeInput) -> object:
        records.append("sink")
        return node_input.payload

    task = asyncio.create_task(DagRunner(_executor(nodes, graph.instances, sink=sink), trigger_executor=trigger).run(graph, "run", {}))
    await asyncio.sleep(0.01)
    await trigger.emit("event:approve:run", {"ok": True})
    result = await task

    assert records == ["sink"]
    assert result.node_outputs["sink"].payload == {"ok": True}


@pytest.mark.asyncio
async def test_stop_releases_waiting_node() -> None:
    graph, nodes = _graph(include_sink=False)
    trigger = TriggerExecutor(_store())
    stop_event = asyncio.Event()
    task = asyncio.create_task(
        DagRunner(_executor(nodes, graph.instances), trigger_executor=trigger).run(graph, "run", {}, stop_event=stop_event)
    )
    await asyncio.sleep(0.01)

    stop_event.set()
    result = await asyncio.wait_for(task, timeout=1)

    assert result.node_outputs["gate"].error == "cancelled"


@pytest.mark.asyncio
async def test_stop_single_source_wait_node_returns_cancelled_result() -> None:
    graph, nodes = _wait_only_graph()
    trigger = TriggerExecutor(_store())
    stop_event = asyncio.Event()
    task = asyncio.create_task(
        DagRunner(_executor(nodes, graph.instances), trigger_executor=trigger).run(graph, "run", {}, stop_event=stop_event)
    )
    await asyncio.sleep(0.01)

    stop_event.set()
    result = await asyncio.wait_for(task, timeout=1)

    assert result.node_outputs["gate"].error == "cancelled"


def _graph(include_sink: bool):
    nodes = {
        "gate": NodeConfig.model_validate(
            {
                "name": "gate",
                "type": "wait",
                "input_type": "Any",
                "output_type": "Any",
                "wait_for": "event:approve:run",
            }
        ),
        "worker": NodeConfig.model_validate(
            {"name": "worker", "type": "function", "handler": "worker", "input_type": "Any", "output_type": "Any"}
        ),
        "sink": NodeConfig.model_validate(
            {"name": "sink", "type": "function", "handler": "sink", "input_type": "Any", "output_type": "Any"}
        ),
    }
    dag_nodes = [{"id": "gate", "type": "gate"}, {"id": "worker", "type": "worker"}]
    edges = []
    if include_sink:
        dag_nodes.append({"id": "sink", "type": "sink"})
        edges.append({"from": "gate", "to": "sink"})
    dag = DagConfig.model_validate({"name": "dispatcher-test", "nodes": dag_nodes, "edges": edges})
    return load_graph(dag, nodes), nodes


def _wait_only_graph():
    nodes = {
        "gate": NodeConfig.model_validate(
            {
                "name": "gate",
                "type": "wait",
                "input_type": "Any",
                "output_type": "Any",
                "wait_for": "event:approve:run",
            }
        )
    }
    dag = DagConfig.model_validate({"name": "dispatcher-test", "nodes": [{"id": "gate", "type": "gate"}], "edges": []})
    return load_graph(dag, nodes), nodes


def _executor(nodes, instances, worker=None, sink=None) -> NodeExecutor:
    async def default(_input: NodeInput) -> object:
        return "ok"

    return NodeExecutor(
        nodes,
        SystemConfig(),
        RuntimeSettings(),
        {"worker": worker or default, "sink": sink or default},
        instances,
    )


async def _until(predicate) -> None:
    for _ in range(100):
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition not reached")
