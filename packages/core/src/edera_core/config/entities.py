from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from edera_core.config.schema import (
    EntitiesConfig,
    EntityConfig,
    EntityRelationConfig,
    EntityRelationsConfig,
    EntityTypeConfig,
    FieldPermission,
    entity_ref,
)
from edera_core.config.entity_query_result import EntityQueryResult
from edera_core.errors import ConfigEditError, ConfigError


logger = logging.getLogger(__name__)
PERMISSIONS: tuple[FieldPermission, ...] = ("none", "read-only", "write-only", "read-write")
CORE_ENTITY_TYPES = {"node", "dag", "trigger", "resource", "input_mapping"}
_ALLOWED_PERMISSION_OVERRIDES: dict[FieldPermission, set[FieldPermission]] = {
    "none": {"none", "read-only", "write-only", "read-write"},
    "read-only": {"read-only", "read-write"},
    "write-only": {"write-only", "read-write"},
    "read-write": {"read-write"},
}


@dataclass(init=False)
class EntityStore:
    entities: EntitiesConfig
    entity_types: dict[str, EntityTypeConfig]
    relations: EntityRelationsConfig
    memory_entities: dict[str, dict[str, EntityConfig]]
    database_entities: list[EntityConfig]
    default_dag_run_id: str | None

    def __init__(
        self,
        entities: EntitiesConfig | None = None,
        entity_types: dict[str, EntityTypeConfig] | None = None,
        relations: EntityRelationsConfig | None = None,
        config_path: object | None = None,
    ) -> None:
        if entities is None or entity_types is None or relations is None:
            from edera_core.config.loader import load_app_config

            config = load_app_config(Path("config"))
            entities = config.entities
            entity_types = config.entity_types
            relations = config.entity_relations
        self.entities = entities
        self.entity_types = entity_types
        self.relations = relations
        self.memory_entities = {}
        self.database_entities = []
        self.default_dag_run_id = None

    def resolve(self, ref: str, dag_run_id: str | None = None) -> EntityConfig:
        effective_dag_run_id = dag_run_id or self.default_dag_run_id
        if effective_dag_run_id is not None:
            cached = self.memory_entities.get(effective_dag_run_id, {}).get(ref)
            if cached is not None:
                return cached.model_copy(deep=True)
        for entity in self.query():
            if _entity_matches(entity, self.entity_types, ref):
                return entity.model_copy(deep=True)
        raise ConfigError(f"Entity not found: {ref}")

    def query(
        self,
        entity_type: str | None = None,
        run_id: str | None = None,
        node_id: str | None = None,
        tags: list[str] | None = None,
    ) -> list[EntityConfig]:
        matched: list[EntityConfig] = []
        for entity in self._all_entities():
            if entity_type is not None and entity.type != entity_type:
                continue
            if run_id is not None and entity.attributes.get("run_id") != run_id:
                continue
            if node_id is not None and entity.attributes.get("node_id") != node_id:
                continue
            if tags is not None and not set(tags).issubset(set(_tags(entity))):
                continue
            matched.append(entity.model_copy(deep=True))
        return matched

    async def create_async(
        self,
        entity_type: str,
        attributes: dict[str, Any],
        session: Any | None = None,
    ) -> EntityConfig:
        if entity_type not in self.entity_types:
            raise ConfigError(f"unknown entity type: {entity_type}")
        if self.entity_types[entity_type].storage_tier != "database":
            return self.create(entity_type, attributes)
        if session is None:
            raise ConfigError("database session is required")
        if entity_type == "relation":
            from edera_core.storage.repository import create_relation

            from_entity_id = str(attributes.get("from_entity_id") or attributes.get("from") or "")
            to_entity_id = str(attributes.get("to_entity_id") or attributes.get("to") or "")
            relation_type = str(attributes.get("relation_type") or "")
            if not from_entity_id or not to_entity_id or not relation_type:
                raise ConfigError("relation requires from_entity_id, to_entity_id and relation_type")
            relation = await create_relation(session, from_entity_id, to_entity_id, relation_type, dict(attributes.get("metadata") or {}), self.entity_types)
            return _relation_entity(relation)
        if entity_type in CORE_ENTITY_TYPES:
            from edera_core.storage.repository import save_core_entity

            entity = EntityConfig(
                id=str(attributes.get("id") or uuid4().hex),
                type=entity_type,
                attributes=attributes,
            )
            _validate_entity_semantics(entity)
            return await save_core_entity(session, entity)
        if not _looks_like_output(attributes):
            from edera_core.storage.repository import save_ordinary_entity

            entity = EntityConfig(id=str(attributes.get("id") or uuid4().hex), type=entity_type, attributes=attributes)
            _validate_entity_semantics(entity)
            return await save_ordinary_entity(session, entity, self.entity_types[entity_type])
        from edera_core.storage.repository import node_output_to_entity, store_node_output_entities

        stored = await store_node_output_entities(
            session,
            str(attributes.get("run_id") or ""),
            str(attributes.get("node_id") or entity_type),
            entity_type,
            attributes.get("payload", attributes),
            str(attributes["session_id"]) if attributes.get("session_id") is not None else None,
        )
        if not stored:
            raise ConfigError(f"database entity was not stored: {entity_type}")
        return node_output_to_entity(stored[0])

    async def query_async(
        self,
        entity_type: str | None = None,
        run_id: str | None = None,
        node_id: str | None = None,
        tags: list[str] | None = None,
        dag_run_id: str | None = None,
        session: Any | None = None,
    ) -> list[EntityQueryResult]:
        if session is None or not self._needs_database(entity_type):
            return self.query_results(entity_type, run_id, node_id, tags, dag_run_id)
        from edera_core.storage.repository import list_core_entities, list_ordinary_entities, list_relations, query_node_output_entities

        memory = [
            entity
            for entity in self.query(entity_type, run_id, node_id, tags)
            if self.entity_types[entity.type].storage_tier != "database"
        ]
        core: list[EntityConfig] = []
        if entity_type in CORE_ENTITY_TYPES or entity_type is None:
            core = await list_core_entities(session, entity_type if entity_type in CORE_ENTITY_TYPES else None)
        ordinary = await list_ordinary_entities(session, self.entity_types, entity_type)
        relations: list[EntityConfig] = []
        if entity_type in {None, "relation"}:
            relations = [_relation_entity(relation) for relation in await list_relations(session)]
        outputs: list[EntityConfig] = []
        if entity_type not in CORE_ENTITY_TYPES:
            outputs = await query_node_output_entities(session, entity_type, run_id, node_id, tags)
        return self._query_results_from_entities(memory + core + ordinary + relations + outputs, entity_type, run_id, node_id, tags, dag_run_id)

    def query_results(
        self,
        entity_type: str | None = None,
        run_id: str | None = None,
        node_id: str | None = None,
        tags: list[str] | None = None,
        dag_run_id: str | None = None,
    ) -> list[EntityQueryResult]:
        dag_run_id = dag_run_id or self.default_dag_run_id
        return self._query_results_from_entities(self.query(entity_type, run_id, node_id, tags), entity_type, run_id, node_id, tags, dag_run_id)

    async def query_one_async(
        self,
        ref: str,
        dag_run_id: str | None = None,
        session: Any | None = None,
    ) -> EntityQueryResult:
        dag_run_id = dag_run_id or self.default_dag_run_id
        if dag_run_id is not None:
            cached = self.memory_entities.get(dag_run_id, {}).get(ref)
            if cached is not None:
                return EntityQueryResult(cached.model_copy(deep=True), True, dag_run_id)
        if session is None:
            return EntityQueryResult(self.resolve(ref), False, None)
        entity = await self._get_database_entity(ref, session)
        if entity is None:
            raise ConfigError(f"Entity not found: {ref}")
        return EntityQueryResult(entity, False, None)

    async def preload_for_dag(
        self,
        dag_run_id: str,
        entity_refs: list[str],
        session: Any | None = None,
    ) -> None:
        if session is None:
            raise ConfigError("database session is required")
        from edera_core.storage.repository import list_relations_for_entity_refs

        cached: dict[str, EntityConfig] = {}
        direct_refs: set[str] = set()
        for ref in entity_refs:
            entity = await self._get_database_entity(ref, session)
            if entity is None:
                raise ValueError(f"entity not found: {ref}")
            _cache_entity(cached, self.entity_types, ref, entity)
            direct_refs.update(_entity_refs(entity, self.entity_types))
        for relation in await list_relations_for_entity_refs(session, direct_refs):
            relation_entity = _relation_entity(relation)
            cached[relation_entity.id] = relation_entity
            for ref in (relation.from_entity_id, relation.to_entity_id):
                entity = await self._get_database_entity(ref, session)
                if entity is not None:
                    _cache_entity(cached, self.entity_types, ref, entity)
        self.memory_entities[dag_run_id] = cached

    def clear_cache_for_dag(self, dag_run_id: str) -> None:
        self.memory_entities.pop(dag_run_id, None)

    async def save_async(
        self,
        entity: EntityConfig,
        permissions: dict[str, Any] | None = None,
        session: Any | None = None,
    ) -> EntityConfig:
        if self.entity_types[entity.type].storage_tier != "database":
            return self.save(entity, permissions)
        if session is None:
            raise ConfigError("database session is required")
        if entity.type == "relation":
            raise ConfigError("relation updates use relation repository operations")
        if entity.type in CORE_ENTITY_TYPES:
            from edera_core.storage.repository import save_core_entity

            saved = entity.model_copy(update={"attributes": self._writable_attributes(entity, entity, permissions)})
            _validate_entity_semantics(saved)
            return await save_core_entity(session, saved)
        from edera_core.storage.repository import save_ordinary_entity

        saved = entity.model_copy(update={"attributes": self._writable_attributes(entity, entity, permissions)})
        _validate_entity_semantics(saved)
        return await save_ordinary_entity(session, saved, self.entity_types[entity.type])

    async def delete_async(self, entity_id: str, session: Any | None = None) -> int:
        if session is not None:
            from edera_core.storage.repository import delete_core_entity, delete_node_output_entity, delete_ordinary_entity, delete_relation

            if await delete_relation(session, entity_id):
                return 0
            if await delete_core_entity(session, entity_id, self.entity_types):
                return 0
            if await delete_ordinary_entity(session, entity_id, self.entity_types):
                return 0
            if await delete_node_output_entity(session, entity_id):
                return 0
        return self.delete(entity_id)

    def discover(self, refs: list[str] | None) -> list[str]:
        if refs is None:
            return []
        return [str(ref) for ref in refs]

    def related_refs(self, ref: str, dag_run_id: str | None = None) -> list[str]:
        effective_dag_run_id = dag_run_id or self.default_dag_run_id
        resolved = entity_ref(self.resolve(ref, effective_dag_run_id), self.entity_types)
        related: list[str] = []
        for relation in self._relations_for_dag(effective_dag_run_id):
            refs = [entity_ref(self.resolve(item, effective_dag_run_id), self.entity_types) for item in relation.entities]
            if resolved not in refs:
                continue
            for item in refs:
                if item != resolved and item not in related:
                    related.append(item)
        return related

    def _relations_for_dag(self, dag_run_id: str | None) -> list[EntityRelationConfig]:
        relations = list(self.relations.relations)
        if dag_run_id is None:
            return relations
        seen = {relation.id for relation in relations}
        for entity in self.memory_entities.get(dag_run_id, {}).values():
            if entity.type != "relation" or entity.id in seen:
                continue
            refs = entity.attributes.get("entities")
            if not isinstance(refs, list):
                refs = [entity.attributes.get("from_entity_id"), entity.attributes.get("to_entity_id")]
            relations.append(
                EntityRelationConfig(
                    id=entity.id,
                    entities=[str(item) for item in refs if item],
                    type=str(entity.attributes.get("relation_type") or ""),
                    metadata=dict(entity.attributes.get("metadata") or {}),
                )
            )
            seen.add(entity.id)
        return relations

    def create(self, entity_type: str, attributes: dict[str, Any], entity_id: str | None = None) -> EntityConfig:
        if entity_type not in self.entity_types:
            raise ConfigError(f"unknown entity type: {entity_type}")
        entity = EntityConfig(id=entity_id or uuid4().hex, type=entity_type, attributes=attributes)
        _validate_entity_semantics(entity)
        tier = self.entity_types[entity_type].storage_tier
        if tier == "memory":
            self.memory_entities.setdefault("", {})[entity.id] = entity
        elif tier == "database":
            self.database_entities.append(entity)
        else:
            self.entities.entities.append(entity)
        try:
            self._validate()
        except (ConfigEditError, ConfigError):
            self._remove_new_entity(entity)
            raise
        return entity

    def save(
        self,
        entity: EntityConfig,
        permissions: dict[str, Any] | None = None,
    ) -> EntityConfig:
        for index, current in enumerate(self.entities.entities):
            if current.id == entity.id:
                if current.type != entity.type:
                    raise ConfigError(f"Entity type cannot change: {entity.id}")
                saved = entity.model_copy(update={"attributes": self._writable_attributes(current, entity, permissions)})
                _validate_entity_semantics(saved)
                self.entities.entities[index] = saved
                try:
                    self._validate()
                except (ConfigEditError, ConfigError):
                    self.entities.entities[index] = current
                    raise
                return saved
        memory_entities = self.memory_entities.setdefault("", {})
        if entity.id in memory_entities:
            current = memory_entities[entity.id]
            if current.type != entity.type:
                raise ConfigError(f"Entity type cannot change: {entity.id}")
            saved = entity.model_copy(
                update={"attributes": self._writable_attributes(current, entity, permissions)}
            )
            _validate_entity_semantics(saved)
            memory_entities[entity.id] = saved
            return saved
        for index, current in enumerate(self.database_entities):
            if current.id != entity.id:
                continue
            if current.type != entity.type:
                raise ConfigError(f"Entity type cannot change: {entity.id}")
            saved = entity.model_copy(
                update={"attributes": self._writable_attributes(current, entity, permissions)}
            )
            _validate_entity_semantics(saved)
            self.database_entities[index] = saved
            return saved
        raise ConfigError(f"Entity not found: {entity.id}")

    def delete(self, entity_id: str) -> int:
        for index, current in enumerate(self.entities.entities):
            if current.id != entity_id:
                continue
            refs = {current.id, entity_ref(current, self.entity_types)}
            removed_relations = [
                relation for relation in self.relations.relations if any(ref in refs for ref in relation.entities)
            ]
            next_relations = [
                relation for relation in self.relations.relations if relation not in removed_relations
            ]
            self.entities.entities.pop(index)
            old_relations = self.relations.relations
            self.relations.relations = next_relations
            try:
                self._validate()
            except (ConfigEditError, ConfigError):
                self.entities.entities.insert(index, current)
                self.relations.relations = old_relations
                raise
            return len(removed_relations)
        raise ConfigError(f"Entity not found: {entity_id}")

    def release_run(self, run_id: str) -> None:
        self.clear_cache_for_dag(run_id)

    def create_relation(
        self,
        refs: list[str],
        relation_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> EntityRelationConfig:
        normalized = [entity_ref(self.resolve(ref), self.entity_types) for ref in refs]
        if any(relation.type == relation_type and [_normalize_relation_ref(self, ref) for ref in relation.entities] == normalized for relation in self.relations.relations):
            raise ConfigEditError("duplicate entity relation")
        relation = EntityRelationConfig(entities=normalized, type=relation_type, metadata=metadata or {})
        self.relations.relations.append(relation)
        return relation

    def delete_relation(self, relation_id: str) -> None:
        for index, relation in enumerate(self.relations.relations):
            if relation.id != relation_id:
                continue
            self.relations.relations.pop(index)
            return
        raise ConfigError(f"Entity relation not found: {relation_id}")

    def _writable_attributes(
        self,
        current: EntityConfig,
        entity: EntityConfig,
        permissions: dict[str, Any] | None,
    ) -> dict[str, Any]:
        entity_type = self.entity_types[current.type]
        overrides = permissions.get(current.type) if isinstance(permissions, dict) else None
        values = dict(current.attributes)
        for field_name in set(current.attributes) | set(entity.attributes):
            permission = field_permission(entity_type, field_name, overrides if isinstance(overrides, dict) else None)
            if field_name not in entity.attributes:
                if can_read(permission) and not can_write(permission):
                    logger.warning("Permission denied: %s.%s is not writable", current.type, field_name)
                elif can_read(permission) and can_write(permission):
                    values.pop(field_name, None)
                continue
            if can_write(permission):
                values[field_name] = entity.attributes[field_name]
            elif entity.attributes.get(field_name) != current.attributes.get(field_name):
                logger.warning("Permission denied: %s.%s is not writable", current.type, field_name)
        return values

    def _validate(self) -> None:
        from edera_core.config.loader import _validate_entities

        _validate_entities(self.entities, self.entity_types)

    def _all_entities(self) -> list[EntityConfig]:
        entities = list(self.entities.entities)
        entities.extend(self.memory_entities.get("", {}).values())
        entities.extend(self.database_entities)
        return _dedupe_entities(entities)

    def _needs_database(self, entity_type: str | None) -> bool:
        if entity_type is None:
            return any(item.storage_tier == "database" for item in self.entity_types.values())
        entity_config = self.entity_types.get(entity_type)
        return entity_config is not None and entity_config.storage_tier == "database"

    def _remove_new_entity(self, entity: EntityConfig) -> None:
        memory_entities = self.memory_entities.get("", {})
        if entity.id in memory_entities:
            del memory_entities[entity.id]
            return
        for collection in (self.database_entities, self.entities.entities):
            for index, current in enumerate(collection):
                if current.id == entity.id:
                    collection.pop(index)
                    return

    async def _get_database_entity(self, ref: str, session: Any) -> EntityConfig | None:
        from edera_core.storage.repository import find_ordinary_entity, get_core_entity, list_relations

        core = await get_core_entity(session, ref, self.entity_types)
        if core is not None:
            return core
        ordinary = await find_ordinary_entity(session, ref, self.entity_types)
        if ordinary is not None:
            return ordinary
        for relation in await list_relations(session):
            if relation.id == ref:
                return _relation_entity(relation)
        return None

    def _query_results_from_entities(
        self,
        entities: list[EntityConfig],
        entity_type: str | None,
        run_id: str | None,
        node_id: str | None,
        tags: list[str] | None,
        dag_run_id: str | None,
    ) -> list[EntityQueryResult]:
        fallback = [
            entity
            for entity in _dedupe_entities(entities)
            if _matches_query(entity, entity_type, run_id, node_id, tags)
        ]
        if dag_run_id is None:
            return [EntityQueryResult(entity.model_copy(deep=True), False, None) for entity in fallback]
        cached = [
            entity
            for entity in _dedupe_entities(list(self.memory_entities.get(dag_run_id, {}).values()))
            if _matches_query(entity, entity_type, run_id, node_id, tags)
        ]
        cached_ids = {entity.id for entity in cached}
        results = [EntityQueryResult(entity.model_copy(deep=True), True, dag_run_id) for entity in cached]
        results.extend(
            EntityQueryResult(entity.model_copy(deep=True), False, None)
            for entity in fallback
            if entity.id not in cached_ids
        )
        return results


def field_permission(
    entity_type: EntityTypeConfig,
    field: str,
    overrides: dict[str, Any] | None = None,
) -> FieldPermission:
    current: FieldPermission = "read-write"
    parts = field.split(".")
    for index in range(1, len(parts) + 1):
        key = ".".join(parts[:index])
        value = entity_type.field_permissions.get(key)
        if value is not None:
            current = value
    override = _override_permission(overrides, field)
    return override or current


def can_read(permission: FieldPermission) -> bool:
    return permission in {"read-only", "read-write"}


def can_write(permission: FieldPermission) -> bool:
    return permission in {"write-only", "read-write"}


def validate_permission_overrides(
    entity_types: dict[str, EntityTypeConfig],
    overrides: dict[str, Any],
) -> None:
    for entity_type_name, fields in overrides.items():
        if entity_type_name not in entity_types:
            raise ConfigError(f"unknown entity type: {entity_type_name}")
        if not isinstance(fields, dict):
            raise ConfigError("entity permission override must be a mapping")
        entity_type = entity_types[entity_type_name]
        for field_name, value in fields.items():
            if value not in PERMISSIONS:
                raise ConfigError(f"invalid field permission: {value}")
            base = field_permission(entity_type, str(field_name))
            if value not in _ALLOWED_PERMISSION_OVERRIDES[base]:
                raise ConfigError(f"invalid permission downgrade: {entity_type_name}.{field_name}")


def _validate_entity_semantics(entity: EntityConfig) -> None:
    if entity.type != "trigger":
        return
    wait_for = entity.attributes.get("wait_for")
    if not isinstance(wait_for, str):
        return
    from edera_core.trigger import parse_trigger_expression

    parse_trigger_expression(wait_for)


def _override_permission(overrides: dict[str, Any] | None, field: str) -> FieldPermission | None:
    if not overrides:
        return None
    value = overrides.get(field)
    return value if value in PERMISSIONS else None


def _normalize_relation_ref(store: EntityStore, ref: str) -> str:
    return entity_ref(store.resolve(ref), store.entity_types)


def _cache_entity(
    cached: dict[str, EntityConfig],
    entity_types: dict[str, EntityTypeConfig],
    ref: str,
    entity: EntityConfig,
) -> None:
    cached[ref] = entity
    for item in _entity_refs(entity, entity_types):
        cached[item] = entity


def _entity_refs(entity: EntityConfig, entity_types: dict[str, EntityTypeConfig]) -> set[str]:
    refs = {entity.id}
    try:
        refs.add(entity_ref(entity, entity_types))
    except (KeyError, ValueError):
        pass
    return refs


def _entity_matches(
    entity: EntityConfig,
    entity_types: dict[str, EntityTypeConfig],
    ref: str,
) -> bool:
    if ref == entity.id:
        return True
    try:
        return ref == entity_ref(entity, entity_types)
    except (KeyError, ValueError):
        return False


def _matches_query(
    entity: EntityConfig,
    entity_type: str | None,
    run_id: str | None,
    node_id: str | None,
    tags: list[str] | None,
) -> bool:
    if entity_type is not None and entity.type != entity_type:
        return False
    if run_id is not None and entity.attributes.get("run_id") != run_id:
        return False
    if node_id is not None and entity.attributes.get("node_id") != node_id:
        return False
    return tags is None or set(tags).issubset(set(_tags(entity)))


def _relation_entity(relation) -> EntityConfig:
    from_entity_id = relation.from_entity_id
    to_entity_id = relation.to_entity_id
    return EntityConfig(
        id=relation.id,
        type="relation",
        attributes={
            "from": from_entity_id,
            "to": to_entity_id,
            "from_entity_id": from_entity_id,
            "to_entity_id": to_entity_id,
            "relation_type": relation.relation_type,
            "entities": [from_entity_id, to_entity_id],
            "metadata": relation.metadata_,
        },
    )


def _tags(entity: EntityConfig) -> list[str]:
    tags = entity.attributes.get("tags")
    if isinstance(tags, list):
        return [str(tag) for tag in tags]
    payload = entity.attributes.get("payload")
    if isinstance(payload, dict) and isinstance(payload.get("tags"), list):
        return [str(tag) for tag in payload["tags"]]
    return []


def _dedupe_entities(entities: list[EntityConfig]) -> list[EntityConfig]:
    seen: set[str] = set()
    result: list[EntityConfig] = []
    for entity in entities:
        if entity.id in seen:
            continue
        seen.add(entity.id)
        result.append(entity)
    return result


def _looks_like_output(attributes: dict[str, Any]) -> bool:
    return isinstance(attributes.get("payload"), dict) and (
        isinstance(attributes.get("run_id"), str) or isinstance(attributes.get("node_id"), str)
    )
