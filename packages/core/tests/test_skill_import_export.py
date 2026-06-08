from __future__ import annotations

from contextlib import asynccontextmanager

import pytest

from edera_core.skills.import_export import export_skill, import_skill_dir, import_skills_batch
from edera_core.storage import create_engine, init_db, session_factory
from edera_core.storage.repository import create_skill, get_skill, list_skills


@pytest.mark.asyncio
async def test_import_skill_dir(tmp_path):
    source = tmp_path / "my-skill"
    (source / "prompts").mkdir(parents=True)
    (source / "SKILL.md").write_text("# Skill", encoding="utf-8")
    (source / "prompts" / "main.txt").write_text("prompt", encoding="utf-8")

    async with _session(tmp_path) as session:
        skill = await import_skill_dir(session, source)
        await session.commit()

    paths = [item["path"] for item in skill.config_body["files"]]
    assert paths == ["SKILL.md", "prompts/main.txt"]


@pytest.mark.asyncio
async def test_import_skills_batch(tmp_path):
    batch = tmp_path / "skills"
    for name in ("a-skill", "b-skill"):
        root = batch / name
        root.mkdir(parents=True)
        (root / "SKILL.md").write_text(name, encoding="utf-8")
    (batch / "not-a-skill").mkdir()

    async with _session(tmp_path) as session:
        imported = await import_skills_batch(session, batch)
        await session.commit()

    assert [skill.name for skill in imported] == ["a-skill", "b-skill"]


@pytest.mark.asyncio
async def test_export_skill(tmp_path):
    async with _session(tmp_path) as session:
        await create_skill(
            session,
            "demo",
            [
                {"path": "SKILL.md", "content": "# Demo"},
                {"path": "prompts/main.txt", "content": "prompt"},
            ],
        )
        await session.commit()

        output = await export_skill(session, "demo", tmp_path / "out")

    assert output == tmp_path / "out" / "demo"
    assert (output / "SKILL.md").read_text(encoding="utf-8") == "# Demo"
    assert (output / "prompts" / "main.txt").read_text(encoding="utf-8") == "prompt"


@asynccontextmanager
async def _session(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'edera.db'}")
    try:
        await init_db(engine)
        async with session_factory(engine)() as session:
            yield session
    finally:
        await engine.dispose()
