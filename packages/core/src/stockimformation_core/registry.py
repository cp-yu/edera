from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Iterator, Mapping

from stockimformation_core.config.schema import EntityTypeConfig
from stockimformation_core.manifest import NodeTypeDescriptor


@dataclass(frozen=True)
class HandlerEntry:
    name: str
    path: Path
    function: str = "run"
    descriptor: NodeTypeDescriptor | None = None


class HandlerRegistry(Mapping[str, HandlerEntry]):
    def __init__(self, entries: dict[str, HandlerEntry] | None = None, sealed: bool = False) -> None:
        self._entries = dict(entries or {})
        self._sealed = sealed

    def register(
        self,
        name: str,
        path: str | Path,
        function: str = "run",
        descriptor: NodeTypeDescriptor | None = None,
    ) -> None:
        if self._sealed:
            raise RuntimeError("handler registry is sealed")
        handler_path = Path(path)
        current = self._entries.get(name)
        if current is not None and current.path != handler_path:
            raise ValueError(f"duplicate handler: {name} ({current.path} vs {handler_path})")
        self._entries[name] = HandlerEntry(name, handler_path, function, descriptor)

    def seal(self) -> HandlerRegistry:
        return HandlerRegistry(self._entries, sealed=True)

    def __getitem__(self, key: str) -> HandlerEntry:
        return self._entries[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._entries)

    def __len__(self) -> int:
        return len(self._entries)


class EntityTypeRegistry(Mapping[str, EntityTypeConfig]):
    def __init__(self, items: dict[str, EntityTypeConfig] | None = None) -> None:
        self._items = MappingProxyType(dict(items or {}))

    def __getitem__(self, key: str) -> EntityTypeConfig:
        return self._items[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def as_dict(self) -> dict[str, EntityTypeConfig]:
        return dict(self._items)
