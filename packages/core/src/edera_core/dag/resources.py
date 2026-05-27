from __future__ import annotations

import asyncio
from dataclasses import dataclass

from edera_core.config.entities import EntityStore
from edera_core.errors import ConfigError


@dataclass
class ResourceSemaphore:
    semaphore: asyncio.Semaphore
    released: asyncio.Event

    def acquire_nowait(self) -> bool:
        if getattr(self.semaphore, "_value", 0) <= 0:
            return False
        self.semaphore._value -= 1
        return True

    def available(self) -> bool:
        return getattr(self.semaphore, "_value", 0) > 0

    def release(self) -> None:
        self.semaphore.release()
        self.released.set()


_SEMAPHORES: dict[str, ResourceSemaphore] = {}


def get_semaphore(resource_id: str, entity_store: EntityStore | None) -> ResourceSemaphore:
    if entity_store is None:
        raise ConfigError(f"Entity not found: {resource_id}")
    resource = entity_store.resolve(resource_id)
    if resource.type != "resource":
        raise ConfigError(f"Entity is not a resource: {resource_id}")
    if resource.id in _SEMAPHORES:
        return _SEMAPHORES[resource.id]
    permits = resource.attributes.get("permits")
    if not isinstance(permits, int) or isinstance(permits, bool) or permits < 1:
        raise ConfigError(f"resource {resource_id} permits must be >= 1")
    resource_semaphore = ResourceSemaphore(asyncio.Semaphore(permits), asyncio.Event())
    _SEMAPHORES[resource.id] = resource_semaphore
    return resource_semaphore


def clear_semaphore_cache() -> None:
    _SEMAPHORES.clear()
