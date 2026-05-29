from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from edera_core.config.schema import DagNodeInstance
from edera_core.node.models import NodeOutput


@dataclass(frozen=True)
class DagGraph:
    name: str
    nodes: list[str]
    instances: dict[str, DagNodeInstance]
    edges: dict[str, list[str]]
    reverse_edges: dict[str, list[str]]
    fan_out_edges: set[tuple[str, str]] = field(default_factory=set)
    fan_in_edges: set[tuple[str, str]] = field(default_factory=set)
    optional_edges: set[tuple[str, str]] = field(default_factory=set)
    conditions: dict[tuple[str, str], str] = field(default_factory=dict)
    fan_in_modes: dict[tuple[str, str], str] = field(default_factory=dict)


@dataclass
class DagRunResult:
    run_id: str
    node_outputs: dict[str, NodeOutput]
    failures: dict[str, str]
    payload: Any = None
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.node_outputs) and not all(not output.ok for output in self.node_outputs.values())
