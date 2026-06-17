import asyncio
import builtins
import tempfile
from pathlib import Path
from threading import Thread

import pytest

from edera_core.config.entities import EntityStore
from edera_core.config.loader import _load_runtime_base_config, materialize_runtime_app_config
from edera_core.config.schema import EntitiesConfig, EntityConfig, NodeConfig
from edera_core.dag.loader import load_graph
from edera_core.dag.resources import clear_semaphore_cache
from edera_core.dag.runner import DagRunner
from edera_core.extension_manager import ExtensionManager
from edera_core.node.executor import NodeExecutor
from edera_core.node.models import NodeInput
from edera_core.resolver import HandlerMeta, StaticHandlerResolver
from edera_core.snapshot import DagExecutionClosure, DagExecutionSnapshot
from edera_core.storage import create_engine, init_db, sqlite_url


@pytest.fixture(autouse=True)
def _clear_resource_semaphores() -> None:
    clear_semaphore_cache()


def _load_config():
    result: dict[str, object] = {}

    def run() -> None:
        try:
            result["config"] = asyncio.run(_load_runtime_config())
        except BaseException as exc:
            result["error"] = exc

    thread = Thread(target=run)
    thread.start()
    thread.join()
    error = result.get("error")
    if isinstance(error, BaseException):
        raise error
    return result["config"]


async def _load_runtime_config():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        engine = create_engine(sqlite_url(root / "edera.db"))
        try:
            await init_db(engine)
            config = _load_runtime_base_config(Path("config"))
            await _install_default_extensions(engine, root / "handlers", config.entity_types)
            return await materialize_runtime_app_config(Path("config"), config, engine)
        finally:
            await engine.dispose()


async def _install_default_extensions(engine, handlers_dir: Path, entity_types: dict[str, object]) -> None:
    manager = ExtensionManager(
        extensions_dir=Path("extensions"),
        handlers_dir=handlers_dir,
        engine=engine,
        config_entity_types=entity_types,
    )
    await manager.install("default-news-workflow")


def _test_snapshot(handlers: dict[str, object]) -> DagExecutionSnapshot:
    entries: dict[str, HandlerMeta] = {}
    root = Path(tempfile.mkdtemp(prefix="edera-handlers-"))
    for name, handler in handlers.items():
        attr = f"_edera_loop_handler_{id(handler)}"
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


def _nodes():
    return {
        "rss-fetcher": NodeConfig(
            name="rss-fetcher",
            type="function",
            role="source",
            handler="fetch-rss",
            input_type="Any",
            output_type="Any",
        ),
    }


def _resource_store(permits: int) -> EntityStore:
    config = _load_config()
    entities = config.entities.model_copy(deep=True)
    entities.entities = [e for e in entities.entities if not (e.type == "resource" and e.id == "test_resource")]
    entities.entities.append(EntityConfig(id="test_resource", type="resource", attributes={"permits": permits}))
    return EntityStore(entities, config.entity_types, config.entity_relations)


@pytest.mark.asyncio
async def test_parallel_until_short_circuit() -> None:
    config = _load_config()
    nodes = _nodes()
    graph = load_graph(
        config.dags["default"].model_validate(
            {
                "name": "until-test",
                "nodes": [
                    {"id": "loop", "type": "rss-fetcher", "loop": {"mode": "parallel", "count": 5, "until": "output.value > 7"}},
                ],
                "edges": [],
            }
        ),
        nodes,
    )
    counter = {"val": 0}

    async def handler(_node_input: NodeInput) -> object:
        import random
        idx = counter["val"]
        counter["val"] += 1
        await asyncio.sleep(random.uniform(0.01, 0.05))
        value = idx * 3
        return {"value": value}

    executor = NodeExecutor(nodes, config.system, config.runtime, _test_snapshot({"fetch-rss": handler}), graph.instances)
    result = await DagRunner(executor).run(graph, "run")

    assert result.node_outputs["loop"].ok
    assert result.node_outputs["loop"].metadata["loop_until_matched"] is True
    assert len(result.node_outputs["loop"].payload) == 1
    assert result.node_outputs["loop"].payload[0]["value"] > 7


@pytest.mark.asyncio
async def test_parallel_until_not_matched() -> None:
    config = _load_config()
    nodes = _nodes()
    graph = load_graph(
        config.dags["default"].model_validate(
            {
                "name": "until-not-matched",
                "nodes": [
                    {"id": "loop", "type": "rss-fetcher", "loop": {"mode": "parallel", "count": 3, "until": "output.match == True"}},
                ],
                "edges": [],
            }
        ),
        nodes,
    )

    async def handler(_node_input: NodeInput) -> object:
        await asyncio.sleep(0.01)
        return {"match": False}

    executor = NodeExecutor(nodes, config.system, config.runtime, _test_snapshot({"fetch-rss": handler}), graph.instances)
    result = await DagRunner(executor).run(graph, "run")

    assert result.node_outputs["loop"].ok
    assert result.node_outputs["loop"].metadata["loop_until_matched"] is False
    assert len(result.node_outputs["loop"].payload) == 3


@pytest.mark.asyncio
async def test_parallel_output_is_list() -> None:
    config = _load_config()
    nodes = _nodes()
    graph = load_graph(
        config.dags["default"].model_validate(
            {
                "name": "output-list",
                "nodes": [
                    {"id": "loop", "type": "rss-fetcher", "loop": {"mode": "parallel", "count": 2}},
                ],
                "edges": [],
            }
        ),
        nodes,
    )

    async def handler(_node_input: NodeInput) -> object:
        return {"value": 1}

    executor = NodeExecutor(nodes, config.system, config.runtime, _test_snapshot({"fetch-rss": handler}), graph.instances)
    result = await DagRunner(executor).run(graph, "run")

    assert isinstance(result.node_outputs["loop"].payload, list)
    assert len(result.node_outputs["loop"].payload) == 2


@pytest.mark.asyncio
async def test_loop_iteration_level_resource() -> None:
    config = _load_config()
    nodes = _nodes()
    graph = load_graph(
        config.dags["default"].model_validate(
            {
                "name": "loop-resource",
                "nodes": [
                    {"id": "loop", "type": "rss-fetcher", "loop": {"mode": "parallel", "count": 5}, "resource": "test_resource"},
                ],
                "edges": [],
            }
        ),
        nodes,
    )
    active = 0
    max_active = 0

    async def handler(_node_input: NodeInput) -> object:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.02)
        active -= 1
        return {"value": 1}

    executor = NodeExecutor(nodes, config.system, config.runtime, _test_snapshot({"fetch-rss": handler}), graph.instances, _resource_store(2))
    result = await DagRunner(executor).run(graph, "run")

    assert result.node_outputs["loop"].ok
    assert max_active == 2
    assert len(result.node_outputs["loop"].payload) == 5


@pytest.mark.asyncio
async def test_loop_permits_one_no_deadlock() -> None:
    config = _load_config()
    nodes = _nodes()
    graph = load_graph(
        config.dags["default"].model_validate(
            {
                "name": "loop-permits-one",
                "nodes": [
                    {"id": "loop", "type": "rss-fetcher", "loop": {"mode": "parallel", "count": 3}, "resource": "test_resource"},
                ],
                "edges": [],
            }
        ),
        nodes,
    )

    async def handler(_node_input: NodeInput) -> object:
        await asyncio.sleep(0.01)
        return {"value": 1}

    executor = NodeExecutor(nodes, config.system, config.runtime, _test_snapshot({"fetch-rss": handler}), graph.instances, _resource_store(1))
    result = await DagRunner(executor).run(graph, "run")

    assert result.node_outputs["loop"].ok
    assert len(result.node_outputs["loop"].payload) == 3


@pytest.mark.asyncio
async def test_serial_loop_iteration_level_resource() -> None:
    config = _load_config()
    nodes = _nodes()
    graph = load_graph(
        config.dags["default"].model_validate(
            {
                "name": "serial-loop-resource",
                "nodes": [
                    {"id": "loop", "type": "rss-fetcher", "loop": {"mode": "serial", "count": 3}, "resource": "test_resource"},
                ],
                "edges": [],
            }
        ),
        nodes,
    )
    iterations = []

    async def handler(_node_input: NodeInput) -> object:
        iterations.append(len(iterations) + 1)
        await asyncio.sleep(0.01)
        return {"iteration": len(iterations)}

    executor = NodeExecutor(nodes, config.system, config.runtime, _test_snapshot({"fetch-rss": handler}), graph.instances, _resource_store(1))
    result = await DagRunner(executor).run(graph, "run")

    assert result.node_outputs["loop"].ok
    assert iterations == [1, 2, 3]
