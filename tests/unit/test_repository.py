from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlmodel import select

from stockimformation.models.database import create_engine, init_db, session_factory, sqlite_url
from stockimformation.models.entities import RawItem
from stockimformation.models.repository import add_raw_item


@pytest.mark.asyncio
async def test_add_raw_item_skips_existing_url(tmp_path: Path) -> None:
    engine = create_engine(sqlite_url(tmp_path / "repo.db"))
    await init_db(engine)
    factory = session_factory(engine)
    async with factory() as session:
        first = await add_raw_item(session, _raw_item("https://example.com/a"))
        second = await add_raw_item(session, _raw_item("https://example.com/a"))
        await session.commit()
        result = await session.exec(select(RawItem))
    assert first is not None
    assert second is None
    assert len(result.all()) == 1


def _raw_item(url: str) -> RawItem:
    return RawItem(
        url=url,
        title="title",
        content="content",
        source_name="fixture",
        source_type="rss",
        stock_codes=["00700.HK"],
        published_at=datetime.now(timezone.utc),
    )
