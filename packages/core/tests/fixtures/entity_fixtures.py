from __future__ import annotations

from edera_core.config.schema import EntityTypeConfig
from edera_core.storage.repository import create_ordinary_entity


async def seed_entity_records(session, entity_types: dict[str, EntityTypeConfig]) -> None:
    if "stock" in entity_types:
        await create_ordinary_entity(session, "stock", "stock:test", {"code": "TEST"}, entity_types)
    if "rss-source" in entity_types:
        await create_ordinary_entity(session, "rss-source", "source:test", {"name": "rss"}, entity_types)
