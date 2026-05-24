import asyncio
from pathlib import Path

import pytest

from stockimformation_core.config.loader import load_app_config
from stockimformation_core.config.schema import NodeConfig
from stockimformation_core.dag.loader import load_graph, topological_layers, validate_sub_dag_nesting
from stockimformation_core.dag.runner import DagRunner
from stockimformation_core.errors import DagError
from stockimformation_core.node.executor import NodeExecutor
from stockimformation_core.node.models import FunctionHandler, NodeInput


@pytest.mark.asyncio
async def test_default_dag_runs_with_fake_handlers() -> None:
    config = load_app_config(Path("config"))
    handlers = {
        "fetch-rss": _handler([{"url": "a"}]),
        "fetch-api": _handler([{"url": "a"}, {"url": "b"}]),
        "summarize": _handler([{"summary": "a"}]),
        "classify-sentiment": _handler([{"summary": "a"}]),
        "generate-advice": _handler([{"direction": "hold"}]),
        "generate-briefing": _handler({"content": "briefing"}),
        "notify-ntfy": _handler([{"skipped": True}]),
    }
    config.nodes["reader"].type = "function"
    executor = NodeExecutor(config.nodes, config.system, config.runtime, handlers)
    graph = load_graph(config.dags["default"], config.nodes)
    result = await DagRunner(executor).run(graph, "cycle", {"source_names": ["hn-rss"]})
    assert result.payload == [{"skipped": True}]
    assert result.failures == {}


@pytest.mark.asyncio
async def test_single_source_failure_does_not_block() -> None:
    config = load_app_config(Path("config"))
    handlers = {
        "fetch-rss": _failing_handler,
        "fetch-api": _handler([{"url": "b"}]),
        "summarize": _handler([{"summary": "b"}]),
        "classify-sentiment": _handler([{"summary": "b"}]),
        "generate-advice": _handler([{"direction": "hold"}]),
        "generate-briefing": _handler({"content": "briefing"}),
        "notify-ntfy": _handler([{"skipped": True}]),
    }
    config.nodes["reader"].type = "function"
    executor = NodeExecutor(config.nodes, config.system, config.runtime, handlers)
    graph = load_graph(config.dags["default"], config.nodes)
    result = await DagRunner(executor).run(graph, "cycle", {"source_names": ["cls-telegraph"]})
    assert _instance_id(graph, "rss-fetcher") in result.failures
    assert result.payload == [{"skipped": True}]


def test_topological_layers_have_parallel_sources() -> None:
    config = load_app_config(Path("config"))
    graph = load_graph(config.dags["default"], config.nodes)
    assert set(topological_layers(graph)[0]) == {
        _instance_id(graph, "rss-fetcher"),
        _instance_id(graph, "api-fetcher"),
    }


@pytest.mark.asyncio
async def test_node_entity_execution() -> None:
    config = load_app_config(Path("config"))
    handlers = {
        "fetch-rss": _handler([{"url": "a"}]),
        "fetch-api": _handler([]),
        "summarize": _handler([]),
        "classify-sentiment": _handler([]),
        "generate-advice": _handler([]),
        "generate-briefing": _handler({"content": "briefing"}),
        "notify-ntfy": _handler([{"skipped": True}]),
    }
    executor = NodeExecutor(config.nodes, config.system, config.runtime, handlers)
    output = await executor.execute("rss-fetcher", NodeInput(cycle_id="cycle", payload={}))
    assert output.ok
    assert output.payload == [{"url": "a"}]


def test_dag_entity_loading() -> None:
    config = load_app_config(Path("config"))
    graph = load_graph(config.dags["default"], config.nodes)
    first_layer = topological_layers(graph)[0]
    assert graph.name == "default"
    assert first_layer == sorted(first_layer)


@pytest.mark.asyncio
async def test_condition_branch() -> None:
    config = load_app_config(Path("config"))
    graph = load_graph(
        config.dags["default"].model_validate(
            {
                "name": "condition-test",
                "nodes": [
                    {"id": "source", "type": "rss-fetcher"},
                    {"id": "negative", "type": "advisor"},
                    {"id": "positive", "type": "briefing-generator"},
                ],
                "edges": [
                    {"from": "source", "to": "negative", "condition": "output.sentiment == 'negative'"},
                    {"from": "source", "to": "positive", "condition": "output.score > 0.3"},
                ],
            }
        ),
        _condition_nodes(),
    )
    handlers = {
        "fetch-rss": _handler({"sentiment": "negative", "score": 0.8}),
        "generate-advice": _handler({"routed": "negative"}),
        "generate-briefing": _handler({"routed": "positive"}),
    }
    executor = NodeExecutor(_condition_nodes(), config.system, config.runtime, handlers, graph.instances)
    result = await DagRunner(executor).run(graph, "cycle", {})

    assert set(result.node_outputs) == {"source", "negative", "positive"}


@pytest.mark.asyncio
async def test_dead_path_detection() -> None:
    config = load_app_config(Path("config"))
    graph = load_graph(
        config.dags["default"].model_validate(
            {
                "name": "dead-path-test",
                "nodes": [
                    {"id": "source", "type": "rss-fetcher"},
                    {"id": "negative", "type": "advisor"},
                ],
                "edges": [
                    {"from": "source", "to": "negative", "condition": "output.sentiment == 'negative'"},
                ],
            }
        ),
        _condition_nodes(),
    )
    handlers = {
        "fetch-rss": _handler({"sentiment": "positive"}),
        "generate-advice": _handler({"routed": "negative"}),
    }
    executor = NodeExecutor(_condition_nodes(), config.system, config.runtime, handlers, graph.instances)
    result = await DagRunner(executor).run(graph, "cycle", {})

    assert set(result.node_outputs) == {"source"}
    assert result.failures == {}
    assert result.warnings == ["dead path after source"]


@pytest.mark.asyncio
async def test_single_node_loop() -> None:
    config = load_app_config(Path("config"))
    graph = load_graph(
        config.dags["default"].model_validate(
            {
                "name": "loop-test",
                "nodes": [
                    {"id": "parallel", "type": "rss-fetcher", "loop": {"mode": "parallel", "count": 3}},
                    {"id": "serial", "type": "advisor", "loop": {"mode": "serial", "count": 2}},
                ],
                "edges": [{"from": "parallel", "to": "serial"}],
            }
        ),
        _condition_nodes(),
    )
    calls: list[object] = []

    async def parallel_handler(node_input: NodeInput) -> object:
        return {"input": node_input.payload}

    async def serial_handler(node_input: NodeInput) -> object:
        calls.append(node_input.payload)
        return {"iteration": len(calls)}

    executor = NodeExecutor(
        _condition_nodes(),
        config.system,
        config.runtime,
        {"fetch-rss": parallel_handler, "generate-advice": serial_handler},
        graph.instances,
    )
    result = await DagRunner(executor).run(graph, "cycle", {"seed": True})

    assert result.node_outputs["parallel"].payload == [
        {"input": {"seed": True}},
        {"input": {"seed": True}},
        {"input": {"seed": True}},
    ]
    assert calls[0] == result.node_outputs["parallel"].payload
    assert calls[1] == {"iteration": 1}
    assert result.node_outputs["serial"].payload == {"iteration": 2}


@pytest.mark.asyncio
async def test_fan_in_stream() -> None:
    config = load_app_config(Path("config"))
    nodes = _condition_nodes()
    graph = load_graph(
        config.dags["default"].model_validate(
            {
                "name": "stream-test",
                "nodes": [
                    {"id": "fast", "type": "rss-fetcher"},
                    {"id": "slow", "type": "web-scraper"},
                    {"id": "sink", "type": "advisor"},
                ],
                "edges": [
                    {"from": "fast", "to": "sink", "fan_in_mode": "stream"},
                    {"from": "slow", "to": "sink", "fan_in_mode": "stream"},
                ],
            }
        ),
        nodes,
    )
    events: list[str] = []

    async def fast(_node_input: NodeInput) -> object:
        events.append("fast-done")
        return "fast"

    async def slow(_node_input: NodeInput) -> object:
        await asyncio.sleep(0.05)
        events.append("slow-done")
        return "slow"

    async def sink(node_input: NodeInput) -> object:
        events.append(f"sink-{node_input.payload}")
        return node_input.payload

    executor = NodeExecutor(
        nodes,
        config.system,
        config.runtime,
        {"fetch-rss": fast, "fetch-web": slow, "generate-advice": sink},
        graph.instances,
    )
    result = await DagRunner(executor).run(graph, "cycle", {})

    assert events.index("sink-fast") < events.index("slow-done")
    assert result.node_outputs["sink"].payload == ["fast", "slow"]


@pytest.mark.asyncio
async def test_sub_dag_execution() -> None:
    config = load_app_config(Path("config"))
    nodes = _condition_nodes()
    child = config.dags["default"].model_validate(
        {
            "name": "child",
            "nodes": [{"id": "source", "type": "rss-fetcher"}],
            "edges": [],
        }
    )
    parent = config.dags["default"].model_validate(
        {
            "name": "parent",
            "nodes": [{"id": "child-node", "type": "child"}],
            "edges": [],
        }
    )
    graph = load_graph(parent, {**nodes, "child": nodes["rss-fetcher"]})
    executor = NodeExecutor(
        {**nodes, "child": nodes["rss-fetcher"]},
        config.system,
        config.runtime,
        {"fetch-rss": _handler({"from": "child"})},
        graph.instances,
    )

    result = await DagRunner(executor, dags={"child": child}, nodes=nodes).run(graph, "cycle", {"seed": True})

    assert result.node_outputs["child-node"].payload == {"from": "child"}


@pytest.mark.asyncio
async def test_optional_node_and_fallback() -> None:
    config = load_app_config(Path("config"))
    nodes = _condition_nodes()
    graph = load_graph(
        config.dags["default"].model_validate(
            {
                "name": "optional-test",
                "nodes": [
                    {"id": "optional", "type": "rss-fetcher", "optional": True},
                    {"id": "fallback", "type": "advisor", "fallback": "skip"},
                    {"id": "sink", "type": "briefing-generator"},
                ],
                "edges": [
                    {"from": "optional", "to": "sink"},
                    {"from": "fallback", "to": "sink"},
                ],
            }
        ),
        nodes,
    )
    executor = NodeExecutor(
        nodes,
        config.system,
        config.runtime,
        {
            "fetch-rss": _failing_handler,
            "generate-advice": _failing_handler,
            "generate-briefing": _handler({"done": True}),
        },
        graph.instances,
    )

    result = await DagRunner(executor).run(graph, "cycle", {})

    assert result.node_outputs["optional"].ok is False
    assert result.node_outputs["fallback"].metadata["skipped"] is True
    assert result.node_outputs["sink"].payload == {"done": True}


@pytest.mark.asyncio
async def test_sub_dag_depth_and_cycle_rejected() -> None:
    config = load_app_config(Path("config"))
    nodes = _condition_nodes()
    child = config.dags["default"].model_validate(
        {"name": "child", "nodes": [{"id": "again", "type": "child"}], "edges": []}
    )
    parent = config.dags["default"].model_validate(
        {"name": "parent", "nodes": [{"id": "child-node", "type": "child"}], "edges": []}
    )
    graph = load_graph(parent, {**nodes, "child": nodes["rss-fetcher"]})
    executor = NodeExecutor({**nodes, "child": nodes["rss-fetcher"]}, config.system, config.runtime, {}, graph.instances)

    cycle = await DagRunner(executor, dags={"child": child}, nodes={**nodes, "child": nodes["rss-fetcher"]}).run(
        graph, "cycle", {}
    )
    assert cycle.node_outputs["child-node"].error == "sub DAG cycle: child -> child"

    executor.system.max_dag_depth = 1
    depth = await DagRunner(executor, dags={"child": child}, nodes={**nodes, "child": nodes["rss-fetcher"]}).run(
        graph, "cycle", {}
    )
    assert depth.node_outputs["child-node"].error == "max DAG depth exceeded: child"


def test_sub_dag_nesting_validation() -> None:
    config = load_app_config(Path("config"))
    child = config.dags["default"].model_validate(
        {"name": "child", "nodes": [{"id": "again", "type": "child"}], "edges": []}
    )
    parent = config.dags["default"].model_validate(
        {"name": "parent", "nodes": [{"id": "child-node", "type": "child"}], "edges": []}
    )
    with pytest.raises(DagError, match="sub DAG cycle: parent -> child -> child"):
        validate_sub_dag_nesting({"parent": parent, "child": child}, 3)
    with pytest.raises(DagError, match="max DAG depth exceeded: parent -> child"):
        validate_sub_dag_nesting({"parent": parent, "child": child.model_copy(update={"nodes": []})}, 1)


def test_cycle_rejected() -> None:
    config = load_app_config(Path("config"))
    graph = load_graph(config.dags["default"], config.nodes)
    notifier_id = _instance_id(graph, "notifier")
    fetcher_id = _instance_id(graph, "rss-fetcher")
    dag = config.dags["default"].model_copy(
        update={
            "edges": [
                *config.dags["default"].edges,
                {"from": notifier_id, "to": fetcher_id},
            ]
        }
    )
    with pytest.raises(DagError):
        load_graph(dag, config.nodes)


def _handler(value: object) -> FunctionHandler:
    async def handler(_node_input: NodeInput) -> object:
        await asyncio.sleep(0)
        return value

    return handler


async def _failing_handler(_node_input: NodeInput) -> object:
    raise RuntimeError("source failed")


def _instance_id(graph, node_type: str) -> str:
    return next(node_id for node_id, instance in graph.instances.items() if instance.type == node_type)


def _condition_nodes() -> dict[str, NodeConfig]:
    return {
        "rss-fetcher": NodeConfig(
            name="rss-fetcher",
            type="function",
            role="source",
            handler="fetch-rss",
            input_type="Any",
            output_type="Any",
        ),
        "advisor": NodeConfig(
            name="advisor",
            type="function",
            role="processor",
            handler="generate-advice",
            input_type="Any",
            output_type="Any",
        ),
        "web-scraper": NodeConfig(
            name="web-scraper",
            type="function",
            role="source",
            handler="fetch-web",
            input_type="Any",
            output_type="Any",
        ),
        "briefing-generator": NodeConfig(
            name="briefing-generator",
            type="function",
            role="processor",
            handler="generate-briefing",
            input_type="Any",
            output_type="Any",
        ),
    }
