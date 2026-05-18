from pathlib import Path

import pytest

from stockimformation.config.loader import load_app_config
from stockimformation.config.schema import DagNodeInstance
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
