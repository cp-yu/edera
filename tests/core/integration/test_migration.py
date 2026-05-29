import sqlite3
import importlib.util
import json
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
import yaml


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


def test_migration_scripts(tmp_path) -> None:
    db = tmp_path / "outputs.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE raw_items (id INTEGER PRIMARY KEY, url TEXT, title TEXT, tags TEXT, fetched_at TEXT)")
        conn.execute(
            "INSERT INTO raw_items (id, url, title, tags, fetched_at) VALUES (1, 'https://e.test', 'title', '[\"stock:00700.HK\"]', '2026-01-01')"
        )
        conn.commit()
    spec = importlib.util.spec_from_file_location("migrate_node_outputs", "scripts/migrate_node_outputs.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.migrate(db)
    with sqlite3.connect(db) as conn:
        row = conn.execute("SELECT type, node_id, url FROM node_outputs").fetchone()
    assert row == ("raw-item", "rss-fetcher", "https://e.test")

    config = tmp_path / "config"
    (config / "nodes").mkdir(parents=True)
    (config / "dags").mkdir()
    (config / "nodes" / "reader.yaml").write_text("name: reader\ntype: function\n", encoding="utf-8")
    (config / "dags" / "default.yaml").write_text("name: default\nnodes: []\nedges: []\n", encoding="utf-8")
    spec = importlib.util.spec_from_file_location("migrate_config_entities", "scripts/migrate_config_entities.py")
    assert spec is not None and spec.loader is not None
    config_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config_module)
    config_module.migrate(config)
    node = yaml.safe_load((config / "nodes" / "reader.yaml").read_text(encoding="utf-8"))
    dag = yaml.safe_load((config / "dags" / "default.yaml").read_text(encoding="utf-8"))
    assert node["type"] == "node"
    assert node["attributes"]["name"] == "reader"
    assert dag["type"] == "dag"


def test_alembic_upgrade_head_creates_trigger_event_tables(tmp_path) -> None:
    db = tmp_path / "alembic.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db}")

    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{db}")
    try:
        inspector = inspect(engine)
        assert {"event_group_bits", "emit_records"}.issubset(inspector.get_table_names())
        assert _column_names(inspector, "event_group_bits") >= {"id", "event", "created_at"}
        assert _column_names(inspector, "emit_records") >= {
            "id",
            "event",
            "payload",
            "source",
            "depth",
            "created_at",
        }
    finally:
        engine.dispose()


def _column_names(inspector, table: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table)}
