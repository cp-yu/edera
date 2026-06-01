from __future__ import annotations

import json
from pathlib import Path

import pytest

from edera_core.config.entities import EntityStore
from edera_core.config.loader import load_app_config
from edera_core.dag_controller import DagController, _ensure_default_cron_triggers
from edera_core.event_service import _EventService
from edera_core.hot_reload import HotReloader
from edera_core.proto import edera_pb2 as pb2


class _Daemon:
    pb2 = pb2

    def __init__(self) -> None:
        self.controller = _Controller()


class _Controller:
    async def emit(self, event: str, payload: object | None, *, source: str, depth: int) -> list[str]:
        assert event == "event:price-drop"
        assert payload == {"symbol": "TEST"}
        assert source == "test"
        assert depth == 1
        return ["dag:default"]


@pytest.mark.asyncio
async def test_emit_rpc() -> None:
    response = await _EventService(_Daemon()).Emit(
        pb2.EmitRequest(
            event="event:price-drop",
            payload_json='{"symbol":"TEST"}',
            source="test",
            depth=1,
        ),
        object(),
    )

    assert json.loads(response.json) == {"event": "event:price-drop", "fired": ["dag:default"]}


@pytest.mark.asyncio
async def test_no_apscheduler(tmp_path: Path) -> None:
    _write_config(tmp_path)
    ctrl = DagController(tmp_path)
    await ctrl.start(run_startup=False)
    try:
        assert ctrl.scheduler.get_jobs() == []
    finally:
        await ctrl.shutdown()


@pytest.mark.asyncio
async def test_config_changed_rescans_cron_tokens(tmp_path: Path) -> None:
    _write_config(tmp_path)
    ctrl = DagController(tmp_path)

    (tmp_path / "triggers").mkdir()
    trigger_path = tmp_path / "triggers" / "hourly.yaml"
    trigger_path.write_text(
        "id: hourly\n"
        "type: trigger\n"
        "attributes:\n"
        "  name: hourly\n"
        "  wait_for: 'cron:\"0 * * * *\"'\n"
        "  target: dag:default\n"
        "  enabled: true\n",
        encoding="utf-8",
    )

    await ctrl.emit("event:bootstrap")

    assert ctrl.cron_emitter is not None
    assert ctrl.cron_emitter.cron_tokens() == {'cron:"0 * * * *"'}

    trigger_path.write_text(
        "id: hourly\n"
        "type: trigger\n"
        "attributes:\n"
        "  name: hourly\n"
        "  wait_for: 'cron:\"15 * * * *\"'\n"
        "  target: dag:default\n"
        "  enabled: true\n",
        encoding="utf-8",
    )
    await ctrl.emit("event:config-changed")

    assert ctrl.cron_emitter is not None
    assert ctrl.cron_emitter.cron_tokens() == {'cron:"15 * * * *"'}

    trigger_path.unlink()
    await ctrl.emit("event:config-changed")

    assert ctrl.cron_emitter is not None
    assert ctrl.cron_emitter.cron_tokens() == set()


@pytest.mark.asyncio
async def test_failed_config_changed_reload_preserves_cron_registry(tmp_path: Path) -> None:
    _write_config(tmp_path)
    ctrl = DagController(tmp_path)

    (tmp_path / "triggers").mkdir()
    trigger_path = tmp_path / "triggers" / "hourly.yaml"
    trigger_path.write_text(
        "id: hourly\n"
        "type: trigger\n"
        "attributes:\n"
        "  name: hourly\n"
        "  wait_for: 'cron:\"0 * * * *\"'\n"
        "  target: dag:default\n"
        "  enabled: true\n",
        encoding="utf-8",
    )
    await ctrl.emit("event:bootstrap")

    assert ctrl.cron_emitter is not None
    assert ctrl.cron_emitter.cron_tokens() == {'cron:"0 * * * *"'}

    trigger_path.write_text(
        "id: hourly\n"
        "type: trigger\n"
        "attributes:\n"
        "  name: hourly\n"
        "  wait_for: 'cron:\"15 * * * *\"'\n"
        "  target: dag:default\n"
        "  enabled: true\n",
        encoding="utf-8",
    )

    async def fail_reload(_config, _bootstrap) -> None:
        raise RuntimeError("reload failed")

    async def emit_config_changed(event: str) -> object:
        return await ctrl.emit(event, source="hot-reload")

    reloader = HotReloader(
        tmp_path,
        [],
        fail_reload,
        config_loader=lambda: load_app_config(tmp_path),
        emit=emit_config_changed,
    )

    with pytest.raises(RuntimeError, match="reload failed"):
        await reloader.reload_once()

    assert ctrl.cron_emitter is not None
    assert ctrl.cron_emitter.cron_tokens() == {'cron:"0 * * * *"'}


def test_migration_trigger_entity_generated(tmp_path: Path) -> None:
    _write_config(tmp_path)
    config = load_app_config(tmp_path)
    store = EntityStore(
        config.entities,
        config.entity_types,
        config.entity_relations,
        tmp_path / "entities.yaml",
    )

    _ensure_default_cron_triggers(config, store)

    assert (tmp_path / "triggers" / "default-default-cron.yaml").exists()
    assert (tmp_path / "triggers" / "realtime-default-cron.yaml").exists()
    assert 'cron:"*/30 * * * *"' in (tmp_path / "triggers" / "default-default-cron.yaml").read_text(encoding="utf-8")


def _write_config(root: Path) -> None:
    (root / "dags").mkdir()
    (root / "nodes").mkdir()
    (root / "skills").mkdir()
    (root.parent / "schemas" / "entity-types").mkdir(parents=True, exist_ok=True)
    (root.parent / "schemas" / "entity-types" / "trigger.yaml").write_text(
        "display_name: Trigger\n"
        "business_id_field: name\n"
        "display_template: '{name}'\n"
        "storage_tier: filesystem\n"
        "schema:\n"
        "  type: object\n"
        "  required: [name, wait_for, target]\n"
        "  properties:\n"
        "    name: {type: string}\n"
        "    wait_for: {type: string}\n"
        "    target: {type: string}\n"
        "    enabled: {type: boolean}\n",
        encoding="utf-8",
    )
    (root / "entities.yaml").write_text("entities: []\n", encoding="utf-8")
    (root / "entity-relations.yaml").write_text("relations: []\n", encoding="utf-8")
    (root / "system.toml").write_text(
        f'database_url = "sqlite+aiosqlite:///{root / "test.db"}"\n',
        encoding="utf-8",
    )
    (root / "dags" / "default.yaml").write_text("name: default\nnodes: []\nedges: []\n", encoding="utf-8")
    (root / "dags" / "realtime.yaml").write_text("name: realtime\nnodes: []\nedges: []\n", encoding="utf-8")
