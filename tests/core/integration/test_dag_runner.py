import asyncio
import tempfile
from pathlib import Path
from threading import Thread

import pytest

from edera_core.bootstrap import load_installed_extensions
from edera_core.config.loader import _load_runtime_base_config, materialize_runtime_app_config
from edera_core.config.schema import DagConfig, NodeConfig, RuntimeSettings, SystemConfig
from edera_core.dag.loader import load_graph, topological_layers, validate_sub_dag_nesting
from edera_core.dag.runner import DagRunner, EdgeInputFact
from edera_core.errors import DagError
from edera_core.migration.migrate_extensions import migrate_existing_extensions
from edera_core.node.executor import NodeExecutor
from edera_core.node.models import FunctionHandler, NodeInput
from edera_core.storage import create_engine, init_db, session_factory, sqlite_url


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
            factory = session_factory(engine)
            async with factory() as session:
                await migrate_existing_extensions(
                    session,
                    [Path("extensions")],
                    handlers_dir=root / "handlers",
                    entity_types=config.entity_types,
                )
                bootstrap = await load_installed_extensions(session, root / "handlers")
                await session.commit()
            config.entity_types.update(bootstrap.entity_type_registry.as_dict())
            return await materialize_runtime_app_config(Path("config"), config, engine)
        finally:
            await engine.dispose()


@pytest.mark.asyncio
async def test_default_dag_runs_with_fake_handlers() -> None:
    config = _load_config()
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
    result = await DagRunner(executor).run(graph, "run", {"source_names": ["hn-rss"]})
    assert result.payload == [{"skipped": True}]
    assert result.failures == {}


@pytest.mark.asyncio
async def test_single_source_failure_does_not_block() -> None:
    config = _load_config()
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
    result = await DagRunner(executor).run(graph, "run", {"source_names": ["cls-telegraph"]})
    assert _instance_id(graph, "rss-fetcher") in result.failures
    assert result.payload == [{"skipped": True}]


def test_topological_layers_have_parallel_sources() -> None:
    config = _load_config()
    graph = load_graph(config.dags["default"], config.nodes)
    assert set(topological_layers(graph)[0]) == {
        _instance_id(graph, "rss-fetcher"),
        _instance_id(graph, "api-fetcher"),
    }


@pytest.mark.asyncio
async def test_node_entity_execution() -> None:
    config = _load_config()
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
    output = await executor.execute("rss-fetcher", NodeInput(run_id="run", payload={}))
    assert output.ok
    assert output.payload == [{"url": "a"}]


def test_dag_entity_loading() -> None:
    config = _load_config()
    graph = load_graph(config.dags["default"], config.nodes)
    first_layer = topological_layers(graph)[0]
    assert graph.name == "default"
    assert first_layer == sorted(first_layer)


@pytest.mark.asyncio
async def test_condition_branch() -> None:
    config = _load_config()
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
    result = await DagRunner(executor).run(graph, "run", {})

    assert set(result.node_outputs) == {"source", "negative", "positive"}


@pytest.mark.asyncio
async def test_dead_path_detection() -> None:
    config = _load_config()
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
    result = await DagRunner(executor).run(graph, "run", {})

    assert set(result.node_outputs) == {"source"}
    assert result.failures == {}
    assert result.warnings == ["dead path after source"]


@pytest.mark.asyncio
async def test_single_node_loop() -> None:
    config = _load_config()
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
    result = await DagRunner(executor).run(graph, "run", {"seed": True})

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
    config = _load_config()
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
    result = await DagRunner(executor).run(graph, "run", {})

    assert events.index("sink-fast") < events.index("slow-done")
    assert result.node_outputs["sink"].payload == ["fast", "slow"]


@pytest.mark.asyncio
async def test_event_driven_dispatch_does_not_wait_for_layer() -> None:
    config = _load_config()
    nodes = _condition_nodes()
    graph = load_graph(
        config.dags["default"].model_validate(
            {
                "name": "event-driven-test",
                "nodes": [
                    {"id": "fast", "type": "rss-fetcher"},
                    {"id": "slow", "type": "web-scraper"},
                    {"id": "sink", "type": "advisor"},
                ],
                "edges": [{"from": "fast", "to": "sink"}],
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

    async def sink(_node_input: NodeInput) -> object:
        events.append("sink-start")
        return "sink"

    executor = NodeExecutor(
        nodes,
        config.system,
        config.runtime,
        {"fetch-rss": fast, "fetch-web": slow, "generate-advice": sink},
        graph.instances,
    )
    await DagRunner(executor).run(graph, "run", {})

    assert events.index("sink-start") < events.index("slow-done")


@pytest.mark.asyncio
async def test_fan_in_barrier_waits_for_all_upstreams() -> None:
    config = _load_config()
    nodes = _condition_nodes()
    graph = load_graph(
        config.dags["default"].model_validate(
            {
                "name": "barrier-test",
                "nodes": [
                    {"id": "fast", "type": "rss-fetcher"},
                    {"id": "slow", "type": "web-scraper"},
                    {"id": "sink", "type": "advisor", "fan_in_mode": "barrier"},
                ],
                "edges": [{"from": "fast", "to": "sink"}, {"from": "slow", "to": "sink"}],
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
        events.append("sink-start")
        return node_input.payload

    executor = NodeExecutor(
        nodes,
        config.system,
        config.runtime,
        {"fetch-rss": fast, "fetch-web": slow, "generate-advice": sink},
        graph.instances,
    )
    result = await DagRunner(executor).run(graph, "run", {})

    assert events.index("slow-done") < events.index("sink-start")
    assert result.node_outputs["sink"].payload == ["fast", "slow"]


@pytest.mark.asyncio
async def test_fan_in_accumulate_spawns_per_upstream_task() -> None:
    config = _load_config()
    nodes = _condition_nodes()
    graph = load_graph(
        config.dags["default"].model_validate(
            {
                "name": "accumulate-test",
                "nodes": [
                    {"id": "fast", "type": "rss-fetcher"},
                    {"id": "slow", "type": "web-scraper"},
                    {"id": "sink", "type": "advisor", "fan_in_mode": "accumulate"},
                ],
                "edges": [{"from": "fast", "to": "sink"}, {"from": "slow", "to": "sink"}],
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
    result = await DagRunner(executor).run(graph, "run", {})

    assert events.index("sink-fast") < events.index("slow-done")
    assert result.node_outputs["sink"].payload == ["fast", "slow"]


@pytest.mark.asyncio
async def test_fan_out_splits_list_payload_to_concurrent_downstream_runs() -> None:
    config = _load_config()
    nodes = _condition_nodes()
    graph = load_graph(
        config.dags["default"].model_validate(
            {
                "name": "fan-out-test",
                "nodes": [{"id": "source", "type": "rss-fetcher"}, {"id": "sink", "type": "advisor"}],
                "edges": [{"from": "source", "to": "sink", "fan_out": True}],
            }
        ),
        nodes,
    )
    seen: list[int] = []

    async def source(_node_input: NodeInput) -> object:
        return list(range(10))

    async def sink(node_input: NodeInput) -> object:
        value = int(node_input.payload)
        seen.append(value)
        await asyncio.sleep(0.01 if value == 0 else 0)
        return value * 2

    executor = NodeExecutor(
        nodes,
        config.system,
        config.runtime,
        {"fetch-rss": source, "generate-advice": sink},
        graph.instances,
    )
    result = await DagRunner(executor).run(graph, "run", {})

    assert sorted(seen) == list(range(10))
    assert sorted(result.node_outputs["sink"].payload) == [value * 2 for value in range(10)]


@pytest.mark.asyncio
async def test_soft_stop_finishes_running_node_without_starting_downstream() -> None:
    config = _load_config()
    nodes = _condition_nodes()
    graph = load_graph(
        config.dags["default"].model_validate(
            {
                "name": "soft-stop-test",
                "nodes": [{"id": "source", "type": "rss-fetcher"}, {"id": "sink", "type": "advisor"}],
                "edges": [{"from": "source", "to": "sink"}],
            }
        ),
        nodes,
    )
    stop_event = asyncio.Event()
    source_started = asyncio.Event()

    async def source(_node_input: NodeInput) -> object:
        source_started.set()
        await asyncio.sleep(0.05)
        return "source"

    async def sink(_node_input: NodeInput) -> object:
        return "sink"

    executor = NodeExecutor(
        nodes,
        config.system,
        config.runtime,
        {"fetch-rss": source, "generate-advice": sink},
        graph.instances,
    )
    task = asyncio.create_task(DagRunner(executor).run(graph, "run", {}, stop_event=stop_event))
    await source_started.wait()
    stop_event.set()
    result = await task

    assert set(result.node_outputs) == {"source"}


@pytest.mark.asyncio
async def test_required_upstream_failure_does_not_record_summary_for_unstarted_node() -> None:
    nodes = {
        "source-type": NodeConfig(name="source-type", handler="source", input_type="Any", output_type="Any"),
        "other-type": NodeConfig(name="other-type", handler="other", input_type="Any", output_type="Any"),
        "sink-type": NodeConfig(name="sink-type", handler="sink", input_type="Any", output_type="Any"),
    }
    graph = load_graph(
        DagConfig.model_validate(
            {
                "name": "upstream-failed-summary-test",
                "nodes": [
                    {"id": "source", "type": "source-type"},
                    {"id": "other", "type": "other-type"},
                    {"id": "sink", "type": "sink-type"},
                ],
                "edges": [{"from": "source", "to": "sink"}],
            }
        ),
        nodes,
    )
    summaries: list[tuple[str, str]] = []

    async def source(_node_input: NodeInput) -> object:
        raise RuntimeError("source failed")

    async def sink(_node_input: NodeInput) -> object:
        return "unused"

    async def other(_node_input: NodeInput) -> object:
        return "ok"

    async def summary_recorder(run_id: str, node_id: str, _summary: dict[str, object]) -> None:
        summaries.append((run_id, node_id))

    executor = NodeExecutor(
        nodes,
        SystemConfig(),
        RuntimeSettings(),
        {"source": source, "other": other, "sink": sink},
        graph.instances,
        execution_summary_recorder=summary_recorder,
    )
    result = await DagRunner(executor).run(graph, "run", {})

    assert result.failures["source"] == "source failed"
    assert result.failures["sink"].startswith("required upstream failed")
    assert set(summaries) == {("run", "source"), ("run", "other")}


@pytest.mark.asyncio
async def test_retry_single_uses_prefilled_upstream_outputs() -> None:
    config = _load_config()
    nodes = _condition_nodes()
    graph = load_graph(
        config.dags["default"].model_validate(
            {
                "name": "retry-single-test",
                "nodes": [{"id": "source", "type": "rss-fetcher"}, {"id": "sink", "type": "advisor"}],
                "edges": [{"from": "source", "to": "sink"}],
            }
        ),
        nodes,
    )
    calls: list[str] = []

    async def source(_node_input: NodeInput) -> object:
        calls.append("source")
        return "new"

    async def sink(node_input: NodeInput) -> object:
        calls.append("sink")
        return {"input": node_input.payload}

    executor = NodeExecutor(
        nodes,
        config.system,
        config.runtime,
        {"fetch-rss": source, "generate-advice": sink},
        graph.instances,
    )
    result = await DagRunner(executor).run(
        graph,
        "retry",
        {},
        retry_nodes={"sink"},
        prefilled_outputs={"source": _node_output("source", "old")},
    )

    assert calls == ["sink"]
    assert result.node_outputs["sink"].payload == {"input": "old"}


@pytest.mark.asyncio
async def test_retry_single_multiple_nodes_propagates_new_outputs() -> None:
    config = _load_config()
    nodes = _condition_nodes()
    graph = load_graph(
        config.dags["default"].model_validate(
            {
                "name": "retry-single-multi-test",
                "nodes": [
                    {"id": "source", "type": "rss-fetcher"},
                    {"id": "middle", "type": "advisor"},
                    {"id": "sink", "type": "briefing-generator"},
                ],
                "edges": [{"from": "source", "to": "middle"}, {"from": "middle", "to": "sink"}],
            }
        ),
        nodes,
    )
    calls: list[str] = []

    async def source(_node_input: NodeInput) -> object:
        calls.append("source")
        return "new-source"

    async def middle(node_input: NodeInput) -> object:
        calls.append("middle")
        return {"middle": node_input.payload}

    async def sink(node_input: NodeInput) -> object:
        calls.append("sink")
        return {"sink": node_input.payload}

    executor = NodeExecutor(
        nodes,
        config.system,
        config.runtime,
        {"fetch-rss": source, "generate-advice": middle, "generate-briefing": sink},
        graph.instances,
    )
    result = await DagRunner(executor).run(
        graph,
        "retry",
        {},
        retry_nodes={"middle", "sink"},
        prefilled_outputs={"source": _node_output("source", "old-source")},
    )

    assert calls == ["middle", "sink"]
    assert result.node_outputs["sink"].payload == {"sink": {"middle": "old-source"}}


@pytest.mark.asyncio
async def test_retry_single_disconnected_nodes_run_independently() -> None:
    config = _load_config()
    nodes = _condition_nodes()
    graph = load_graph(
        config.dags["default"].model_validate(
            {
                "name": "retry-single-disconnected-test",
                "nodes": [
                    {"id": "source-a", "type": "rss-fetcher"},
                    {"id": "source-b", "type": "web-scraper"},
                    {"id": "sink-a", "type": "advisor"},
                    {"id": "sink-b", "type": "briefing-generator"},
                ],
                "edges": [{"from": "source-a", "to": "sink-a"}, {"from": "source-b", "to": "sink-b"}],
            }
        ),
        nodes,
    )
    calls: list[str] = []

    async def fetch_rss(_node_input: NodeInput) -> object:
        calls.append("source-a")
        return "new-a"

    async def fetch_web(_node_input: NodeInput) -> object:
        calls.append("source-b")
        return "new-b"

    async def sink_a(node_input: NodeInput) -> object:
        calls.append("sink-a")
        return {"a": node_input.payload}

    async def sink_b(node_input: NodeInput) -> object:
        calls.append("sink-b")
        return {"b": node_input.payload}

    executor = NodeExecutor(
        nodes,
        config.system,
        config.runtime,
        {"fetch-rss": fetch_rss, "fetch-web": fetch_web, "generate-advice": sink_a, "generate-briefing": sink_b},
        graph.instances,
    )
    result = await DagRunner(executor).run(
        graph,
        "retry",
        {},
        retry_nodes={"sink-a", "sink-b"},
        prefilled_outputs={
            "source-a": _node_output("source-a", "old-a"),
            "source-b": _node_output("source-b", "old-b"),
        },
    )

    assert set(calls) == {"sink-a", "sink-b"}
    assert result.node_outputs["sink-a"].payload == {"a": "old-a"}
    assert result.node_outputs["sink-b"].payload == {"b": "old-b"}


@pytest.mark.asyncio
async def test_retry_cascade_reruns_target_and_downstream_only() -> None:
    config = _load_config()
    nodes = _condition_nodes()
    graph = load_graph(
        config.dags["default"].model_validate(
            {
                "name": "retry-cascade-test",
                "nodes": [
                    {"id": "source", "type": "rss-fetcher"},
                    {"id": "middle", "type": "advisor"},
                    {"id": "sink", "type": "briefing-generator"},
                ],
                "edges": [{"from": "source", "to": "middle"}, {"from": "middle", "to": "sink"}],
            }
        ),
        nodes,
    )
    calls: list[str] = []

    async def source(_node_input: NodeInput) -> object:
        calls.append("source")
        return "new-source"

    async def middle(node_input: NodeInput) -> object:
        calls.append("middle")
        return {"middle": node_input.payload}

    async def sink(node_input: NodeInput) -> object:
        calls.append("sink")
        return {"sink": node_input.payload}

    executor = NodeExecutor(
        nodes,
        config.system,
        config.runtime,
        {"fetch-rss": source, "generate-advice": middle, "generate-briefing": sink},
        graph.instances,
    )
    result = await DagRunner(executor).run(
        graph,
        "retry",
        {},
        retry_nodes={"middle", "sink"},
        prefilled_outputs={"source": _node_output("source", "old-source")},
    )

    assert calls == ["middle", "sink"]
    assert result.node_outputs["sink"].payload == {"sink": {"middle": "old-source"}}


@pytest.mark.asyncio
async def test_sub_dag_execution() -> None:
    config = _load_config()
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
    node_runs: list[tuple[str, str, str, str | None, str | None, dict[str, object] | None]] = []

    result = await DagRunner(
        executor,
        recorder=lambda run_id, node, status, error, failure_kind, metadata: _append_async(
            node_runs, (run_id, node, status, error, failure_kind, metadata)
        ),
        dags={"child": child},
        nodes=nodes,
    ).run(graph, "run", {"seed": True})

    assert result.node_outputs["child-node"].payload == {"from": "child"}
    metadata = next(item[5] for item in node_runs if item[1] == "child-node" and item[2] == "succeeded")
    assert metadata is not None
    assert metadata["parent_run_id"] == "run"
    assert metadata["parent_node"] == "child-node"
    assert isinstance(metadata["sub_dag_run_id"], str)
    assert metadata["sub_dag_run_id"]
    assert ("run", "child-node", "succeeded") in {(item[0], item[1], item[2]) for item in node_runs}
    assert (metadata["sub_dag_run_id"], "source", "succeeded") in {(item[0], item[1], item[2]) for item in node_runs}


@pytest.mark.asyncio
async def test_explicit_sub_dag_execution_with_emit_callback() -> None:
    nodes = _condition_nodes()
    child = DagConfig.model_validate(
        {
            "name": "child",
            "nodes": [{"id": "source", "type": "rss-fetcher"}],
            "edges": [],
        }
    )
    parent = DagConfig.model_validate(
        {
            "name": "parent",
            "nodes": [{"id": "child-node", "type": "dag", "dag_ref": "child"}],
            "edges": [],
        }
    )
    graph = load_graph(parent, nodes, {"child": child})
    events: list[tuple[str, object]] = []
    executor = NodeExecutor(
        nodes,
        SystemConfig(),
        RuntimeSettings(),
        {"fetch-rss": _handler({"from": "child"})},
        graph.instances,
    )

    result = await DagRunner(
        executor,
        emit=lambda event, payload: _append_async(events, (event, payload)),
        dags={"child": child},
        nodes=nodes,
    ).run(graph, "run", {"seed": True})

    assert result.failures == {}
    assert result.node_outputs["child-node"].payload == {"from": "child"}
    assert events == []


@pytest.mark.asyncio
async def test_optional_failure_excluded_from_payload_and_required_failure_recorded() -> None:
    config = _load_config()
    nodes = {
        **_condition_nodes(),
        "source-a": NodeConfig(name="source-a", type="function", role="source", handler="source-a", input_type="Any", output_type="Any"),
    }
    graph = load_graph(
        config.dags["default"].model_validate(
            {
                "name": "optional-test",
                "nodes": [
                    {"id": "optional", "type": "rss-fetcher", "optional": True},
                    {"id": "required", "type": "advisor"},
                    {"id": "source", "type": "source-a"},
                    {"id": "sink", "type": "briefing-generator"},
                ],
                "edges": [
                    {"from": "optional", "to": "sink"},
                    {"from": "source", "to": "sink"},
                    {"from": "required", "to": "sink"},
                ],
            }
        ),
        nodes,
    )
    edge_facts: list[EdgeInputFact] = []
    node_runs: list[tuple[str, str, str, str | None, str | None, dict[str, object] | None]] = []
    executor = NodeExecutor(
        nodes,
        config.system,
        config.runtime,
        {
            "fetch-rss": _failing_handler,
            "generate-advice": _failing_handler,
            "source-a": _handler(["raw"]),
            "generate-briefing": _handler({"done": True}),
        },
        graph.instances,
    )

    result = await DagRunner(
        executor,
        recorder=lambda run_id, node, status, error, failure_kind, metadata: _append_async(
            node_runs, (run_id, node, status, error, failure_kind, metadata)
        ),
        edge_recorder=lambda fact: _append_async(edge_facts, fact),
    ).run(graph, "run", {})

    assert result.node_outputs["optional"].ok is False
    assert result.node_outputs["sink"].ok is False
    assert result.node_outputs["sink"].error and "required upstream failed" in result.node_outputs["sink"].error
    assert ("run", "sink", "failed", result.node_outputs["sink"].error, "upstream_failed", None) in node_runs
    assert {fact.from_node_id for fact in edge_facts if fact.to_node_id == "sink"} == {"optional", "required", "source"}
    optional_fact = next(fact for fact in edge_facts if fact.from_node_id == "optional" and fact.to_node_id == "sink")
    source_fact = next(fact for fact in edge_facts if fact.from_node_id == "source" and fact.to_node_id == "sink")
    assert optional_fact.status == "failed"
    assert optional_fact.error_summary == "source failed"
    assert source_fact.status == "available"
    assert source_fact.has_payload is True


def test_fallback_skip_is_rejected() -> None:
    config = _load_config()

    with pytest.raises(ValueError):
        config.dags["default"].model_validate(
            {
                "name": "invalid-fallback",
                "nodes": [{"id": "fallback", "type": "advisor", "fallback": "skip"}],
                "edges": [],
            }
        )


@pytest.mark.asyncio
async def test_sub_dag_depth_and_cycle_rejected() -> None:
    config = _load_config()
    nodes = _condition_nodes()
    child = config.dags["default"].model_validate(
        {"name": "child", "nodes": [{"id": "again", "type": "child"}], "edges": []}
    )
    parent = config.dags["default"].model_validate(
        {"name": "parent", "nodes": [{"id": "child-node", "type": "child"}], "edges": []}
    )
    graph = load_graph(parent, {**nodes, "child": nodes["rss-fetcher"]})
    executor = NodeExecutor({**nodes, "child": nodes["rss-fetcher"]}, config.system, config.runtime, {}, graph.instances)

    run = await DagRunner(executor, dags={"child": child}, nodes={**nodes, "child": nodes["rss-fetcher"]}).run(
        graph, "run", {}
    )
    assert "Sub DAG cycle detected" in run.node_outputs["child-node"].error
    assert "child-node" in run.node_outputs["child-node"].error

    executor.system.max_dag_depth = 1
    depth = await DagRunner(executor, dags={"child": child}, nodes={**nodes, "child": nodes["rss-fetcher"]}).run(
        graph, "run", {}
    )
    assert depth.node_outputs["child-node"].error == "max DAG depth exceeded: parent -> child"


@pytest.mark.asyncio
async def test_node_emits() -> None:
    config = _load_config()
    node = NodeConfig.model_validate(
        {
            "name": "sentiment",
            "type": "function",
            "handler": "sentiment",
            "input_type": "Any",
            "output_type": "Any",
            "emits": [{"event": "event:negative-news", "condition": "output.sentiment == 'negative'"}],
        }
    )
    dag = config.dags["default"].model_validate(
        {"name": "emits-test", "nodes": [{"id": "sentiment-1", "type": "sentiment"}], "edges": []}
    )
    graph = load_graph(dag, {"sentiment": node})
    events: list[tuple[str, object]] = []
    executor = NodeExecutor(
        {"sentiment": node},
        config.system,
        config.runtime,
        {"sentiment": _handler({"sentiment": "negative"})},
        graph.instances,
    )

    await DagRunner(executor, emit=lambda event, payload: _append_async(events, (event, payload))).run(graph, "run", {})

    assert events == [("event:negative-news", {"sentiment": "negative"})]


@pytest.mark.asyncio
async def test_node_emits_skip_false_conditions() -> None:
    config = _load_config()
    node = NodeConfig.model_validate(
        {
            "name": "sentiment",
            "type": "function",
            "handler": "sentiment",
            "input_type": "Any",
            "output_type": "Any",
            "emits": [{"event": "event:negative-news", "condition": "output.sentiment == 'negative'"}],
        }
    )
    dag = config.dags["default"].model_validate(
        {"name": "emits-test", "nodes": [{"id": "sentiment-1", "type": "sentiment"}], "edges": []}
    )
    graph = load_graph(dag, {"sentiment": node})
    events: list[tuple[str, object]] = []
    executor = NodeExecutor(
        {"sentiment": node},
        config.system,
        config.runtime,
        {"sentiment": _handler({"sentiment": "positive"})},
        graph.instances,
    )

    result = await DagRunner(executor, emit=lambda event, payload: _append_async(events, (event, payload))).run(
        graph,
        "run",
        {},
    )

    assert result.failures == {}
    assert events == []


@pytest.mark.asyncio
async def test_node_emits_evaluate_each_declaration() -> None:
    config = _load_config()
    node = NodeConfig.model_validate(
        {
            "name": "sentiment",
            "type": "function",
            "handler": "sentiment",
            "input_type": "Any",
            "output_type": "Any",
            "emits": [
                {"event": "event:any-news"},
                {"event": "event:negative-news", "condition": "output.sentiment == 'negative'"},
                {"event": "event:positive-news", "condition": "output.sentiment == 'positive'"},
            ],
        }
    )
    dag = config.dags["default"].model_validate(
        {"name": "emits-test", "nodes": [{"id": "sentiment-1", "type": "sentiment"}], "edges": []}
    )
    graph = load_graph(dag, {"sentiment": node})
    events: list[tuple[str, object]] = []
    executor = NodeExecutor(
        {"sentiment": node},
        config.system,
        config.runtime,
        {"sentiment": _handler({"sentiment": "negative"})},
        graph.instances,
    )

    await DagRunner(executor, emit=lambda event, payload: _append_async(events, (event, payload))).run(graph, "run", {})

    assert events == [
        ("event:any-news", {"sentiment": "negative"}),
        ("event:negative-news", {"sentiment": "negative"}),
    ]


@pytest.mark.asyncio
async def test_node_emits_condition_error_does_not_fail_dag() -> None:
    config = _load_config()
    node = NodeConfig.model_validate(
        {
            "name": "sentiment",
            "type": "function",
            "handler": "sentiment",
            "input_type": "Any",
            "output_type": "Any",
            "emits": [
                {"event": "event:broken", "condition": "unknown_name == 1"},
                {"event": "event:valid"},
            ],
        }
    )
    dag = config.dags["default"].model_validate(
        {"name": "emits-test", "nodes": [{"id": "sentiment-1", "type": "sentiment"}], "edges": []}
    )
    graph = load_graph(dag, {"sentiment": node})
    events: list[tuple[str, object]] = []
    executor = NodeExecutor(
        {"sentiment": node},
        config.system,
        config.runtime,
        {"sentiment": _handler({"sentiment": "negative"})},
        graph.instances,
    )

    result = await DagRunner(executor, emit=lambda event, payload: _append_async(events, (event, payload))).run(
        graph,
        "run",
        {},
    )

    assert result.failures == {}
    assert events == [("event:valid", {"sentiment": "negative"})]


@pytest.mark.asyncio
async def test_instance_emits_override_type_emits() -> None:
    config = _load_config()
    node = NodeConfig.model_validate(
        {
            "name": "sentiment",
            "type": "function",
            "handler": "sentiment",
            "input_type": "Any",
            "output_type": "Any",
            "emits": [{"event": "event:type-default"}],
        }
    )
    dag = config.dags["default"].model_validate(
        {
            "name": "emits-test",
            "nodes": [
                {
                    "id": "sentiment-1",
                    "type": "sentiment",
                    "config": {"emits": [{"event": "event:instance-override"}]},
                }
            ],
            "edges": [],
        }
    )
    graph = load_graph(dag, {"sentiment": node})
    events: list[tuple[str, object]] = []
    executor = NodeExecutor(
        {"sentiment": node},
        config.system,
        config.runtime,
        {"sentiment": _handler({"sentiment": "negative"})},
        graph.instances,
    )

    await DagRunner(executor, emit=lambda event, payload: _append_async(events, (event, payload))).run(graph, "run", {})

    assert events == [("event:instance-override", {"sentiment": "negative"})]


def test_sub_dag_nesting_validation() -> None:
    config = _load_config()
    child = config.dags["default"].model_validate(
        {"name": "child", "nodes": [{"id": "again", "type": "child"}], "edges": []}
    )
    parent = config.dags["default"].model_validate(
        {"name": "parent", "nodes": [{"id": "child-node", "type": "child"}], "edges": []}
    )
    with pytest.raises(DagError, match="Sub DAG cycle detected"):
        validate_sub_dag_nesting({"parent": parent, "child": child}, 3)
    with pytest.raises(DagError, match="max DAG depth exceeded: parent -> child"):
        validate_sub_dag_nesting({"parent": parent, "child": child.model_copy(update={"nodes": []})}, 1)


def test_cycle_rejected() -> None:
    config = _load_config()
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


async def _append_async(target: list, value: object) -> None:
    target.append(value)


async def _failing_handler(_node_input: NodeInput) -> object:
    raise RuntimeError("source failed")


def _node_output(node: str, payload: object):
    from edera_core.node.models import NodeOutput

    return NodeOutput(node_name=node, ok=True, payload=payload)


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
