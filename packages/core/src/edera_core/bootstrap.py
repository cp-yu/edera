from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from edera_core.config.loader import load_entity_types
from edera_core.config.schema import EntityTypeConfig
from edera_core.manifest import (
    EntityTypeDescriptor,
    ExtensionManifest,
    StorageTableDescriptor,
    parse_manifest,
)
from edera_core.registry import EntityTypeRegistry, HandlerRegistry


@dataclass(frozen=True)
class BootstrapResult:
    handler_registry: HandlerRegistry
    entity_type_registry: EntityTypeRegistry
    manifests: list[ExtensionManifest]
    storage_tables: dict[str, list[StorageTableDescriptor]]
    table_names: dict[str, dict[str, str]]
    extension_roots: dict[str, Path]

    def __iter__(self):
        return iter(self.manifests)


def scan_extensions(
    extensions_dirs: list[Path] | None = None,
    config_dir: Path | None = None,
) -> BootstrapResult:
    extensions_dirs = extensions_dirs or [Path("extensions")]
    handlers = HandlerRegistry()
    extension_entity_types: dict[str, EntityTypeConfig] = {}
    manifests: list[ExtensionManifest] = []
    storage_tables: dict[str, list[StorageTableDescriptor]] = {}
    table_names: dict[str, dict[str, str]] = {}
    extension_roots: dict[str, Path] = {}
    for root in extensions_dirs:
        if not root.exists():
            continue
        _ensure_path(root)
        for child in sorted(item for item in root.iterdir() if item.is_dir()):
            if child.name.startswith("_"):
                continue
            manifest_path = child / "manifest.yaml"
            if manifest_path.exists():
                manifest = parse_manifest(manifest_path)
                _validate_dependencies(root, manifest)
                manifests.append(manifest)
                extension_roots[manifest.name] = child
                storage_tables[manifest.name] = manifest.storage_tables
                table_names[manifest.name] = {
                    table.name: extension_table_name(manifest.name, table.name) for table in manifest.storage_tables
                }
                for handler in manifest.handlers:
                    handlers.register(handler.name, child / handler.entry, descriptor=handler)
                for entity_type in manifest.entity_types:
                    extension_entity_types[entity_type.name] = _entity_type_config(entity_type)
                continue
            _register_fallback_handlers(handlers, child)
    merged = extension_entity_types
    if config_dir is not None:
        merged = {**load_entity_types(config_dir), **merged}
    return BootstrapResult(handlers.seal(), EntityTypeRegistry(merged), manifests, storage_tables, table_names, extension_roots)


async def create_extension_tables(engine: AsyncEngine, tables: dict[str, list[StorageTableDescriptor]]) -> None:
    async with engine.begin() as conn:
        for extension_name, descriptors in tables.items():
            for table in descriptors:
                table_name = extension_table_name(extension_name, table.name)
                columns = ", ".join(_column_sql(column) for column in table.columns)
                await conn.execute(text(f"CREATE TABLE IF NOT EXISTS {table_name} ({columns})"))
                for column in table.columns:
                    if column.index and not column.primary_key:
                        index_name = f"idx_{table_name}_{_identifier(column.name)}"
                        await conn.execute(text(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({_identifier(column.name)})"))


def extension_table_name(extension_name: str, table_name: str) -> str:
    return f"ext_{_identifier(extension_name)}_{_identifier(table_name)}"


def _ensure_path(path: Path) -> None:
    value = str(path.resolve())
    if value not in sys.path:
        sys.path.insert(0, value)


def _validate_dependencies(root: Path, manifest: ExtensionManifest) -> None:
    for dependency in manifest.depends:
        if dependency.startswith("_lib/"):
            path = root / f"{dependency}.py"
            if not path.exists():
                raise ValueError(f"missing extension dependency: {dependency}")
            continue
        if not (root / dependency).exists():
            raise ValueError(f"missing extension dependency: {dependency}")


def _register_fallback_handlers(registry: HandlerRegistry, directory: Path) -> None:
    files = [file for file in directory.glob("*.py") if file.name != "__init__.py"]
    if directory.joinpath("handler.py").exists():
        registry.register(directory.name, directory / "handler.py")
        return
    for file in files:
        registry.register(file.stem, file)


def _entity_type_config(descriptor: EntityTypeDescriptor) -> EntityTypeConfig:
    return EntityTypeConfig(
        display_name=descriptor.display_name,
        business_id_field=descriptor.business_id_field,
        display_template=descriptor.display_template or f"{{{descriptor.business_id_field}}}",
        storage_tier=descriptor.storage_tier,
        system_protected=descriptor.system_protected,
        schema=descriptor.schema,
        field_permissions=descriptor.field_permissions,
    )


def _column_sql(column: Any) -> str:
    name = _identifier(column.name)
    sql_type = _sql_type(column.type)
    parts = [name, sql_type]
    if column.primary_key:
        parts.extend(["PRIMARY KEY", "AUTOINCREMENT"])
    if column.unique:
        parts.append("UNIQUE")
    if not column.nullable and not column.primary_key:
        parts.append("NOT NULL")
    return " ".join(parts)


def _sql_type(value: str) -> str:
    types = {
        "integer": "INTEGER",
        "text": "TEXT",
        "real": "REAL",
        "datetime": "TEXT",
        "boolean": "INTEGER",
        "json": "TEXT",
    }
    try:
        return types[value]
    except KeyError as exc:
        raise ValueError(f"unsupported extension column type: {value}") from exc


def _identifier(value: str) -> str:
    normalized = value.replace("-", "_")
    if not normalized.isidentifier():
        raise ValueError(f"invalid SQL identifier: {value}")
    return normalized
