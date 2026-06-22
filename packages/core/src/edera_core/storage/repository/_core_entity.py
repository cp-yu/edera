from __future__ import annotations

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from edera_core.config.schema import DagConfig, EntityConfig, EntityTypeConfig, NodeConfig, entity_ref
from edera_core.storage.entities import (
    CoreEntityDag,
    CoreEntityInputMapping,
    CoreEntityNode,
    CoreEntityResource,
    CoreEntityTrigger,
    utc_now,
)
from edera_core.storage.repository._helpers import (
    CORE_ENTITY_TABLES,
    DeleteEntityResult,
    _all,
    _dict,
    _dict_list,
    _extra_attrs,
    _float_or_none,
    _set_if_not_none,
    _str_list,
    _str_or_none,
    _entity_refs,
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
    from edera_core.storage.repository._relation import list_relations_for_entity_refs
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


def core_node_to_entity(row: CoreEntityNode) -> EntityConfig:
    attrs = dict(row.attributes_json)
    attrs.update({"name": row.name, "type": row.node_type, "role": row.role, "input_type": row.input_type, "output_type": row.output_type, "optional": row.optional})
    if row.node_type in {"function", "agent"}:
        attrs.update({"skills": row.skills, "parameters_schema": row.parameters_schema})
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
    attrs.update({"name": row.name, "shared": row.shared, "nodes": row.nodes, "append_nodes": row.append_nodes})
    return EntityConfig(id=row.entity_id, type="input_mapping", attributes=attrs)


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


_NODE_COLUMNS = {"name", "type", "role", "input_type", "output_type", "optional", "timeout_seconds", "handler", "skills", "system_prompt_file", "system_prompt", "tools", "source_names", "parameters", "parameters_schema", "model", "workdir", "dag_ref", "input_mapping"}


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



