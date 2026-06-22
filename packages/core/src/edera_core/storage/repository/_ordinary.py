from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from edera_core.config.schema import EntityConfig, EntityTypeConfig
from edera_core.storage.entities import utc_now
from edera_core.storage.materialization import encode_value, ensure_ordinary_entity_table
from edera_core.storage.repository._helpers import (
    DeleteEntityResult,
    _entity_refs,
    _is_database_ordinary_entity_type,
    _json_dict,
    _ordinary_entity_from_row,
    _ordinary_row,
    _ordinary_writable_attrs,
    _validate_entity_attributes,
)


async def save_ordinary_entity(
    session: AsyncSession,
    entity: EntityConfig,
    entity_type: EntityTypeConfig,
) -> EntityConfig:
    if entity.type == "relation":
        raise ValueError("relation entities use create_relation")
    _validate_entity_attributes(entity, entity_type)
    table = await ensure_ordinary_entity_table(session, entity.type, entity_type)
    attrs = _ordinary_writable_attrs(entity.attributes, entity_type)
    business_id = entity.id if entity_type.business_id_field == "id" else attrs.get(entity_type.business_id_field)
    if not isinstance(business_id, str) or not business_id:
        raise ValueError(f"entity {entity.id} missing business id field: {entity_type.business_id_field}")
    now = utc_now().isoformat()
    row = await _ordinary_row(session, table, entity.id)
    created_at = row["created_at"] if row is not None else now
    materialized = {
        field: encode_value(attrs[field], config.type)
        for field, config in entity_type.materialized_fields.items()
        if field in attrs and field not in entity_type.deprecated_fields
    }
    json_attrs = {
        key: value
        for key, value in attrs.items()
        if key not in entity_type.materialized_fields and key not in entity_type.deprecated_fields
    }
    columns = ["id", "business_id", "schema_version", "attributes_json", "created_at", "updated_at", *materialized]
    values = {
        "id": entity.id,
        "business_id": business_id,
        "schema_version": entity_type.schema_version,
        "attributes_json": json.dumps(json_attrs, ensure_ascii=False),
        "created_at": created_at,
        "updated_at": now,
        **materialized,
    }
    assignments = [f"{_identifier(column)} = :{column}" for column in columns if column != "id"]
    await session.exec(
        text(
            f"INSERT INTO {table} ({', '.join(_identifier(column) for column in columns)}) "
            f"VALUES ({', '.join(':' + column for column in columns)}) "
            f"ON CONFLICT(id) DO UPDATE SET {', '.join(assignments)}"
        ),
        params=values,
    )
    await session.flush()
    return await get_ordinary_entity(session, entity.type, entity.id, {entity.type: entity_type}) or entity


async def create_ordinary_entity(
    session: AsyncSession,
    entity_type: str,
    entity_id: str,
    attributes: dict[str, Any],
    entity_types: dict[str, EntityTypeConfig],
) -> EntityConfig:
    if entity_type == "relation":
        raise ValueError("relation entities use create_relation")
    config = entity_types.get(entity_type)
    if config is None:
        raise ValueError(f"unknown entity type: {entity_type}")
    return await save_ordinary_entity(session, EntityConfig(id=entity_id, type=entity_type, attributes=attributes), config)


async def update_ordinary_entity(
    session: AsyncSession,
    ref: str,
    attributes: dict[str, Any],
    entity_types: dict[str, EntityTypeConfig],
) -> EntityConfig:
    current = await find_ordinary_entity(session, ref, entity_types)
    if current is None:
        raise ValueError(f"entity not found: {ref}")
    updated = current.model_copy(update={"attributes": {**current.attributes, **attributes}})
    return await save_ordinary_entity(session, updated, entity_types[updated.type])


async def list_ordinary_entities(
    session: AsyncSession,
    entity_types: dict[str, EntityTypeConfig],
    entity_type: str | None = None,
) -> list[EntityConfig]:
    names = [entity_type] if entity_type is not None else sorted(entity_types)
    entities: list[EntityConfig] = []
    for name in names:
        config = entity_types.get(name)
        if not _is_database_ordinary_entity_type(name, config):
            continue
        table = await ensure_ordinary_entity_table(session, name, config)
        result = await session.exec(text(f"SELECT * FROM {table} ORDER BY id"))
        entities.extend(_ordinary_entity_from_row(name, config, row._mapping) for row in result.all())
    return entities


async def find_ordinary_entity(
    session: AsyncSession,
    ref: str,
    entity_types: dict[str, EntityTypeConfig],
) -> EntityConfig | None:
    for entity_type, config in entity_types.items():
        if not _is_database_ordinary_entity_type(entity_type, config):
            continue
        entity = await get_ordinary_entity(session, entity_type, ref, entity_types)
        if entity is not None:
            return entity
    return None


async def get_ordinary_entity(
    session: AsyncSession,
    entity_type: str,
    ref: str,
    entity_types: dict[str, EntityTypeConfig],
) -> EntityConfig | None:
    config = entity_types.get(entity_type)
    if config is None:
        return None
    table = await ensure_ordinary_entity_table(session, entity_type, config)
    business_ref = ref.removeprefix(f"{entity_type}:") if ref.startswith(f"{entity_type}:") else ref
    result = await session.exec(
        text(f"SELECT * FROM {table} WHERE id = :ref OR business_id = :ref OR business_id = :business_ref"),
        params={"ref": ref, "business_ref": business_ref},
    )
    row = result.first()
    return _ordinary_entity_from_row(entity_type, config, row._mapping) if row is not None else None


async def query_ordinary_entities(
    session: AsyncSession,
    entity_type: str,
    entity_types: dict[str, EntityTypeConfig],
    filters: dict[str, object] | None = None,
) -> list[EntityConfig]:
    config = entity_types[entity_type]
    table = await ensure_ordinary_entity_table(session, entity_type, config)
    filters = filters or {}
    materialized = {key: value for key, value in filters.items() if key in config.materialized_fields}
    clauses = [f"{_identifier(key)} = :{key}" for key in materialized]
    sql = f"SELECT * FROM {table}"
    if clauses:
        sql = f"{sql} WHERE {' AND '.join(clauses)}"
    result = await session.exec(text(sql), params={key: encode_value(value, config.materialized_fields[key].type) for key, value in materialized.items()})
    entities = [_ordinary_entity_from_row(entity_type, config, row._mapping) for row in result.all()]
    json_filters = {key: value for key, value in filters.items() if key not in materialized}
    for key, value in json_filters.items():
        entities = [entity for entity in entities if entity.attributes.get(key) == value]
    return entities


async def delete_ordinary_entity(
    session: AsyncSession,
    ref: str,
    entity_types: dict[str, EntityTypeConfig],
) -> DeleteEntityResult:
    current = await find_ordinary_entity(session, ref, entity_types)
    refs = _entity_refs(current, entity_types) if current is not None else {ref}
    from edera_core.storage.repository._relation import list_relations_for_entity_refs
    blocking_relations = await list_relations_for_entity_refs(session, refs)
    if blocking_relations:
        return DeleteEntityResult(False, blocking_relations)
    for entity_type, config in entity_types.items():
        if not _is_database_ordinary_entity_type(entity_type, config):
            continue
        table = await ensure_ordinary_entity_table(session, entity_type, config)
        result = await session.exec(text(f"SELECT id FROM {table} WHERE id = :ref OR business_id = :ref"), params={"ref": ref})
        row = result.first()
        if row is None:
            continue
        await session.exec(text(f"DELETE FROM {table} WHERE id = :id"), params={"id": row[0]})
        await session.flush()
        return DeleteEntityResult(True, [])
    return DeleteEntityResult(False, [])


def _identifier(name: str) -> str:
    return name
