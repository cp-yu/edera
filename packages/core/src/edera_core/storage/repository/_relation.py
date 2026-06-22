from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from edera_core.config.schema import EntityTypeConfig
from edera_core.storage.entities import EntityRelation
from edera_core.storage.repository._helpers import DeleteEntityResult


async def create_relation(
    session: AsyncSession,
    from_entity_id: str,
    to_entity_id: str,
    relation_type: str,
    metadata: dict[str, Any] | None = None,
    entity_types: dict[str, EntityTypeConfig] | None = None,
) -> EntityRelation:
    if entity_types is not None:
        from edera_core.storage.repository._helpers import _entity_exists
        from edera_core.storage.repository._core_entity import get_core_entity
        from edera_core.storage.repository._ordinary import find_ordinary_entity

        async def _exists(s, ref, ets):
            return await get_core_entity(s, ref, ets) is not None or await find_ordinary_entity(s, ref, ets) is not None

        if not await _exists(session, from_entity_id, entity_types):
            raise ValueError(f"from entity not found: {from_entity_id}")
        if not await _exists(session, to_entity_id, entity_types):
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


async def force_delete_entity_relations(session: AsyncSession, refs: set[str]) -> list[EntityRelation]:
    relations = await list_relations_for_entity_refs(session, refs)
    for relation in relations:
        await session.delete(relation)
    await session.flush()
    return relations


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
