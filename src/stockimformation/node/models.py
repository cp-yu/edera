from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from pydantic import BaseModel

from stockimformation.config.entities import EntityStore, can_read, can_write, field_permission
from stockimformation.config.schema import EntityConfig


logger = logging.getLogger(__name__)


def _entity_overrides(
    entity_permissions: dict[str, Any] | None,
    entity_type: str,
) -> dict[str, Any] | None:
    if not isinstance(entity_permissions, dict):
        return None
    overrides = entity_permissions.get(entity_type)
    return overrides if isinstance(overrides, dict) else None


class SkillDefinition(BaseModel):
    name: str
    path: Path
    skill_md: str
    workflow_md: str


class NodeInput(BaseModel):
    cycle_id: str
    payload: Any
    metadata: dict[str, Any] = {}


class NodeOutput(BaseModel):
    node_name: str
    ok: bool
    payload: Any = None
    metadata: dict[str, Any] = {}
    error: str | None = None


@dataclass
class NodeContext:
    cycle_id: str
    instance_id: str
    node_type: str = ""
    dag_name: str = "default"
    entity_store: EntityStore | None = None
    entity_permissions: dict[str, Any] | None = None

    def get_entity(self, ref: str) -> EntityConfig | None:
        if self.entity_store is None:
            return None
        entity = self.entity_store.resolve(ref)
        entity_type = self.entity_store.entity_types[entity.type]
        overrides = _entity_overrides(self.entity_permissions, entity.type)
        attributes = {
            field: value
            for field, value in entity.attributes.items()
            if can_read(field_permission(entity_type, field, overrides))
        }
        return entity.model_copy(update={"attributes": attributes})

    def save_entity(self, entity: EntityConfig) -> EntityConfig | None:
        if self.entity_store is None:
            return None
        return self.entity_store.save(entity, self.entity_permissions)

    def create_entity(self, entity_type: str, attributes: dict[str, Any]) -> EntityConfig | None:
        if self.entity_store is None:
            return None
        return self.entity_store.create(entity_type, attributes)

    def read_entity_field(self, ref: str, field: str) -> Any:
        entity = self.get_entity(ref)
        if entity is None or self.entity_store is None:
            return None
        permission = field_permission(
            self.entity_store.entity_types[entity.type],
            field,
            _entity_overrides(self.entity_permissions, entity.type),
        )
        if not can_read(permission):
            logger.warning("Permission denied: %s.%s is not readable", entity.type, field)
            return None
        return entity.attributes.get(field)

    def write_entity_field(self, ref: str, field: str, value: Any) -> bool:
        entity = self.get_entity(ref)
        if entity is None or self.entity_store is None:
            return False
        permission = field_permission(
            self.entity_store.entity_types[entity.type],
            field,
            _entity_overrides(self.entity_permissions, entity.type),
        )
        if not can_write(permission):
            logger.warning("Permission denied: %s.%s is not writable", entity.type, field)
            return False
        entity.attributes[field] = value
        self.entity_store.save(entity, self.entity_permissions)
        return True


FunctionHandler = Callable[..., Awaitable[Any]]
