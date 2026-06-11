from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field

from edera_core.config.entities import EntityStore
from edera_core.errors import ConfigError


@dataclass
class ResourceSemaphore:
    permits: int
    _count: int = field(init=False)
    _waiters: deque[asyncio.Future[None]] = field(default_factory=deque, init=False)
    released: asyncio.Event = field(default_factory=asyncio.Event, init=False)

    def __post_init__(self):
        self._count = self.permits

    def acquire_nowait(self) -> bool:
        if self._count <= 0:
            return False
        self._count -= 1
        return True

    def available(self) -> bool:
        return self._count > 0

    async def acquire(self) -> None:
        if self._count > 0:
            self._count -= 1
            return

        fut = asyncio.get_running_loop().create_future()
        self._waiters.append(fut)
        try:
            await fut
        except asyncio.CancelledError:
            if not fut.done():
                self._waiters.remove(fut)
            elif self._count > 0:
                self._count -= 1
                self._wakeup_next()
            raise

    def release(self) -> None:
        self._count += 1
        self.released.set()
        self._wakeup_next()

    def _wakeup_next(self) -> None:
        while self._waiters and self._count > 0:
            fut = self._waiters.popleft()
            if not fut.done():
                self._count -= 1
                fut.set_result(None)
                break


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
    resource_semaphore = ResourceSemaphore(permits)
    _SEMAPHORES[resource.id] = resource_semaphore
    return resource_semaphore


def clear_semaphore_cache() -> None:
    _SEMAPHORES.clear()
