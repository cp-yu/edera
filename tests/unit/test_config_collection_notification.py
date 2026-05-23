from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from stockimformation.config.entities import EntityStore
from stockimformation.config.loader import load_app_config
from stockimformation.config.schema import EntitiesConfig, EntityConfig, EntityRelationsConfig, SystemConfig
from stockimformation.models.entities import Advice, RawItem
from stockimformation.node.models import NodeInput
from stockimformation.services.analysis import analyze_raw_item
from stockimformation.services.advisory import generate_advice
from stockimformation.services.briefing import DISCLAIMER, generate_briefing
from stockimformation.services import collection
from stockimformation.services.collection import (
    dedupe_raw_items,
    fetch_source_with_recovery,
    make_fetch_handler,
    parse_api,
    parse_rss,
    parse_web,
)
from stockimformation.services.notification import format_notification, make_notify_handler, priority_for_advice


def test_load_portfolio_holdings() -> None:
    config = load_app_config(Path("config"))
    target = _stocks(_store(config))[0]
    holding = target.attributes.get("holding")
    assert isinstance(holding, dict)
    assert holding["quantity"] == 100


def test_source_association() -> None:
    config = load_app_config(Path("config"))
    store = _store(config)
    assert [ref.split(":", 1)[1] for ref in store.related_refs("stock:00100.HK")] == [
        "hn-rss",
        "cls-telegraph",
        "jqka",
        "solidot",
        "ithome",
        "github",
    ]


def test_rss_source_config() -> None:
    config = load_app_config(Path("config"))
    source = _source_by_name(_store(config), "hn-rss")
    assert source.type == "rss-source"
    assert source.attributes["url"] == "https://news.ycombinator.com/rss"


def test_api_source_config() -> None:
    config = load_app_config(Path("config"))
    source = _source_by_name(_store(config), "cls-telegraph")
    assert source.type == "api-source"
    assert source.attributes["base_url"] == "https://news.yltfspace.com/api/news"
    assert source.attributes["params"] == {"platform": "cls_telegraph"}


def test_api_source_schema_loaded() -> None:
    config = load_app_config(Path("config"))
    assert "api-source" in config.entity_types


def test_minimax_multi_api_source_config() -> None:
    config = load_app_config(Path("config"))
    store = _store(config)
    assert _source_by_name(store, "jqka").attributes["params"] == {"platform": "jqka"}
    assert _source_by_name(store, "solidot").attributes["params"] == {"platform": "solidot"}
    assert "api-source:github" in store.related_refs("stock:00100.HK")


def test_system_config_schedule_is_30_minutes() -> None:
    config = load_app_config(Path("config"))
    assert config.system.schedule_minutes == 30


def test_parse_rss_creates_raw_items() -> None:
    content = Path("tests/fixtures/feed.xml").read_text()
    items = parse_rss(content, "fixture", ["00700.HK"])
    assert len(items) == 2
    assert items[0].url == "https://example.com/tencent-profit"
    assert items[0].tags == ["stock:00700.HK"]
    assert parse_rss(content, "fixture", ["stock:00700.HK"])[0].tags == ["stock:00700.HK"]


def test_dedupe_raw_items_by_url() -> None:
    item = _raw_item("https://example.com/a")
    assert dedupe_raw_items([item, item]) == [item]


@pytest.mark.asyncio
async def test_fetch_handler_limits_items_per_source(monkeypatch: pytest.MonkeyPatch) -> None:
    config = load_app_config(Path("config"))
    source = _api_source()
    store = EntityStore(EntitiesConfig(entities=[source]), config.entity_types, EntityRelationsConfig())

    async def fetch_many(_source: EntityConfig, _tags: list[str]) -> list[RawItem]:
        return [_raw_item(f"https://example.com/{index}") for index in range(3)]

    monkeypatch.setattr(collection, "fetch_api_source", fetch_many)
    handler = make_fetch_handler(store, "api")

    items = await handler(
        NodeInput(cycle_id="cycle", payload={"source_names": ["cls-telegraph"]}),
        {"max_items_per_source": 2},
        None,
    )

    assert [item["url"] for item in items] == ["https://example.com/0", "https://example.com/1"]


def test_parse_web_regex_rule() -> None:
    source = _web_source()
    items = parse_web("<article>公告 positive growth</article>", source, ["00700.HK"])
    assert items[0].title == "公告 positive growth"


def test_parse_api_content_probe_chain() -> None:
    source = _api_source()
    records = [
        {"title": "a", "url": "https://example.com/a", "extra": {"content": "content"}},
        {"title": "b", "url": "https://example.com/b", "extra": {"desc": "desc"}},
        {"title": "c", "url": "https://example.com/c", "extra": {"brief": "brief"}},
        {"title": "d", "url": "https://example.com/d", "extra": {}},
    ]
    items = parse_api(records, source, ["00100.HK"])
    assert [item.content for item in items] == ["content", "desc", "brief", "d"]
    assert items[0].source_name == "cls-telegraph"
    assert items[0].source_type == "api"


def test_parse_api_timestamp_probe_chain() -> None:
    source = _api_source()
    records = [
        {"title": "a", "url": "https://example.com/a", "pubDate": 1700000000000},
        {"title": "b", "url": "https://example.com/b", "extra": {"date": 1700000001000}},
    ]
    items = parse_api(records, source, [])
    assert items[0].published_at == datetime.fromtimestamp(1700000000, timezone.utc)
    assert items[1].published_at == datetime.fromtimestamp(1700000001, timezone.utc)


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
    stocks = _stocks(_store(config))
    analysis = analyze_raw_item(_raw_item("https://example.com/buy", "profit beat positive growth"))
    buy = generate_advice(stocks[1], [analysis])
    sell_signal = analyze_raw_item(_raw_item("https://example.com/sell", "regulatory negative drop"))
    sell = generate_advice(stocks[0], [sell_signal])
    hold = generate_advice(stocks[0], [])
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
    briefing = generate_briefing("cycle", [_advice("hold", 0.6)], _store(config))
    assert "00700.HK Tencent" in briefing.content
    assert "600519.SH Kweichow Moutai: 本周期无新增信息" in briefing.content


def test_briefing_metadata_sources() -> None:
    config = load_app_config(Path("config"))
    recovery: dict[str, object] = {"sample-web": {"recovery_status": "escalated", "escalated": True}}
    briefing = generate_briefing(
        "cycle",
        [_advice("hold", 0.6)],
        _store(config),
        {"sample-web": "failed"},
        recovery,
    )
    assert briefing.metadata_["configured_sources"] == [
        "hn-rss",
        "cls-telegraph",
        "jqka",
        "solidot",
        "ithome",
        "github",
    ]
    assert briefing.metadata_["failed_sources"] == {"sample-web": "failed"}
    assert briefing.metadata_["source_recovery"] == recovery
    assert "sample-web" in briefing.metadata_["escalated_sources"]


@pytest.mark.asyncio
async def test_source_recovery_success(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    async def flaky(_source: EntityConfig, _codes: list[str]) -> list[RawItem]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("timed out")
        return [_raw_item("https://example.com/recovered")]

    monkeypatch.setattr(collection, "fetch_web_source", flaky)
    source = _web_source()
    items, summary = await fetch_source_with_recovery(source, ["00700.HK"], SystemConfig())
    assert len(items) == 1
    assert summary["recovery_status"] == "recovered"
    assert summary["attempt_count"] == 1
    assert summary["recoverable_reason"] == "timeout"


@pytest.mark.asyncio
async def test_source_recovery_exhausted_escalates(monkeypatch: pytest.MonkeyPatch) -> None:
    async def failing(_source: EntityConfig, _codes: list[str]) -> list[RawItem]:
        raise TimeoutError("timed out")

    monkeypatch.setattr(collection, "fetch_web_source", failing)
    source = _web_source()
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
    async def failing(_source: EntityConfig, _codes: list[str]) -> list[RawItem]:
        raise RuntimeError("bad config")

    monkeypatch.setattr(collection, "fetch_web_source", failing)
    source = _web_source()
    _items, summary = await fetch_source_with_recovery(source, ["00700.HK"], SystemConfig())
    assert summary["recovery_status"] == "escalated"
    assert summary["attempt_count"] == 0
    assert summary["escalation_reason"] == "non_recoverable"


@pytest.mark.asyncio
async def test_api_source_missing_base_url_records_failure() -> None:
    config = load_app_config(Path("config"))
    source = EntityConfig(id="source-bad-api", type="api-source", attributes={"name": "bad-api"})
    store = EntityStore(EntitiesConfig(entities=[source]), config.entity_types, EntityRelationsConfig())
    node_input = NodeInput(cycle_id="cycle", payload={"source_names": ["bad-api"]})
    handler = make_fetch_handler(store, "api", SystemConfig(source_recovery_max_attempts=0))

    assert await handler(node_input) == []
    assert node_input.metadata["failures"] == {"bad-api": "missing api base_url: bad-api"}
    assert node_input.metadata["source_recovery"]["bad-api"]["recovery_status"] == "escalated"


def test_briefing_contains_disclaimer() -> None:
    config = load_app_config(Path("config"))
    briefing = generate_briefing("cycle", [_advice("hold", 0.6)], _store(config))
    assert briefing.content.endswith(DISCLAIMER)


def _raw_item(url: str, content: str = "content") -> RawItem:
    return RawItem(
        url=url,
        title="title",
        content=content,
        source_name="fixture",
        source_type="rss",
        tags=["stock:00700.HK"],
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


def _store(config) -> EntityStore:
    return EntityStore(config.entities, config.entity_types, config.entity_relations)


def _stocks(store: EntityStore) -> list[EntityConfig]:
    return [entity for entity in store.entities.entities if entity.type == "stock"]


def _source_by_name(store: EntityStore, name: str) -> EntityConfig:
    return next(entity for entity in store.entities.entities if entity.attributes.get("name") == name)


def _web_source() -> EntityConfig:
    return EntityConfig(
        id="source-sample-web",
        type="web-source",
        attributes={"name": "sample-web", "url": "https://example.com", "regex": "<article>(?P<title>.*?)</article>"},
    )


def _api_source() -> EntityConfig:
    return EntityConfig(
        id="source-cls-telegraph",
        type="api-source",
        attributes={
            "name": "cls-telegraph",
            "base_url": "https://news.yltfspace.com/api/news",
            "params": {"platform": "cls_telegraph"},
        },
    )
