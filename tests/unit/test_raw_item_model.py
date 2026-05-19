from datetime import datetime, timezone

from stockimformation.models.entities import RawItem


def test_tags_field() -> None:
    item = RawItem(
        url="https://example.com",
        title="title",
        content="content",
        source_name="source",
        source_type="rss",
        tags=["stock:00700.HK"],
        published_at=datetime.now(timezone.utc),
    )
    assert item.tags == ["stock:00700.HK"]
