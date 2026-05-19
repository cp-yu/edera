from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

from stockimformation.config.schema import (
    EntitiesConfig,
    EntityConfig,
    EntityRelationsConfig,
    EntityTypeConfig,
    FieldPermission,
    entity_ref,
)
from stockimformation.errors import ConfigEditError, ConfigError


logger = logging.getLogger(__name__)
PERMISSIONS: tuple[FieldPermission, ...] = ("none", "read-only", "write-only", "read-write")
_ALLOWED_PERMISSION_OVERRIDES: dict[FieldPermission, set[FieldPermission]] = {
    "none": {"none", "read-only", "write-only", "read-write"},
    "read-only": {"read-only", "read-write"},
    "write-only": {"write-only", "read-write"},
    "read-write": {"read-write"},
}


@dataclass
class EntityStore:
    entities: EntitiesConfig
    entity_types: dict[str, EntityTypeConfig]
    relations: EntityRelationsConfig
    config_path: Path | None = None

    def resolve(self, ref: str) -> EntityConfig:
        for entity in self.entities.entities:
            if ref == entity.id or ref == entity_ref(entity, self.entity_types):
                return entity.model_copy(deep=True)
        raise ConfigError(f"Entity not found: {ref}")

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

    def create(self, entity_type: str, attributes: dict[str, Any]) -> EntityConfig:
        if entity_type not in self.entity_types:
            raise ConfigError(f"unknown entity type: {entity_type}")
        entity = EntityConfig(id=uuid4().hex, type=entity_type, attributes=attributes)
        self.entities.entities.append(entity)
        try:
            self._validate()
            self._persist()
        except (ConfigEditError, ConfigError):
            self.entities.entities.pop()
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
                self.entities.entities[index] = saved
                try:
                    self._validate()
                    self._persist()
                except (ConfigEditError, ConfigError):
                    self.entities.entities[index] = current
                    raise
                return saved
        raise ConfigError(f"Entity not found: {entity.id}")

    def _writable_attributes(
        self,
        current: EntityConfig,
        entity: EntityConfig,
        permissions: dict[str, Any] | None,
    ) -> dict[str, Any]:
        entity_type = self.entity_types[current.type]
        overrides = permissions.get(current.type) if isinstance(permissions, dict) else None
        values = dict(current.attributes)
        for field in set(current.attributes) | set(entity.attributes):
            permission = field_permission(entity_type, field, overrides if isinstance(overrides, dict) else None)
            if field not in entity.attributes:
                if can_read(permission) and not can_write(permission):
                    logger.warning("Permission denied: %s.%s is not writable", current.type, field)
                elif can_read(permission) and can_write(permission):
                    values.pop(field, None)
                continue
            if can_write(permission):
                values[field] = entity.attributes[field]
            elif entity.attributes.get(field) != current.attributes.get(field):
                logger.warning("Permission denied: %s.%s is not writable", current.type, field)
        return values

    def _validate(self) -> None:
        from stockimformation.config.loader import _validate_entities

        _validate_entities(self.entities, self.entity_types)

    def _persist(self) -> None:
        if self.config_path is None:
            return
        from stockimformation.config.editor import RuntimeConfigEditor

        content = yaml.safe_dump(self.entities.model_dump(mode="json"), allow_unicode=True, sort_keys=False)
        RuntimeConfigEditor(self.config_path.parent).save("entities", "entities", content)


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
        for field, value in fields.items():
            if value not in PERMISSIONS:
                raise ConfigError(f"invalid field permission: {value}")
            base = field_permission(entity_type, str(field))
            if value not in _ALLOWED_PERMISSION_OVERRIDES[base]:
                raise ConfigError(f"invalid permission downgrade: {entity_type_name}.{field}")


def _override_permission(overrides: dict[str, Any] | None, field: str) -> FieldPermission | None:
    if not overrides:
        return None
    value = overrides.get(field)
    return value if value in PERMISSIONS else None
