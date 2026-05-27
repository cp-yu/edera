from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from edera_core.config.entities import EntityStore
from edera_core.config.schema import EntityConfig
from edera_core.errors import ConfigError


TriggerTarget = Callable[[str], Awaitable[None]]


@dataclass
class EventGroup:
    events: set[str] = field(default_factory=set)

    def set(self, event: str) -> None:
        self.events.add(event)

    def consume(self, mode: str, wanted: list[str]) -> bool:
        if not wanted:
            return False
        mode = mode.upper()
        matched = all(event in self.events for event in wanted) if mode == "AND" else any(event in self.events for event in wanted)
        if matched:
            for event in wanted:
                self.events.discard(event)
        return matched


@dataclass
class TriggerExecutor:
    store: EntityStore
    run_dag: TriggerTarget | None = None
    run_node: TriggerTarget | None = None
    events: EventGroup = field(default_factory=EventGroup)
    records: list[dict[str, str]] = field(default_factory=list)

    def triggers(self) -> list[EntityConfig]:
        return self.store.query("trigger")

    async def emit(self, event: str) -> list[str]:
        self.events.set(event)
        fired: list[str] = []
        for trigger in self.triggers():
            wait_for = trigger.attributes.get("wait_for")
            if not isinstance(wait_for, dict):
                continue
            events = wait_for.get("events")
            if not isinstance(events, list):
                continue
            wanted = [str(item) for item in events]
            if not self.events.consume(str(wait_for.get("mode", "OR")), wanted):
                continue
            target = str(trigger.attributes.get("target", ""))
            await self.fire(target)
            fired.append(target)
            self._record(event, target)
        return fired

    async def fire(self, target: str) -> None:
        if target.startswith("dag:") and self.run_dag is not None:
            await self.run_dag(target.removeprefix("dag:"))
            return
        if target.startswith("node:") and self.run_node is not None:
            await self.run_node(target.removeprefix("node:"))
            return
        raise ConfigError(f"unsupported trigger target: {target}")

    def entity_changed(self, ref: str) -> str:
        return f"event:entity-changed:{ref}"

    def config_changed(self) -> str:
        return "event:config-changed"

    def schedule_event(self, time_value: str) -> str:
        return f"schedule:{time_value}"

    def node_output_event(self, name: str) -> str:
        return f"event:{name}"

    def _record(self, event: str, target: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.records.append({"event": event, "target": target, "produced_at": now, "consumed_at": now})
