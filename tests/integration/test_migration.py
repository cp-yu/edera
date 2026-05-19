import sqlite3
import importlib.util
import json
from pathlib import Path


def _migrate(raw_items_db: Path) -> None:
    spec = importlib.util.spec_from_file_location("migrate_raw_items_tags", "scripts/migrate_raw_items_tags.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.migrate(raw_items_db)


def test_stock_codes_to_tags(tmp_path) -> None:
    db = tmp_path / "items.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE raw_items (id INTEGER PRIMARY KEY, stock_codes TEXT)")
        conn.execute(
            "INSERT INTO raw_items (id, stock_codes) VALUES (?, ?)",
            (1, json.dumps(["00700.HK", "stock:600519.SH"])),
        )
        conn.execute("INSERT INTO raw_items (id, stock_codes) VALUES (?, ?)", (2, json.dumps([])))
        conn.execute("INSERT INTO raw_items (id, stock_codes) VALUES (?, ?)", (3, None))
        conn.commit()
    _migrate(db)
    with sqlite3.connect(db) as conn:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(raw_items)")]
        tags = {
            row_id: json.loads(raw_tags)
            for row_id, raw_tags in conn.execute("SELECT id, tags FROM raw_items ORDER BY id")
        }
    assert "tags" in columns
    assert "stock_codes" not in columns
    assert tags == {
        1: ["stock:00700.HK", "stock:600519.SH"],
        2: [],
        3: [],
    }
