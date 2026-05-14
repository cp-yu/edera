from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from pydantic import BaseModel


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


@dataclass(frozen=True)
class NodeContext:
    cycle_id: str
    instance_id: str


FunctionHandler = Callable[[NodeInput], Awaitable[Any]]
