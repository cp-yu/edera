from __future__ import annotations

from dataclasses import dataclass

from edera_core.config.schema import EntityConfig


@dataclass(frozen=True)
class EntityQueryResult:
    entity: EntityConfig
    from_cache: bool
    dag_run_id: str | None
