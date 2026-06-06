from __future__ import annotations

from pathlib import Path

from sqlmodel.ext.asyncio.session import AsyncSession

from edera_core.storage.entities import Skill
from edera_core.storage.repository import get_skill, upsert_skill


async def import_skill_dir(session: AsyncSession, dir_path: Path) -> Skill:
    if not (dir_path / "SKILL.md").is_file():
        raise ValueError("skill directory must contain SKILL.md")
    return await upsert_skill(session, dir_path.name, _files_from_dir(dir_path))


async def import_skills_batch(session: AsyncSession, base_dir: Path) -> list[Skill]:
    imported: list[Skill] = []
    for path in sorted(item for item in base_dir.iterdir() if item.is_dir()):
        if not (path / "SKILL.md").is_file():
            continue
        imported.append(await import_skill_dir(session, path))
    return imported


async def export_skill(session: AsyncSession, name: str, output_dir: Path) -> Path:
    skill = await get_skill(session, name)
    if skill is None:
        raise ValueError(f"skill not found: {name}")
    target = output_dir / name
    for item in skill.config_body["files"]:
        relative = Path(str(item["path"]))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"unsafe skill file path: {item['path']}")
        path = target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(item["content"]), encoding="utf-8")
    return target


def _files_from_dir(dir_path: Path) -> list[dict[str, str]]:
    files: list[dict[str, str]] = []
    for path in sorted(item for item in dir_path.rglob("*") if item.is_file()):
        relative = path.relative_to(dir_path).as_posix()
        files.append({"path": relative, "content": path.read_text(encoding="utf-8")})
    return files
