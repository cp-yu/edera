from __future__ import annotations

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from edera_core.storage.entities import LogIndex, utc_now


async def record_log_index(
    session: AsyncSession,
    run_id: str,
    node_id: str,
    path: str,
    digest: str,
    size: int,
    kind: str = "raw",
) -> LogIndex:
    row = LogIndex(run_id=run_id, node_id=node_id, kind=kind, path=path, digest=digest, size=size, updated_at=utc_now())
    session.add(row)
    await session.flush()
    return row


async def query_log_index(
    session: AsyncSession,
    run_id: str | None = None,
    node_id: str | None = None,
    limit: int = 100,
) -> list[LogIndex]:
    statement = select(LogIndex).order_by(col(LogIndex.created_at).desc()).limit(limit)
    if run_id is not None:
        statement = statement.where(LogIndex.run_id == run_id)
    if node_id is not None:
        statement = statement.where(LogIndex.node_id == node_id)
    result = await session.exec(statement)
    return list(result.all())
