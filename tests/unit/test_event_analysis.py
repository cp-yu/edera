from datetime import datetime, timezone

from stockimformation.models.entities import AnalysisResult, RawItem
from stockimformation.services.event_analysis import rebuild_event_records


def test_event_records_use_stock_entity_tags() -> None:
    raw = RawItem(
        id=1,
        url="https://example.com/a",
        title="Tencent profit",
        content="Tencent profit growth",
        source_name="fixture",
        source_type="rss",
        tags=["city:hongkong", "stock:00700.HK"],
        published_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    analysis = AnalysisResult(
        id=2,
        raw_item_id=1,
        summary="Tencent profit growth",
        keywords=["Tencent", "profit"],
        sentiment="bullish",
        confidence=0.8,
        source_quote="Tencent profit growth",
        source_url="https://example.com/a",
    )
    events = rebuild_event_records([raw], [analysis], [])
    assert len(events) == 1
    assert events[0].stock_code == "00700.HK"


def test_event_records_ignore_non_stock_tags() -> None:
    raw = RawItem(
        id=1,
        url="https://example.com/a",
        title="Hong Kong growth",
        content="Hong Kong growth",
        source_name="fixture",
        source_type="rss",
        tags=["city:hongkong"],
        published_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    analysis = AnalysisResult(
        id=2,
        raw_item_id=1,
        summary="Hong Kong growth",
        keywords=["Hong", "Kong"],
        sentiment="neutral",
        confidence=0.8,
        source_quote="Hong Kong growth",
        source_url="https://example.com/a",
    )
    assert rebuild_event_records([raw], [analysis], []) == []
