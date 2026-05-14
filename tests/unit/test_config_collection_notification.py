from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from stockimformation.config.loader import load_app_config
from stockimformation.models.entities import Advice, RawItem
from stockimformation.services.analysis import analyze_raw_item
from stockimformation.services.advisory import generate_advice
from stockimformation.services.briefing import DISCLAIMER, generate_briefing
from stockimformation.services.collection import dedupe_raw_items, parse_rss, parse_web
from stockimformation.services.notification import format_notification, make_notify_handler, priority_for_advice


def test_load_portfolio_holdings() -> None:
    config = load_app_config(Path("config"))
    target = config.portfolio.targets[0]
    assert target.holding is not None
    assert target.holding.quantity == 100


def test_source_association() -> None:
    config = load_app_config(Path("config"))
    assert config.portfolio.targets[0].sources == ["sample-rss", "sample-web"]


def test_rss_source_config() -> None:
    config = load_app_config(Path("config"))
    assert config.portfolio.source_map()["sample-rss"].type == "rss"


def test_web_source_rule_config() -> None:
    config = load_app_config(Path("config"))
    assert config.portfolio.source_map()["sample-web"].regex


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
    briefing = generate_briefing("cycle", [_advice("hold", 0.6)], config.portfolio, {"sample-web": "failed"})
    assert briefing.metadata_["configured_sources"] == ["sample-rss", "sample-web"]
    assert briefing.metadata_["failed_sources"] == {"sample-web": "failed"}


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
