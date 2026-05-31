from __future__ import annotations

from pathlib import Path

import pytest

from edera_core.bootstrap import scan_extensions
from edera_core.config.loader import load_app_config
from edera_core.dag.models import DagGraph
from edera_core.dag_controller import DagController
from edera_core.hot_reload import HotReloader


@pytest.mark.asyncio
async def test_snapshot_commit_success(tmp_path: Path) -> None:
    _write_config(tmp_path)
    extensions = tmp_path.parent / "extensions"
    controller = DagController(tmp_path, extensions_dirs=[extensions])
    await controller.start(run_startup=False)
    old_snapshot = controller.runtime_snapshot()
    _write_extension(extensions, "new-handler")

    snapshot = await controller.install_snapshot(
        load_app_config(tmp_path),
        scan_extensions([extensions], tmp_path),
    )

    assert controller.runtime_snapshot() is snapshot
    assert snapshot is not old_snapshot
    assert "new-handler" in snapshot.bootstrap.handler_registry
    assert "new-handler" in controller.runtime_snapshot().bootstrap.handler_registry
    assert snapshot.trigger_executor is controller.trigger_executor
    assert snapshot.cron_emitter is controller.cron_emitter
    await controller.shutdown()


@pytest.mark.asyncio
async def test_snapshot_commit_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_config(tmp_path)
    extensions = tmp_path.parent / "extensions"
    controller = DagController(tmp_path, extensions_dirs=[extensions])
    await controller.start(run_startup=False)
    old_snapshot = controller.runtime_snapshot()
    _write_extension(extensions, "failed-handler")

    async def fail_create_extension_tables(*_args, **_kwargs) -> None:
        raise RuntimeError("table failure")

    monkeypatch.setattr("edera_core.dag_controller.create_extension_tables", fail_create_extension_tables)
    with pytest.raises(RuntimeError, match="table failure"):
        await controller.install_snapshot(load_app_config(tmp_path), scan_extensions([extensions], tmp_path))

    assert controller.runtime_snapshot() is old_snapshot
    assert "failed-handler" not in controller.runtime_snapshot().bootstrap.handler_registry
    await controller.shutdown()


@pytest.mark.asyncio
async def test_snapshot_commit_serialized(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_config(tmp_path)
    extensions = tmp_path.parent / "extensions"
    controller = DagController(tmp_path, extensions_dirs=[extensions])
    await controller.start(run_startup=False)
    _write_extension(extensions, "serial-handler")
    candidate = load_app_config(tmp_path)
    bootstrap = scan_extensions([extensions], tmp_path)
    active = 0
    max_active = 0

    async def tracked_create_extension_tables(*_args, **_kwargs) -> None:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        try:
            await __import__("asyncio").sleep(0)
        finally:
            active -= 1

    monkeypatch.setattr("edera_core.dag_controller.create_extension_tables", tracked_create_extension_tables)
    await __import__("asyncio").gather(
        controller.install_snapshot(candidate.model_copy(deep=True), bootstrap),
        controller.install_snapshot(candidate.model_copy(deep=True), bootstrap),
    )

    assert max_active == 1
    assert "serial-handler" in controller.runtime_snapshot().bootstrap.handler_registry
    await controller.shutdown()


@pytest.mark.asyncio
async def test_active_run_snapshot_isolation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_config(tmp_path)
    extensions = tmp_path.parent / "extensions"
    controller = DagController(tmp_path, extensions_dirs=[extensions])
    await controller.start(run_startup=False)
    old_snapshot = controller.runtime_snapshot()
    started = __import__("asyncio").Event()
    release = __import__("asyncio").Event()
    captured = []

    async def fake_run(*_args, snapshot=None, **_kwargs):
        captured.append(snapshot)
        started.set()
        await release.wait()

    monkeypatch.setattr(controller, "_run", fake_run)
    await controller.start_run("manual")
    await started.wait()
    _write_dag(tmp_path, nodes=["changed"])
    await controller.install_snapshot(load_app_config(tmp_path), scan_extensions([extensions], tmp_path))

    assert captured == [old_snapshot]
    assert controller.runtime_snapshot() is not old_snapshot
    release.set()
    await __import__("asyncio").sleep(0)
    await controller.shutdown()


@pytest.mark.asyncio
async def test_new_run_uses_committed_snapshot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_config(tmp_path)
    extensions = tmp_path.parent / "extensions"
    controller = DagController(tmp_path, extensions_dirs=[extensions])
    await controller.start(run_startup=False)
    captured: list[list[str]] = []

    async def fake_run(*_args, snapshot=None, **_kwargs):
        captured.append([node.type for node in snapshot.config.dags["default"].nodes])

    monkeypatch.setattr(controller, "_run", fake_run)
    await controller.run_now("manual")
    _write_dag(tmp_path, nodes=["changed"])
    await controller.install_snapshot(load_app_config(tmp_path), scan_extensions([extensions], tmp_path))
    await controller.run_now("manual")

    assert captured == [[], ["changed"]]
    await controller.shutdown()


@pytest.mark.asyncio
async def test_handler_reload_new_executor_only(tmp_path: Path) -> None:
    _write_config(tmp_path)
    extensions = tmp_path.parent / "extensions"
    _write_dag(tmp_path, nodes=["first-handler"])
    _write_extension(extensions, "first-handler")
    controller = DagController(tmp_path, extensions_dirs=[extensions])
    await controller.start(run_startup=False)
    graph = DagGraph("default", [], {}, {}, {})
    old_executor = controller._build_run_executor(
        controller.runtime_snapshot(),
        graph,
    )
    old_executor._modules["first-handler"] = object()  # type: ignore[assignment]
    _write_dag(tmp_path, nodes=["second-handler"])
    _write_extension(extensions, "second-handler")

    await controller.install_snapshot(load_app_config(tmp_path), scan_extensions([extensions], tmp_path))
    new_executor = controller._build_run_executor(
        controller.runtime_snapshot(),
        graph,
    )

    assert old_executor._modules == {"first-handler": old_executor._modules["first-handler"]}
    assert new_executor._modules == {}
    assert "second-handler" in new_executor.handler_registry
    await controller.shutdown()


@pytest.mark.asyncio
async def test_handler_manifest_deletion_rebuilds_registry(tmp_path: Path) -> None:
    _write_config(tmp_path)
    extensions = tmp_path.parent / "extensions"
    _write_extension(extensions, "removed-handler")
    controller = DagController(tmp_path, extensions_dirs=[extensions])
    await controller.start(run_startup=False)
    assert "removed-handler" in controller.runtime_snapshot().bootstrap.handler_registry

    (extensions / "removed-handler" / "manifest.yaml").write_text(
        'name: removed-handler\nversion: "1.0"\nhandlers: []\n',
        encoding="utf-8",
    )

    await controller.install_snapshot(load_app_config(tmp_path), scan_extensions([extensions], tmp_path))

    assert "removed-handler" not in controller.runtime_snapshot().bootstrap.handler_registry
    await controller.shutdown()


@pytest.mark.asyncio
async def test_config_parse_failure_preserves_snapshot(tmp_path: Path) -> None:
    _write_config(tmp_path)
    extensions = tmp_path.parent / "extensions"
    controller = DagController(tmp_path, extensions_dirs=[extensions])
    await controller.start(run_startup=False)
    old_snapshot = controller.runtime_snapshot()
    emitted: list[str] = []

    async def emit(event: str) -> None:
        emitted.append(event)

    (tmp_path / "nodes" / "broken.yaml").write_text("name: broken\ntype: function\n", encoding="utf-8")

    with pytest.raises(Exception):
        await HotReloader(tmp_path, [extensions], controller.install_snapshot, emit=emit).reload_once()

    assert controller.runtime_snapshot() is old_snapshot
    assert emitted == []
    await controller.shutdown()


@pytest.mark.asyncio
async def test_config_changed_uses_snapshot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_config(tmp_path)
    _write_trigger_schema(tmp_path)
    _write_triggers(tmp_path, ['cron:"0 9 * * *"'])
    controller = DagController(tmp_path, extensions_dirs=[tmp_path.parent / "extensions"])
    await controller.start(run_startup=False)
    called = False

    async def fail_reload_triggers() -> None:
        nonlocal called
        called = True
        raise AssertionError("emit reloaded triggers from disk")

    monkeypatch.setattr(controller, "_reload_triggers", fail_reload_triggers)
    await controller.emit("event:config-changed", source="hot-reload")

    assert called is False
    assert controller.trigger_executor is controller.runtime_snapshot().trigger_executor
    await controller.shutdown()


@pytest.mark.asyncio
async def test_cron_registry_update_and_preservation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_config(tmp_path)
    _write_trigger_schema(tmp_path)
    _write_triggers(tmp_path, ['cron:"0 9 * * *"'])
    extensions = tmp_path.parent / "extensions"
    controller = DagController(tmp_path, extensions_dirs=[extensions])
    await controller.start(run_startup=False)
    old_emitter = controller.cron_emitter
    assert old_emitter is not None
    assert old_emitter.cron_tokens() == {'cron:"0 9 * * *"', 'cron:"*/30 * * * *"'}

    _write_triggers(tmp_path, ['cron:"0 10 * * *"'])
    await controller.install_snapshot(load_app_config(tmp_path), scan_extensions([extensions], tmp_path))
    updated_emitter = controller.cron_emitter
    assert updated_emitter is not None
    assert updated_emitter is not old_emitter
    assert updated_emitter.cron_tokens() == {'cron:"0 10 * * *"', 'cron:"*/30 * * * *"'}

    async def fail_create_extension_tables(*_args, **_kwargs) -> None:
        raise RuntimeError("table failure")

    _write_triggers(tmp_path, ['cron:"0 11 * * *"'])
    monkeypatch.setattr("edera_core.dag_controller.create_extension_tables", fail_create_extension_tables)
    with pytest.raises(RuntimeError, match="table failure"):
        await controller.install_snapshot(load_app_config(tmp_path), scan_extensions([extensions], tmp_path))

    assert controller.cron_emitter is updated_emitter
    assert controller.cron_emitter.cron_tokens() == {'cron:"0 10 * * *"', 'cron:"*/30 * * * *"'}
    await controller.shutdown()


@pytest.mark.asyncio
async def test_emit_config_changed(tmp_path: Path) -> None:
    calls: list[str] = []

    async def callback(_config, _bootstrap) -> None:
        calls.append("commit")

    async def emit(event: str) -> None:
        calls.append(f"emit:{event}")

    _write_config(tmp_path)
    reloader = HotReloader(tmp_path, [], callback, emit=emit)

    await reloader.reload_once()

    assert calls == ["commit", "emit:event:config-changed"]


@pytest.mark.asyncio
async def test_failure_isolation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    events: list[str] = []
    attempts = 0

    async def fake_awatch(*_roots, **_kwargs):
        yield {("modified", str(tmp_path / "bad"))}
        yield {("modified", str(tmp_path / "good"))}

    async def callback(_config, _bootstrap) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ValueError("bad config")

    async def emit(event: str) -> None:
        events.append(event)

    _write_config(tmp_path)
    monkeypatch.setitem(__import__("sys").modules, "watchfiles", type("Watchfiles", (), {"awatch": fake_awatch}))

    await HotReloader(tmp_path, [], callback, emit=emit).watch()

    assert attempts == 2
    assert events == ["event:config-changed"]


def _write_config(root: Path) -> None:
    (root / "dags").mkdir()
    (root / "nodes").mkdir()
    (root / "skills").mkdir()
    (root.parent / "schemas" / "entity-types").mkdir(parents=True, exist_ok=True)
    (root.parent / "schemas" / "entity-types" / "stock.yaml").write_text(
        "display_name: Stock\nbusiness_id_field: code\ndisplay_template: '{code}'\nschema: {}\n",
        encoding="utf-8",
    )
    (root / "entities.yaml").write_text("entities: []\n", encoding="utf-8")
    (root / "entity-relations.yaml").write_text("relations: []\n", encoding="utf-8")
    (root / "system.toml").write_text(f'database_url = "sqlite+aiosqlite:///{root / "test.db"}"\n', encoding="utf-8")
    (root / "dags" / "default.yaml").write_text("name: default\nnodes: []\nedges: []\n", encoding="utf-8")


def _write_trigger_schema(root: Path) -> None:
    (root.parent / "schemas" / "entity-types" / "trigger.yaml").write_text(
        "display_name: Trigger\n"
        "business_id_field: name\n"
        "display_template: '{name}'\n"
        "schema:\n"
        "  type: object\n"
        "  required: [name, wait_for, target]\n"
        "  properties:\n"
        "    name: {type: string}\n"
        "    wait_for: {type: string}\n"
        "    target: {type: string}\n",
        encoding="utf-8",
    )


def _write_triggers(root: Path, wait_for: list[str]) -> None:
    entries = "\n".join(
        f"  - id: trigger-{index}\n    type: trigger\n    attributes:\n      name: trigger-{index}\n      wait_for: '{value}'\n      target: dag:default"
        for index, value in enumerate(wait_for)
    )
    (root / "entities.yaml").write_text(f"entities:\n{entries}\n", encoding="utf-8")


def _write_dag(root: Path, nodes: list[str]) -> None:
    if not nodes:
        (root / "dags" / "default.yaml").write_text("name: default\nnodes: []\nedges: []\n", encoding="utf-8")
        return
    entries = "\n".join(f"  - id: {name}\n    type: {name}\n    config: {{}}" for name in nodes)
    (root / "dags" / "default.yaml").write_text(f"name: default\nnodes:\n{entries}\nedges: []\n", encoding="utf-8")


def _write_extension(root: Path, handler_name: str) -> None:
    extension = root / handler_name
    extension.mkdir(parents=True)
    (extension / "handler.py").write_text("def run(ctx):\n    return {}\n", encoding="utf-8")
    (extension / "manifest.yaml").write_text(
        f"""name: {handler_name}
version: "1.0"
handlers:
  - name: {handler_name}
    role: processor
    input_type: Any
    output_type: Any
    entry: handler.py
""",
        encoding="utf-8",
    )
