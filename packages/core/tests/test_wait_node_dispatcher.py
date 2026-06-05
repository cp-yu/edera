from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from edera_core.config.schema import DagConfig, NodeConfig, RuntimeSettings, SystemConfig
from edera_core.dag.loader import load_graph
from edera_core.dag.runner import DagRunner
from edera_core.node.executor import NodeExecutor
from edera_core.trigger import TriggerExecutor

from snapshot_fixtures import create_test_snapshot, write_handler
from test_wait_registry import _store


@pytest.mark.asyncio
async def test_independent_path_runs_while_wait_node_is_waiting() -> None:
    graph, nodes = _graph(include_sink=False)
    trigger = TriggerExecutor(_store())
    records: list[str] = ["pending"]

    task = asyncio.create_task(DagRunner(_executor(nodes, graph.instances, records=records), trigger_executor=trigger).run(graph, "run", {}))
    await _until(lambda: records == ["worker"])

    assert not task.done()
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_resume_starts_downstream_after_wait_node_wakes() -> None:
    graph, nodes = _graph(include_sink=True)
    trigger = TriggerExecutor(_store())
    records: list[str] = ["pending"]

    task = asyncio.create_task(DagRunner(_executor(nodes, graph.instances, records=records), trigger_executor=trigger).run(graph, "run", {}))
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


def _executor(nodes, instances, records: list[str] | None = None) -> NodeExecutor:
    import tempfile

    root = Path(tempfile.mkdtemp(prefix="edera-test-handlers-"))
    handlers = {
        "worker": write_handler(root / "worker.py", "ctx.params['records'][:] = ['worker']; return 'done'"),
        "sink": write_handler(root / "sink.py", "ctx.params['records'][:] = ['sink']; return ctx.input.payload"),
    }
    for node in nodes.values():
        if hasattr(node, "parameters"):
            node.parameters["records"] = records if records is not None else []
    return NodeExecutor(
        nodes,
        SystemConfig(),
        RuntimeSettings(),
        create_test_snapshot(nodes, handlers),
        instances,
    )


async def _until(predicate) -> None:
    for _ in range(100):
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition not reached")
