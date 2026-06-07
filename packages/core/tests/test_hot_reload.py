from __future__ import annotations

import pytest

from edera_core.bootstrap import BootstrapResult
from edera_core.config.schema import AppConfig, EntitiesConfig, EntityRelationsConfig, RuntimeSettings, SystemConfig
from edera_core.dag_controller import DagController, RuntimeControlSnapshot
from edera_core.hot_reload import HotReloader
from edera_core.storage import create_engine, init_db


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


@pytest.mark.asyncio
async def test_control_snapshot_commit_failure_preserves_old_snapshot(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'edera.db'}")
    await init_db(engine)
    controller = DagController(tmp_path / "config")
    controller.engine = engine
    old_config = _config()
    old_snapshot = RuntimeControlSnapshot(SystemConfig(), RuntimeSettings(), None, None, generation=7)
    controller._runtime_config = old_config
    controller._snapshot = old_snapshot
    controller._snapshot_generation = 7

    async def fail_create_tables(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("edera_core.dag_controller.create_extension_tables", fail_create_tables)

    try:
        with pytest.raises(RuntimeError, match="boom"):
            await controller.install_snapshot(_config(), BootstrapResult([], {}, {}, {}))
    finally:
        await engine.dispose()

    assert controller.runtime_snapshot() is old_snapshot
    assert controller.runtime_config() is old_config
    assert controller.runtime_snapshot().generation == 7


def _config() -> AppConfig:
    return AppConfig(
        system=SystemConfig(),
        entity_types={},
        entities=EntitiesConfig(),
        entity_relations=EntityRelationsConfig(),
        runtime=RuntimeSettings(),
        nodes={},
        skills={},
        dags={},
    )
