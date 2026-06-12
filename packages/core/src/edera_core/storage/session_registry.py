from __future__ import annotations

import aiosqlite
from typing import Any


class SessionRegistry:
    """Session run 注册表与消费账本"""

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self):
        """初始化数据库表"""
        self._db = await aiosqlite.connect(self.db_path)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS session_runs (
                dag_name TEXT NOT NULL,
                group_name TEXT NOT NULL,
                run_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                path TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (dag_name, group_name, run_id)
            )
        """)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS session_consumptions (
                source_session_id TEXT NOT NULL,
                consumer TEXT NOT NULL,
                consumed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (source_session_id, consumer)
            )
        """)
        await self._db.commit()

    async def close(self):
        """关闭数据库连接"""
        if self._db:
            await self._db.close()

    async def register(self, dag_name: str, group: str, run_id: str, session_id: str, path: str):
        """登记 session run，状态为 active"""
        from datetime import datetime
        now = datetime.now().isoformat()
        await self._db.execute(
            """INSERT OR REPLACE INTO session_runs
               (dag_name, group_name, run_id, session_id, path, status, created_at)
               VALUES (?, ?, ?, ?, ?, 'active', ?)""",
            (dag_name, group, run_id, session_id, path, now),
        )
        await self._db.commit()

    async def finish(self, dag_name: str, group: str, run_id: str, status: str):
        """DAG run 结束时更新状态为 completed 或 failed"""
        await self._db.execute(
            """UPDATE session_runs
               SET status = ?
               WHERE dag_name = ? AND group_name = ? AND run_id = ?""",
            (status, dag_name, group, run_id),
        )
        await self._db.commit()

    async def reconcile_on_startup(self, active_run_ids: set[str]):
        """启动对账：将不属于活跃 run 的 active 记录落为 failed"""
        if not active_run_ids:
            await self._db.execute("UPDATE session_runs SET status = 'failed' WHERE status = 'active'")
        else:
            placeholders = ",".join("?" * len(active_run_ids))
            await self._db.execute(
                f"UPDATE session_runs SET status = 'failed' WHERE status = 'active' AND run_id NOT IN ({placeholders})",
                tuple(active_run_ids),
            )
        await self._db.commit()

    async def list_sessions(self, dag_name: str, group: str) -> list[dict[str, Any]]:
        """列出指定组的所有 session run"""
        self._db.row_factory = aiosqlite.Row
        async with self._db.execute(
            """SELECT dag_name, group_name, run_id, session_id, path, status, created_at
               FROM session_runs
               WHERE dag_name = ? AND group_name = ?
               ORDER BY created_at DESC""",
            (dag_name, group),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_latest(self, dag_name: str, group: str) -> dict[str, Any] | None:
        """获取最近的 completed run"""
        self._db.row_factory = aiosqlite.Row
        async with self._db.execute(
            """SELECT dag_name, group_name, run_id, session_id, path, status, created_at
               FROM session_runs
               WHERE dag_name = ? AND group_name = ? AND status = 'completed'
               ORDER BY created_at DESC
               LIMIT 1""",
            (dag_name, group),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def mark_consumed(self, source_session_id: str, consumer: str):
        """登记消费"""
        await self._db.execute(
            """INSERT OR IGNORE INTO session_consumptions (source_session_id, consumer)
               VALUES (?, ?)""",
            (source_session_id, consumer),
        )
        await self._db.commit()

    async def list_with_consumption(self, dag_name: str, group: str, consumer: str) -> list[dict[str, Any]]:
        """列出 session 并附带 consumed 标记"""
        self._db.row_factory = aiosqlite.Row
        async with self._db.execute(
            """SELECT
                   s.dag_name, s.group_name, s.run_id, s.session_id, s.path, s.status, s.created_at,
                   CASE WHEN c.source_session_id IS NOT NULL THEN 1 ELSE 0 END as consumed
               FROM session_runs s
               LEFT JOIN session_consumptions c
                   ON s.session_id = c.source_session_id AND c.consumer = ?
               WHERE s.dag_name = ? AND s.group_name = ? AND s.status = 'completed'
               ORDER BY s.created_at ASC""",
            (consumer, dag_name, group),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_oldest_unconsumed(self, dag_name: str, group: str, consumer: str) -> dict[str, Any] | None:
        """获取最旧的未消费 session"""
        self._db.row_factory = aiosqlite.Row
        async with self._db.execute(
            """SELECT s.dag_name, s.group_name, s.run_id, s.session_id, s.path, s.status, s.created_at
               FROM session_runs s
               WHERE s.dag_name = ? AND s.group_name = ? AND s.status = 'completed'
                 AND NOT EXISTS (
                     SELECT 1 FROM session_consumptions c
                     WHERE c.source_session_id = s.session_id AND c.consumer = ?
                 )
               ORDER BY s.created_at ASC
               LIMIT 1""",
            (dag_name, group, consumer),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
