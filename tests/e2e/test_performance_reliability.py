from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import pytest

from stockimformation.config.loader import load_app_config
from stockimformation.config.entities import EntityStore
from stockimformation.dag.loader import load_graph
from stockimformation.dag.runner import DagRunner
from stockimformation.models.entities import Advice, RawItem
from stockimformation.node.executor import NodeExecutor
from stockimformation.node.models import NodeInput
from stockimformation.services import analyze_handler, make_advice_handler, make_briefing_handler
from stockimformation.services.notification import format_notification, make_notify_handler


@pytest.mark.asyncio
async def test_analysis_latency_under_30s() -> None:
    start = perf_counter()
    result = await analyze_handler(
        NodeInput(
            cycle_id="latency",
            payload=[
                _raw("https://example.com/latency", "profit beat positive growth").model_dump(
                    mode="json"
                )
            ],
        )
    )
    assert result[0]["summary"]
    assert perf_counter() - start < 30


@pytest.mark.asyncio
async def test_default_cycle_completes_with_output() -> None:
    config = load_app_config(Path("config"))
    entity_store = _entity_store(config)

    async def fetch(_node_input: NodeInput) -> list[dict[str, object]]:
        return [_raw("https://example.com/cycle", "profit beat positive growth").model_dump(mode="json")]

    handlers = {
        "fetch-rss": fetch,
        "fetch-api": _empty,
        "summarize": analyze_handler,
        "classify-sentiment": analyze_handler,
        "generate-advice": make_advice_handler(entity_store),
        "generate-briefing": make_briefing_handler(entity_store),
        "notify-ntfy": make_notify_handler(config.runtime),
    }
    graph = load_graph(config.dags["default"], config.nodes)
    result = await DagRunner(NodeExecutor(config.nodes, config.system, config.runtime, handlers)).run(
        graph,
        "cycle",
        {"source_names": ["hn-rss"]},
    )
    assert result.payload
    assert config.system.schedule_minutes == 30


@pytest.mark.asyncio
async def test_priority5_notification_generated_under_5min() -> None:
    config = load_app_config(Path("config"))
    advice = make_advice_handler(_entity_store(config))
    raw = _raw("https://example.com/urgent", "profit beat positive growth")
    start = perf_counter()
    raw2 = _raw("https://example.com/urgent-2", "positive surge beat")
    analysis = await analyze_handler(
        NodeInput(cycle_id="priority", payload=[raw.model_dump(mode="json"), raw2.model_dump(mode="json")])
    )
    advices = await advice(NodeInput(cycle_id="priority", payload=analysis))
    title, body, priority = format_notification(Advice.model_validate(advices[1]))
    assert priority == 5
    assert "buy" in body
    assert title
    assert perf_counter() - start < 300


async def _empty(_node_input: NodeInput) -> list[dict[str, object]]:
    return []


def _raw(url: str, content: str) -> RawItem:
    return RawItem(
        url=url,
        title="title",
        content=content,
        source_name="fixture",
        source_type="rss",
        tags=["stock:00700.HK"],
        published_at=datetime.now(timezone.utc),
    )


def _entity_store(config) -> EntityStore:
    return EntityStore(config.entities, config.entity_types, config.entity_relations)
