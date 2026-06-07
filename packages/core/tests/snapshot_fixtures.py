from __future__ import annotations

from pathlib import Path

from edera_core.config.schema import DagConfig, EntityTypeConfig, NodeConfig
from edera_core.resolver import HandlerMeta, StaticHandlerResolver
from edera_core.snapshot import DagExecutionClosure
from edera_core.snapshot import DagExecutionSnapshot


def create_test_snapshot(
    nodes: dict[str, NodeConfig],
    handlers: dict[str, HandlerMeta] | None = None,
    entity_types: dict[str, EntityTypeConfig] | None = None,
    extension_table_names: dict[str, dict[str, str]] | None = None,
) -> DagExecutionSnapshot:
    return DagExecutionSnapshot(
        DagExecutionClosure("test", {"test": DagConfig(name="test", nodes=[], edges=[], ui={})}, nodes),
        dict(entity_types or {}),
        StaticHandlerResolver(handlers or {}),
        {key: dict(value) for key, value in (extension_table_names or {}).items()},
        {},
    )


def write_handler(path: Path, body: str = "return ctx.input.payload") -> HandlerMeta:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"async def run(ctx):\n    {body}\n", encoding="utf-8")
    return HandlerMeta(path)
