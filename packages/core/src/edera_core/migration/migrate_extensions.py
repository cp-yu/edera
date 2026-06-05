from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import yaml
from sqlmodel.ext.asyncio.session import AsyncSession

from edera_core.bootstrap import discover_available_extensions
from edera_core.config.loader import _runtime_entity_types
from edera_core.config.schema import EntityTypeConfig
from edera_core.extension_imports import import_manifest_entities
from edera_core.manifest import ExtensionManifest
from edera_core.storage.repository import list_installed_extensions, save_installed_extension


async def migrate_existing_extensions(
    session: AsyncSession,
    extensions_dirs: list[Path],
    *,
    handlers_dir: Path | None = None,
    entity_types: dict[str, EntityTypeConfig] | None = None,
    installed_by: str = "migration",
) -> int:
    if await list_installed_extensions(session):
        return 0
    manifests = discover_available_extensions(extensions_dirs)
    merged_entity_types = _extension_entity_types(manifests, entity_types or {})
    count = 0
    for manifest in manifests:
        manifest_path = _manifest_path(extensions_dirs, manifest.name)
        if handlers_dir is not None:
            _copy_handlers(manifest_path.parent, handlers_dir / manifest.name)
        import_records = await import_manifest_entities(
            session,
            manifest_path.parent,
            manifest,
            merged_entity_types,
        )
        await save_installed_extension(
            session,
            name=manifest.name,
            version=manifest.version,
            manifest_snapshot=_manifest_snapshot(manifest_path),
            import_records=import_records,
            installed_by=installed_by,
        )
        count += 1
    return count


def _extension_entity_types(
    manifests: list[ExtensionManifest],
    entity_types: dict[str, EntityTypeConfig],
) -> dict[str, EntityTypeConfig]:
    merged = _runtime_entity_types(entity_types)
    for manifest in manifests:
        for descriptor in manifest.entity_types:
            merged[descriptor.name] = EntityTypeConfig(
                display_name=descriptor.display_name,
                business_id_field=descriptor.business_id_field,
                display_template=descriptor.display_template or f"{{{descriptor.business_id_field}}}",
                storage_tier=descriptor.storage_tier,
                system_protected=descriptor.system_protected,
                schema=descriptor.schema,
                field_permissions=descriptor.field_permissions,
            )
    return merged


def _manifest_path(extensions_dirs: list[Path], name: str) -> Path:
    for root in extensions_dirs:
        path = root / name / "manifest.yaml"
        if path.exists():
            return path
    raise FileNotFoundError(f"extension manifest not found: {name}")


def _manifest_snapshot(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"invalid manifest: {path}")
    return data


def _copy_handlers(root: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    for item in root.iterdir():
        if item.name in {"manifest.yaml", "entities", "_lib"}:
            continue
        destination = target / item.name
        if item.is_dir():
            shutil.copytree(item, destination)
        else:
            shutil.copy2(item, destination)
    shared = root / "_lib"
    if shared.exists():
        lib_target = target.parent / "_lib"
        lib_target.mkdir(parents=True, exist_ok=True)
        for item in shared.iterdir():
            destination = lib_target / item.name
            if item.is_dir():
                if destination.exists():
                    shutil.rmtree(destination)
                shutil.copytree(item, destination)
            else:
                shutil.copy2(item, destination)
