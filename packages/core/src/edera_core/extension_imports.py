from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml
from sqlmodel.ext.asyncio.session import AsyncSession

from edera_core.config.loader import CORE_ENTITY_TYPES
from edera_core.config.schema import EntityConfig, EntityTypeConfig, entity_ref
from edera_core.manifest import ExtensionManifest
from edera_core.storage.repository import (
    get_core_entity,
    get_ordinary_entity,
    save_core_entity,
    save_ordinary_entity,
)


async def import_manifest_entities(
    session: AsyncSession,
    extension_root: Path,
    manifest: ExtensionManifest,
    entity_types: dict[str, EntityTypeConfig],
    existing_records: list[dict[str, object]] | None = None,
    *,
    overwrite: bool = False,
) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    imported_paths = {
        str(record.get("import_path"))
        for record in existing_records or []
        if record.get("import_path") is not None
    }
    for import_path in expand_import_paths(extension_root, manifest.entity_imports):
        if import_path in imported_paths:
            continue
        content = (extension_root / import_path).read_bytes()
        entity = EntityConfig.model_validate(yaml.safe_load(content) or {})
        entity_type = entity_types.get(entity.type)
        if entity_type is None:
            raise ValueError(f"unknown entity type in extension import: {entity.type}")
        existing = await _get_entity(session, entity, entity_types)
        if existing is None or overwrite:
            saved = await _save_entity(session, entity, entity_type)
            status = "imported"
        else:
            saved = existing
            status = "skipped_existing"
        records.append(
            {
                "import_path": import_path,
                "entity_type": entity.type,
                "entity_id": entity.id,
                "entity_ref": entity_ref(saved, entity_types),
                "content_digest": hashlib.sha256(content).hexdigest(),
                "imported_entity_digest": _entity_digest(saved),
                "status": status,
            }
        )
    return records


async def _get_entity(
    session: AsyncSession,
    entity: EntityConfig,
    entity_types: dict[str, EntityTypeConfig],
) -> EntityConfig | None:
    ref = entity_ref(entity, entity_types)
    if entity.type in CORE_ENTITY_TYPES:
        return await get_core_entity(session, ref, entity_types)
    return await get_ordinary_entity(session, entity.type, ref.removeprefix(f"{entity.type}:"), entity_types)


async def _save_entity(
    session: AsyncSession,
    entity: EntityConfig,
    entity_type: EntityTypeConfig,
) -> EntityConfig:
    if entity.type in CORE_ENTITY_TYPES:
        return await save_core_entity(session, entity)
    if entity_type.storage_tier != "database":
        raise ValueError(f"extension import requires database-backed entity type: {entity.type}")
    return await save_ordinary_entity(session, entity, entity_type)


def _entity_digest(entity: EntityConfig) -> str:
    content = json.dumps(entity.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def expand_import_paths(root: Path, imports: list[str], *, files_only: bool = True) -> list[str]:
    paths: list[str] = []
    for item in imports:
        matches = _import_matches(root, item, files_only=files_only)
        if not matches:
            raise ValueError(f"glob pattern matched no files: {item}")
        for path in matches:
            relative = path.relative_to(root).as_posix()
            if relative not in paths:
                paths.append(relative)
    return paths


def _import_matches(root: Path, item: str, *, files_only: bool) -> list[Path]:
    if not _is_glob(item):
        return [root / item]
    matches = sorted(root.glob(item))
    return [path for path in matches if path.is_file()] if files_only else matches


def _is_glob(value: str) -> bool:
    return any(char in value for char in "*?[")
