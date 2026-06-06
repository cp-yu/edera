from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml
from sqlmodel.ext.asyncio.session import AsyncSession

from edera_core.config.schema import EntityConfig, EntityTypeConfig
from edera_core.storage.repository import (
    CORE_ENTITY_TABLES,
    create_relation,
    entity_exists,
    find_ordinary_entity,
    get_core_entity,
    list_ordinary_entities,
    list_relations,
    save_core_entity,
    save_ordinary_entity,
)


@dataclass(frozen=True)
class ImportExportResult:
    imported: int = 0
    updated: int = 0
    skipped: int = 0
    exported: int = 0
    warnings: list[str] = field(default_factory=list)


async def import_entities_from_yaml(
    session: AsyncSession,
    path: Path,
    entity_types: dict[str, EntityTypeConfig],
) -> ImportExportResult:
    imported = 0
    updated = 0
    for entity in _entities(path):
        if entity.type == "relation":
            await _import_relation_entity(session, entity, entity_types)
            imported += 1
            continue
        if entity.type in CORE_ENTITY_TABLES:
            existing = await get_core_entity(session, entity.id, entity_types)
            await save_core_entity(session, entity)
            if existing is None:
                imported += 1
            else:
                updated += 1
            continue
        existing = await find_ordinary_entity(session, entity.id, entity_types)
        await save_ordinary_entity(session, entity, entity_types[entity.type])
        if existing is None:
            imported += 1
        else:
            updated += 1
    await session.flush()
    return ImportExportResult(imported=imported, updated=updated)


async def _import_relation_entity(
    session: AsyncSession,
    entity: EntityConfig,
    entity_types: dict[str, EntityTypeConfig],
) -> None:
    attrs = entity.attributes
    refs = attrs.get("entities")
    from_entity_id = attrs.get("from_entity_id") or attrs.get("from")
    to_entity_id = attrs.get("to_entity_id") or attrs.get("to")
    if isinstance(refs, list) and len(refs) == 2:
        from_entity_id = from_entity_id or refs[0]
        to_entity_id = to_entity_id or refs[1]
    relation_type = attrs.get("relation_type")
    if not from_entity_id or not to_entity_id or not relation_type:
        raise ValueError("relation entity requires from_entity_id, to_entity_id and relation_type")
    await create_relation(
        session,
        str(from_entity_id),
        str(to_entity_id),
        str(relation_type),
        dict(attrs.get("metadata") or {}),
        entity_types,
    )


async def export_entities_to_yaml(
    session: AsyncSession,
    path: Path,
    entity_types: dict[str, EntityTypeConfig],
    entity_type: str | None = None,
) -> ImportExportResult:
    entities = await list_ordinary_entities(session, entity_types, entity_type)
    path.write_text(
        yaml.safe_dump({"entities": [entity.model_dump(mode="json") for entity in entities]}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return ImportExportResult(exported=len(entities))


async def import_relations_from_yaml(
    session: AsyncSession,
    path: Path,
    entity_types: dict[str, EntityTypeConfig],
) -> ImportExportResult:
    imported = 0
    skipped = 0
    warnings: list[str] = []
    for relation in _relations(path):
        refs = relation.get("entities")
        if not isinstance(refs, list) or len(refs) != 2:
            skipped += 1
            warnings.append("relation skipped: expected exactly two entities")
            continue
        from_entity_id = str(refs[0])
        to_entity_id = str(refs[1])
        missing = await _missing_relation_ref(session, from_entity_id, to_entity_id, entity_types)
        if missing is not None:
            skipped += 1
            warnings.append(f"relation skipped: missing entity {missing}")
            continue
        await create_relation(
            session,
            from_entity_id,
            to_entity_id,
            str(relation.get("type") or relation.get("relation_type") or ""),
            dict(relation.get("metadata") or {}),
            entity_types,
        )
        imported += 1
    await session.flush()
    return ImportExportResult(imported=imported, skipped=skipped, warnings=warnings)


async def export_relations_to_yaml(session: AsyncSession, path: Path) -> ImportExportResult:
    relations = await list_relations(session)
    path.write_text(
        yaml.safe_dump(
            {
                "relations": [
                    {
                        "id": relation.id,
                        "entities": [relation.from_entity_id, relation.to_entity_id],
                        "type": relation.relation_type,
                        "metadata": relation.metadata_,
                    }
                    for relation in relations
                ]
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return ImportExportResult(exported=len(relations))


def _entities(path: Path) -> list[EntityConfig]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entities = raw.get("entities") if isinstance(raw, dict) else None
    if not isinstance(entities, list):
        return []
    return [EntityConfig.model_validate(entity) for entity in entities]


def _relations(path: Path) -> list[dict[str, object]]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    relations = raw.get("relations") if isinstance(raw, dict) else None
    return [dict(relation) for relation in relations] if isinstance(relations, list) else []


async def _missing_relation_ref(
    session: AsyncSession,
    from_entity_id: str,
    to_entity_id: str,
    entity_types: dict[str, EntityTypeConfig],
) -> str | None:
    for ref in (from_entity_id, to_entity_id):
        if not await entity_exists(session, ref, entity_types):
            return ref
    return None
