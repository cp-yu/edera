import asyncio
from pathlib import Path

import pytest

from stockimformation.config.entities import EntityStore
from stockimformation.config.loader import load_app_config
from stockimformation.config.schema import (
    DagNodeInstance,
    EntitiesConfig,
    EntityRelationsConfig,
    EntityTypeConfig,
)
from stockimformation.node.executor import NodeExecutor
from stockimformation.node.models import NodeContext, NodeInput


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


def test_llm_workspace_isolated_and_precreated(tmp_path: Path) -> None:
    config = load_app_config(Path("config"))
    system = config.system.model_copy(update={"workspace_root": tmp_path})
    node = config.nodes["reader"].model_copy(update={"type": "llm"})
    executor = NodeExecutor({"reader": node}, system, config.runtime)
    workspace = executor._prepare_workspace(node, NodeContext("cycle", "reader"))
    assert workspace == tmp_path / "cycle" / "reader-reader"
    assert (workspace / "sessions").is_dir()
    assert (workspace / "pi-home").is_dir()
    assert "list[AnalysisResult]" in (workspace / "AGENTS.md").read_text()
    assert (workspace / ".pi" / "SYSTEM.md").read_text()
    assert "defaultModel" in (workspace / ".pi" / "settings.json").read_text()


@pytest.mark.asyncio
async def test_node_entity_execution_reloads_handler_each_run(tmp_path: Path) -> None:
    config = load_app_config(Path("config"))
    handler = tmp_path / "dynamic.py"
    handler.write_text("async def run(node_input):\n    return {'version': 1}\n", encoding="utf-8")
    node = config.nodes["rss-fetcher"].model_copy(update={"handler": "dynamic"})
    executor = NodeExecutor({"rss-fetcher": node}, config.system, config.runtime, handlers_dir=tmp_path)

    first = await executor.execute("rss-fetcher", NodeInput(cycle_id="cycle", payload={}))
    handler.write_text("async def run(node_input):\n    return {'version': 2}\n", encoding="utf-8")
    second = await executor.execute("rss-fetcher", NodeInput(cycle_id="cycle", payload={}))

    assert first.payload == {"version": 1}
    assert second.payload == {"version": 2}


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
    assert output.error == "Entity is not executable: missing handler or system_prompt_file"


@pytest.mark.asyncio
async def test_node_executor_records_output_entity_type_and_session_id() -> None:
    config = load_app_config(Path("config"))
    recorded: list[tuple[str, str, str, object, str | None]] = []

    class Executor(NodeExecutor):
        async def _run_pi(self, *_args: object) -> tuple[object, str]:
            return {"summary": "ok"}, "/tmp/session"

    node = config.nodes["reader"].model_copy(update={"type": "llm", "output_type": "AnalysisResult"})
    executor = Executor(
        {"reader": node},
        config.system,
        config.runtime,
        output_recorder=lambda cycle_id, node_id, entity_type, payload, session_id: _record(
            recorded, cycle_id, node_id, entity_type, payload, session_id
        ),
    )

    output = await executor.execute("reader", NodeInput(cycle_id="cycle", payload={}))

    assert output.ok
    assert output.metadata["session_id"] == "/tmp/session"
    assert recorded == [("cycle", "reader", "analysis", {"summary": "ok"}, "/tmp/session")]


@pytest.mark.asyncio
async def test_system_zero_timeout_disables_wait_for() -> None:
    config = load_app_config(Path("config"))

    async def handler(_node_input: NodeInput) -> dict[str, object]:
        await asyncio.sleep(0.01)
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
async def test_three_argument_node_input_handler_receives_full_input() -> None:
    config = load_app_config(Path("config"))

    async def handler(
        node_input: NodeInput,
        parameters: dict[str, object],
        _context: NodeContext,
    ) -> dict[str, object]:
        node_input.metadata["failures"] = {"source": "failed"}
        return {"payload": node_input.payload, "limit": parameters["limit"]}

    node = config.nodes["rss-fetcher"].model_copy(update={"parameters": {"limit": 2}})
    executor = NodeExecutor({"rss-fetcher": node}, config.system, config.runtime, handlers={"fetch-rss": handler})
    node_input = NodeInput(cycle_id="cycle", payload={"source_names": ["hn-rss"]}, metadata={})

    output = await executor.execute("rss-fetcher", node_input)

    assert output.payload == {"payload": {"source_names": ["hn-rss"]}, "limit": 2}
    assert output.metadata["failures"] == {"source": "failed"}


async def _record(
    recorded: list[tuple[str, str, str, object, str | None]],
    cycle_id: str,
    node_id: str,
    entity_type: str,
    payload: object,
    session_id: str | None,
) -> None:
    recorded.append((cycle_id, node_id, entity_type, payload, session_id))
