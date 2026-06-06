from __future__ import annotations

from pathlib import Path
from typing import Any


def generate_skill_files(session_dir: Path, skills: list[object]) -> Path:
    skills_dir = session_dir / "skills"
    for skill in skills:
        name, files = _skill_parts(skill)
        target = skills_dir / name
        for item in files:
            path = _safe_relative_path(str(item["path"]))
            output = target / path
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(str(item["content"]), encoding="utf-8")
    return skills_dir


def _skill_parts(skill: object) -> tuple[str, list[dict[str, Any]]]:
    if isinstance(skill, dict):
        name = str(skill.get("name") or "").strip()
        body = skill.get("config_body") if isinstance(skill.get("config_body"), dict) else skill
    else:
        name = str(getattr(skill, "name", "") or "").strip()
        body = getattr(skill, "config_body", {})
        if not isinstance(body, dict):
            body = {}
        if not body and isinstance(getattr(skill, "files", None), list):
            body = {"files": getattr(skill, "files")}
    files = body.get("files") if isinstance(body, dict) else None
    if not name:
        raise ValueError("skill name is required")
    _safe_skill_name(name)
    if not isinstance(files, list):
        raise ValueError(f"skill files are required: {name}")
    return name, [item for item in files if isinstance(item, dict)]


def _safe_skill_name(value: str) -> None:
    path = Path(value)
    if path.is_absolute() or path.name != value or value in {".", ".."}:
        raise ValueError(f"unsafe skill name: {value}")


def _safe_relative_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or not value:
        raise ValueError(f"unsafe skill file path: {value}")
    return path
