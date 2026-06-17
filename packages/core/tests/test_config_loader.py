from __future__ import annotations

import pytest

from edera_core.config.loader import _load_runtime_base_config, load_system_config, materialize_runtime_app_config
from edera_core.storage import create_engine, init_db, session_factory
from edera_core.storage.repository import create_skill


@pytest.mark.asyncio
async def test_runtime_config_loads_skills_from_database(tmp_path):
    root = tmp_path / "config"
    _write_runtime_config(root)
    (root / "skills").mkdir()
    (root / "skills" / "legacy.yaml").write_text(
        "name: legacy\ndescription: legacy\nhandler: legacy\n",
        encoding="utf-8",
    )
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'edera.db'}")
    try:
        await init_db(engine)
        async with session_factory(engine)() as session:
            await create_skill(session, "db-skill", [{"path": "SKILL.md", "content": "# DB"}], description="db")
            await session.commit()

        config = await materialize_runtime_app_config(root, _load_runtime_base_config(root), engine)
    finally:
        await engine.dispose()

    assert sorted(config.skills) == ["db-skill"]
    assert config.skills["db-skill"].files == [{"path": "SKILL.md", "content": "# DB"}]


def test_startup_window_default_10(tmp_path):
    root = tmp_path / "config"
    root.mkdir()
    (root / "system.toml").write_text(
        'database_url = "sqlite+aiosqlite:///tmp/test.db"\n',
        encoding="utf-8",
    )

    config = load_system_config(root / "system.toml")

    assert config.startup_window_seconds == 10


def test_startup_window_custom_value(tmp_path):
    root = tmp_path / "config"
    root.mkdir()
    (root / "system.toml").write_text(
        'database_url = "sqlite+aiosqlite:///tmp/test.db"\nstartup_window_seconds = 1\n',
        encoding="utf-8",
    )

    config = load_system_config(root / "system.toml")

    assert config.startup_window_seconds == 1


def _write_runtime_config(root):
    (root / "schemas").mkdir(parents=True)
    (root / "dags").mkdir()
    (root / "nodes").mkdir()
    (root / "schemas" / "stock.yaml").write_text(
        "display_name: Stock\nbusiness_id_field: code\ndisplay_template: '{code}'\nstorage_tier: database\nschema:\n  properties:\n    code:\n      type: string\n",
        encoding="utf-8",
    )
    (root / "system.toml").write_text(
        "database_url = \"sqlite+aiosqlite:///tmp/test.db\"\nschedule_minutes = 1\n",
        encoding="utf-8",
    )
