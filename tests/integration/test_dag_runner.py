import asyncio
from pathlib import Path

import pytest

from stockimformation.config.loader import load_app_config
from stockimformation.dag.loader import load_graph, topological_layers
from stockimformation.dag.runner import DagRunner
from stockimformation.errors import DagError
from stockimformation.node.executor import NodeExecutor
from stockimformation.node.models import NodeInput


@pytest.mark.asyncio
async def test_default_dag_runs_with_fake_handlers() -> None:
    config = load_app_config(Path("config"))
    handlers = {
        "fetch-rss": _handler([{"url": "a"}]),
        "fetch-web": _handler([{"url": "a"}, {"url": "b"}]),
        "summarize": _handler([{"summary": "a"}]),
        "classify-sentiment": _handler([{"summary": "a"}]),
        "generate-advice": _handler([{"direction": "hold"}]),
        "generate-briefing": _handler({"content": "briefing"}),
        "notify-ntfy": _handler([{"skipped": True}]),
    }
    executor = NodeExecutor(config.nodes, config.system, config.runtime, handlers)
    graph = load_graph(config.dags["default"], config.nodes)
    result = await DagRunner(executor).run(graph, "cycle", {"source_names": ["sample-rss"]})
    assert result.payload == [{"skipped": True}]
    assert result.failures == {}


@pytest.mark.asyncio
async def test_single_source_failure_does_not_block() -> None:
    config = load_app_config(Path("config"))
    handlers = {
        "fetch-rss": _failing_handler,
        "fetch-web": _handler([{"url": "b"}]),
        "summarize": _handler([{"summary": "b"}]),
        "classify-sentiment": _handler([{"summary": "b"}]),
        "generate-advice": _handler([{"direction": "hold"}]),
        "generate-briefing": _handler({"content": "briefing"}),
        "notify-ntfy": _handler([{"skipped": True}]),
    }
    executor = NodeExecutor(config.nodes, config.system, config.runtime, handlers)
    graph = load_graph(config.dags["default"], config.nodes)
    result = await DagRunner(executor).run(graph, "cycle", {"source_names": ["sample-web"]})
    assert "rss-fetcher" in result.failures
    assert result.payload == [{"skipped": True}]


def test_topological_layers_have_parallel_sources() -> None:
    config = load_app_config(Path("config"))
    graph = load_graph(config.dags["default"], config.nodes)
    assert set(topological_layers(graph)[0]) == {"rss-fetcher", "web-scraper"}


def test_cycle_rejected() -> None:
    config = load_app_config(Path("config"))
    dag = config.dags["default"].model_copy(
        update={
            "edges": [
                *config.dags["default"].edges,
                {"from": "notifier", "to": "rss-fetcher"},
            ]
        }
    )
    with pytest.raises(DagError):
        load_graph(dag, config.nodes)


def _handler(value: object):
    async def handler(_node_input: NodeInput) -> object:
        await asyncio.sleep(0)
        return value

    return handler


async def _failing_handler(_node_input: NodeInput) -> object:
    raise RuntimeError("source failed")
