from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from edera_core.manifest import (
    ExtensionManifest,
    StorageTableDescriptor,
    manifest_from_mapping,
    parse_manifest,
)
from edera_core.storage.repository import list_enabled_extensions


@dataclass(frozen=True)
class BootstrapResult:
    manifests: list[ExtensionManifest]
    storage_tables: dict[str, list[StorageTableDescriptor]]
    table_names: dict[str, dict[str, str]]
    extension_roots: dict[str, Path]

    def __iter__(self):
        return iter(self.manifests)


def discover_available_extensions(extensions_dirs: list[Path] | None = None) -> list[ExtensionManifest]:
    extensions_dirs = extensions_dirs or [Path("extensions")]
    manifests: list[ExtensionManifest] = []
    for root in extensions_dirs:
        if not root.exists():
            continue
        for child in sorted(item for item in root.iterdir() if item.is_dir() and not item.name.startswith("_")):
            manifest_path = child / "manifest.yaml"
            if manifest_path.exists():
                manifests.append(parse_manifest(manifest_path))
    return manifests


async def load_installed_extensions(session, handlers_dir: Path = Path("handlers")) -> BootstrapResult:
    _ensure_path(handlers_dir)
    manifests: list[ExtensionManifest] = []
    storage_tables: dict[str, list[StorageTableDescriptor]] = {}
    table_names: dict[str, dict[str, str]] = {}
    extension_roots: dict[str, Path] = {}
    for record in await list_enabled_extensions(session):
        manifest = manifest_from_mapping(record.manifest_data)
        manifests.append(manifest)
        root = handlers_dir / manifest.name
        extension_roots[manifest.name] = root
        storage_tables[manifest.name] = manifest.storage_tables
        table_names[manifest.name] = {
            table.name: extension_table_name(manifest.name, table.name) for table in manifest.storage_tables
        }
    return BootstrapResult(
        manifests,
        storage_tables,
        table_names,
        extension_roots,
    )


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
