from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from stockimformation.config.loader import load_app_config
from stockimformation.config.schema import SourceConfig, SystemConfig
from stockimformation.models.entities import Advice, RawItem
from stockimformation.services.analysis import analyze_raw_item
from stockimformation.services.advisory import generate_advice
from stockimformation.services.briefing import DISCLAIMER, generate_briefing
from stockimformation.services import collection
from stockimformation.services.collection import (
    dedupe_raw_items,
    fetch_source_with_recovery,
    parse_rss,
    parse_web,
)
from stockimformation.services.notification import format_notification, make_notify_handler, priority_for_advice


def test_load_portfolio_holdings() -> None:
    config = load_app_config(Path("config"))
    target = config.portfolio.targets[0]
    assert target.holding is not None
    assert target.holding.quantity == 100


def test_source_association() -> None:
    config = load_app_config(Path("config"))
    assert config.portfolio.targets[0].sources == [
        "sample-rss",
        "sample-web",
        "minimax-docs",
        "minimax-docs-index",
        "tonghuashun-minimax",
    ]


def test_rss_source_config() -> None:
    config = load_app_config(Path("config"))
    assert config.portfolio.source_map()["sample-rss"].type == "rss"


def test_web_source_rule_config() -> None:
    config = load_app_config(Path("config"))
    assert config.portfolio.source_map()["sample-web"].regex


def test_minimax_docs_source_config() -> None:
    config = load_app_config(Path("config"))
    source = config.portfolio.source_map()["minimax-docs"]
    assert source.type == "web"
    assert str(source.url) == "https://platform.minimax.io/docs/api-reference/text-chat-openai"
    assert "minimax-docs" in config.portfolio.targets[0].sources


def test_minimax_multi_source_config() -> None:
    config = load_app_config(Path("config"))
    assert str(config.portfolio.source_map()["minimax-docs-index"].url) == (
        "https://platform.minimax.io/docs/llms.txt"
    )
    assert str(config.portfolio.source_map()["tonghuashun-minimax"].url) == (
        "https://basic.10jqka.com.cn/176/HK0100/field.html"
    )
    assert "tonghuashun-minimax" in config.portfolio.targets[1].sources


def test_system_config_schedule_is_30_minutes() -> None:
    config = load_app_config(Path("config"))
    assert config.system.schedule_minutes == 30


def test_parse_rss_creates_raw_items() -> None:
    content = Path("tests/fixtures/feed.xml").read_text()
    items = parse_rss(content, "fixture", ["00700.HK"])
    assert len(items) == 2
    assert items[0].url == "https://example.com/tencent-profit"
    assert items[0].stock_codes == ["00700.HK"]


def test_dedupe_raw_items_by_url() -> None:
    item = _raw_item("https://example.com/a")
    assert dedupe_raw_items([item, item]) == [item]


def test_parse_web_regex_rule() -> None:
    config = load_app_config(Path("config"))
    source = config.portfolio.source_map()["sample-web"]
    items = parse_web("<article>公告 positive growth</article>", source, ["00700.HK"])
    assert items[0].title == "公告 positive growth"


def test_parse_minimax_docs_fixture() -> None:
    config = load_app_config(Path("config"))
    source = config.portfolio.source_map()["minimax-docs"]
    content = Path("tests/fixtures/minimax_text_chat.html").read_text()
    items = parse_web(content, source, ["00700.HK"])
    assert items[0].url == "https://platform.minimax.io/docs/api-reference/text-chat-openai"
    assert items[0].source_name == "minimax-docs"
    assert "Text Chat (Compatible OpenAI API)" in items[0].title
    assert "Bearer Auth" in items[0].content
    assert "MiniMax-M2.7" in items[0].content


def test_parse_minimax_docs_index_fixture() -> None:
    config = load_app_config(Path("config"))
    source = config.portfolio.source_map()["minimax-docs-index"]
    content = Path("tests/fixtures/minimax_llms.txt").read_text()
    items = parse_web(content, source, ["00700.HK"])
    assert items[0].source_name == "minimax-docs-index"
    assert "MiniMax API Docs" in items[0].title
    assert "MiniMax-M2.7" in items[0].content


def test_parse_tonghuashun_minimax_fixture() -> None:
    config = load_app_config(Path("config"))
    source = config.portfolio.source_map()["tonghuashun-minimax"]
    content = Path("tests/fixtures/tonghuashun_minimax.html").read_text()
    items = parse_web(content, source, ["00700.HK"])
    assert items[0].source_name == "tonghuashun-minimax"
    assert "MINIMAX-WP" in items[0].title
    assert "亏损" in items[0].content


def test_analysis_summary_keywords_sentiment() -> None:
    result = analyze_raw_item(_raw_item("https://example.com/b", "profit beat positive growth"))
    assert result.sentiment == "bullish"
    assert result.summary
    assert result.keywords


def test_analysis_requires_traceability() -> None:
    with pytest.raises(ValidationError):
        data = analyze_raw_item(_raw_item("https://example.com/c")).model_dump()
        data["source_url"] = ""
        type(analyze_raw_item(_raw_item("https://example.com/c"))).model_validate(data)


def test_notification_summary_format() -> None:
    title, body, _priority = format_notification(_advice("hold", 0.6))
    assert len(title) <= 16
    for field in ("标的", "方向", "核心原因", "时间", "置信度"):
        assert field in body


def test_priority_mapping() -> None:
    assert priority_for_advice(_advice("buy", 0.8)) == 5
    assert priority_for_advice(_advice("hold", 0.3, low_confidence=True)) == 1
    assert priority_for_advice(_advice("hold", 0.6)) == 3


def test_high_priority_contains_action() -> None:
    _title, body, priority = format_notification(_advice("sell", 0.9))
    assert priority == 5
    assert "sell" in body
    assert "核心原因" in body


@pytest.mark.asyncio
async def test_empty_cycle_status_notification() -> None:
    config = load_app_config(Path("config"))
    result = await make_notify_handler(config.runtime)(
        type("NodeInputStub", (), {"payload": [], "cycle_id": "cycle", "metadata": {}})()
    )
    assert result[0]["title"] == "系统在线"


def test_generate_buy_sell_hold_advice() -> None:
    config = load_app_config(Path("config"))
    analysis = analyze_raw_item(_raw_item("https://example.com/buy", "profit beat positive growth"))
    buy = generate_advice(config.portfolio.targets[1], [analysis])
    sell_signal = analyze_raw_item(_raw_item("https://example.com/sell", "regulatory negative drop"))
    sell = generate_advice(config.portfolio.targets[0], [sell_signal])
    hold = generate_advice(config.portfolio.targets[0], [])
    assert buy.direction == "buy"
    assert sell.direction == "sell"
    assert hold.direction == "hold"


def test_advice_rejects_missing_evidence() -> None:
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        Advice.model_validate(
            {
                "stock_code": "00700.HK",
                "stock_name": "Tencent",
                "direction": "buy",
                "confidence": 0.8,
                "reason": "reason",
                "evidence": [],
                "source_quotes": [],
                "source_urls": [],
                "portfolio_snapshot": {"quantity": 0},
                "data_window_start": now,
                "data_window_end": now,
            }
        )


def test_briefing_groups_targets() -> None:
    config = load_app_config(Path("config"))
    briefing = generate_briefing("cycle", [_advice("hold", 0.6)], config.portfolio)
    assert "00700.HK Tencent" in briefing.content
    assert "600519.SH Kweichow Moutai: 本周期无新增信息" in briefing.content


def test_briefing_metadata_sources() -> None:
    config = load_app_config(Path("config"))
    recovery: dict[str, object] = {"sample-web": {"recovery_status": "escalated", "escalated": True}}
    briefing = generate_briefing(
        "cycle",
        [_advice("hold", 0.6)],
        config.portfolio,
        {"sample-web": "failed"},
        recovery,
    )
    assert briefing.metadata_["configured_sources"] == [
        "sample-rss",
        "sample-web",
        "minimax-docs",
        "minimax-docs-index",
        "tonghuashun-minimax",
    ]
    assert briefing.metadata_["failed_sources"] == {"sample-web": "failed"}
    assert briefing.metadata_["source_recovery"] == recovery
    assert "sample-web" in briefing.metadata_["escalated_sources"]


@pytest.mark.asyncio
async def test_source_recovery_success(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    async def flaky(_source: SourceConfig, _codes: list[str]) -> list[RawItem]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("timed out")
        return [_raw_item("https://example.com/recovered")]

    monkeypatch.setattr(collection, "fetch_web_source", flaky)
    source = SourceConfig.model_validate(
        {"name": "sample-web", "type": "web", "url": "https://example.com"}
    )
    items, summary = await fetch_source_with_recovery(source, ["00700.HK"], SystemConfig())
    assert len(items) == 1
    assert summary["recovery_status"] == "recovered"
    assert summary["attempt_count"] == 1
    assert summary["recoverable_reason"] == "timeout"


@pytest.mark.asyncio
async def test_source_recovery_exhausted_escalates(monkeypatch: pytest.MonkeyPatch) -> None:
    async def failing(_source: SourceConfig, _codes: list[str]) -> list[RawItem]:
        raise TimeoutError("timed out")

    monkeypatch.setattr(collection, "fetch_web_source", failing)
    source = SourceConfig.model_validate(
        {"name": "sample-web", "type": "web", "url": "https://example.com"}
    )
    _items, summary = await fetch_source_with_recovery(
        source,
        ["00700.HK"],
        SystemConfig(source_recovery_max_attempts=1),
    )
    assert summary["recovery_status"] == "escalated"
    assert summary["attempt_count"] == 1
    assert summary["escalation_reason"] == "recovery_exhausted"


@pytest.mark.asyncio
async def test_source_recovery_non_recoverable_escalates_without_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    async def failing(_source: SourceConfig, _codes: list[str]) -> list[RawItem]:
        raise RuntimeError("bad config")

    monkeypatch.setattr(collection, "fetch_web_source", failing)
    source = SourceConfig.model_validate(
        {"name": "sample-web", "type": "web", "url": "https://example.com"}
    )
    _items, summary = await fetch_source_with_recovery(source, ["00700.HK"], SystemConfig())
    assert summary["recovery_status"] == "escalated"
    assert summary["attempt_count"] == 0
    assert summary["escalation_reason"] == "non_recoverable"


def test_briefing_contains_disclaimer() -> None:
    config = load_app_config(Path("config"))
    briefing = generate_briefing("cycle", [_advice("hold", 0.6)], config.portfolio)
    assert briefing.content.endswith(DISCLAIMER)


def _raw_item(url: str, content: str = "content") -> RawItem:
    return RawItem(
        url=url,
        title="title",
        content=content,
        source_name="fixture",
        source_type="rss",
        stock_codes=["00700.HK"],
        published_at=datetime.now(timezone.utc),
    )


def _advice(direction: str, confidence: float, low_confidence: bool = False) -> Advice:
    now = datetime.now(timezone.utc)
    return Advice(
        stock_code="00700.HK",
        stock_name="Tencent",
        direction=direction,
        confidence=confidence,
        reason="reason",
        evidence=[1],
        source_quotes=["quote"],
        source_urls=["https://example.com/a"],
        portfolio_snapshot={"quantity": 1},
        low_confidence=low_confidence,
        data_window_start=now,
        data_window_end=now,
    )
