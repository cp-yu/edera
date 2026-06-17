from __future__ import annotations

import pytest

from edera_core.config.schema import SkillConfig
from edera_core.skills.generator import (
    generate_skill_files,
    refresh_skill_files,
    remove_skill_files,
)


def test_generate_files(tmp_path):
    skills_dir = tmp_path / "skills"

    generate_skill_files(
        skills_dir,
        [
            {
                "name": "demo",
                "config_body": {
                    "files": [
                        {"path": "SKILL.md", "content": "# Demo"},
                        {"path": "prompts/main.txt", "content": "prompt"},
                    ]
                },
            }
        ],
    )

    assert (skills_dir / "demo" / "SKILL.md").exists()
    assert (skills_dir / "demo" / "prompts" / "main.txt").exists()


def test_content_consistency(tmp_path):
    skills_dir = tmp_path / "skills"

    generate_skill_files(
        skills_dir,
        [
            {
                "name": "demo",
                "config_body": {
                    "files": [
                        {"path": "SKILL.md", "content": "# Demo"},
                        {"path": "scripts/helper.py", "content": "print('ok')\n"},
                    ]
                },
            }
        ],
    )

    assert (skills_dir / "demo" / "SKILL.md").read_text(encoding="utf-8") == "# Demo"
    assert (skills_dir / "demo" / "scripts" / "helper.py").read_text(encoding="utf-8") == "print('ok')\n"


def test_rejects_unsafe_skill_name(tmp_path):
    with pytest.raises(ValueError, match="unsafe skill name"):
        generate_skill_files(
            tmp_path / "skills",
            [{"name": "../demo", "config_body": {"files": [{"path": "SKILL.md", "content": "# Demo"}]}}],
        )


def test_refresh_skill_files_writes_single_skill(tmp_path):
    skills_dir = tmp_path / "skills"
    skill = SkillConfig(
        name="foo",
        files=[
            {"path": "SKILL.md", "content": "# Foo"},
            {"path": "prompts/main.txt", "content": "run"},
        ],
    )

    refresh_skill_files(skills_dir, skill)

    assert (skills_dir / "foo" / "SKILL.md").read_text(encoding="utf-8") == "# Foo"
    assert (skills_dir / "foo" / "prompts" / "main.txt").read_text(encoding="utf-8") == "run"


def test_refresh_skill_files_replaces_stale_files(tmp_path):
    skills_dir = tmp_path / "skills"
    skill = SkillConfig(
        name="foo",
        files=[
            {"path": "SKILL.md", "content": "# Foo"},
            {"path": "old.txt", "content": "stale"},
        ],
    )
    refresh_skill_files(skills_dir, skill)

    updated = SkillConfig.model_construct(
        name="foo",
        files=[{"path": "SKILL.md", "content": "# Foo v2"}],
    )
    refresh_skill_files(skills_dir, updated)

    assert (skills_dir / "foo" / "SKILL.md").read_text(encoding="utf-8") == "# Foo v2"
    assert not (skills_dir / "foo" / "old.txt").exists()


def test_remove_skill_files_removes_directory(tmp_path):
    skills_dir = tmp_path / "skills"
    skill = SkillConfig(name="foo", files=[{"path": "SKILL.md", "content": "# Foo"}])
    refresh_skill_files(skills_dir, skill)

    removed = remove_skill_files(skills_dir, "foo")

    assert removed
    assert not (skills_dir / "foo").exists()


def test_remove_skill_files_missing_is_noop(tmp_path):
    skills_dir = tmp_path / "skills"

    assert not remove_skill_files(skills_dir, "absent")

