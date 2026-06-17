import builtins
import tempfile
from pathlib import Path

import pytest

from edera_core.config.schema import DagConfig, NodeConfig, RuntimeSettings, SystemConfig
from edera_core.dag.loader import load_graph
from edera_core.dag.runner import DagRunner
from edera_core.node.executor import NodeExecutor
from edera_core.node.models import FunctionHandler, NodeInput
from edera_core.resolver import HandlerMeta, StaticHandlerResolver
from edera_core.snapshot import DagExecutionClosure, DagExecutionSnapshot


def _nodes() -> dict[str, NodeConfig]:
    return {
        "source": NodeConfig(
            name="source",
            type="function",
            role="source",
            handler="source-handler",
            input_type="Any",
            output_type="Any",
        ),
        "worker": NodeConfig(
            name="worker",
            type="function",
            role="processor",
            handler="worker-handler",
            input_type="Any",
            output_type="Any",
        ),
    }


def _dag(edges: list[dict[str, str]] | None = None) -> DagConfig:
    return DagConfig.model_validate(
        {
            "name": "input-test",
            "nodes": [{"id": "source", "type": "source"}, {"id": "worker", "type": "worker"}],
            "edges": edges or [],
        }
    )


def _executor(seen: dict[str, object]) -> NodeExecutor:
    async def source_handler(node_input: NodeInput) -> object:
        seen["source"] = node_input.payload
        return node_input.payload

    async def worker_handler(node_input: NodeInput) -> object:
        seen["worker"] = node_input.payload
        return node_input.payload

    handlers = {
        "source-handler": source_handler,
        "worker-handler": worker_handler,
    }
    return NodeExecutor(_nodes(), SystemConfig(), RuntimeSettings(), _test_snapshot(handlers))


def _test_snapshot(handlers: dict[str, FunctionHandler]) -> DagExecutionSnapshot:
    entries: dict[str, HandlerMeta] = {}
    root = Path(tempfile.mkdtemp(prefix="edera-input-resolution-"))
    for name, handler in handlers.items():
        attr = f"_edera_input_resolution_handler_{id(handler)}"
        setattr(builtins, attr, handler)
        path = root / f"{name}.py"
        path.write_text(
            "import builtins\n"
            "async def run(ctx):\n"
            f"    return await builtins.{attr}(ctx.input)\n",
            encoding="utf-8",
        )
        entries[name] = HandlerMeta(path)
    return DagExecutionSnapshot(
        DagExecutionClosure("test", {}, {}),
        {},
        StaticHandlerResolver(entries),
        {},
        {},
    )


@pytest.mark.asyncio
async def test_source_no_temp_input() -> None:
    seen: dict[str, object] = {}
    graph = load_graph(_dag(), _nodes())
    graph.instances["source"].config["default_entity"] = {"symbol": "AAPL"}

    result = await DagRunner(_executor(seen)).run(graph, "run")

    assert result.node_outputs["source"].payload == {"symbol": "AAPL"}


@pytest.mark.asyncio
async def test_source_no_temp_input_no_default_is_none() -> None:
    seen: dict[str, object] = {}
    graph = load_graph(_dag(), _nodes())

    result = await DagRunner(_executor(seen)).run(graph, "run")

    assert result.node_outputs["source"].payload is None


@pytest.mark.asyncio
async def test_node_inputs_replace() -> None:
    seen: dict[str, object] = {}
    graph = load_graph(_dag(), _nodes())
    graph.instances["source"].config["default_entity"] = {"symbol": "AAPL"}

    await DagRunner(_executor(seen)).run(
        graph,
        "run",
        node_inputs={"source": {"symbol": "MSFT"}},
    )

    assert seen["source"] == {"symbol": "MSFT"}


@pytest.mark.asyncio
async def test_node_inputs_append() -> None:
    seen: dict[str, object] = {}
    graph = load_graph(_dag(), _nodes())
    graph.instances["source"].config["default_entity"] = {"symbol": "AAPL", "limit": 10}

    await DagRunner(_executor(seen)).run(
        graph,
        "run",
        node_inputs={"source": {"limit": 5}},
        append_nodes={"source"},
    )

    assert seen["source"] == {"symbol": "AAPL", "limit": 5}


@pytest.mark.asyncio
async def test_source_shared_inputs() -> None:
    seen: dict[str, object] = {}
    graph = load_graph(_dag([{"from": "source", "to": "worker"}]), _nodes())
    graph.instances["source"].config["default_entity"] = {"source": "default"}
    graph.instances["worker"].config["default_entity"] = {"worker": "default"}

    await DagRunner(_executor(seen)).run(
        graph,
        "run",
        source_shared_inputs={"shared": True},
    )

    assert seen["source"] == {"shared": True}
    assert seen["worker"] == {"shared": True}


@pytest.mark.asyncio
async def test_non_source_node_inputs_replace() -> None:
    seen: dict[str, object] = {}
    graph = load_graph(_dag([{"from": "source", "to": "worker"}]), _nodes())

    await DagRunner(_executor(seen)).run(
        graph,
        "run",
        node_inputs={"worker": {"override": True}},
    )

    assert seen["worker"] == {"override": True}


@pytest.mark.asyncio
async def test_non_source_node_inputs_append() -> None:
    seen: dict[str, object] = {}
    graph = load_graph(_dag([{"from": "source", "to": "worker"}]), _nodes())

    await DagRunner(_executor(seen)).run(
        graph,
        "run",
        source_shared_inputs={"limit": 10, "symbol": "AAPL"},
        node_inputs={"worker": {"limit": 5}},
        append_nodes={"worker"},
    )

    assert seen["worker"] == {"limit": 5, "symbol": "AAPL"}


@pytest.mark.asyncio
async def test_non_source_ignores_source_shared_inputs_without_node_override() -> None:
    seen: dict[str, object] = {}
    graph = load_graph(_dag([{"from": "source", "to": "worker"}]), _nodes())
    graph.instances["source"].config["default_entity"] = {"source": "default"}

    await DagRunner(_executor(seen)).run(
        graph,
        "run",
        source_shared_inputs={"shared": True},
    )

    assert seen["worker"] == {"shared": True}


@pytest.mark.asyncio
async def test_node_inputs_override_source_shared_inputs() -> None:
    seen: dict[str, object] = {}
    graph = load_graph(_dag([{"from": "source", "to": "worker"}]), _nodes())
    graph.instances["source"].config["default_entity"] = {"source": "default"}

    await DagRunner(_executor(seen)).run(
        graph,
        "run",
        source_shared_inputs={"shared": True},
        node_inputs={"source": {"symbol": "MSFT"}},
    )

    assert seen["source"] == {"symbol": "MSFT"}
    assert seen["worker"] == {"symbol": "MSFT"}


def test_shallow_merge() -> None:
    assert DagRunner._merge({"outer": {"a": 1}, "keep": True}, {"outer": {"b": 2}}) == {
        "outer": {"b": 2},
        "keep": True,
    }
