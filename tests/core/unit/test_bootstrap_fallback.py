from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from edera_core.bootstrap import BootstrapResult
from edera_core.registry import EntityTypeRegistry, HandlerRegistry
from edera_core.server import BOOTSTRAP_HOST, BOOTSTRAP_PORT_END, BOOTSTRAP_PORT_START, Server


class _Controller:
    agent_certificate_issuer = None
    daemon_data_dir = None

    async def load_bootstrap(self) -> BootstrapResult:
        return BootstrapResult(
            HandlerRegistry().seal(),
            EntityTypeRegistry(),
            [],
            {},
            {},
            {},
        )


@pytest.mark.asyncio
async def test_bootstrap_port_fallback(tmp_path: Path) -> None:
    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    blocker.bind((BOOTSTRAP_HOST, BOOTSTRAP_PORT_START))
    blocker.listen()

    daemon = Server(tmp_path / "data", "127.0.0.1:0", tmp_path / "config", controller=_Controller())  # type: ignore[arg-type]
    try:
        await daemon.start()
        assert daemon.bootstrap_bound_port is not None
        assert BOOTSTRAP_PORT_START < daemon.bootstrap_bound_port <= BOOTSTRAP_PORT_END
    finally:
        await daemon.stop()
        blocker.close()


@pytest.mark.asyncio
async def test_bootstrap_status_file(tmp_path: Path) -> None:
    daemon = Server(tmp_path / "data", "127.0.0.1:0", tmp_path / "config", controller=_Controller())  # type: ignore[arg-type]
    try:
        await daemon.start()
        payload = json.loads((tmp_path / "data" / "bootstrap.json").read_text(encoding="utf-8"))
    finally:
        await daemon.stop()

    assert payload == {"host": "127.0.0.1", "port": daemon.bootstrap_bound_port}


def test_bootstrap_port_exhaustion(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("edera_core.server._tcp_port_available", lambda _host, _port: False)
    daemon = Server(tmp_path / "data", "127.0.0.1:0", tmp_path / "config", controller=_Controller())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="no available bootstrap port"):
        daemon._add_bootstrap_port()
