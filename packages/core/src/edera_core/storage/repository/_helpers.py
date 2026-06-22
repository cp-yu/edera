from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from edera_core.config.schema import EntityConfig, EntityTypeConfig, entity_ref
from edera_core.storage.entities import EntityRelation, EntityTypeRecord
from edera_core.storage.materialization import (
    decode_value,
    ensure_ordinary_entity_table,
)


@dataclass(frozen=True)
class DeleteEntityResult:
    deleted: bool
    relations: list[EntityRelation]

    def __bool__(self) -> bool:
        return self.deleted


CORE_ENTITY_TABLES: dict[str, str] = {
    "node": "entity_node",
    "dag": "entity_dag",
    "input_mapping": "entity_input_mapping",
    "trigger": "entity_trigger",
    "resource": "entity_resource",
}


async def _all(session: AsyncSession, model):
    result = await session.exec(select(model).order_by(col(model.id)))
    return list(result.all())


def _skill_name(name: str) -> str:
    value = name.strip()
    if not value:
        raise ValueError("skill name is required")
    return value


def _skill_body(files: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    normalized: list[dict[str, str]] = []
    for item in files:
        path = str(item.get("path") or "").strip()
        content = item.get("content")
        if not path:
            raise ValueError("skill file path is required")
        relative = Path(path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"unsafe skill file path: {path}")
        if content is None:
            raise ValueError(f"skill file content is required: {path}")
        normalized.append({"path": path, "content": str(content)})
    if not any(item["path"] == "SKILL.md" for item in normalized):
        raise ValueError("skill must include SKILL.md")
    return {"files": normalized}


def _extra_attrs(attrs: dict[str, object], column_names: set[str]) -> dict[str, object]:
    return {key: value for key, value in attrs.items() if key not in column_names}


def _set_if_not_none(attrs: dict[str, object], key: str, value: object | None) -> None:
    if value is not None:
        attrs[key] = value


def _str_or_none(value: object) -> str | None:
    return str(value) if value is not None else None


def _float_or_none(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def _dict(value: object) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def _str_list(value: object) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _dict_list(value: object) -> list[dict[str, object]]:
    return [dict(item) for item in value] if isinstance(value, list) and all(isinstance(item, dict) for item in value) else []


def _json_dict(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value:
        data = json.loads(value)
        return dict(data) if isinstance(data, dict) else {}
    return {}


def _entity_refs(entity: EntityConfig, entity_types: dict[str, EntityTypeConfig]) -> set[str]:
    refs = {entity.id}
    try:
        refs.add(entity_ref(entity, entity_types))
    except (KeyError, ValueError):
        pass
    return refs


async def _ordinary_row(session: AsyncSession, table: str, entity_id: str):
    result = await session.exec(text(f"SELECT * FROM {table} WHERE id = :id"), params={"id": entity_id})
    row = result.first()
    return row._mapping if row is not None else None


async def _entity_exists(
    session: AsyncSession,
    ref: str,
    entity_types: dict[str, EntityTypeConfig],
    *,
    get_core_entity_fn=None,
    find_ordinary_entity_fn=None,
) -> bool:
    if get_core_entity_fn is not None and await get_core_entity_fn(session, ref, entity_types) is not None:
        return True
    if find_ordinary_entity_fn is not None and await find_ordinary_entity_fn(session, ref, entity_types) is not None:
        return True
    return False


async def _relation_by_key(
    session: AsyncSession,
    from_entity_id: str,
    to_entity_id: str,
    relation_type: str,
) -> EntityRelation | None:
    result = await session.exec(
        select(EntityRelation).where(
            EntityRelation.from_entity_id == from_entity_id,
            EntityRelation.to_entity_id == to_entity_id,
            EntityRelation.relation_type == relation_type,
        )
    )
    return result.first()


def _ordinary_entity_from_row(
    entity_type: str,
    config: EntityTypeConfig,
    row: object,
) -> EntityConfig:
    values = dict(row)
    attrs = _json_dict(values.get("attributes_json"))
    for field, field_config in config.materialized_fields.items():
        if field in config.deprecated_fields:
            continue
        if field in values and values[field] is not None:
            attrs[field] = decode_value(values[field], field_config.type)
    if config.business_id_field not in attrs:
        attrs[config.business_id_field] = values.get("business_id")
    return EntityConfig(id=str(values["id"]), type=entity_type, attributes=attrs)


def _ordinary_writable_attrs(attrs: dict[str, Any], config: EntityTypeConfig) -> dict[str, Any]:
    return {key: value for key, value in attrs.items() if key not in config.deprecated_fields}


def _is_database_ordinary_entity_type(entity_type: str, config: EntityTypeConfig | None) -> bool:
    return (
        config is not None
        and entity_type not in CORE_ENTITY_TABLES
        and entity_type != "relation"
        and config.storage_tier == "database"
    )


def _validate_entity_attributes(entity: EntityConfig, entity_type: EntityTypeConfig) -> None:
    from edera_core.config.loader import _validate_entity_attributes as validate
    from edera_core.errors import ConfigError

    try:
        validate(entity, entity_type)
    except ConfigError as exc:
        raise ValueError(str(exc)) from exc


def entity_type_record_to_config(record: EntityTypeRecord) -> EntityTypeConfig:
    return EntityTypeConfig.model_validate(
        {
            "display_name": record.display_name,
            "business_id_field": record.business_id_field,
            "display_template": record.display_template,
            "storage_tier": record.storage_tier,
            "table_name": record.table_name,
            "schema_version": record.schema_version,
            "materialized_fields": record.materialized_fields,
            "deprecated_fields": record.deprecated_fields,
            "system_protected": record.system_protected,
            "schema": record.schema_body,
            "field_permissions": record.field_permissions,
            "validate": record.validate_,
        }
    )
