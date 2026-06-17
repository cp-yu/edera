from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


def generate_skill_files(skills_dir: Path, skills: list[object]) -> Path:
    for skill in skills:
        refresh_skill_files(skills_dir, skill)
    return skills_dir


def refresh_all_skill_files(skills_dir: Path, skills: dict[str, object] | list[object]) -> Path:
    iterable = skills.values() if isinstance(skills, dict) else skills
    for skill in iterable:
        refresh_skill_files(skills_dir, skill)
    return skills_dir


def refresh_skill_files(skills_dir: Path, skill: object) -> Path:
    name, files = _skill_parts(skill)
    target = skills_dir / name
    if target.exists():
        shutil.rmtree(target)
    for item in files:
        path = _safe_relative_path(str(item["path"]))
        output = target / path
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(str(item["content"]), encoding="utf-8")
    return target


def remove_skill_files(skills_dir: Path, name: str) -> bool:
    _safe_skill_name(name)
    target = skills_dir / name
    if not target.exists():
        return False
    shutil.rmtree(target)
    return True


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
