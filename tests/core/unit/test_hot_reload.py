from __future__ import annotations

import pytest

from edera_core.hot_reload import HotReloader


@pytest.mark.asyncio
async def test_emit_config_changed(tmp_path) -> None:
    events: list[str] = []

    async def callback(_config, _bootstrap) -> None:
        return None

    async def emit(event: str) -> None:
        events.append(event)

    _write_config(tmp_path)
    reloader = HotReloader(tmp_path, [], callback, emit=emit)

    await reloader.reload_once()

    assert events == ["event:config-changed"]


@pytest.mark.asyncio
async def test_failure_isolation(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
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


def _write_config(root) -> None:
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
    (root / "system.toml").write_text("database_url = \"sqlite+aiosqlite:///test.db\"\n", encoding="utf-8")
    (root / "dags" / "default.yaml").write_text("name: default\nnodes: []\nedges: []\n", encoding="utf-8")
