from __future__ import annotations

import pytest

from edera_core.storage import create_engine, init_db, session_factory
from edera_core.storage.repository import create_skill, list_skills


@pytest.mark.asyncio
async def test_create_skill(tmp_path):
    async with await _session(tmp_path) as session:
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
    async with await _session(tmp_path) as session:
        await create_skill(session, "b-skill", [{"path": "SKILL.md", "content": "b"}])
        await create_skill(session, "a-skill", [{"path": "SKILL.md", "content": "a"}])
        await session.commit()

        skills = await list_skills(session)

    assert [(item.name, item.config_body["files"][0]["content"]) for item in skills] == [
        ("a-skill", "a"),
        ("b-skill", "b"),
    ]


async def _session(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'edera.db'}")
    await init_db(engine)
    return session_factory(engine)()
