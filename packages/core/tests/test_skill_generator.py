from __future__ import annotations

import pytest

from edera_core.skills.generator import generate_skill_files


def test_generate_files(tmp_path):
    session_dir = tmp_path / "session"

    generate_skill_files(
        session_dir,
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

    assert (session_dir / "skills" / "demo" / "SKILL.md").exists()
    assert (session_dir / "skills" / "demo" / "prompts" / "main.txt").exists()


def test_content_consistency(tmp_path):
    session_dir = tmp_path / "session"

    generate_skill_files(
        session_dir,
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

    assert (session_dir / "skills" / "demo" / "SKILL.md").read_text(encoding="utf-8") == "# Demo"
    assert (session_dir / "skills" / "demo" / "scripts" / "helper.py").read_text(encoding="utf-8") == "print('ok')\n"


def test_rejects_unsafe_skill_name(tmp_path):
    with pytest.raises(ValueError, match="unsafe skill name"):
        generate_skill_files(
            tmp_path / "session",
            [{"name": "../demo", "config_body": {"files": [{"path": "SKILL.md", "content": "# Demo"}]}}],
        )
