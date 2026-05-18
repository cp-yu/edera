from datetime import datetime, timezone
from pathlib import Path

import pytest

from stockimformation.config.loader import load_app_config
from stockimformation.dag.loader import load_graph
from stockimformation.dag.runner import DagRunner
from stockimformation.models.entities import RawItem
from stockimformation.node.executor import NodeExecutor
from stockimformation.node.models import NodeInput
from stockimformation.services import analyze_handler, make_advice_handler, make_briefing_handler
from stockimformation.services.collection import dedupe_raw_items
from stockimformation.services.notification import make_notify_handler


@pytest.mark.asyncio
async def test_fixture_pipeline_generates_e2e_artifacts() -> None:
    config = load_app_config(Path("config"))
    raw_items = [
        _raw("https://example.com/tencent", "profit beat positive growth", ["00700.HK"]),
        _raw("https://example.com/moutai", "regulatory negative drop", ["600519.SH"]),
        _raw("https://example.com/tencent", "duplicate", ["00700.HK"]),
    ]

    async def fetch_rss(_node_input: NodeInput) -> list[dict[str, object]]:
        return [item.model_dump(mode="json") for item in dedupe_raw_items(raw_items)]

    handlers = {
        "fetch-rss": fetch_rss,
        "fetch-web": _empty,
        "summarize": analyze_handler,
        "classify-sentiment": analyze_handler,
        "generate-advice": make_advice_handler(config.portfolio),
        "generate-briefing": make_briefing_handler(config.portfolio),
        "notify-ntfy": make_notify_handler(config.runtime),
    }
    config.nodes["reader"].type = "function"
    executor = NodeExecutor(config.nodes, config.system, config.runtime, handlers)
    graph = load_graph(config.dags["default"], config.nodes)
    result = await DagRunner(executor).run(graph, "cycle-e2e", {"source_names": ["sample-rss"]})
    assert result.payload
    outputs = _outputs_by_type(graph, result.node_outputs)
    briefing = outputs["briefing-generator"].payload
    notifications = outputs["notifier"].payload
    advice = outputs["advisor"].payload
    analysis = outputs["reader"].payload
    assert analysis[0]["source_url"] == "https://example.com/tencent"
    assert advice[0]["source_urls"]
    assert "本系统产出仅供学习参考，不构成投资建议。" in briefing["content"]
    assert notifications[0]["message"]
    assert result.failures == {}


@pytest.mark.asyncio
async def test_minimax_docs_fixture_generates_web_visible_evidence() -> None:
    config = load_app_config(Path("config"))
    minimax_url = "https://platform.minimax.io/docs/api-reference/text-chat-openai"
    raw_item = _raw(
        minimax_url,
        "MiniMax OpenAI compatible chat completions use Bearer Auth and MiniMax-M2.7",
        ["00700.HK"],
    )
    raw_item.source_name = "minimax-docs"
    raw_item.source_type = "web"

    async def fetch_web(_node_input: NodeInput) -> list[dict[str, object]]:
        return [raw_item.model_dump(mode="json")]

    handlers = {
        "fetch-rss": _empty,
        "fetch-web": fetch_web,
        "summarize": analyze_handler,
        "classify-sentiment": analyze_handler,
        "generate-advice": make_advice_handler(config.portfolio),
        "generate-briefing": make_briefing_handler(config.portfolio),
        "notify-ntfy": make_notify_handler(config.runtime),
    }
    config.nodes["reader"].type = "function"
    executor = NodeExecutor(config.nodes, config.system, config.runtime, handlers)
    graph = load_graph(config.dags["default"], config.nodes)
    result = await DagRunner(executor).run(graph, "cycle-minimax", {"source_names": ["minimax-docs"]})
    outputs = _outputs_by_type(graph, result.node_outputs)
    analysis = outputs["reader"].payload
    advice = outputs["advisor"].payload
    briefing = outputs["briefing-generator"].payload
    notifications = outputs["notifier"].payload
    assert analysis[0]["source_url"] == minimax_url
    assert minimax_url in advice[0]["source_urls"]
    assert "minimax-docs" in briefing["content"]
    assert notifications[0]["message"]
    assert result.failures == {}


@pytest.mark.asyncio
async def test_reliability_fixture_recovers_next_cycle_after_failure() -> None:
    config = load_app_config(Path("config"))
    calls = 0

    async def flaky(_node_input: NodeInput) -> list[dict[str, object]]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary")
        return [_raw("https://example.com/recovered", "positive", ["00700.HK"]).model_dump(mode="json")]

    handlers = {
        "fetch-rss": flaky,
        "fetch-web": _empty,
        "summarize": analyze_handler,
        "classify-sentiment": analyze_handler,
        "generate-advice": make_advice_handler(config.portfolio),
        "generate-briefing": make_briefing_handler(config.portfolio),
        "notify-ntfy": make_notify_handler(config.runtime),
    }
    config.nodes["reader"].type = "function"
    executor = NodeExecutor(config.nodes, config.system, config.runtime, handlers)
    graph = load_graph(config.dags["default"], config.nodes)
    first = await DagRunner(executor).run(graph, "cycle-1", {"source_names": ["sample-rss"]})
    second = await DagRunner(executor).run(graph, "cycle-2", {"source_names": ["sample-rss"]})
    assert _instance_id(graph, "rss-fetcher") in first.failures
    assert second.failures == {}


async def _empty(_node_input: NodeInput) -> list[dict[str, object]]:
    return []


def _raw(url: str, content: str, stock_codes: list[str]) -> RawItem:
    return RawItem(
        url=url,
        title="title",
        content=content,
        source_name="fixture",
        source_type="rss",
        stock_codes=stock_codes,
        published_at=datetime.now(timezone.utc),
    )


def _instance_id(graph, node_type: str) -> str:
    return next(node_id for node_id, instance in graph.instances.items() if instance.type == node_type)


def _outputs_by_type(graph, outputs):
    return {graph.instances[node_id].type: output for node_id, output in outputs.items()}
