from __future__ import annotations

from dataclasses import dataclass

from edera_core.config.schema import DagConfig, EntityTypeConfig, NodeConfig
from edera_core.resolver import DatabaseHandlerResolver


@dataclass(frozen=True)
class DagExecutionSnapshot:
    dag_config: DagConfig
    node_configs: dict[str, NodeConfig]
    entity_types: dict[str, EntityTypeConfig]
    handler_resolver: DatabaseHandlerResolver

    @classmethod
    async def create(cls, dag_config: DagConfig, node_configs: dict[str, NodeConfig], entity_types: dict[str, EntityTypeConfig], session, handlers_dir) -> DagExecutionSnapshot:
        return cls(
            dag_config,
            dict(node_configs),
            dict(entity_types),
            await DatabaseHandlerResolver.snapshot(session, handlers_dir),
        )
