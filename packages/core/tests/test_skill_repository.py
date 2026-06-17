from __future__ import annotations

from contextlib import asynccontextmanager

import pytest

from edera_core.storage import create_engine, init_db, session_factory
from edera_core.storage.repository import create_skill, delete_skill, list_skills, upsert_skill


@pytest.mark.asyncio
async def test_create_skill(tmp_path):
    async with _session(tmp_path) as session:
        skill = await create_skill(
            session,
            "demo-skill",
            [{"path": "SKILL.md", "content": "# Demo"}],
            display_name="Demo Skill",
            description="demo",
        )
        await session.commit()

    assert skill.name == "demo-skill"
    assert skill.config_body == {"files": [{"path": "SKILL.md", "content": "# Demo"}]}


@pytest.mark.asyncio
async def test_list_skills(tmp_path):
    async with _session(tmp_path) as session:
        await create_skill(session, "b-skill", [{"path": "SKILL.md", "content": "b"}])
        await create_skill(session, "a-skill", [{"path": "SKILL.md", "content": "a"}])
        await session.commit()

        skills = await list_skills(session)

    assert [(item.name, item.config_body["files"][0]["content"]) for item in skills] == [
        ("a-skill", "a"),
        ("b-skill", "b"),
    ]


@asynccontextmanager
async def _session(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'edera.db'}")
    try:
        await init_db(engine)
        async with session_factory(engine)() as session:
            yield session
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_upsert_skill_refreshes_materialized_dir(tmp_path):
    skills_dir = tmp_path / "skills"
    async with _session(tmp_path) as session:
        await upsert_skill(
            session,
            "foo",
            [
                {"path": "SKILL.md", "content": "# Foo"},
                {"path": "prompts/main.txt", "content": "run"},
            ],
            skills_dir=skills_dir,
        )
        await session.commit()

    assert (skills_dir / "foo" / "SKILL.md").read_text(encoding="utf-8") == "# Foo"
    assert (skills_dir / "foo" / "prompts" / "main.txt").read_text(encoding="utf-8") == "run"


@pytest.mark.asyncio
async def test_delete_skill_removes_materialized_dir(tmp_path):
    skills_dir = tmp_path / "skills"
    async with _session(tmp_path) as session:
        await upsert_skill(
            session,
            "foo",
            [{"path": "SKILL.md", "content": "# Foo"}],
            skills_dir=skills_dir,
        )
        await session.commit()

    assert (skills_dir / "foo").exists()

    async with _session(tmp_path) as session:
        deleted = await delete_skill(session, "foo", skills_dir)
        await session.commit()

    assert deleted
    assert not (skills_dir / "foo").exists()

