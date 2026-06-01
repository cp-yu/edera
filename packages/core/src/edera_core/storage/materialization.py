from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from edera_core.config.schema import EntityTypeConfig, MaterializedFieldConfig


COLUMN_TYPES = {
    "integer": "INTEGER",
    "text": "TEXT",
    "real": "REAL",
    "datetime": "TEXT",
    "boolean": "INTEGER",
    "json": "TEXT",
}


@dataclass(frozen=True)
class MaterializationPlan:
    entity_type: str
    table_name: str
    field: str
    column_type: str
    index: bool
    backfill_count: int
    column_exists: bool
    index_name: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "entity_type": self.entity_type,
            "table_name": self.table_name,
            "field": self.field,
            "column": self.field,
            "column_type": self.column_type,
            "index": self.index,
            "index_name": self.index_name,
            "backfill_count": self.backfill_count,
            "column_exists": self.column_exists,
        }


def entity_table_name(entity_type: str) -> str:
    return f"entity_{identifier(entity_type)}"


def identifier(value: str) -> str:
    normalized = value.replace("-", "_")
    if not normalized.isidentifier():
        raise ValueError(f"invalid SQL identifier: {value}")
    return normalized


async def ensure_ordinary_entity_table(
    session: AsyncSession,
    type_name: str,
    entity_type: EntityTypeConfig,
) -> str:
    table_name = entity_type.table_name or entity_table_name(type_name)
    table = identifier(table_name)
    await session.exec(
        text(
            f"CREATE TABLE IF NOT EXISTS {table} ("
            "id TEXT PRIMARY KEY, "
            "business_id TEXT NOT NULL UNIQUE, "
            "schema_version INTEGER NOT NULL, "
            "attributes_json TEXT NOT NULL, "
            "created_at TEXT NOT NULL, "
            "updated_at TEXT NOT NULL"
            ")"
        )
    )
    for field in entity_type.materialized_fields:
        await _ensure_column(session, table, field, entity_type.materialized_fields[field].type)
    for field, config in entity_type.materialized_fields.items():
        if config.index:
            await _ensure_index(session, table, field)
    return table


async def materialization_plan(
    session: AsyncSession,
    type_name: str,
    entity_type: EntityTypeConfig,
    field: str,
    field_type: str | None = None,
    index: bool | None = None,
) -> MaterializationPlan:
    config = _field_config(entity_type, field, field_type, index)
    table = await ensure_ordinary_entity_table(session, type_name, entity_type)
    column_exists = await has_column(session, table, field)
    result = await session.exec(text(f"SELECT attributes_json FROM {table}"))
    backfill_count = 0
    for row in result.all():
        attrs = _json(row[0])
        if field in attrs:
            backfill_count += 1
    return MaterializationPlan(
        entity_type=type_name,
        table_name=table,
        field=field,
        column_type=config.type,
        index=config.index,
        backfill_count=backfill_count,
        column_exists=column_exists,
        index_name=_index_name(table, field) if config.index else None,
    )


async def apply_materialization(
    session: AsyncSession,
    type_name: str,
    entity_type: EntityTypeConfig,
    field: str,
    field_type: str | None = None,
    index: bool | None = None,
) -> MaterializationPlan:
    plan = await materialization_plan(session, type_name, entity_type, field, field_type, index)
    if not plan.column_exists:
        await _ensure_column(session, plan.table_name, field, plan.column_type)
    if plan.index:
        await _ensure_index(session, plan.table_name, field)
    result = await session.exec(text(f"SELECT id, attributes_json FROM {plan.table_name}"))
    for row in result.all():
        attrs = _json(row[1])
        if field not in attrs:
            continue
        await session.exec(
            text(f"UPDATE {plan.table_name} SET {identifier(field)} = :value WHERE id = :id"),
            params={"value": encode_value(attrs[field], plan.column_type), "id": row[0]},
        )
    return plan


async def deprecated_cleanup_ready(
    session: AsyncSession,
    type_name: str,
    entity_type: EntityTypeConfig,
    field: str,
) -> bool:
    if field not in entity_type.deprecated_fields:
        return False
    table = await ensure_ordinary_entity_table(session, type_name, entity_type)
    result = await session.exec(text(f"SELECT attributes_json FROM {table}"))
    return all(field not in _json(row[0]) for row in result.all())


async def has_column(session: AsyncSession, table_name: str, column_name: str) -> bool:
    result = await session.exec(text(f"PRAGMA table_info({identifier(table_name)})"))
    return identifier(column_name) in {row[1] for row in result.all()}


def encode_value(value: object, column_type: str) -> object:
    if value is None:
        return None
    if column_type == "boolean":
        return int(bool(value))
    if column_type == "integer":
        return int(value)
    if column_type == "real":
        return float(value)
    if column_type == "json":
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def decode_value(value: object, column_type: str) -> object:
    if value is None:
        return None
    if column_type == "boolean":
        return bool(value)
    if column_type == "integer":
        return int(value)
    if column_type == "real":
        return float(value)
    if column_type == "json":
        return json.loads(str(value))
    return value


async def _ensure_column(
    session: AsyncSession,
    table_name: str,
    field: str,
    field_type: str,
) -> None:
    if field_type not in COLUMN_TYPES:
        raise ValueError(f"unsupported materialized field type: {field_type}")
    if await has_column(session, table_name, field):
        return
    await session.exec(text(f"ALTER TABLE {identifier(table_name)} ADD COLUMN {identifier(field)} {COLUMN_TYPES[field_type]}"))


async def _ensure_index(session: AsyncSession, table_name: str, field: str) -> None:
    index_name = _index_name(table_name, field)
    await session.exec(
        text(f"CREATE INDEX IF NOT EXISTS {identifier(index_name)} ON {identifier(table_name)} ({identifier(field)})")
    )


def _field_config(
    entity_type: EntityTypeConfig,
    field: str,
    field_type: str | None,
    index: bool | None,
) -> MaterializedFieldConfig:
    existing = entity_type.materialized_fields.get(field)
    if existing is not None:
        return MaterializedFieldConfig(type=field_type or existing.type, index=existing.index if index is None else index)
    return MaterializedFieldConfig(type=field_type or _schema_field_type(entity_type, field), index=bool(index))


def _schema_field_type(entity_type: EntityTypeConfig, field: str) -> str:
    properties = entity_type.schema_.get("properties")
    field_schema = properties.get(field) if isinstance(properties, dict) else None
    raw = field_schema.get("type") if isinstance(field_schema, dict) else None
    if raw == "number":
        return "real"
    if raw == "string":
        return "text"
    if raw in COLUMN_TYPES:
        return str(raw)
    return "text"


def _index_name(table_name: str, field: str) -> str:
    return f"idx_{identifier(table_name)}_{identifier(field)}"


def _json(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value:
        data = json.loads(value)
        return dict(data) if isinstance(data, dict) else {}
    return {}
