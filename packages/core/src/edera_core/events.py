from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Event:
    type: str
    payload: dict[str, Any]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[Event]] = set()

    async def publish(self, event_type: str, **payload: Any) -> None:
        event = Event(event_type, payload)
        for queue in list(self._subscribers):
            await queue.put(event)

    async def subscribe(self):
        queue: asyncio.Queue[Event] = asyncio.Queue()
        self._subscribers.add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._subscribers.discard(queue)


event_bus = EventBus()
