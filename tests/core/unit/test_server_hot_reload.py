from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from edera_core.server import Server


class _Controller:
    agent_certificate_issuer = None
    daemon_data_dir = None
    extensions_dirs: list[Path] = []

    async def emit(self, event: str, payload: object | None = None, *, source: str = "rpc", depth: int = 0) -> list[str]:
        return [event]


@pytest.mark.asyncio
async def test_lifecycle(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cancelled = asyncio.Event()

    class FakeHotReloader:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        async def watch(self) -> None:
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise

    monkeypatch.setattr("edera_core.server.HotReloader", FakeHotReloader)
    daemon = Server(tmp_path / "data", "127.0.0.1:0", tmp_path / "config", controller=_Controller())  # type: ignore[arg-type]

    await daemon.start()
    task = daemon._hot_reload_task
    assert task is not None
    assert not task.done()

    await asyncio.sleep(0)
    await daemon.stop()
    assert cancelled.is_set()
    assert daemon._hot_reload_task is None
