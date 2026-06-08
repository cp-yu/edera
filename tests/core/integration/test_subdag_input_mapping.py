import builtins
import tempfile
from pathlib import Path

import pytest

from edera_core.config.entities import EntityStore
from edera_core.config.loader import _default_core_entity_types
from edera_core.config.schema import DagConfig, EntitiesConfig, EntityConfig, EntityRelationsConfig, NodeConfig, RuntimeSettings, SystemConfig
from edera_core.dag.loader import load_graph
from edera_core.dag.runner import DagRunner
from edera_core.node.executor import NodeExecutor
from edera_core.node.models import FunctionHandler, NodeInput
from edera_core.resolver import HandlerMeta, StaticHandlerResolver
from edera_core.snapshot import DagExecutionClosure, DagExecutionSnapshot


def _nodes() -> dict[str, NodeConfig]:
    return {
        "parent-node": NodeConfig(
            name="parent-node",
            type="function",
            role="source",
            handler="parent-handler",
            input_type="Any",
            output_type="Any",
        ),
        "child-source": NodeConfig(
            name="child-source",
            type="function",
            role="source",
            handler="child-handler",
            input_type="Any",
            output_type="Any",
        ),
    }


def _parent(input_mapping: object) -> DagConfig:
    return DagConfig.model_validate(
        {
            "name": "parent",
            "nodes": [
                {"id": "parent", "type": "parent-node"},
                {"id": "child", "type": "dag", "dag_ref": "child", "input_mapping": input_mapping},
            ],
            "edges": [{"from": "parent", "to": "child"}],
        }
    )


def _child() -> DagConfig:
    return DagConfig.model_validate(
        {
            "name": "child",
            "nodes": [{"id": "child-source", "type": "child-source"}],
            "edges": [],
        }
    )


def _executor(seen: dict[str, object], store: EntityStore | None = None) -> NodeExecutor:
    async def parent_handler(_node_input: NodeInput) -> object:
        return {"output": {"symbol": "AAPL", "config": {"limit": 3}}}

    async def child_handler(node_input: NodeInput) -> object:
        seen["child-source"] = node_input.payload
        return node_input.payload

    handlers: dict[str, FunctionHandler] = {
        "parent-handler": parent_handler,
        "child-handler": child_handler,
    }
    return NodeExecutor(_nodes(), SystemConfig(), RuntimeSettings(), _test_snapshot(handlers), entity_store=store)


def _test_snapshot(handlers: dict[str, FunctionHandler]) -> DagExecutionSnapshot:
    entries: dict[str, HandlerMeta] = {}
    root = Path(tempfile.mkdtemp(prefix="edera-subdag-mapping-"))
    for name, handler in handlers.items():
        attr = f"_edera_subdag_mapping_handler_{id(handler)}"
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
async def test_input_mapping_dict() -> None:
    seen: dict[str, object] = {}
    dags = {"parent": _parent({"symbol": "output.symbol"}), "child": _child()}
    graph = load_graph(dags["parent"], _nodes(), dags)

    await DagRunner(_executor(seen), dags=dags).run(graph, "run", {})

    assert seen["child-source"] == {"symbol": "AAPL"}


@pytest.mark.asyncio
async def test_input_mapping_entity() -> None:
    seen: dict[str, object] = {}
    entity_types = _default_core_entity_types()
    store = EntityStore(
        EntitiesConfig(
            entities=[
                EntityConfig(
                    id="scoring-mapping",
                    type="input_mapping",
                    attributes={"name": "scoring-mapping", "shared": {"symbol": "output.symbol"}},
                )
            ]
        ),
        entity_types,
        EntityRelationsConfig(),
    )
    dags = {"parent": _parent("entity://scoring-mapping"), "child": _child()}
    graph = load_graph(dags["parent"], _nodes(), dags)

    await DagRunner(_executor(seen, store), dags=dags).run(graph, "run", {})

    assert seen["child-source"] == {"symbol": "AAPL"}


@pytest.mark.asyncio
async def test_mapping_application() -> None:
    seen: dict[str, object] = {}
    entity_types = _default_core_entity_types()
    store = EntityStore(
        EntitiesConfig(
            entities=[
                EntityConfig(
                    id="scoring-mapping",
                    type="input_mapping",
                    attributes={
                        "name": "scoring-mapping",
                        "shared": {"symbol": "output.symbol"},
                        "nodes": {"child-source": {"limit": "output.config.limit"}},
                        "append_nodes": ["child-source"],
                    },
                )
            ]
        ),
        entity_types,
        EntityRelationsConfig(),
    )
    dags = {"parent": _parent("entity://scoring-mapping"), "child": _child()}
    graph = load_graph(dags["parent"], _nodes(), dags)

    await DagRunner(_executor(seen, store), dags=dags).run(graph, "run", {})

    assert seen["child-source"] == {"symbol": "AAPL", "limit": 3}


@pytest.mark.asyncio
async def test_input_mapping_entity_node_string_mapping() -> None:
    seen: dict[str, object] = {}
    entity_types = _default_core_entity_types()
    store = EntityStore(
        EntitiesConfig(
            entities=[
                EntityConfig(
                    id="scoring-mapping",
                    type="input_mapping",
                    attributes={
                        "name": "scoring-mapping",
                        "nodes": {"child-source": "output.config"},
                    },
                )
            ]
        ),
        entity_types,
        EntityRelationsConfig(),
    )
    dags = {"parent": _parent("entity://scoring-mapping"), "child": _child()}
    graph = load_graph(dags["parent"], _nodes(), dags)

    await DagRunner(_executor(seen, store), dags=dags).run(graph, "run", {})

    assert seen["child-source"] == {"limit": 3}


@pytest.mark.asyncio
async def test_input_mapping_entity_node_string_mapping_missing_path_skips_node_input() -> None:
    seen: dict[str, object] = {}
    entity_types = _default_core_entity_types()
    store = EntityStore(
        EntitiesConfig(
            entities=[
                EntityConfig(
                    id="scoring-mapping",
                    type="input_mapping",
                    attributes={
                        "name": "scoring-mapping",
                        "nodes": {"child-source": "output.missing"},
                    },
                )
            ]
        ),
        entity_types,
        EntityRelationsConfig(),
    )
    dags = {"parent": _parent("entity://scoring-mapping"), "child": _child()}
    graph = load_graph(dags["parent"], _nodes(), dags)

    await DagRunner(_executor(seen, store), dags=dags).run(graph, "run", {})

    assert seen["child-source"] == {"output": {"symbol": "AAPL", "config": {"limit": 3}}}
