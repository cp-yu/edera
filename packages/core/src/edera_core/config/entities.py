from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

from edera_core.config.schema import (
    EntitiesConfig,
    EntityConfig,
    EntityRelationConfig,
    EntityRelationsConfig,
    EntityTypeConfig,
    FieldPermission,
    entity_ref,
)
from edera_core.errors import ConfigEditError, ConfigError


logger = logging.getLogger(__name__)
PERMISSIONS: tuple[FieldPermission, ...] = ("none", "read-only", "write-only", "read-write")
CORE_ENTITY_TYPES = {"node", "dag", "trigger", "resource"}
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
    config_path: Path | None
    memory_entities: dict[str, EntityConfig]
    database_entities: list[EntityConfig]

    def __init__(
        self,
        entities: EntitiesConfig | None = None,
        entity_types: dict[str, EntityTypeConfig] | None = None,
        relations: EntityRelationsConfig | None = None,
        config_path: Path | None = None,
    ) -> None:
        if entities is None or entity_types is None or relations is None:
            from edera_core.config.loader import load_app_config

            config = load_app_config(Path("config"))
            entities = config.entities
            entity_types = config.entity_types
            relations = config.entity_relations
            config_path = Path("config/entities.yaml")
        self.entities = entities
        self.entity_types = entity_types
        self.relations = relations
        self.config_path = config_path
        self.memory_entities = {}
        self.database_entities = []

    def resolve(self, ref: str) -> EntityConfig:
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
        if entity_type in CORE_ENTITY_TYPES:
            from edera_core.storage.repository import save_core_entity

            entity = EntityConfig(
                id=str(attributes.get("id") or uuid4().hex),
                type=entity_type,
                attributes=attributes,
            )
            _validate_entity_semantics(entity)
            return await save_core_entity(session, entity)
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
        session: Any | None = None,
    ) -> list[EntityConfig]:
        if session is None or not self._needs_database(entity_type):
            return self.query(entity_type, run_id, node_id, tags)
        from edera_core.storage.repository import list_core_entities, query_node_output_entities

        filesystem_and_memory = [
            entity
            for entity in self.query(entity_type, run_id, node_id, tags)
            if self.entity_types[entity.type].storage_tier != "database"
        ]
        core: list[EntityConfig] = []
        if entity_type in CORE_ENTITY_TYPES or entity_type is None:
            core = await list_core_entities(session, entity_type if entity_type in CORE_ENTITY_TYPES else None)
        outputs: list[EntityConfig] = []
        if entity_type not in CORE_ENTITY_TYPES:
            outputs = await query_node_output_entities(session, entity_type, run_id, node_id, tags)
        return _dedupe_entities(filesystem_and_memory + core + outputs)

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
        if entity.type in CORE_ENTITY_TYPES:
            from edera_core.storage.repository import save_core_entity

            saved = entity.model_copy(update={"attributes": self._writable_attributes(entity, entity, permissions)})
            _validate_entity_semantics(saved)
            return await save_core_entity(session, saved)
        from edera_core.storage.repository import save_node_output_entity

        return await save_node_output_entity(session, entity)

    async def delete_async(self, entity_id: str, session: Any | None = None) -> int:
        if session is not None:
            from edera_core.storage.repository import delete_core_entity, delete_node_output_entity

            if await delete_core_entity(session, entity_id, self.entity_types):
                return 0
            if await delete_node_output_entity(session, entity_id):
                return 0
        return self.delete(entity_id)

    def discover(self, refs: list[str] | None) -> list[str]:
        if refs is None:
            return []
        return [str(ref) for ref in refs]

    def related_refs(self, ref: str) -> list[str]:
        resolved = entity_ref(self.resolve(ref), self.entity_types)
        related: list[str] = []
        for relation in self.relations.relations:
            refs = [entity_ref(self.resolve(item), self.entity_types) for item in relation.entities]
            if resolved not in refs:
                continue
            for item in refs:
                if item != resolved and item not in related:
                    related.append(item)
        return related

    def create(self, entity_type: str, attributes: dict[str, Any], entity_id: str | None = None) -> EntityConfig:
        if entity_type not in self.entity_types:
            raise ConfigError(f"unknown entity type: {entity_type}")
        entity = EntityConfig(id=entity_id or uuid4().hex, type=entity_type, attributes=attributes)
        _validate_entity_semantics(entity)
        tier = self.entity_types[entity_type].storage_tier
        if tier == "memory":
            self.memory_entities[entity.id] = entity
        elif tier == "database":
            self.database_entities.append(entity)
        elif self.config_path is None:
            self.entities.entities.append(entity)
        try:
            self._validate()
            if tier != "filesystem" or self.config_path is None:
                self._persist()
            self._persist_entity_file(entity)
        except (ConfigEditError, ConfigError):
            self._remove_new_entity(entity)
            raise
        return entity

    def save(
        self,
        entity: EntityConfig,
        permissions: dict[str, Any] | None = None,
    ) -> EntityConfig:
        if self.config_path is not None and self.entity_types[entity.type].storage_tier == "filesystem":
            current = self._filesystem_entity(entity.id)
            if current is not None:
                if current.type != entity.type:
                    raise ConfigError(f"Entity type cannot change: {entity.id}")
                saved = entity.model_copy(
                    update={"attributes": self._writable_attributes(current, entity, permissions)}
                )
                _validate_entity_semantics(saved)
                self._persist_entity_file(saved)
                return saved
        for index, current in enumerate(self.entities.entities):
            if current.id == entity.id:
                if current.type != entity.type:
                    raise ConfigError(f"Entity type cannot change: {entity.id}")
                saved = entity.model_copy(update={"attributes": self._writable_attributes(current, entity, permissions)})
                _validate_entity_semantics(saved)
                self.entities.entities[index] = saved
                try:
                    self._validate()
                    self._persist()
                except (ConfigEditError, ConfigError):
                    self.entities.entities[index] = current
                    raise
                return saved
        if entity.id in self.memory_entities:
            current = self.memory_entities[entity.id]
            if current.type != entity.type:
                raise ConfigError(f"Entity type cannot change: {entity.id}")
            saved = entity.model_copy(
                update={"attributes": self._writable_attributes(current, entity, permissions)}
            )
            _validate_entity_semantics(saved)
            self.memory_entities[entity.id] = saved
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
        if self.config_path is not None:
            for file, current in self._filesystem_entity_files():
                if current.id != entity_id:
                    continue
                file.unlink()
                return 0
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
                self._persist()
                self._persist_relations()
            except (ConfigEditError, ConfigError):
                self.entities.entities.insert(index, current)
                self.relations.relations = old_relations
                raise
            return len(removed_relations)
        raise ConfigError(f"Entity not found: {entity_id}")

    def release_run(self, run_id: str) -> None:
        self.memory_entities = {
            entity_id: entity
            for entity_id, entity in self.memory_entities.items()
            if entity.attributes.get("run_id") != run_id
        }

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
        try:
            self._persist_relations()
        except ConfigEditError:
            self.relations.relations.pop()
            raise
        return relation

    def delete_relation(self, relation_id: str) -> None:
        for index, relation in enumerate(self.relations.relations):
            if relation.id != relation_id:
                continue
            removed = self.relations.relations.pop(index)
            try:
                self._persist_relations()
            except ConfigEditError:
                self.relations.relations.insert(index, removed)
                raise
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

    def _persist(self) -> None:
        if self.config_path is None:
            return
        from edera_core.config.editor import RuntimeConfigEditor

        content = yaml.safe_dump(self.entities.model_dump(mode="json"), allow_unicode=True, sort_keys=False)
        RuntimeConfigEditor(self.config_path.parent).save("entities", "entities", content)

    def _persist_relations(self) -> None:
        if self.config_path is None:
            return
        from edera_core.config.editor import RuntimeConfigEditor

        content = yaml.safe_dump(self.relations.model_dump(mode="json"), allow_unicode=True, sort_keys=False)
        RuntimeConfigEditor(self.config_path.parent).save("entity-relations", "entity-relations", content)

    def _persist_entity_file(self, entity: EntityConfig) -> None:
        if self.config_path is None or self.entity_types[entity.type].storage_tier != "filesystem":
            return
        path = self._entity_file_path(entity)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(entity.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def _entity_file_path(self, entity: EntityConfig) -> Path:
        if self.config_path is None:
            raise ConfigError("config path is required")
        directory = _filesystem_dir(self.config_path.parent, entity.type)
        entity_type = self.entity_types[entity.type]
        raw_business_id = entity.id if entity_type.business_id_field == "id" else entity.attributes.get(entity_type.business_id_field)
        business_id = _safe_name(raw_business_id)
        name = business_id or _safe_name(entity.id)
        return directory / f"{name}.yaml"

    def _all_entities(self) -> list[EntityConfig]:
        entities = list(self.entities.entities)
        entities.extend(self.memory_entities.values())
        entities.extend(self.database_entities)
        entities.extend(self._filesystem_entities())
        return _dedupe_entities(entities)

    def _needs_database(self, entity_type: str | None) -> bool:
        if entity_type is None:
            return any(item.storage_tier == "database" for item in self.entity_types.values())
        entity_config = self.entity_types.get(entity_type)
        return entity_config is not None and entity_config.storage_tier == "database"

    def _filesystem_entities(self) -> list[EntityConfig]:
        if self.config_path is None:
            return []
        from edera_core.config.loader import _entity_from_file

        config_dir = self.config_path.parent
        entities: list[EntityConfig] = []
        for entity_type, directory in _filesystem_dirs(config_dir).items():
            if entity_type != "entities" and entity_type not in self.entity_types:
                continue
            if not directory.exists():
                continue
            for file in sorted(directory.glob("*.yaml")):
                entities.append(_entity_from_file(file, entity_type if entity_type != "entities" else None))
        return entities

    def _filesystem_entity(self, entity_id: str) -> EntityConfig | None:
        for _file, entity in self._filesystem_entity_files():
            if entity.id == entity_id:
                return entity
        return None

    def _filesystem_entity_files(self) -> list[tuple[Path, EntityConfig]]:
        if self.config_path is None:
            return []
        from edera_core.config.loader import _entity_from_file

        config_dir = self.config_path.parent
        entities: list[tuple[Path, EntityConfig]] = []
        for entity_type, directory in _filesystem_dirs(config_dir).items():
            if entity_type != "entities" and entity_type not in self.entity_types:
                continue
            if not directory.exists():
                continue
            for file in sorted(directory.glob("*.yaml")):
                entities.append((file, _entity_from_file(file, entity_type if entity_type != "entities" else None)))
        return entities

    def _remove_new_entity(self, entity: EntityConfig) -> None:
        if entity.id in self.memory_entities:
            del self.memory_entities[entity.id]
            return
        if self.config_path is not None and self.entity_types[entity.type].storage_tier == "filesystem":
            path = self._entity_file_path(entity)
            if path.exists():
                path.unlink()
            return
        for collection in (self.database_entities, self.entities.entities):
            for index, current in enumerate(collection):
                if current.id == entity.id:
                    collection.pop(index)
                    return


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


def _filesystem_dirs(config_dir: Path) -> dict[str, Path]:
    return {
        "node": config_dir / "nodes",
        "dag": config_dir / "dags",
        "trigger": config_dir / "triggers",
        "entities": config_dir / "entities",
    }


def _filesystem_dir(config_dir: Path, entity_type: str) -> Path | None:
    if entity_type in {"node", "dag", "trigger"}:
        return _filesystem_dirs(config_dir)[entity_type]
    return config_dir / "entities"


def _safe_name(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.replace("/", "_").replace(":", "_").strip()
