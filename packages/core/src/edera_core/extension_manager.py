from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from edera_core.bootstrap import create_extension_tables, extension_table_name
from edera_core.config.loader import CORE_ENTITY_TYPES
from edera_core.config.schema import EntityConfig, EntityTypeConfig
from edera_core.extension_imports import _entity_digest, import_manifest_entities
from edera_core.manifest import EntityTypeDescriptor, parse_manifest
from edera_core.storage import session_factory
from edera_core.storage.repository import (
    delete_core_entity,
    delete_installed_extension,
    delete_ordinary_entity,
    get_core_entity,
    get_installed_extension,
    get_ordinary_entity,
    list_enabled_extensions,
    list_installed_extensions,
    save_installed_extension,
    seed_entity_type_records,
)


class ExtensionManager:
    def __init__(
        self,
        *,
        extensions_dir: Path = Path("extensions"),
        handlers_dir: Path = Path("handlers"),
        engine: AsyncEngine,
        config_entity_types: dict[str, EntityTypeConfig] | None = None,
    ) -> None:
        self.extensions_dir = extensions_dir
        self.handlers_dir = handlers_dir
        self.engine = engine
        self.config_entity_types = dict(config_entity_types or {})

    async def install(self, name: str, *, installed_by: str | None = None) -> dict[str, int]:
        root = self.extensions_dir / name
        manifest_path = root / "manifest.yaml"
        if not manifest_path.exists():
            raise FileNotFoundError(f"missing extension manifest: {manifest_path}")
        manifest = parse_manifest(manifest_path)
        if manifest.name != name:
            raise ValueError(f"manifest name mismatch: {manifest.name}")
        factory = session_factory(self.engine)
        async with factory() as session:
            if await get_installed_extension(session, manifest.name) is not None:
                raise ValueError(f"extension already installed: {manifest.name}")
            installed = {record.name for record in await list_enabled_extensions(session)}
            missing = [
                dependency
                for dependency in manifest.depends
                if not self._dependency_available(dependency, installed)
            ]
            if missing:
                raise ValueError(f"missing extension dependencies: {', '.join(missing)}")
            try:
                self._copy_handlers(root, manifest.name)
                await create_extension_tables(self.engine, {manifest.name: manifest.storage_tables})
                entity_types = await seed_entity_type_records(session, self._install_entity_types(manifest.entity_types))
                import_records = await import_manifest_entities(session, root, manifest, entity_types)
                await save_installed_extension(
                    session,
                    name=manifest.name,
                    version=manifest.version,
                    manifest_snapshot=_manifest_snapshot(manifest_path),
                    import_records=import_records,
                    installed_by=installed_by,
                )
                await session.commit()
            except Exception:
                await session.rollback()
                shutil.rmtree(self.handlers_dir / manifest.name, ignore_errors=True)
                await self._drop_extension_tables(manifest.name, manifest.storage_tables)
                raise
        return {
            "handlers": len(manifest.handlers),
            "entities": sum(1 for record in import_records if record["status"] == "imported"),
        }

    async def uninstall(self, name: str, strategy: str) -> dict[str, int]:
        if strategy not in {"purge", "keep-modified", "deactivate"}:
            raise ValueError("strategy must be purge, keep-modified, or deactivate")
        factory = session_factory(self.engine)
        async with factory() as session:
            record = await get_installed_extension(session, name)
            if record is None:
                raise ValueError(f"extension is not installed: {name}")
            dependents = [
                item.name
                for item in await list_installed_extensions(session)
                if item.name != name and name in item.manifest_data.get("depends", [])
            ]
            if dependents:
                raise ValueError(f"dependent extensions: {', '.join(sorted(dependents))}")
            if strategy == "deactivate":
                record.enabled = False
                session.add(record)
                await session.commit()
                return {"deleted_entities": 0, "deleted_tables": 0}

            entity_types = await seed_entity_type_records(session, self.config_entity_types)
            deleted_entities = 0
            for import_record in record.import_record_data:
                if await self._delete_imported_entity(session, import_record, entity_types, strategy):
                    deleted_entities += 1
            deleted_tables = 0
            if strategy == "purge":
                for table in record.manifest_data.get("storage", {}).get("tables", []):
                    table_name = table.get("name") if isinstance(table, dict) else None
                    if isinstance(table_name, str):
                        await session.exec(text(f"DROP TABLE IF EXISTS {extension_table_name(name, table_name)}"))
                        deleted_tables += 1
            await delete_installed_extension(session, name)
            await session.commit()
        shutil.rmtree(self.handlers_dir / name, ignore_errors=True)
        return {"deleted_entities": deleted_entities, "deleted_tables": deleted_tables}

    def _install_entity_types(self, manifest_entity_types: list[EntityTypeDescriptor]) -> dict[str, EntityTypeConfig]:
        entity_types = dict(self.config_entity_types)
        for descriptor in manifest_entity_types:
            entity_types[descriptor.name] = EntityTypeConfig.model_validate(
                {
                    "display_name": descriptor.display_name,
                    "business_id_field": descriptor.business_id_field,
                    "storage_tier": descriptor.storage_tier,
                    "schema": descriptor.schema,
                    "display_template": descriptor.display_template or f"{{{descriptor.business_id_field}}}",
                    "system_protected": descriptor.system_protected,
                    "field_permissions": descriptor.field_permissions,
                }
            )
        return entity_types

    def _copy_handlers(self, root: Path, name: str) -> None:
        target = self.handlers_dir / name
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
            lib_target = self.handlers_dir / "_lib"
            lib_target.mkdir(parents=True, exist_ok=True)
            for item in shared.iterdir():
                destination = lib_target / item.name
                if item.is_dir():
                    if destination.exists():
                        shutil.rmtree(destination)
                    shutil.copytree(item, destination)
                else:
                    shutil.copy2(item, destination)

    def _dependency_available(self, dependency: str, installed: set[str]) -> bool:
        if not dependency.startswith("_lib/"):
            return dependency in installed
        return (self.extensions_dir / f"{dependency}.py").exists() or (self.handlers_dir / f"{dependency}.py").exists()

    async def _drop_extension_tables(self, extension_name: str, tables: list[Any]) -> None:
        async with self.engine.begin() as conn:
            for table in tables:
                table_name = getattr(table, "name", None)
                if isinstance(table_name, str):
                    await conn.execute(text(f"DROP TABLE IF EXISTS {extension_table_name(extension_name, table_name)}"))

    async def _delete_imported_entity(
        self,
        session,
        import_record: dict[str, Any],
        entity_types: dict[str, EntityTypeConfig],
        strategy: str,
    ) -> bool:
        entity_type = str(import_record.get("entity_type") or "")
        entity_id = str(import_record.get("entity_id") or "")
        if not entity_type or not entity_id:
            return False
        if strategy == "keep-modified":
            if import_record.get("status") != "imported":
                return False
            current = await _get_entity(session, entity_type, entity_id, entity_types)
            if current is None or _entity_digest(current) != import_record.get("imported_entity_digest"):
                return False
        if entity_type in CORE_ENTITY_TYPES:
            return await delete_core_entity(session, entity_id, entity_types)
        return await delete_ordinary_entity(session, entity_id, entity_types)


def _manifest_snapshot(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"invalid manifest: {path}")
    return data


async def _get_entity(session, entity_type: str, entity_id: str, entity_types: dict[str, EntityTypeConfig]) -> EntityConfig | None:
    if entity_type in CORE_ENTITY_TYPES:
        return await get_core_entity(session, entity_id, entity_types)
    return await get_ordinary_entity(session, entity_type, entity_id, entity_types)
