from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from pydantic import BaseModel


class NodeInput(BaseModel):
    run_id: str
    payload: Any
    metadata: dict[str, Any] = {}


class NodeOutput(BaseModel):
    node_name: str
    ok: bool
    payload: Any = None
    metadata: dict[str, Any] = {}
    error: str | None = None


@dataclass
class HandlerContext:
    input: NodeInput
    params: dict[str, Any]
    node_name: str
    node_type: str
    run_id: str
    entity_store: EntityStoreProtocol
    storage: StorageProtocol | None = None
    runtime: RuntimeContextProtocol | None = None


class HandlerProtocol(Protocol):
    async def run(self, ctx: HandlerContext) -> Any: ...


class EntityStoreProtocol(Protocol):
    def query(self, type: str | None = None) -> list[Any]: ...

    def resolve(self, ref: str) -> Any: ...

    def related_refs(self, ref: str) -> list[str]: ...


class StorageProtocol(Protocol):
    def table(self, name: str) -> str: ...


class RuntimeContextProtocol(Protocol):
    def record_source_recovery(self, source_name: str, summary: dict[str, Any]) -> Awaitable[None]: ...


RuntimeSourceRecoveryRecorder = Callable[[str, str, str, dict[str, Any]], Awaitable[None]]


__all__ = [
    "EntityStoreProtocol",
    "HandlerContext",
    "HandlerProtocol",
    "NodeInput",
    "NodeOutput",
    "RuntimeContextProtocol",
    "RuntimeSourceRecoveryRecorder",
    "StorageProtocol",
]
