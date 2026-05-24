from pathlib import Path

import pytest

from stockimformation_core.config.entities import EntityStore
from stockimformation_core.config.loader import load_app_config
from stockimformation_core.config.schema import (
    DagNodeInstance,
    EntitiesConfig,
    EntityRelationsConfig,
    EntityTypeConfig,
    NodeConfig,
)
from stockimformation_core.node.executor import NodeExecutor, _apply_instance_config
from stockimformation_core.node.models import NodeContext, NodeInput


@pytest.mark.asyncio
async def test_node_executor_function_handler_returns_json_payload() -> None:
    config = load_app_config(Path("config"))

    async def handler(node_input: NodeInput) -> dict[str, object]:
        return {"cycle": node_input.cycle_id, "value": node_input.payload}

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
        NodeInput(cycle_id="cycle", payload={"source_names": []}),
    )
    assert output.ok
    assert output.payload == {"cycle": "cycle", "value": {"source_names": []}}


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
        NodeInput(cycle_id="cycle", payload={"source_names": []}),
    )
    assert not output.ok
    assert "fetch-rss" in (output.error or "")


@pytest.mark.asyncio
async def test_node_entity_execution_uses_registry_module_cache(tmp_path: Path) -> None:
    config = load_app_config(Path("config"))
    handler = tmp_path / "dynamic.py"
    handler.write_text("async def run(ctx):\n    return {'version': 1}\n", encoding="utf-8")
    node = config.nodes["rss-fetcher"].model_copy(update={"handler": "dynamic"})
    from stockimformation_core.registry import HandlerRegistry

    registry = HandlerRegistry()
    registry.register("dynamic", handler)
    executor = NodeExecutor({"rss-fetcher": node}, config.system, config.runtime, registry.seal())

    first = await executor.execute("rss-fetcher", NodeInput(cycle_id="cycle", payload={}))
    handler.write_text("async def run(ctx):\n    return {'version': 2}\n", encoding="utf-8")
    second = await executor.execute("rss-fetcher", NodeInput(cycle_id="cycle", payload={}))

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

    output = await executor.execute("reader", NodeInput(cycle_id="cycle", payload={}))

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

    output = await executor.execute("metadata", NodeInput(cycle_id="cycle", payload={}))

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

    output = await executor.execute("rss-fetcher", NodeInput(cycle_id="cycle", payload={}))

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
    from stockimformation_core.registry import HandlerRegistry

    registry = HandlerRegistry()
    registry.register("fetch-rss", handler)
    executor = NodeExecutor({"rss-fetcher": node}, config.system, config.runtime, registry.seal())
    node_input = NodeInput(cycle_id="cycle", payload={"source_names": ["hn-rss"]}, metadata={})

    output = await executor.execute("rss-fetcher", node_input)

    assert output.payload == {"payload": {"source_names": ["hn-rss"]}, "limit": 2}
    assert output.metadata["failures"] == {"source": "failed"}


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

    output = await executor.execute(instance.id, NodeInput(cycle_id="cycle", payload={}))

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


async def _unused_handler(_node_input: NodeInput) -> dict[str, object]:
    return {}
