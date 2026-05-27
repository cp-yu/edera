from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def migrate(path: Path = Path("data/edera.db")) -> None:
    if not path.exists():
        return
    with sqlite3.connect(path) as conn:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(raw_items)")]
        if "stock_codes" not in columns or "tags" in columns:
            return
        conn.execute("ALTER TABLE raw_items RENAME COLUMN stock_codes TO tags")
        for row_id, raw_tags in conn.execute("SELECT id, tags FROM raw_items"):
            conn.execute(
                "UPDATE raw_items SET tags = ? WHERE id = ?",
                (json.dumps(_entity_tags(raw_tags), ensure_ascii=False), row_id),
            )
        conn.commit()


def _entity_tags(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    values = json.loads(raw_value)
    if not isinstance(values, list):
        return []
    return [value if ":" in value else f"stock:{value}" for value in values if isinstance(value, str)]


if __name__ == "__main__":
    migrate()
