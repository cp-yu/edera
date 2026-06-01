from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from edera_core.errors import DatabaseError


@event.listens_for(Engine, "connect")
def _enable_sqlite_wal(dbapi_connection: Any, _connection_record: object) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()


def create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url, echo=False, future=True)


async def init_db(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        await _ensure_dag_retry_of(conn)
        await _ensure_node_run_failure_kind(conn)
        await _ensure_node_run_metadata(conn)
        await _ensure_entity_type_materialization_metadata(conn)
        result = await conn.execute(text("PRAGMA journal_mode"))
        mode = result.scalar_one()
        if str(mode).lower() != "wal":
            raise DatabaseError("SQLite WAL mode is not enabled")


def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def session_scope(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def sqlite_url(path: str | Path) -> str:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite+aiosqlite:///{db_path}"


async def _has_column(conn, table_name: str, column_name: str) -> bool:
    result = await conn.execute(text(f"PRAGMA table_info({table_name})"))
    return column_name in {row[1] for row in result.fetchall()}


async def _ensure_dag_retry_of(conn) -> None:
    if await _has_column(conn, "dag_runs", "retry_of"):
        return
    await conn.execute(text("ALTER TABLE dag_runs ADD COLUMN retry_of VARCHAR"))


async def _ensure_node_run_failure_kind(conn) -> None:
    if await _has_column(conn, "node_runs", "failure_kind"):
        return
    await conn.execute(text("ALTER TABLE node_runs ADD COLUMN failure_kind VARCHAR"))


async def _ensure_node_run_metadata(conn) -> None:
    if await _has_column(conn, "node_runs", "metadata"):
        return
    await conn.execute(text("ALTER TABLE node_runs ADD COLUMN metadata JSON NOT NULL DEFAULT '{}'"))


async def _ensure_entity_type_materialization_metadata(conn) -> None:
    for column, default in (("materialized_fields", "{}"), ("deprecated_fields", "[]")):
        if await _has_column(conn, "entity_types", column):
            continue
        await conn.execute(text(f"ALTER TABLE entity_types ADD COLUMN {column} JSON NOT NULL DEFAULT '{default}'"))
