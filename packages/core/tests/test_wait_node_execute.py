from __future__ import annotations

import asyncio

import pytest

from edera_core.config.schema import DagConfig, NodeConfig, RuntimeSettings, SystemConfig
from edera_core.dag.loader import load_graph
from edera_core.dag.runner import DagRunner
from edera_core.errors import DagError
from edera_core.events import event_bus
from edera_core.node.executor import NodeExecutor
from edera_core.trigger import TriggerExecutor

from snapshot_fixtures import create_test_snapshot
from test_wait_registry import _store


@pytest.mark.asyncio
async def test_signal_first_returns_payload_without_waiting() -> None:
    graph, nodes = _graph()
    trigger = TriggerExecutor(_store())
    await trigger.emit("event:approve:run", {"approved": True})
    records: list[tuple[str, str]] = []
    outputs: list[object] = []
    executor = _executor(nodes, graph.instances, outputs)

    result = await DagRunner(executor, recorder=_recorder(records), trigger_executor=trigger).run(graph, "run", {})

    assert result.node_outputs["gate"].payload == {"approved": True}
    assert ("gate", "waiting") not in records
    assert outputs == [{"approved": True}]


@pytest.mark.asyncio
async def test_signal_after_wakes_waiting_node() -> None:
    graph, nodes = _graph()
    trigger = TriggerExecutor(_store())
    records: list[tuple[str, str]] = []
    executor = _executor(nodes, graph.instances, [])
    task = asyncio.create_task(DagRunner(executor, recorder=_recorder(records), trigger_executor=trigger).run(graph, "run", {}))
    await _until(lambda: ("gate", "waiting") in records)

    await trigger.emit("event:approve:run", {"approved": True})
    result = await task

    assert result.node_outputs["gate"].payload == {"approved": True}
    assert ("gate", "running") in records


@pytest.mark.asyncio
async def test_signal_between_register_and_waiting_wakes_node() -> None:
    graph, nodes = _graph()
    trigger = TriggerExecutor(_store())
    executor = _executor(nodes, graph.instances, [])

    async def record(
        _run_id: str,
        _node: str,
        status: str,
        _error: str | None,
        _failure_kind: str | None,
        _metadata: dict[str, object] | None,
    ) -> None:
        if status == "waiting":
            await trigger.emit("event:approve:run", {"approved": True})

    result = await asyncio.wait_for(
        DagRunner(executor, recorder=record, trigger_executor=trigger).run(graph, "run", {}),
        timeout=1,
    )

    assert result.node_outputs["gate"].payload == {"approved": True}


@pytest.mark.asyncio
async def test_mismatch_does_not_wake_waiting_node() -> None:
    graph, nodes = _graph()
    trigger = TriggerExecutor(_store())
    records: list[tuple[str, str]] = []
    executor = _executor(nodes, graph.instances, [])
    task = asyncio.create_task(DagRunner(executor, recorder=_recorder(records), trigger_executor=trigger).run(graph, "run", {}))
    await _until(lambda: ("gate", "waiting") in records)

    await trigger.emit("event:approve:other", {"approved": True})
    await asyncio.sleep(0.01)

    assert not task.done()
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_timeout_marks_wait_timeout() -> None:
    graph, nodes = _graph(timeout_seconds=0.01)
    trigger = TriggerExecutor(_store())
    records: list[tuple[str, str, str | None]] = []
    executor = _executor(nodes, graph.instances, [])

    async def record(
        _run_id: str,
        node: str,
        status: str,
        _error: str | None,
        failure_kind: str | None,
        _metadata: dict[str, object] | None,
    ) -> None:
        records.append((node, status, failure_kind))

    with pytest.raises(DagError):
        await DagRunner(executor, recorder=record, trigger_executor=trigger).run(graph, "run", {})

    assert ("gate", "failed", "wait_timeout") in records


@pytest.mark.asyncio
async def test_publish_node_waiting_event() -> None:
    graph, nodes = _graph()
    trigger = TriggerExecutor(_store())
    executor = _executor(nodes, graph.instances, [])
    events = event_bus.subscribe()
    task = asyncio.create_task(DagRunner(executor, trigger_executor=trigger).run(graph, "run", {}))

    event = await asyncio.wait_for(events.__anext__(), timeout=1)

    assert event.type == "node.waiting"
    assert event.payload == {"run_id": "run", "node": "gate", "node_id": "gate", "wait_for": "event:approve:run"}
    await events.aclose()
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


def _graph(timeout_seconds: float | None = None):
    wait = {
        "name": "gate",
        "type": "wait",
        "input_type": "Any",
        "output_type": "Any",
        "wait_for": "event:approve:run",
    }
    if timeout_seconds is not None:
        wait["timeout_seconds"] = timeout_seconds
    nodes = {"gate": NodeConfig.model_validate(wait)}
    dag = DagConfig.model_validate({"name": "wait-test", "nodes": [{"id": "gate", "type": "gate"}], "edges": []})
    return load_graph(dag, nodes), nodes


def _executor(nodes, instances, outputs: list[object]) -> NodeExecutor:
    async def record_output(_run_id: str, _node: str, _type: str, payload: object, _session_id: str | None) -> None:
        outputs.append(payload)

    return NodeExecutor(
        nodes,
        SystemConfig(),
        RuntimeSettings(),
        create_test_snapshot(nodes),
        instances,
        output_recorder=record_output,
    )


def _recorder(records: list[tuple[str, str]]):
    async def record(
        _run_id: str,
        node: str,
        status: str,
        _error: str | None,
        _failure_kind: str | None,
        _metadata: dict[str, object] | None,
    ) -> None:
        records.append((node, status))

    return record


async def _until(predicate) -> None:
    for _ in range(100):
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition not reached")
