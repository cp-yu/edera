from __future__ import annotations

from pathlib import Path

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from edera_core.config.schema import SkillConfig
from edera_core.storage.entities import Skill, utc_now
from edera_core.storage.repository._helpers import _skill_body, _skill_name


async def create_skill(
    session: AsyncSession,
    name: str,
    files: list[dict[str, str]],
    display_name: str | None = None,
    description: str | None = None,
    skills_dir: Path | None = None,
) -> Skill:
    body = _skill_body(files)
    skill = Skill(name=_skill_name(name), display_name=display_name, description=description, config_body=body)
    session.add(skill)
    await session.flush()
    if skills_dir is not None:
        from edera_core.skills.generator import refresh_skill_files
        refresh_skill_files(skills_dir, skill_to_config(skill))
    return skill


async def update_skill(
    session: AsyncSession,
    name: str,
    files: list[dict[str, str]],
    display_name: str | None = None,
    description: str | None = None,
    skills_dir: Path | None = None,
) -> Skill:
    skill = await get_skill(session, name)
    if skill is None:
        raise ValueError(f"skill not found: {name}")
    skill.config_body = _skill_body(files)
    skill.display_name = display_name
    skill.description = description
    skill.updated_at = utc_now()
    session.add(skill)
    await session.flush()
    if skills_dir is not None:
        from edera_core.skills.generator import refresh_skill_files
        refresh_skill_files(skills_dir, skill_to_config(skill))
    return skill


async def upsert_skill(
    session: AsyncSession,
    name: str,
    files: list[dict[str, str]],
    display_name: str | None = None,
    description: str | None = None,
    skills_dir: Path | None = None,
) -> Skill:
    current = await get_skill(session, name)
    if current is None:
        return await create_skill(session, name, files, display_name, description, skills_dir)
    return await update_skill(session, name, files, display_name, description, skills_dir)


async def get_skill(session: AsyncSession, name: str) -> Skill | None:
    result = await session.exec(select(Skill).where(Skill.name == name))
    return result.first()


async def delete_skill(session: AsyncSession, name: str, skills_dir: Path | None = None) -> bool:
    skill = await get_skill(session, name)
    if skill is None:
        return False
    await session.delete(skill)
    await session.flush()
    if skills_dir is not None:
        from edera_core.skills.generator import remove_skill_files
        remove_skill_files(skills_dir, name)
    return True


async def list_skills(session: AsyncSession) -> list[Skill]:
    result = await session.exec(select(Skill).order_by(col(Skill.name)))
    return list(result.all())


async def list_skill_configs(session: AsyncSession) -> dict[str, SkillConfig]:
    return {skill.name: skill_to_config(skill) for skill in await list_skills(session)}


def skill_to_config(skill: Skill) -> SkillConfig:
    body = skill.config_body if isinstance(skill.config_body, dict) else {}
    files = body.get("files") if isinstance(body.get("files"), list) else []
    return SkillConfig.model_validate(
        {
            "name": skill.name,
            "display_name": skill.display_name,
            "description": skill.description or "",
            "handler": skill.name,
            "parameters_schema": {},
            "files": files,
        }
    )
