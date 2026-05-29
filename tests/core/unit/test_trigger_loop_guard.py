from __future__ import annotations

import pytest

from edera_core.config.entities import EntityStore
from edera_core.config.schema import EntitiesConfig, EntityRelationsConfig
from edera_core.errors import ConfigError
from edera_core.trigger import TriggerExecutor


@pytest.mark.asyncio
async def test_depth_limit_rejects_emit() -> None:
    executor = TriggerExecutor(
        EntityStore(EntitiesConfig(), {}, EntityRelationsConfig()),
        max_depth=1,
    )

    with pytest.raises(ConfigError):
        await executor.emit("event:loop", depth=1)
