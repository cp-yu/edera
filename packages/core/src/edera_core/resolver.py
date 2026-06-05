from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from edera_core.storage.repository import list_enabled_extensions


class HandlerNotFoundError(KeyError):
    pass


@dataclass(frozen=True)
class HandlerMeta:
    path: Path
    function: str = "run"
    extension_name: str | None = None


class DatabaseHandlerResolver:
    def __init__(self, session, handlers_dir: Path = Path("handlers"), entries: dict[str, HandlerMeta] | None = None) -> None:
        self.session = session
        self.handlers_dir = handlers_dir
        self._entries = dict(entries) if entries is not None else None

    @classmethod
    async def snapshot(cls, session, handlers_dir: Path = Path("handlers")) -> DatabaseHandlerResolver:
        entries = {}
        resolver = cls(session, handlers_dir)
        for record in await list_enabled_extensions(session):
            for handler in _handlers(record.manifest_data):
                name = handler.get("name")
                if isinstance(name, str) and name:
                    entries[name] = resolver._meta(record.name, handler)
        return cls(session, handlers_dir, entries)

    async def get(self, handler_name: str) -> HandlerMeta:
        if self._entries is not None:
            try:
                return self._entries[handler_name]
            except KeyError as exc:
                raise HandlerNotFoundError(handler_name) from exc
        for record in await list_enabled_extensions(self.session):
            manifest = record.manifest_data
            for handler in _handlers(manifest):
                if handler.get("name") == handler_name:
                    return self._meta(record.name, handler)
        raise HandlerNotFoundError(handler_name)

    def _meta(self, extension_name: str, handler: dict[str, object]) -> HandlerMeta:
        entry = handler.get("entry")
        if not isinstance(entry, str) or not entry:
            raise HandlerNotFoundError(handler.get("name"))
        function = handler.get("function")
        return HandlerMeta(
            self.handlers_dir / extension_name / entry,
            function if isinstance(function, str) and function else "run",
            extension_name,
        )


class StaticHandlerResolver:
    def __init__(self, entries: dict[str, HandlerMeta]) -> None:
        self._entries = dict(entries)

    async def get(self, handler_name: str) -> HandlerMeta:
        try:
            return self._entries[handler_name]
        except KeyError as exc:
            raise HandlerNotFoundError(handler_name) from exc


def _handlers(manifest: dict[str, object]) -> list[dict[str, object]]:
    handlers = manifest.get("handlers")
    return [item for item in handlers if isinstance(item, dict)] if isinstance(handlers, list) else []
