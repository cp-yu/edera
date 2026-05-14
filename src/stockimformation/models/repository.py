from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from stockimformation.models.entities import Advice, AnalysisResult, Briefing, RawItem


async def add_raw_item(session: AsyncSession, item: RawItem) -> RawItem | None:
    existing = await session.exec(select(RawItem).where(RawItem.url == item.url))
    if existing.first() is not None:
        return None
    session.add(item)
    await session.flush()
    return item


async def url_exists(session: AsyncSession, url: str) -> bool:
    result = await session.exec(select(RawItem.id).where(RawItem.url == url))
    return result.first() is not None


async def store_cycle_outputs(
    session: AsyncSession,
    raw_items: list[RawItem],
    analyses: list[AnalysisResult],
    advices: list[Advice],
    briefing: Briefing | None,
) -> None:
    url_to_id: dict[str, int] = {}
    for raw_item in raw_items:
        stored = await add_raw_item(session, raw_item)
        if stored is not None and stored.id is not None:
            url_to_id[stored.url] = stored.id
        else:
            existing = await session.exec(select(RawItem).where(RawItem.url == raw_item.url))
            item = existing.first()
            if item and item.id is not None:
                url_to_id[item.url] = item.id
    for analysis in analyses:
        analysis.raw_item_id = url_to_id.get(analysis.source_url, analysis.raw_item_id)
        session.add(analysis)
    for advice in advices:
        session.add(advice)
    if briefing is not None:
        session.add(briefing)
