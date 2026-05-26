import asyncio
from pathlib import Path

import pytest

from stockimformation_core.config.entities import EntityStore
from stockimformation_core.config.loader import _validate_entities, load_app_config
from stockimformation_core.config.schema import EntitiesConfig, EntityConfig
from stockimformation_core.dag.loader import load_graph
from stockimformation_core.dag.resources import clear_semaphore_cache, get_semaphore
from stockimformation_core.dag.runner import DagRunner
from stockimformation_core.errors import ConfigError
from stockimformation_core.node.executor import NodeExecutor
from stockimformation_core.node.models import NodeInput


@pytest.fixture(autouse=True)
def _clear_resource_semaphores() -> None:
    clear_semaphore_cache()


def test_get_semaphore_caches() -> None:
    store = _resource_store(1)

    first = get_semaphore("v8_isolate", store)
    second = get_semaphore("resource:v8_isolate", store)

    assert first is second


@pytest.mark.parametrize("permits", [0, "one", True])
def test_invalid_permits_rejected(permits: object) -> None:
    config = load_app_config(Path("config"))
    entities = EntitiesConfig(
        entities=[EntityConfig(id="v8_isolate", type="resource", attributes={"permits": permits})]
    )

    with pytest.raises(ConfigError):
        _validate_entities(entities, config.entity_types)


@pytest.mark.asyncio
async def test_serial_execution() -> None:
    events, max_active = await _run_resource_dag(["v8_isolate", "v8_isolate"], permits=1)

    assert max_active == 1
    assert events == ["start", "end", "start", "end"]


@pytest.mark.asyncio
async def test_no_resource_unchanged() -> None:
    _events, max_active = await _run_resource_dag([None, None], permits=1)

    assert max_active == 2


@pytest.mark.asyncio
async def test_permits_two() -> None:
    _events, max_active = await _run_resource_dag(["v8_isolate", "v8_isolate", "v8_isolate"], permits=2)

    assert max_active == 2


@pytest.mark.asyncio
async def test_release_on_failure() -> None:
    config = load_app_config(Path("config"))
    nodes = _nodes(config)
    graph = load_graph(
        config.dags["default"].model_validate(
            {
                "name": "resource-failure",
                "nodes": [
                    {"id": "first", "type": "rss-fetcher", "resource": "v8_isolate"},
                    {"id": "second", "type": "web-scraper", "resource": "v8_isolate"},
                ],
                "edges": [],
            }
        ),
        nodes,
    )
    store = _resource_store(1)

    async def fail(_node_input: NodeInput) -> object:
        raise RuntimeError("boom")

    executor = NodeExecutor(
        nodes,
        config.system,
        config.runtime,
        {"fetch-rss": fail, "fetch-web": _delayed_handler("second", [], 0)},
        graph.instances,
        store,
    )

    result = await DagRunner(executor).run(graph, "cycle", {})

    assert result.failures == {"first": "boom"}
    assert result.node_outputs["second"].ok


@pytest.mark.asyncio
async def test_cross_dag_sharing() -> None:
    config = load_app_config(Path("config"))
    store = _resource_store(1)
    started = asyncio.Event()
    finish = asyncio.Event()
    events: list[str] = []
    nodes = _nodes(config)

    async def first(_node_input: NodeInput) -> object:
        events.append("dag-a-start")
        started.set()
        await finish.wait()
        events.append("dag-a-end")
        return "a"

    async def second(_node_input: NodeInput) -> object:
        events.append("dag-b-start")
        return "b"

    graph_a = _single_resource_graph(config, "dag-a", "rss-fetcher")
    graph_b = _single_resource_graph(config, "dag-b", "web-scraper")
    runner_a = DagRunner(NodeExecutor(nodes, config.system, config.runtime, {"fetch-rss": first}, graph_a.instances, store))
    runner_b = DagRunner(NodeExecutor(nodes, config.system, config.runtime, {"fetch-web": second}, graph_b.instances, store))

    task_a = asyncio.create_task(runner_a.run(graph_a, "cycle-a", {}))
    await started.wait()
    task_b = asyncio.create_task(runner_b.run(graph_b, "cycle-b", {}))
    await asyncio.sleep(0.01)

    assert events == ["dag-a-start"]

    finish.set()
    await asyncio.gather(task_a, task_b)

    assert events == ["dag-a-start", "dag-a-end", "dag-b-start"]


@pytest.mark.asyncio
async def test_different_resources_do_not_block() -> None:
    _events, max_active = await _run_resource_dag(["v8_isolate", "eastmoney_api"], permits=1)

    assert max_active == 2


@pytest.mark.asyncio
async def test_cancel_releases_resource() -> None:
    config = load_app_config(Path("config"))
    nodes = _nodes(config)
    graph = _single_resource_graph(config, "cancel-resource", "rss-fetcher")
    started = asyncio.Event()
    finish = asyncio.Event()

    async def blocked(_node_input: NodeInput) -> object:
        started.set()
        await finish.wait()
        return "done"

    runner = DagRunner(
        NodeExecutor(
            nodes,
            config.system,
            config.runtime,
            {"fetch-rss": blocked},
            graph.instances,
            _resource_store(1),
        )
    )
    task = asyncio.create_task(runner.run(graph, "cancel", {}))
    await started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    events, max_active = await _run_resource_dag(["v8_isolate"], permits=1)

    assert events == ["start", "end"]
    assert max_active == 1


@pytest.mark.asyncio
async def test_accumulate_resource_nodes_are_limited() -> None:
    config = load_app_config(Path("config"))
    nodes = _nodes(config)
    nodes["advisor"] = config.nodes["advisor"].model_copy(update={"input_type": "Any"})
    graph = load_graph(
        config.dags["default"].model_validate(
            {
                "name": "accumulate-resource",
                "nodes": [
                    {"id": "fast", "type": "rss-fetcher"},
                    {"id": "slow", "type": "web-scraper"},
                    {"id": "sink", "type": "advisor", "fan_in_mode": "accumulate", "resource": "v8_isolate"},
                ],
                "edges": [
                    {"from": "fast", "to": "sink", "fan_in_mode": "stream"},
                    {"from": "slow", "to": "sink", "fan_in_mode": "stream"},
                ],
            }
        ),
        nodes,
    )
    active = 0
    max_active = 0

    async def source(_node_input: NodeInput) -> object:
        return "item"

    async def sink(_node_input: NodeInput) -> object:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.01)
        active -= 1
        return "sink"

    executor = NodeExecutor(
        nodes,
        config.system,
        config.runtime,
        {"fetch-rss": source, "fetch-web": source, "generate-advice": sink},
        graph.instances,
        _resource_store(1),
    )
    result = await DagRunner(executor).run(graph, "cycle", {})

    assert result.node_outputs["sink"].ok
    assert max_active == 1


@pytest.mark.asyncio
async def test_accumulate_resource_waits_for_running_holder() -> None:
    config = load_app_config(Path("config"))
    nodes = _nodes(config)
    nodes["advisor"] = config.nodes["advisor"].model_copy(update={"input_type": "Any"})
    graph = load_graph(
        config.dags["default"].model_validate(
            {
                "name": "accumulate-resource-contention",
                "nodes": [
                    {"id": "holder", "type": "rss-fetcher", "resource": "v8_isolate"},
                    {"id": "source", "type": "web-scraper"},
                    {"id": "sink", "type": "advisor", "fan_in_mode": "accumulate", "resource": "v8_isolate"},
                ],
                "edges": [{"from": "source", "to": "sink", "fan_in_mode": "stream"}],
            }
        ),
        nodes,
    )
    source_done = asyncio.Event()
    release_holder = asyncio.Event()
    events: list[str] = []

    async def holder(_node_input: NodeInput) -> object:
        events.append("holder-start")
        await source_done.wait()
        await asyncio.sleep(0.01)
        assert events == ["holder-start", "source-done"]
        release_holder.set()
        events.append("holder-end")
        return "holder"

    async def source(_node_input: NodeInput) -> object:
        events.append("source-done")
        source_done.set()
        return "source"

    async def sink(_node_input: NodeInput) -> object:
        events.append("sink-start")
        assert release_holder.is_set()
        return "sink"

    executor = NodeExecutor(
        nodes,
        config.system,
        config.runtime,
        {"fetch-rss": holder, "fetch-web": source, "generate-advice": sink},
        graph.instances,
        _resource_store(1),
    )
    result = await DagRunner(executor).run(graph, "cycle", {})

    assert result.node_outputs["sink"].ok
    assert events == ["holder-start", "source-done", "holder-end", "sink-start"]


def _resource_store(permits: int, resource_ids: list[str] | None = None) -> EntityStore:
    config = load_app_config(Path("config"))
    entities = config.entities.model_copy(deep=True)
    resource_ids = resource_ids or ["v8_isolate"]
    entities.entities = [
        entity
        for entity in entities.entities
        if not (entity.type == "resource" and entity.id in resource_ids)
    ]
    for resource_id in resource_ids:
        entities.entities.append(EntityConfig(id=resource_id, type="resource", attributes={"permits": permits}))
    return EntityStore(
        entities,
        config.entity_types,
        config.entity_relations,
    )


def _nodes(config):
    return {
        "rss-fetcher": config.nodes["rss-fetcher"].model_copy(update={"role": "processor"}),
        "web-scraper": config.nodes["web-scraper"].model_copy(update={"role": "processor"}),
    }


async def _run_resource_dag(resources: list[str | None], permits: int) -> tuple[list[str], int]:
    config = load_app_config(Path("config"))
    nodes = _nodes(config)
    graph = load_graph(
        config.dags["default"].model_validate(
            {
                "name": "resource-test",
                "nodes": [
                    {"id": f"n{index}", "type": "rss-fetcher", **({"resource": resource} if resource else {})}
                    for index, resource in enumerate(resources)
                ],
                "edges": [],
            }
        ),
        nodes,
    )
    events: list[str] = []
    active = 0
    max_active = 0

    async def handler(node_input: NodeInput) -> object:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        events.append("start")
        await asyncio.sleep(0.01)
        events.append("end")
        active -= 1
        return "ok"

    resource_ids = sorted({resource for resource in resources if resource is not None})
    executor = NodeExecutor(
        nodes,
        config.system,
        config.runtime,
        {"fetch-rss": handler},
        graph.instances,
        _resource_store(permits, resource_ids),
    )
    await DagRunner(executor).run(graph, "cycle", {})
    return events, max_active


def _single_resource_graph(config, name: str, node_type: str):
    return load_graph(
        config.dags["default"].model_validate(
            {
                "name": name,
                "nodes": [{"id": "node", "type": node_type, "resource": "v8_isolate"}],
                "edges": [],
            }
        ),
        _nodes(config),
    )


def _delayed_handler(value: str, events: list[str], delay: float):
    async def handler(_node_input: NodeInput) -> object:
        events.append(value)
        if delay:
            await asyncio.sleep(delay)
        return value

    return handler
