from __future__ import annotations

import pytest

from edera_core.bootstrap import BootstrapResult
from edera_core.config.schema import AppConfig, EntitiesConfig, EntityRelationsConfig, RuntimeSettings, SystemConfig
from edera_core.hot_reload import HotReloader


@pytest.mark.asyncio
async def test_hot_reload_without_registry(tmp_path):
    called = []
    config = AppConfig(
        system=SystemConfig(),
        entity_types={},
        entities=EntitiesConfig(),
        entity_relations=EntityRelationsConfig(),
        runtime=RuntimeSettings(),
        nodes={},
        skills={},
        dags={},
    )

    async def callback(loaded_config, bootstrap):
        called.append((loaded_config, bootstrap))

    reloader = HotReloader(tmp_path / "config", [], callback, lambda: config, lambda: BootstrapResult([], {}, {}, {}))

    await reloader.reload_once()

    assert called == [(config, BootstrapResult([], {}, {}, {}))]
