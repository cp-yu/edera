import hashlib
from pathlib import Path

import pytest

from edera_core.config.entities import EntityStore
from edera_core.config.loader import load_app_config
from edera_core.config.schema import (
    DagNodeInstance,
    EntitiesConfig,
    EntityRelationsConfig,
    EntityTypeConfig,
    NodeConfig,
)
from edera_core.dag_controller import _record_raw_log
from edera_core.node.executor import NodeExecutor, _apply_instance_config
from edera_core.node.models import NodeContext, NodeInput
from edera_core.storage import create_engine, init_db, session_factory, sqlite_url
from edera_core.storage.repository import query_log_index
from edera_types import NodeOutput


@pytest.mark.asyncio
async def test_node_executor_function_handler_returns_json_payload() -> None:
    config = load_app_config(Path("config"))

    async def handler(node_input: NodeInput) -> dict[str, object]:
        return {"run": node_input.run_id, "value": node_input.payload}

    instance = DagNodeInstance(
        id="0194f7a6-7b17-7c01-b601-100000000001",
        type="rss-fetcher",
        alias="empty-rss-fetcher",
        config={"source_names": []},
    )
    executor = NodeExecutor(
        config.nodes,
        config.system,
        config.runtime,
        handlers={"fetch-rss": handler},
        instances={instance.id: instance},
    )
    output = await executor.execute(
        instance.id,
        NodeInput(run_id="run", payload={"source_names": []}),
    )
    assert output.ok
    assert output.payload == {"run": "run", "value": {"source_names": []}}


@pytest.mark.asyncio
async def test_node_executor_records_handler_node_output() -> None:
    config = load_app_config(Path("config"))
    recorded: list[tuple[str, str, str, object, str | None]] = []

    async def handler(_node_input: NodeInput) -> NodeOutput:
        return NodeOutput(node_name="report", ok=True, payload={"report_path": "/tmp/report.html"})

    async def recorder(
        run_id: str,
        node_id: str,
        entity_type: str,
        payload: object,
        session_id: str | None,
    ) -> None:
        recorded.append((run_id, node_id, entity_type, payload, session_id))

    node = NodeConfig(
        name="report-node",
        type="function",
        handler="report",
        input_type="Any",
        output_type="Any",
    )
    executor = NodeExecutor(
        {"report-node": node},
        config.system,
        config.runtime,
        handlers={"report": handler},
        output_recorder=recorder,
    )

    output = await executor.execute("report-node", NodeInput(run_id="run", payload={}))

    assert output.ok
    assert output.payload == {"report_path": "/tmp/report.html"}
    assert recorded == [("run", "report-node", "any", {"report_path": "/tmp/report.html"}, None)]


@pytest.mark.asyncio
async def test_node_executor_missing_skill_reports_name(tmp_path: Path) -> None:
    config = load_app_config(Path("config"))
    instance = DagNodeInstance(
        id="0194f7a6-7b17-7c01-b601-100000000002",
        type="rss-fetcher",
        alias="missing-handler-fetcher",
        config={"source_names": []},
    )
    executor = NodeExecutor(
        config.nodes,
        config.system,
        config.runtime,
        handlers={},
        instances={instance.id: instance},
        handlers_dir=tmp_path,
        skills_dir=tmp_path,
    )
    output = await executor.execute(
        instance.id,
        NodeInput(run_id="run", payload={"source_names": []}),
    )
    assert not output.ok
    assert "fetch-rss" in (output.error or "")


@pytest.mark.asyncio
async def test_node_entity_execution_uses_registry_module_cache(tmp_path: Path) -> None:
    config = load_app_config(Path("config"))
    handler = tmp_path / "dynamic.py"
    handler.write_text("async def run(ctx):\n    return {'version': 1}\n", encoding="utf-8")
    node = config.nodes["rss-fetcher"].model_copy(update={"handler": "dynamic"})
    from edera_core.registry import HandlerRegistry

    registry = HandlerRegistry()
    registry.register("dynamic", handler)
    executor = NodeExecutor({"rss-fetcher": node}, config.system, config.runtime, registry.seal())

    first = await executor.execute("rss-fetcher", NodeInput(run_id="run", payload={}))
    handler.write_text("async def run(ctx):\n    return {'version': 2}\n", encoding="utf-8")
    second = await executor.execute("rss-fetcher", NodeInput(run_id="run", payload={}))

    assert first.payload == {"version": 1}
    assert second.payload == {"version": 1}


@pytest.mark.asyncio
async def test_node_executor_prefers_node_entity() -> None:
    config = load_app_config(Path("config"))

    async def entity_handler(_node_input: NodeInput) -> dict[str, object]:
        return {"source": "entity"}

    async def legacy_handler(_node_input: NodeInput) -> dict[str, object]:
        return {"source": "legacy"}

    store = EntityStore(
        EntitiesConfig.model_validate(
            {
                "entities": [
                    {
                        "id": "entity-reader",
                        "type": "node",
                        "attributes": {
                            "name": "reader",
                            "type": "function",
                            "handler": "entity-handler",
                            "input_type": "RawItem",
                            "output_type": "AnalysisResult",
                        },
                    }
                ]
            }
        ),
        {"node": config.entity_types["node"]},
        EntityRelationsConfig(),
    )
    executor = NodeExecutor(
        {"reader": config.nodes["reader"].model_copy(update={"handler": "legacy-handler"})},
        config.system,
        config.runtime,
        handlers={"entity-handler": entity_handler, "legacy-handler": legacy_handler},
        entity_store=store,
    )

    output = await executor.execute("reader", NodeInput(run_id="run", payload={}))

    assert output.payload == {"source": "entity"}


@pytest.mark.asyncio
async def test_node_executor_reports_non_executable_entity() -> None:
    config = load_app_config(Path("config"))
    store = EntityStore(
        EntitiesConfig.model_validate(
            {
                "entities": [
                    {
                        "id": "metadata-node",
                        "type": "node",
                        "attributes": {
                            "name": "metadata",
                            "type": "function",
                            "input_type": "JsonObject",
                            "output_type": "JsonObject",
                        },
                    }
                ]
            }
        ),
        {
            "node": EntityTypeConfig.model_validate(
                {
                    "display_name": "Node",
                    "business_id_field": "name",
                    "display_template": "{name}",
                    "schema": {
                        "required": ["name", "type", "input_type", "output_type"],
                        "properties": {
                            "name": {"type": "string"},
                            "type": {"type": "string"},
                            "handler": {"type": "string"},
                            "system_prompt_file": {"type": "string"},
                            "input_type": {"type": "string"},
                            "output_type": {"type": "string"},
                        },
                    },
                }
            )
        },
        EntityRelationsConfig(),
    )
    executor = NodeExecutor({}, config.system, config.runtime, entity_store=store)

    output = await executor.execute("metadata", NodeInput(run_id="run", payload={}))

    assert not output.ok
    assert output.error == "handler not registered: metadata"


@pytest.mark.asyncio
async def test_system_zero_timeout_disables_wait_for() -> None:
    config = load_app_config(Path("config"))

    async def handler(_node_input: NodeInput) -> dict[str, object]:
        return {"ok": True}

    node = config.nodes["rss-fetcher"].model_copy(update={"timeout_seconds": None})
    system = config.system.model_copy(update={"llm_timeout_seconds": 0})
    executor = NodeExecutor(
        {"rss-fetcher": node},
        system,
        config.runtime,
        handlers={"fetch-rss": handler},
    )

    output = await executor.execute("rss-fetcher", NodeInput(run_id="run", payload={}))

    assert output.ok
    assert output.payload == {"ok": True}


@pytest.mark.asyncio
async def test_context_handler_receives_full_input_and_params(tmp_path: Path) -> None:
    config = load_app_config(Path("config"))
    handler = tmp_path / "handler.py"
    handler.write_text(
        "async def run(ctx):\n"
        "    ctx.input.metadata['failures'] = {'source': 'failed'}\n"
        "    return {'payload': ctx.input.payload, 'limit': ctx.params['limit']}\n",
        encoding="utf-8",
    )
    node = config.nodes["rss-fetcher"].model_copy(update={"parameters": {"limit": 2}})
    from edera_core.registry import HandlerRegistry

    registry = HandlerRegistry()
    registry.register("fetch-rss", handler)
    executor = NodeExecutor({"rss-fetcher": node}, config.system, config.runtime, registry.seal())
    node_input = NodeInput(run_id="run", payload={"source_names": ["hn-rss"]}, metadata={})

    output = await executor.execute("rss-fetcher", node_input)

    assert output.payload == {"payload": {"source_names": ["hn-rss"]}, "limit": 2}
    assert "failures" not in output.metadata


@pytest.mark.asyncio
async def test_context_handler_records_source_recovery(tmp_path: Path) -> None:
    config = load_app_config(Path("config"))
    handler = tmp_path / "handler.py"
    handler.write_text(
        "async def run(ctx):\n"
        "    await ctx.runtime.record_source_recovery('hn-rss', {'recovery_status': 'escalated'})\n"
        "    return {'ok': True}\n",
        encoding="utf-8",
    )
    recorded: list[tuple[str, str, str, dict[str, object]]] = []

    async def recorder(run_id: str, node_id: str, source_name: str, summary: dict[str, object]) -> None:
        recorded.append((run_id, node_id, source_name, summary))

    from edera_core.registry import HandlerRegistry

    registry = HandlerRegistry()
    registry.register("fetch-rss", handler)
    executor = NodeExecutor(
        {"rss-fetcher": config.nodes["rss-fetcher"]},
        config.system,
        config.runtime,
        registry.seal(),
        source_recovery_recorder=recorder,
    )

    output = await executor.execute("rss-fetcher", NodeInput(run_id="run", payload={}))

    assert output.ok
    assert recorded == [("run", "rss-fetcher", "hn-rss", {"recovery_status": "escalated"})]


@pytest.mark.asyncio
async def test_pi_node_requires_instance_model() -> None:
    config = load_app_config(Path("config"))
    node = NodeConfig(
        name="llm-node",
        type="function",
        handler="run-pi",
        input_type="Any",
        output_type="Any",
    )
    instance = DagNodeInstance(id="llm-1", type="llm-node", config={})
    executor = NodeExecutor(
        {"llm-node": node},
        config.system,
        config.runtime,
        handlers={"run-pi": _unused_handler},
        instances={instance.id: instance},
    )

    output = await executor.execute(instance.id, NodeInput(run_id="run", payload={}))

    assert not output.ok
    assert output.error == "model not configured for instance"


@pytest.mark.asyncio
async def test_instance_config_sets_model_tools_and_session_dir() -> None:
    config = load_app_config(Path("config"))
    node = NodeConfig(
        name="llm-node",
        type="function",
        handler="run-pi",
        tools=["bash"],
        input_type="Any",
        output_type="Any",
    )
    instance = DagNodeInstance(
        id="llm-1",
        type="llm-node",
        config={
            "model": "hf-share/deepseek-v4-flash",
            "tools": ["bash", "read"],
            "session_dir": "sandbox:llm-0:latest",
        },
    )
    effective = _apply_instance_config(node, instance)

    assert effective.parameters["model"] == "hf-share/deepseek-v4-flash"
    assert effective.parameters["session_dir"] == "sandbox:llm-0:latest"
    assert effective.tools == ["bash", "read"]


@pytest.mark.asyncio
async def test_agent_executor_records_raw_log_file(tmp_path: Path) -> None:
    config = load_app_config(Path("config"))
    pi = tmp_path / "pi"
    pi.write_text("#!/bin/sh\nprintf 'line one\\nline two\\n'\n", encoding="utf-8")
    pi.chmod(0o755)
    node = NodeConfig.model_validate(
        {
            "name": "agent-node",
            "type": "agent",
            "model": "test-model",
            "input_type": "Any",
            "output_type": "Any",
        }
    )
    runtime = config.runtime.model_copy(update={"pi_bin": str(pi)})
    records: list[tuple[str, str, str, str, int]] = []

    async def recorder(run_id: str, node_id: str, path: str, digest: str, size: int) -> None:
        records.append((run_id, node_id, path, digest, size))

    executor = NodeExecutor(
        {"agent-node": node},
        config.system,
        runtime,
        daemon_data_dir=tmp_path / "data",
        raw_log_recorder=recorder,
    )

    output = await executor.execute("agent-node", NodeInput(run_id="run-1", payload={}))

    assert output.ok
    assert output.payload["stdout"] == "line one\nline two"
    assert len(records) == 1
    run_id, node_id, log_path, digest, size = records[0]
    content = Path(log_path).read_bytes()
    assert run_id == "run-1"
    assert node_id == "agent-node"
    assert content == b"line one\nline two\n"
    assert digest == hashlib.sha256(content).hexdigest()
    assert size == len(content)


@pytest.mark.asyncio
async def test_raw_log_index_is_queryable(tmp_path: Path) -> None:
    engine = create_engine(sqlite_url(tmp_path / "edera.db"))
    try:
        await init_db(engine)
        factory = session_factory(engine)
        await _record_raw_log(factory, "run-1", "agent-node", "/tmp/stdout.log", "digest", 12)

        async with factory() as session:
            rows = await query_log_index(session, run_id="run-1", node_id="agent-node")

        assert len(rows) == 1
        assert rows[0].path == "/tmp/stdout.log"
        assert rows[0].digest == "digest"
        assert rows[0].size == 12
    finally:
        await engine.dispose()


async def _unused_handler(_node_input: NodeInput) -> dict[str, object]:
    return {}
