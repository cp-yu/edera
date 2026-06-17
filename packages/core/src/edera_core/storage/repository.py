from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from edera_core.config.schema import DagConfig, EntityConfig, EntityTypeConfig, NodeConfig, entity_ref
from edera_core.config.schema import SkillConfig
from edera_core.storage.materialization import (
    decode_value,
    encode_value,
    ensure_ordinary_entity_table,
    entity_table_name,
    identifier,
)
from edera_core.storage.entities import EdgeInput, EntityRelation, InstalledExtension, NodeOutputEntity, NodeRun, DagRun, Skill, SourceRecovery, utc_now
from edera_core.storage.entities import (
    CoreEntityDag,
    CoreEntityInputMapping,
    CoreEntityNode,
    CoreEntityResource,
    CoreEntityTrigger,
    EntityTypeRecord,
    LogIndex,
)


CORE_ENTITY_TABLES = {
    "node": "entity_node",
    "dag": "entity_dag",
    "input_mapping": "entity_input_mapping",
    "trigger": "entity_trigger",
    "resource": "entity_resource",
}


@dataclass(frozen=True)
class DeleteEntityResult:
    deleted: bool
    relations: list[EntityRelation]

    def __bool__(self) -> bool:
        return self.deleted


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


async def save_core_entity(session: AsyncSession, entity: EntityConfig) -> EntityConfig:
    if entity.type == "node":
        return core_node_to_entity(await _save_core_node(session, entity))
    if entity.type == "dag":
        return core_dag_to_entity(await _save_core_dag(session, entity))
    if entity.type == "trigger":
        return core_trigger_to_entity(await _save_core_trigger(session, entity))
    if entity.type == "resource":
        return core_resource_to_entity(await _save_core_resource(session, entity))
    if entity.type == "input_mapping":
        return core_input_mapping_to_entity(await _save_core_input_mapping(session, entity))
    raise ValueError(f"unsupported core entity type: {entity.type}")


async def list_core_entities(session: AsyncSession, entity_type: str | None = None) -> list[EntityConfig]:
    if entity_type == "node":
        return [core_node_to_entity(item) for item in await _all(session, CoreEntityNode)]
    if entity_type == "dag":
        return [core_dag_to_entity(item) for item in await _all(session, CoreEntityDag)]
    if entity_type == "trigger":
        return [core_trigger_to_entity(item) for item in await _all(session, CoreEntityTrigger)]
    if entity_type == "resource":
        return [core_resource_to_entity(item) for item in await _all(session, CoreEntityResource)]
    if entity_type == "input_mapping":
        return [core_input_mapping_to_entity(item) for item in await _all(session, CoreEntityInputMapping)]
    if entity_type is not None:
        return []
    entities: list[EntityConfig] = []
    for core_type in CORE_ENTITY_TABLES:
        entities.extend(await list_core_entities(session, core_type))
    return entities


async def get_dag_config(session: AsyncSession, name: str) -> DagConfig | None:
    result = await session.exec(select(CoreEntityDag).where(CoreEntityDag.name == name))
    row = result.first()
    return _dag_config(row) if row is not None else None


async def get_dag_entity(session: AsyncSession, name: str) -> EntityConfig | None:
    result = await session.exec(select(CoreEntityDag).where(CoreEntityDag.name == name))
    row = result.first()
    return core_dag_to_entity(row) if row is not None else None


async def get_node_config(session: AsyncSession, name: str) -> NodeConfig | None:
    result = await session.exec(select(CoreEntityNode).where(CoreEntityNode.name == name))
    row = result.first()
    return _node_config(row) if row is not None else None


async def list_dag_names(session: AsyncSession) -> list[str]:
    result = await session.exec(select(CoreEntityDag.name).order_by(col(CoreEntityDag.name)))
    return list(result.all())


async def list_node_summaries(session: AsyncSession) -> list[dict[str, str]]:
    result = await session.exec(select(CoreEntityNode).order_by(col(CoreEntityNode.name)))
    return [{"name": row.name, "type": row.node_type} for row in result.all()]


async def list_dag_configs(session: AsyncSession) -> dict[str, DagConfig]:
    result = await session.exec(select(CoreEntityDag).order_by(col(CoreEntityDag.name)))
    return {row.name: _dag_config(row) for row in result.all()}


async def list_node_configs(session: AsyncSession) -> dict[str, NodeConfig]:
    result = await session.exec(select(CoreEntityNode).order_by(col(CoreEntityNode.name)))
    return {row.name: _node_config(row) for row in result.all()}


async def get_core_entity(
    session: AsyncSession,
    ref: str,
    entity_types: dict[str, EntityTypeConfig],
) -> EntityConfig | None:
    for entity in await list_core_entities(session):
        try:
            if ref in {entity.id, entity_ref(entity, entity_types)}:
                return entity
        except (KeyError, ValueError):
            if ref == entity.id:
                return entity
    return None


async def delete_core_entity(
    session: AsyncSession,
    ref: str,
    entity_types: dict[str, EntityTypeConfig],
) -> DeleteEntityResult:
    entity = await get_core_entity(session, ref, entity_types)
    if entity is None:
        return DeleteEntityResult(False, [])
    blocking_relations = await list_relations_for_entity_refs(session, _entity_refs(entity, entity_types))
    if blocking_relations:
        return DeleteEntityResult(False, blocking_relations)
    table = _core_model(entity.type)
    result = await session.exec(select(table).where(table.entity_id == entity.id))
    row = result.first()
    if row is None:
        return DeleteEntityResult(False, [])
    await session.delete(row)
    await session.flush()
    return DeleteEntityResult(True, [])


async def force_delete_entity_relations(session: AsyncSession, refs: set[str]) -> list[EntityRelation]:
    relations = await list_relations_for_entity_refs(session, refs)
    for relation in relations:
        await session.delete(relation)
    await session.flush()
    return relations


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
    assignments = [f"{identifier(column)} = :{column}" for column in columns if column != "id"]
    await session.exec(
        text(
            f"INSERT INTO {table} ({', '.join(identifier(column) for column in columns)}) "
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
    clauses = [f"{identifier(key)} = :{key}" for key in materialized]
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


async def create_relation(
    session: AsyncSession,
    from_entity_id: str,
    to_entity_id: str,
    relation_type: str,
    metadata: dict[str, Any] | None = None,
    entity_types: dict[str, EntityTypeConfig] | None = None,
) -> EntityRelation:
    if entity_types is not None:
        if not await _entity_exists(session, from_entity_id, entity_types):
            raise ValueError(f"from entity not found: {from_entity_id}")
        if not await _entity_exists(session, to_entity_id, entity_types):
            raise ValueError(f"to entity not found: {to_entity_id}")
    existing = await _relation_by_key(session, from_entity_id, to_entity_id, relation_type)
    if existing is not None:
        return existing
    relation = EntityRelation(
        id=uuid4().hex,
        from_entity_id=from_entity_id,
        to_entity_id=to_entity_id,
        relation_type=relation_type,
        metadata_=metadata or {},
    )
    session.add(relation)
    await session.flush()
    return relation


async def delete_relation(session: AsyncSession, relation_id: str) -> bool:
    result = await session.exec(select(EntityRelation).where(EntityRelation.id == relation_id))
    relation = result.first()
    if relation is None:
        return False
    await session.delete(relation)
    await session.flush()
    return True


async def list_relations(
    session: AsyncSession,
    from_entity_id: str | None = None,
    to_entity_id: str | None = None,
    relation_type: str | None = None,
) -> list[EntityRelation]:
    statement = select(EntityRelation).order_by(col(EntityRelation.created_at), col(EntityRelation.id))
    if from_entity_id is not None:
        statement = statement.where(EntityRelation.from_entity_id == from_entity_id)
    if to_entity_id is not None:
        statement = statement.where(EntityRelation.to_entity_id == to_entity_id)
    if relation_type is not None:
        statement = statement.where(EntityRelation.relation_type == relation_type)
    result = await session.exec(statement)
    return list(result.all())


async def list_relations_for_entity(session: AsyncSession, entity_id: str) -> list[EntityRelation]:
    statement = (
        select(EntityRelation)
        .where((EntityRelation.from_entity_id == entity_id) | (EntityRelation.to_entity_id == entity_id))
        .order_by(col(EntityRelation.created_at), col(EntityRelation.id))
    )
    result = await session.exec(statement)
    return list(result.all())


async def list_relations_for_entity_refs(session: AsyncSession, refs: set[str]) -> list[EntityRelation]:
    if not refs:
        return []
    statement = (
        select(EntityRelation)
        .where((col(EntityRelation.from_entity_id).in_(refs)) | (col(EntityRelation.to_entity_id).in_(refs)))
        .order_by(col(EntityRelation.created_at), col(EntityRelation.id))
    )
    result = await session.exec(statement)
    return list(result.all())


async def create_skill(
    session: AsyncSession,
    name: str,
    files: list[dict[str, str]],
    display_name: str | None = None,
    description: str | None = None,
    skills_dir: Path | None = None,
) -> Skill:
    body = _skill_body(files)
    skill = Skill(name=_skill_name(name), display_name=display_name, description=description, config_body=body)
    session.add(skill)
    await session.flush()
    if skills_dir is not None:
        from edera_core.skills.generator import refresh_skill_files

        refresh_skill_files(skills_dir, skill_to_config(skill))
    return skill


async def update_skill(
    session: AsyncSession,
    name: str,
    files: list[dict[str, str]],
    display_name: str | None = None,
    description: str | None = None,
    skills_dir: Path | None = None,
) -> Skill:
    skill = await get_skill(session, name)
    if skill is None:
        raise ValueError(f"skill not found: {name}")
    skill.config_body = _skill_body(files)
    skill.display_name = display_name
    skill.description = description
    skill.updated_at = utc_now()
    session.add(skill)
    await session.flush()
    if skills_dir is not None:
        from edera_core.skills.generator import refresh_skill_files

        refresh_skill_files(skills_dir, skill_to_config(skill))
    return skill


async def upsert_skill(
    session: AsyncSession,
    name: str,
    files: list[dict[str, str]],
    display_name: str | None = None,
    description: str | None = None,
    skills_dir: Path | None = None,
) -> Skill:
    current = await get_skill(session, name)
    if current is None:
        return await create_skill(session, name, files, display_name, description, skills_dir)
    return await update_skill(session, name, files, display_name, description, skills_dir)


async def get_skill(session: AsyncSession, name: str) -> Skill | None:
    result = await session.exec(select(Skill).where(Skill.name == name))
    return result.first()


async def delete_skill(session: AsyncSession, name: str, skills_dir: Path | None = None) -> bool:
    skill = await get_skill(session, name)
    if skill is None:
        return False
    await session.delete(skill)
    await session.flush()
    if skills_dir is not None:
        from edera_core.skills.generator import remove_skill_files

        remove_skill_files(skills_dir, name)
    return True


async def list_skills(session: AsyncSession) -> list[Skill]:
    result = await session.exec(select(Skill).order_by(col(Skill.name)))
    return list(result.all())


async def list_skill_configs(session: AsyncSession) -> dict[str, SkillConfig]:
    return {skill.name: skill_to_config(skill) for skill in await list_skills(session)}


def skill_to_config(skill: Skill) -> SkillConfig:
    body = skill.config_body if isinstance(skill.config_body, dict) else {}
    files = body.get("files") if isinstance(body.get("files"), list) else []
    return SkillConfig.model_validate(
        {
            "name": skill.name,
            "display_name": skill.display_name,
            "description": skill.description or "",
            "handler": skill.name,
            "parameters_schema": {},
            "files": files,
        }
    )


async def entity_exists(
    session: AsyncSession,
    ref: str,
    entity_types: dict[str, EntityTypeConfig],
) -> bool:
    return await _entity_exists(session, ref, entity_types)


async def save_installed_extension(
    session: AsyncSession,
    *,
    name: str,
    version: str,
    manifest_snapshot: dict[str, object],
    import_records: list[dict[str, object]] | None = None,
    enabled: bool = True,
    installed_by: str | None = None,
) -> InstalledExtension:
    record = await get_installed_extension(session, name)
    if record is None:
        record = InstalledExtension(name=name, version=version, manifest_snapshot="{}")
    record.version = version
    record.manifest_snapshot = json.dumps(manifest_snapshot, ensure_ascii=False, sort_keys=True)
    record.import_records = json.dumps(import_records or [], ensure_ascii=False, sort_keys=True)
    record.enabled = enabled
    record.installed_by = installed_by
    record.updated_at = utc_now().isoformat()
    session.add(record)
    await session.flush()
    return record


async def get_installed_extension(session: AsyncSession, name: str) -> InstalledExtension | None:
    result = await session.exec(select(InstalledExtension).where(InstalledExtension.name == name))
    return result.first()


async def list_installed_extensions(session: AsyncSession) -> list[InstalledExtension]:
    result = await session.exec(select(InstalledExtension).order_by(col(InstalledExtension.name)))
    return list(result.all())


async def list_enabled_extensions(session: AsyncSession) -> list[InstalledExtension]:
    result = await session.exec(
        select(InstalledExtension).where(InstalledExtension.enabled == True).order_by(col(InstalledExtension.name))
    )
    return list(result.all())


async def delete_installed_extension(session: AsyncSession, name: str) -> bool:
    record = await get_installed_extension(session, name)
    if record is None:
        return False
    await session.delete(record)
    await session.flush()
    return True


async def record_log_index(
    session: AsyncSession,
    run_id: str,
    node_id: str,
    path: str,
    digest: str,
    size: int,
    kind: str = "raw",
) -> LogIndex:
    row = LogIndex(run_id=run_id, node_id=node_id, kind=kind, path=path, digest=digest, size=size, updated_at=utc_now())
    session.add(row)
    await session.flush()
    return row


async def query_log_index(
    session: AsyncSession,
    run_id: str | None = None,
    node_id: str | None = None,
    limit: int = 100,
) -> list[LogIndex]:
    statement = select(LogIndex).order_by(col(LogIndex.created_at).desc()).limit(limit)
    if run_id is not None:
        statement = statement.where(LogIndex.run_id == run_id)
    if node_id is not None:
        statement = statement.where(LogIndex.node_id == node_id)
    result = await session.exec(statement)
    return list(result.all())


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


def _core_model(entity_type: str):
    if entity_type == "node":
        return CoreEntityNode
    if entity_type == "dag":
        return CoreEntityDag
    if entity_type == "trigger":
        return CoreEntityTrigger
    if entity_type == "resource":
        return CoreEntityResource
    if entity_type == "input_mapping":
        return CoreEntityInputMapping
    raise ValueError(f"unsupported core entity type: {entity_type}")


async def _save_core_node(session: AsyncSession, entity: EntityConfig) -> CoreEntityNode:
    attrs = dict(entity.attributes)
    attrs.pop("input_binding", None)
    row = await _one_by_entity_id(session, CoreEntityNode, entity.id)
    if row is None:
        row = CoreEntityNode(entity_id=entity.id, name=str(attrs.get("name") or entity.id), node_type=str(attrs.get("type") or "function"), input_type=str(attrs.get("input_type") or "Any"), output_type=str(attrs.get("output_type") or "Any"))
    row.name = str(attrs["name"])
    row.node_type = str(attrs.get("type") or "function")
    row.role = str(attrs.get("role") or "processor")
    row.input_type = str(attrs["input_type"])
    row.output_type = str(attrs["output_type"])
    row.optional = bool(attrs.get("optional", False))
    row.timeout_seconds = _float_or_none(attrs.get("timeout_seconds"))
    row.handler = _str_or_none(attrs.get("handler"))
    row.skills = _str_list(attrs.get("skills"))
    row.system_prompt_file = _str_or_none(attrs.get("system_prompt_file"))
    row.system_prompt = _str_or_none(attrs.get("system_prompt"))
    row.tools = _str_list(attrs.get("tools"))
    row.source_names = _str_list(attrs.get("source_names"))
    row.parameters = _dict(attrs.get("parameters"))
    row.parameters_schema = _dict(attrs.get("parameters_schema"))
    row.model = _str_or_none(attrs.get("model"))
    row.workdir = _str_or_none(attrs.get("workdir"))
    row.dag_ref = _str_or_none(attrs.get("dag_ref"))
    row.input_mapping = {str(key): str(value) for key, value in _dict(attrs.get("input_mapping")).items()}
    row.attributes_json = _extra_attrs(attrs, _NODE_COLUMNS)
    row.updated_at = utc_now()
    session.add(row)
    await session.flush()
    return row


async def _save_core_dag(session: AsyncSession, entity: EntityConfig) -> CoreEntityDag:
    attrs = dict(entity.attributes)
    row = await _one_by_entity_id(session, CoreEntityDag, entity.id)
    if row is None:
        row = CoreEntityDag(entity_id=entity.id, name=str(attrs.get("name") or entity.id))
    row.name = str(attrs["name"])
    row.nodes = _dict_list(attrs["nodes"])
    row.edges = _dict_list(attrs["edges"])
    row.ui = _dict(attrs.get("ui"))
    row.attributes_json = _extra_attrs(attrs, {"name", "inputs", "nodes", "edges", "ui"})
    row.updated_at = utc_now()
    session.add(row)
    await session.flush()
    return row


async def _save_core_trigger(session: AsyncSession, entity: EntityConfig) -> CoreEntityTrigger:
    attrs = dict(entity.attributes)
    row = await _one_by_entity_id(session, CoreEntityTrigger, entity.id)
    if row is None:
        row = CoreEntityTrigger(entity_id=entity.id, name=str(attrs.get("name") or entity.id), wait_for=str(attrs.get("wait_for") or ""), target=str(attrs.get("target") or ""))
    row.name = str(attrs["name"])
    row.wait_for = str(attrs["wait_for"])
    row.target = str(attrs["target"])
    row.enabled = bool(attrs.get("enabled", True))
    row.attributes_json = _extra_attrs(attrs, {"name", "wait_for", "target", "enabled"})
    row.updated_at = utc_now()
    session.add(row)
    await session.flush()
    return row


async def _save_core_resource(session: AsyncSession, entity: EntityConfig) -> CoreEntityResource:
    attrs = dict(entity.attributes)
    row = await _one_by_entity_id(session, CoreEntityResource, entity.id)
    if row is None:
        row = CoreEntityResource(entity_id=entity.id, resource_id=str(attrs.get("id") or entity.id), permits=int(attrs.get("permits") or 1))
    row.resource_id = str(attrs.get("id") or entity.id)
    row.permits = int(attrs["permits"])
    row.attributes_json = _extra_attrs(attrs, {"id", "permits"})
    row.updated_at = utc_now()
    session.add(row)
    await session.flush()
    return row


async def _save_core_input_mapping(session: AsyncSession, entity: EntityConfig) -> CoreEntityInputMapping:
    attrs = dict(entity.attributes)
    row = await _one_by_entity_id(session, CoreEntityInputMapping, entity.id)
    if row is None:
        row = CoreEntityInputMapping(entity_id=entity.id, name=str(attrs.get("name") or entity.id))
    row.name = str(attrs["name"])
    row.shared = _dict(attrs.get("shared"))
    row.nodes = _dict(attrs.get("nodes"))
    row.append_nodes = _str_list(attrs.get("append_nodes"))
    row.attributes_json = _extra_attrs(attrs, {"name", "shared", "nodes", "append_nodes"})
    row.updated_at = utc_now()
    session.add(row)
    await session.flush()
    return row


async def _one_by_entity_id(session: AsyncSession, model, entity_id: str):
    result = await session.exec(select(model).where(model.entity_id == entity_id))
    return result.first()


_NODE_COLUMNS = {
    "name",
    "type",
    "role",
    "input_type",
    "output_type",
    "optional",
    "timeout_seconds",
    "handler",
    "skills",
    "system_prompt_file",
    "system_prompt",
    "tools",
    "source_names",
    "parameters",
    "parameters_schema",
    "model",
    "workdir",
    "dag_ref",
    "input_mapping",
}


def core_node_to_entity(row: CoreEntityNode) -> EntityConfig:
    attrs = dict(row.attributes_json)
    attrs.update(
        {
            "name": row.name,
            "type": row.node_type,
            "role": row.role,
            "input_type": row.input_type,
            "output_type": row.output_type,
            "optional": row.optional,
        }
    )
    if row.node_type in {"function", "agent"}:
        attrs.update(
            {
                "skills": row.skills,
                "parameters_schema": row.parameters_schema,
            }
        )
    if row.node_type == "agent":
        attrs["tools"] = row.tools
    if row.node_type == "function":
        attrs.update({"source_names": row.source_names, "parameters": row.parameters})
    _set_if_not_none(attrs, "timeout_seconds", row.timeout_seconds)
    _set_if_not_none(attrs, "handler", row.handler)
    _set_if_not_none(attrs, "system_prompt_file", row.system_prompt_file)
    _set_if_not_none(attrs, "system_prompt", row.system_prompt)
    _set_if_not_none(attrs, "model", row.model)
    _set_if_not_none(attrs, "workdir", row.workdir)
    _set_if_not_none(attrs, "dag_ref", row.dag_ref)
    if row.input_mapping:
        attrs["input_mapping"] = row.input_mapping
    return EntityConfig(id=row.entity_id, type="node", attributes=attrs)


def _node_config(row: CoreEntityNode) -> NodeConfig:
    attrs = core_node_to_entity(row).attributes
    return NodeConfig.model_validate(attrs)


def core_dag_to_entity(row: CoreEntityDag) -> EntityConfig:
    attrs = dict(row.attributes_json)
    attrs.update({"name": row.name, "nodes": row.nodes, "edges": row.edges, "ui": row.ui})
    return EntityConfig(id=row.entity_id, type="dag", attributes=attrs)


def _dag_config(row: CoreEntityDag) -> DagConfig:
    attrs = core_dag_to_entity(row).attributes
    return DagConfig.model_validate(attrs)


def core_trigger_to_entity(row: CoreEntityTrigger) -> EntityConfig:
    attrs = dict(row.attributes_json)
    attrs.update({"name": row.name, "wait_for": row.wait_for, "target": row.target, "enabled": row.enabled})
    return EntityConfig(id=row.entity_id, type="trigger", attributes=attrs)


def core_resource_to_entity(row: CoreEntityResource) -> EntityConfig:
    attrs = dict(row.attributes_json)
    attrs.update({"id": row.resource_id, "permits": row.permits})
    return EntityConfig(id=row.entity_id, type="resource", attributes=attrs)


def core_input_mapping_to_entity(row: CoreEntityInputMapping) -> EntityConfig:
    attrs = dict(row.attributes_json)
    attrs.update(
        {
            "name": row.name,
            "shared": row.shared,
            "nodes": row.nodes,
            "append_nodes": row.append_nodes,
        }
    )
    return EntityConfig(id=row.entity_id, type="input_mapping", attributes=attrs)


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


async def _ordinary_row(session: AsyncSession, table: str, entity_id: str):
    result = await session.exec(text(f"SELECT * FROM {table} WHERE id = :id"), params={"id": entity_id})
    row = result.first()
    return row._mapping if row is not None else None


async def _entity_exists(
    session: AsyncSession,
    ref: str,
    entity_types: dict[str, EntityTypeConfig],
) -> bool:
    if await get_core_entity(session, ref, entity_types) is not None:
        return True
    return await find_ordinary_entity(session, ref, entity_types) is not None


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


def _entity_refs(entity: EntityConfig, entity_types: dict[str, EntityTypeConfig]) -> set[str]:
    refs = {entity.id}
    try:
        refs.add(entity_ref(entity, entity_types))
    except (KeyError, ValueError):
        pass
    return refs


def _json_dict(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value:
        data = json.loads(value)
        return dict(data) if isinstance(data, dict) else {}
    return {}


async def store_node_output_entities(
    session: AsyncSession,
    run_id: str,
    node_id: str,
    entity_type: str,
    payload: object,
    session_id: str | None = None,
) -> list[NodeOutputEntity]:
    values = payload if isinstance(payload, list) else [payload]
    stored: list[NodeOutputEntity] = []
    for value in values:
        if not isinstance(value, dict):
            value = {"value": value}
        url = value.get("url") if isinstance(value.get("url"), str) else None
        if entity_type == "raw-item" and url is not None:
            existing = await session.exec(
                select(NodeOutputEntity).where(
                    NodeOutputEntity.type == "raw-item",
                    NodeOutputEntity.url == url,
                )
            )
            if existing.first() is not None:
                continue
        entity = NodeOutputEntity(
            entity_id=uuid4().hex,
            type=entity_type,
            run_id=str(value.get("run_id") or run_id or ""),
            node_id=node_id,
            payload=dict(value),
            tags=[str(tag) for tag in value.get("tags", [])] if isinstance(value.get("tags"), list) else [],
            session_id=session_id,
            url=url,
        )
        session.add(entity)
        stored.append(entity)
    await session.flush()
    return stored


async def query_node_output_entities(
    session: AsyncSession,
    entity_type: str | None = None,
    run_id: str | None = None,
    node_id: str | None = None,
    tags: list[str] | None = None,
    limit: int = 100,
) -> list[EntityConfig]:
    statement = select(NodeOutputEntity).order_by(col(NodeOutputEntity.created_at).desc()).limit(limit)
    if entity_type is not None:
        statement = statement.where(NodeOutputEntity.type == entity_type)
    if run_id is not None:
        statement = statement.where(NodeOutputEntity.run_id == run_id)
    if node_id is not None:
        statement = statement.where(NodeOutputEntity.node_id == node_id)
    result = await session.exec(statement)
    entities = [node_output_to_entity(item) for item in result.all()]
    if tags is None:
        return entities
    wanted = set(tags)
    return [entity for entity in entities if wanted.issubset(set(_entity_tags(entity)))]


async def save_node_output_entity(session: AsyncSession, entity: EntityConfig) -> EntityConfig:
    result = await session.exec(select(NodeOutputEntity).where(NodeOutputEntity.entity_id == entity.id))
    current = result.first()
    if current is None:
        raise ValueError(f"node output entity not found: {entity.id}")
    if current.type != entity.type:
        raise ValueError(f"node output entity type cannot change: {entity.id}")
    current.run_id = str(entity.attributes.get("run_id") or current.run_id)
    current.node_id = str(entity.attributes.get("node_id") or current.node_id)
    current.session_id = str(entity.attributes["session_id"]) if entity.attributes.get("session_id") is not None else None
    current.url = str(entity.attributes["url"]) if entity.attributes.get("url") is not None else None
    payload = entity.attributes.get("payload")
    current.payload = dict(payload) if isinstance(payload, dict) else dict(entity.attributes)
    tags = entity.attributes.get("tags")
    current.tags = [str(tag) for tag in tags] if isinstance(tags, list) else []
    session.add(current)
    await session.flush()
    return node_output_to_entity(current)


async def delete_node_output_entity(session: AsyncSession, entity_id: str) -> bool:
    result = await session.exec(select(NodeOutputEntity).where(NodeOutputEntity.entity_id == entity_id))
    current = result.first()
    if current is None:
        return False
    await session.delete(current)
    await session.flush()
    return True


async def delete_node_outputs_for_nodes(session: AsyncSession, run_id: str, node_ids: set[str]) -> None:
    if not node_ids:
        return
    result = await session.exec(
        select(NodeOutputEntity).where(
            NodeOutputEntity.run_id == run_id,
            col(NodeOutputEntity.node_id).in_(node_ids),
        )
    )
    for output in result.all():
        await session.delete(output)
    await session.flush()


def node_output_to_entity(output: NodeOutputEntity) -> EntityConfig:
    attributes = dict(output.payload)
    attributes.setdefault("id", output.entity_id)
    attributes.update(
        {
            "run_id": output.run_id,
            "node_id": output.node_id,
            "payload": output.payload,
        }
    )
    if output.session_id:
        attributes["session_id"] = output.session_id
    return EntityConfig(id=output.entity_id, type=output.type, attributes=attributes)


async def cleanup_node_output_entities(
    session: AsyncSession,
    retention_count: int,
    retention_hours: int,
    now: datetime | None = None,
) -> None:
    current = now or utc_now()
    if retention_hours > 0:
        cutoff = current.timestamp() - retention_hours * 3600
        result = await session.exec(select(NodeOutputEntity))
        for output in result.all():
            if output.created_at.timestamp() < cutoff:
                await session.delete(output)
    if retention_count > 0:
        result = await session.exec(select(NodeOutputEntity.run_id).order_by(col(NodeOutputEntity.created_at).desc()))
        run_ids: list[str] = []
        for run_id in result.all():
            if run_id not in run_ids:
                run_ids.append(run_id)
        expired = run_ids[retention_count:]
        if expired:
            result = await session.exec(select(NodeOutputEntity).where(col(NodeOutputEntity.run_id).in_(expired)))
            for output in result.all():
                await session.delete(output)
    await session.flush()


async def create_dag_run(
    session: AsyncSession,
    run_id: str,
    source: str,
    node_names: list[str] | None = None,
    dag_name: str = "default",
    retry_of: str | None = None,
) -> DagRun:
    run = DagRun(run_id=run_id, source=source, status="running", dag_name=dag_name, retry_of=retry_of)
    session.add(run)
    for node_name in node_names or []:
        session.add(NodeRun(run_id=run_id, node_name=node_name, status="pending"))
    await session.flush()
    return run


async def finish_dag_run(
    session: AsyncSession,
    run_id: str,
    status: str,
    error: str | None = None,
    ended_at: datetime | None = None,
) -> DagRun | None:
    run = await get_dag_run(session, run_id)
    if run is None:
        return None
    run.status = status
    run.error = error
    run.ended_at = ended_at or utc_now()
    session.add(run)
    await session.flush()
    return run


async def restart_dag_run(session: AsyncSession, run_id: str) -> DagRun | None:
    run = await get_dag_run(session, run_id)
    if run is None:
        return None
    run.status = "running"
    run.error = None
    run.ended_at = None
    session.add(run)
    await session.flush()
    return run


async def mark_node_run(
    session: AsyncSession,
    run_id: str,
    node_name: str,
    status: str,
    error: str | None = None,
    failure_kind: str | None = None,
    metadata: dict[str, object] | None = None,
) -> NodeRun:
    result = await session.exec(select(NodeRun).where(NodeRun.run_id == run_id, NodeRun.node_name == node_name))
    node_run = result.first()
    now = utc_now()
    if node_run is None:
        node_run = NodeRun(run_id=run_id, node_name=node_name, status=status)
    node_run.status = status
    node_run.error = error
    node_run.failure_kind = failure_kind if status == "failed" else None
    if metadata:
        node_run.metadata_ = {**node_run.metadata_, **metadata}
    if status == "running" and node_run.started_at is None:
        node_run.started_at = now
    if status in {"succeeded", "failed", "skipped", "cancelled"}:
        node_run.ended_at = now
    session.add(node_run)
    await session.flush()
    return node_run


async def upsert_edge_input(
    session: AsyncSession,
    run_id: str,
    from_node_id: str,
    to_node_id: str,
    edge_optional: bool,
    status: str,
    has_payload: bool,
    error_summary: str | None = None,
) -> EdgeInput:
    result = await session.exec(
        select(EdgeInput).where(
            EdgeInput.run_id == run_id,
            EdgeInput.from_node_id == from_node_id,
            EdgeInput.to_node_id == to_node_id,
        )
    )
    edge_input = result.first()
    if edge_input is None:
        edge_input = EdgeInput(
            run_id=run_id,
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            edge_optional=edge_optional,
            status=status,
            has_payload=has_payload,
            error_summary=error_summary,
        )
    else:
        edge_input.edge_optional = edge_optional
        edge_input.status = status
        edge_input.has_payload = has_payload
        edge_input.error_summary = error_summary
    session.add(edge_input)
    await session.flush()
    return edge_input


async def edge_inputs_for_run(session: AsyncSession, run_id: str) -> list[EdgeInput]:
    result = await session.exec(
        select(EdgeInput).where(EdgeInput.run_id == run_id).order_by(col(EdgeInput.id))
    )
    return list(result.all())


async def upsert_source_recovery(
    session: AsyncSession,
    run_id: str,
    node_id: str,
    source_name: str,
    summary: dict[str, object],
) -> SourceRecovery:
    result = await session.exec(
        select(SourceRecovery).where(
            SourceRecovery.run_id == run_id,
            SourceRecovery.node_id == node_id,
            SourceRecovery.source_name == source_name,
        )
    )
    recovery = result.first()
    if recovery is None:
        recovery = SourceRecovery(
            run_id=run_id,
            node_id=node_id,
            source_name=source_name,
            recovery_status=str(summary.get("recovery_status") or "none"),
        )
    recovery.recovery_status = str(summary.get("recovery_status") or recovery.recovery_status)
    recovery.attempt_count = _int_value(summary.get("attempt_count"))
    recovery.recoverable_reason = _optional_str(summary.get("recoverable_reason"))
    recovery.latest_failure_reason = _optional_str(summary.get("latest_failure_reason"))
    recovery.escalated = bool(summary.get("escalated") or recovery.recovery_status == "escalated")
    recovery.escalation_reason = _optional_str(summary.get("escalation_reason"))
    session.add(recovery)
    await session.flush()
    return recovery


async def source_recoveries(
    session: AsyncSession,
    source_name: str | None = None,
    limit: int = 100,
    source_names: list[str] | None = None,
) -> list[SourceRecovery]:
    statement = select(SourceRecovery).order_by(col(SourceRecovery.created_at).desc(), col(SourceRecovery.id).desc()).limit(limit)
    if source_name is not None:
        statement = statement.where(SourceRecovery.source_name == source_name)
    elif source_names is not None:
        statement = statement.where(col(SourceRecovery.source_name).in_(source_names))
    result = await session.exec(statement)
    return list(result.all())


async def get_dag_run(session: AsyncSession, run_id: str) -> DagRun | None:
    result = await session.exec(select(DagRun).where(DagRun.run_id == run_id))
    return result.first()


async def current_dag_run(session: AsyncSession, dag_name: str | None = None) -> DagRun | None:
    statement = (
        select(DagRun)
        .where(DagRun.status == "running")
        .order_by(col(DagRun.started_at).desc())
        .limit(1)
    )
    if dag_name is not None:
        statement = statement.where(DagRun.dag_name == dag_name)
    result = await session.exec(statement)
    return result.first()


async def recent_dag_runs(
    session: AsyncSession,
    limit: int = 20,
    dag_name: str | None = None,
) -> list[DagRun]:
    statement = select(DagRun).order_by(col(DagRun.started_at).desc()).limit(limit)
    if dag_name is not None:
        statement = statement.where(DagRun.dag_name == dag_name)
    result = await session.exec(statement)
    return list(result.all())


async def latest_finished_dag_run(session: AsyncSession, dag_name: str) -> DagRun | None:
    result = await session.exec(
        select(DagRun)
        .where(DagRun.dag_name == dag_name, DagRun.status != "running")
        .order_by(col(DagRun.started_at).desc())
        .limit(1)
    )
    return result.first()


async def node_runs_for_run(session: AsyncSession, run_id: str) -> list[NodeRun]:
    result = await session.exec(select(NodeRun).where(NodeRun.run_id == run_id).order_by(col(NodeRun.id)))
    return list(result.all())


async def node_run_for_run_node(session: AsyncSession, run_id: str, node_name: str) -> NodeRun | None:
    result = await session.exec(select(NodeRun).where(NodeRun.run_id == run_id, NodeRun.node_name == node_name))
    return result.first()


async def source_execution_logs(
    session: AsyncSession,
    source_name: str | None = None,
    limit: int = 50,
    source_names: list[str] | None = None,
) -> list[dict[str, object]]:
    allowed_sources = set(source_names or [])
    if source_name is not None and source_names is not None and source_name not in allowed_sources:
        return []
    recovery_rows = await source_recoveries(session, source_name, limit, source_names)
    logs = [_source_recovery_log_dict(item) for item in recovery_rows]
    if source_name is None and not allowed_sources:
        return logs[:limit]
    statement = (
        select(NodeRun, DagRun)
        .join(DagRun, col(NodeRun.run_id) == col(DagRun.run_id))
        .order_by(col(NodeRun.started_at).desc(), col(NodeRun.id).desc())
        .limit(limit)
    )
    if source_name:
        statement = statement.where(NodeRun.node_name == source_name)
    else:
        statement = statement.where(col(NodeRun.node_name).in_(allowed_sources))
    result = await session.exec(statement)
    logs.extend(_source_log_dict(node, run) for node, run in result.all())
    logs.sort(key=_source_log_time, reverse=True)
    return logs[:limit]


async def source_health_summary(
    session: AsyncSession,
    source_names: list[str],
    window: int = 20,
) -> list[dict[str, object]]:
    summaries = []
    for source_name in source_names:
        recoveries = await source_recoveries(session, source_name, 1)
        latest_recovery = recoveries[0] if recoveries else None
        result = await session.exec(
            select(NodeRun)
            .where(NodeRun.node_name == source_name)
            .order_by(col(NodeRun.started_at).desc(), col(NodeRun.id).desc())
            .limit(window)
        )
        runs = list(result.all())
        finished = [run for run in runs if run.status in {"succeeded", "failed"}]
        success_count = sum(1 for run in finished if run.status == "succeeded")
        latest = runs[0] if runs else None
        failed = next((run for run in runs if run.status == "failed" and run.error), None)
        latest_failure_reason = latest_recovery.latest_failure_reason if latest_recovery else None
        if not latest_failure_reason and failed:
            latest_failure_reason = failed.error
        summaries.append(
            {
                "source_name": source_name,
                "latest_status": latest.status if latest else "unknown",
                "run_id": latest.run_id if latest else None,
                "latest_run_at": latest.started_at.isoformat() if latest and latest.started_at else None,
                "success_rate": success_count / len(finished) if finished else None,
                "window_size": len(finished),
                "latest_failure_reason": latest_failure_reason,
                "recovery_status": latest_recovery.recovery_status if latest_recovery else "none",
                "recovery": _source_recovery_dict(latest_recovery) if latest_recovery else None,
            }
        )
    return summaries


async def latest_briefing(session: AsyncSession) -> EntityConfig | None:
    items = await _node_outputs(session, "briefing", 1)
    return items[0] if items else None


async def list_briefings(
    session: AsyncSession,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: int = 50,
) -> list[EntityConfig]:
    return [item for item in await _node_outputs(session, "briefing", limit) if _within_window(_created_at(item), created_from, created_to)]


async def get_briefing(session: AsyncSession, entity_id: str) -> EntityConfig | None:
    return await _node_output_by_entity_id(session, "briefing", entity_id)


async def list_advices(
    session: AsyncSession,
    limit: int = 50,
    stock_code: str | None = None,
    direction: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> list[EntityConfig]:
    items = await _node_outputs(session, "advice", limit)
    return [
        item
        for item in items
        if (stock_code is None or item.attributes.get("stock_code") == stock_code)
        and (direction is None or item.attributes.get("direction") == direction)
        and _within_window(_created_at(item), created_from, created_to)
    ]


async def get_advice(session: AsyncSession, entity_id: str) -> EntityConfig | None:
    return await _node_output_by_entity_id(session, "advice", entity_id)


async def analyses_for_advice(session: AsyncSession, advice: EntityConfig) -> list[EntityConfig]:
    urls = advice.attributes.get("source_urls")
    if not isinstance(urls, list):
        return []
    analyses = await _node_outputs(session, "analysis")
    wanted = {str(url) for url in urls}
    return [item for item in analyses if str(item.attributes.get("source_url") or "") in wanted]


async def raw_items_for_analyses(session: AsyncSession, analyses: list[EntityConfig]) -> list[EntityConfig]:
    urls = {str(item.attributes.get("source_url") or "") for item in analyses}
    raw_items = await _node_outputs(session, "raw-item")
    return [item for item in raw_items if str(item.attributes.get("url") or "") in urls]


async def list_event_records(session: AsyncSession, limit: int = 50, stock_code: str | None = None) -> list[EntityConfig]:
    return []


async def event_records_for_advices(session: AsyncSession, advices: list[EntityConfig]) -> dict[str, list[EntityConfig]]:
    return {}


async def event_evidence_details(session: AsyncSession, events: list[EntityConfig]) -> dict[str, object]:
    return {}


def _entity_tags(entity: EntityConfig) -> list[str]:
    tags = entity.attributes.get("tags")
    return [str(tag) for tag in tags] if isinstance(tags, list) else []


def _source_log_dict(node: NodeRun, run: DagRun) -> dict[str, object]:
    return {
        "source_name": node.node_name,
        "run_id": node.run_id,
        "dag_name": run.dag_name,
        "node_id": node.node_name,
        "status": node.status,
        "dag_status": run.status,
        "started_at": node.started_at.isoformat() if node.started_at else None,
        "ended_at": node.ended_at.isoformat() if node.ended_at else None,
        "error": node.error,
    }


def _source_recovery_log_dict(recovery: SourceRecovery) -> dict[str, object]:
    return {
        "source_name": recovery.source_name,
        "run_id": recovery.run_id,
        "dag_name": None,
        "node_id": recovery.node_id,
        "status": "failed" if recovery.escalated else "succeeded",
        "dag_status": None,
        "started_at": recovery.created_at.isoformat(),
        "ended_at": recovery.created_at.isoformat(),
        "error": recovery.latest_failure_reason,
        "recovery": _source_recovery_dict(recovery),
    }


def _source_log_time(log: dict[str, object]) -> str:
    return str(log.get("started_at") or log.get("ended_at") or "")


def _source_recovery_dict(recovery: SourceRecovery | None) -> dict[str, object] | None:
    if recovery is None:
        return None
    return {
        "run_id": recovery.run_id,
        "node_id": recovery.node_id,
        "source_name": recovery.source_name,
        "recovery_status": recovery.recovery_status,
        "attempt_count": recovery.attempt_count,
        "recoverable_reason": recovery.recoverable_reason,
        "latest_failure_reason": recovery.latest_failure_reason,
        "escalated": recovery.escalated,
        "escalation_reason": recovery.escalation_reason,
        "created_at": recovery.created_at.isoformat(),
    }


def _optional_str(value: object) -> str | None:
    return str(value) if value is not None and str(value) else None


def _int_value(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    return 0


async def _node_outputs(session: AsyncSession, entity_type: str, limit: int = 100) -> list[EntityConfig]:
    statement = (
        select(NodeOutputEntity)
        .where(NodeOutputEntity.type == entity_type)
        .order_by(col(NodeOutputEntity.created_at).desc())
        .limit(limit)
    )
    result = await session.exec(statement)
    return [node_output_to_entity(item) for item in result.all()]


async def _node_output_by_entity_id(session: AsyncSession, entity_type: str, entity_id: str) -> EntityConfig | None:
    result = await session.exec(
        select(NodeOutputEntity).where(NodeOutputEntity.type == entity_type, NodeOutputEntity.entity_id == entity_id)
    )
    output = result.first()
    return node_output_to_entity(output) if output is not None else None


def _created_at(entity: EntityConfig) -> datetime | None:
    value = entity.attributes.get("created_at")
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _within_window(value: datetime | None, created_from: datetime | None, created_to: datetime | None) -> bool:
    if value is None:
        return True
    if created_from is not None and value < created_from:
        return False
    if created_to is not None and value > created_to:
        return False
    return True
