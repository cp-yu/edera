from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class NodeTypeDescriptor:
    name: str
    role: str
    input_type: str
    output_type: str
    entry: str
    timeout_seconds: float | None = None


@dataclass(frozen=True)
class EntityTypeDescriptor:
    name: str
    display_name: str
    business_id_field: str
    storage_tier: str = "filesystem"
    schema: dict[str, Any] = field(default_factory=dict)
    display_template: str | None = None
    system_protected: bool = False
    field_permissions: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class StorageTableColumn:
    name: str
    type: str
    primary_key: bool = False
    unique: bool = False
    index: bool = False
    nullable: bool = True


@dataclass(frozen=True)
class StorageTableDescriptor:
    name: str
    columns: list[StorageTableColumn]


@dataclass(frozen=True)
class ExtensionManifest:
    name: str
    version: str
    description: str | None = None
    depends: list[str] = field(default_factory=list)
    handlers: list[NodeTypeDescriptor] = field(default_factory=list)
    entity_types: list[EntityTypeDescriptor] = field(default_factory=list)
    storage_tables: list[StorageTableDescriptor] = field(default_factory=list)
    entity_imports: list[str] = field(default_factory=list)


def parse_manifest(path: Path) -> ExtensionManifest:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return manifest_from_mapping(raw, path)


def manifest_from_mapping(raw: Any, path: Path | None = None) -> ExtensionManifest:
    if not isinstance(raw, dict):
        raise ValueError(f"invalid manifest: {path}")
    missing = [field for field in ("name", "version") if not isinstance(raw.get(field), str) or not raw.get(field)]
    if missing:
        raise ValueError(f"missing manifest field(s): {', '.join(missing)} in {path}")
    source = path or Path("<manifest>")
    handlers = [_parse_handler(item, source) for item in _list(raw.get("handlers"))]
    entity_types = [_parse_entity_type(item, source) for item in _list(raw.get("entity_types"))]
    storage_tables = [_parse_storage_table(item, source) for item in _list(raw.get("storage"), "tables")]
    entity_imports = [_parse_entity_import(item, source) for item in _list(raw.get("imports"), "entities")]
    return ExtensionManifest(
        name=str(raw["name"]),
        version=str(raw["version"]),
        description=str(raw["description"]) if isinstance(raw.get("description"), str) else None,
        depends=[str(item) for item in _list(raw.get("depends"))],
        handlers=handlers,
        entity_types=entity_types,
        storage_tables=storage_tables,
        entity_imports=entity_imports,
    )


def _list(raw: Any, key: str | None = None) -> list[Any]:
    if key is not None:
        if not isinstance(raw, dict):
            return []
        raw = raw.get(key)
    return raw if isinstance(raw, list) else []


def _parse_handler(raw: Any, path: Path) -> NodeTypeDescriptor:
    if not isinstance(raw, dict):
        raise ValueError(f"invalid handler entry in {path}")
    required = [name for name in ("name", "role", "input_type", "entry") if not isinstance(raw.get(name), str) or not raw.get(name)]
    if required:
        raise ValueError(f"missing handler field(s): {', '.join(required)} in {path}")
    return NodeTypeDescriptor(
        name=str(raw["name"]),
        role=str(raw["role"]),
        input_type=str(raw["input_type"]),
        output_type=str(raw.get("output_type") or "Any"),
        entry=str(raw["entry"]),
        timeout_seconds=_float(raw.get("timeout_seconds")),
    )


def _parse_entity_type(raw: Any, path: Path) -> EntityTypeDescriptor:
    if not isinstance(raw, dict):
        raise ValueError(f"invalid entity type entry in {path}")
    required = [name for name in ("name", "display_name", "business_id_field") if not isinstance(raw.get(name), str) or not raw.get(name)]
    if required:
        raise ValueError(f"missing entity type field(s): {', '.join(required)} in {path}")
    return EntityTypeDescriptor(
        name=str(raw["name"]),
        display_name=str(raw["display_name"]),
        business_id_field=str(raw["business_id_field"]),
        storage_tier=str(raw.get("storage_tier") or "filesystem"),
        schema=raw.get("schema") if isinstance(raw.get("schema"), dict) else {},
        display_template=str(raw["display_template"]) if isinstance(raw.get("display_template"), str) else None,
        system_protected=bool(raw.get("system_protected", False)),
        field_permissions=raw.get("field_permissions") if isinstance(raw.get("field_permissions"), dict) else {},
    )


def _parse_storage_table(raw: Any, path: Path) -> StorageTableDescriptor:
    if not isinstance(raw, dict):
        raise ValueError(f"invalid storage table entry in {path}")
    if not isinstance(raw.get("name"), str) or not raw.get("name"):
        raise ValueError(f"missing storage table field: name in {path}")
    if not isinstance(raw.get("columns"), list) or not raw.get("columns"):
        raise ValueError(f"missing storage table field: columns in {path}")
    columns: list[StorageTableColumn] = []
    for item in raw["columns"]:
        if not isinstance(item, dict):
            raise ValueError(f"invalid storage table column in {path}")
        if not isinstance(item.get("name"), str) or not isinstance(item.get("type"), str):
            raise ValueError(f"missing storage table column field in {path}")
        columns.append(
            StorageTableColumn(
                name=str(item["name"]),
                type=str(item["type"]),
                primary_key=bool(item.get("primary_key", False)),
                unique=bool(item.get("unique", False)),
                index=bool(item.get("index", False)),
                nullable=bool(item.get("nullable", True)),
            )
        )
    return StorageTableDescriptor(name=str(raw["name"]), columns=columns)


def _parse_entity_import(raw: Any, path: Path) -> str:
    if not isinstance(raw, str) or not raw:
        raise ValueError(f"invalid entity import path in {path}: {raw}")
    import_path = Path(raw)
    if import_path.is_absolute() or ".." in import_path.parts:
        raise ValueError(f"invalid entity import path in {path}: {raw}")
    return raw


def _float(value: Any) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    return None
