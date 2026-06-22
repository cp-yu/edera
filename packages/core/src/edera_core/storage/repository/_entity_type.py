from __future__ import annotations

from sqlalchemy import text
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from edera_core.config.schema import EntityTypeConfig
from edera_core.storage.entities import EntityTypeRecord, utc_now
from edera_core.storage.materialization import entity_table_name, identifier
from edera_core.storage.repository._helpers import CORE_ENTITY_TABLES, entity_type_record_to_config


async def upsert_entity_type_record(
    session: AsyncSession,
    name: str,
    entity_type: EntityTypeConfig,
    schema_version: int = 1,
) -> EntityTypeRecord:
    result = await session.exec(select(EntityTypeRecord).where(EntityTypeRecord.name == name))
    record = result.first()
    if record is None:
        record = EntityTypeRecord(
            name=name,
            display_name=entity_type.display_name,
            business_id_field=entity_type.business_id_field,
            display_template=entity_type.display_template,
            storage_tier=entity_type.storage_tier,
        )
    record.display_name = entity_type.display_name
    record.business_id_field = entity_type.business_id_field
    record.display_template = entity_type.display_template
    record.storage_tier = entity_type.storage_tier
    record.table_name = CORE_ENTITY_TABLES.get(name) or entity_type.table_name or entity_table_name(name)
    record.schema_version = entity_type.schema_version or schema_version
    record.system_protected = entity_type.system_protected
    if entity_type.materialized_fields or record.materialized_fields is None:
        record.materialized_fields = {
            field: config.model_dump(mode="json") for field, config in entity_type.materialized_fields.items()
        }
    if entity_type.deprecated_fields or record.deprecated_fields is None:
        record.deprecated_fields = list(entity_type.deprecated_fields)
    record.schema_body = dict(entity_type.schema_)
    record.field_permissions = dict(entity_type.field_permissions)
    record.validate_ = entity_type.validate_
    record.updated_at = utc_now()
    session.add(record)
    await session.flush()
    return record


async def seed_entity_type_records(
    session: AsyncSession,
    entity_types: dict[str, EntityTypeConfig],
) -> dict[str, EntityTypeConfig]:
    for name, entity_type in entity_types.items():
        await upsert_entity_type_record(session, name, entity_type)
    return await list_entity_type_configs(session)


async def list_entity_type_configs(session: AsyncSession) -> dict[str, EntityTypeConfig]:
    result = await session.exec(select(EntityTypeRecord).order_by(col(EntityTypeRecord.name)))
    return {record.name: entity_type_record_to_config(record) for record in result.all()}


async def get_entity_type_config(session: AsyncSession, name: str) -> EntityTypeConfig | None:
    result = await session.exec(select(EntityTypeRecord).where(EntityTypeRecord.name == name))
    record = result.first()
    return entity_type_record_to_config(record) if record is not None else None


async def delete_entity_type_record(session: AsyncSession, name: str) -> bool:
    result = await session.exec(select(EntityTypeRecord).where(EntityTypeRecord.name == name))
    record = result.first()
    if record is None:
        return False
    await session.delete(record)
    await session.flush()
    return True


async def count_entities_for_type(session: AsyncSession, name: str, entity_type: EntityTypeConfig) -> int:
    if name in CORE_ENTITY_TABLES:
        result = await session.exec(text(f"SELECT COUNT(*) FROM {CORE_ENTITY_TABLES[name]}"))
        return int(result.one()[0])
    if entity_type.storage_tier != "database":
        return 0
    table = identifier(entity_type.table_name or entity_table_name(name))
    exists = await session.exec(text("SELECT name FROM sqlite_master WHERE type = 'table' AND name = :name"), params={"name": table})
    if exists.first() is None:
        return 0
    result = await session.exec(text(f"SELECT COUNT(*) FROM {table}"))
    return int(result.one()[0])
