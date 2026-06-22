from __future__ import annotations

import json

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from edera_core.storage.entities import InstalledExtension, utc_now


async def save_installed_extension(
    session: AsyncSession,
    *,
    name: str,
    version: str,
    manifest_snapshot: dict[str, object],
    import_records: list[dict[str, object]] | None = None,
    enabled: bool = True,
    installed_by: str | None = None,
) -> InstalledExtension:
    record = await get_installed_extension(session, name)
    if record is None:
        record = InstalledExtension(name=name, version=version, manifest_snapshot="{}")
    record.version = version
    record.manifest_snapshot = json.dumps(manifest_snapshot, ensure_ascii=False, sort_keys=True)
    record.import_records = json.dumps(import_records or [], ensure_ascii=False, sort_keys=True)
    record.enabled = enabled
    record.installed_by = installed_by
    record.updated_at = utc_now().isoformat()
    session.add(record)
    await session.flush()
    return record


async def get_installed_extension(session: AsyncSession, name: str) -> InstalledExtension | None:
    result = await session.exec(select(InstalledExtension).where(InstalledExtension.name == name))
    return result.first()


async def list_installed_extensions(session: AsyncSession) -> list[InstalledExtension]:
    result = await session.exec(select(InstalledExtension).order_by(col(InstalledExtension.name)))
    return list(result.all())


async def list_enabled_extensions(session: AsyncSession) -> list[InstalledExtension]:
    result = await session.exec(
        select(InstalledExtension).where(InstalledExtension.enabled == True).order_by(col(InstalledExtension.name))
    )
    return list(result.all())


async def delete_installed_extension(session: AsyncSession, name: str) -> bool:
    record = await get_installed_extension(session, name)
    if record is None:
        return False
    await session.delete(record)
    await session.flush()
    return True
