from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from uuid import uuid4


def migrate(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        _ensure_table(conn)
        _copy_rows(conn, "raw_items", "raw-item", "rss-fetcher")
        _copy_rows(conn, "analysis_results", "analysis", "reader")
        _copy_rows(conn, "advices", "advice", "advisor")
        _copy_rows(conn, "briefings", "briefing", "briefing-generator")
        conn.commit()


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS node_outputs ("
        "id INTEGER PRIMARY KEY, entity_id TEXT UNIQUE NOT NULL, type TEXT NOT NULL, "
        "cycle_id TEXT NOT NULL, node_id TEXT NOT NULL, payload TEXT NOT NULL, "
        "tags TEXT NOT NULL, session_id TEXT, url TEXT, created_at TEXT NOT NULL)"
    )


def _copy_rows(conn: sqlite3.Connection, table: str, entity_type: str, node_id: str) -> None:
    if not _table_exists(conn, table):
        return
    columns = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
    for row in conn.execute(f"SELECT * FROM {table}"):
        payload = dict(zip(columns, row, strict=True))
        url = payload.get("url") if isinstance(payload.get("url"), str) else None
        cycle_id = str(payload.get("cycle_id") or payload.get("id") or "")
        created_at = str(payload.get("created_at") or payload.get("fetched_at") or "")
        tags = payload.get("tags") if isinstance(payload.get("tags"), list) else []
        conn.execute(
            "INSERT OR IGNORE INTO node_outputs "
            "(entity_id, type, cycle_id, node_id, payload, tags, session_id, url, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (uuid4().hex, entity_type, cycle_id, node_id, json.dumps(payload), json.dumps(tags), None, url, created_at),
        )


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None
