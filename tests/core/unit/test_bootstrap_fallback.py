from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from edera_core.server import BOOTSTRAP_HOST, BOOTSTRAP_PORT_END, BOOTSTRAP_PORT_START, Server


@pytest.mark.asyncio
async def test_bootstrap_port_fallback(tmp_path: Path) -> None:
    config_dir = _minimal_config(tmp_path)
    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    blocker.bind((BOOTSTRAP_HOST, BOOTSTRAP_PORT_START))
    blocker.listen()

    daemon = Server(tmp_path / "data", "127.0.0.1:0", config_dir)
    try:
        await daemon.start()
        assert daemon.bootstrap_bound_port is not None
        assert BOOTSTRAP_PORT_START < daemon.bootstrap_bound_port <= BOOTSTRAP_PORT_END
    finally:
        await daemon.stop()
        blocker.close()


@pytest.mark.asyncio
async def test_bootstrap_status_file(tmp_path: Path) -> None:
    daemon = Server(tmp_path / "data", "127.0.0.1:0", _minimal_config(tmp_path))
    try:
        await daemon.start()
        payload = json.loads((tmp_path / "data" / "bootstrap.json").read_text(encoding="utf-8"))
    finally:
        await daemon.stop()

    assert payload == {"host": "127.0.0.1", "port": daemon.bootstrap_bound_port}


@pytest.mark.asyncio
async def test_bootstrap_port_exhaustion(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("edera_core.server._tcp_port_available", lambda _host, _port: False)
    daemon = Server(tmp_path / "data", "127.0.0.1:0", _minimal_config(tmp_path))

    with pytest.raises(RuntimeError, match="no available bootstrap port"):
        daemon._add_bootstrap_port()


def _minimal_config(tmp_path: Path) -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir(exist_ok=True)
    schema_dir = tmp_path / "schemas" / "entity-types"
    schema_dir.mkdir(parents=True, exist_ok=True)
    (schema_dir / "node.yaml").write_text(
        "display_name: Node\n"
        "business_id_field: name\n"
        "display_template: '{name}'\n"
        "schema:\n"
        "  type: object\n"
        "  required: [name]\n"
        "  properties:\n"
        "    name:\n"
        "      type: string\n",
        encoding="utf-8",
    )
    (schema_dir / "dag.yaml").write_text(
        "display_name: DAG\n"
        "business_id_field: name\n"
        "display_template: '{name}'\n"
        "schema:\n"
        "  type: object\n"
        "  required: [name]\n"
        "  properties:\n"
        "    name:\n"
        "      type: string\n",
        encoding="utf-8",
    )
    (config_dir / "entities.yaml").write_text("entities: []\n", encoding="utf-8")
    (config_dir / "entity-relations.yaml").write_text("relations: []\n", encoding="utf-8")
    (config_dir / "system.toml").write_text(
        f'database_url = "sqlite+aiosqlite:///{tmp_path / "test.db"}"\n',
        encoding="utf-8",
    )
    (config_dir / "dags").mkdir(exist_ok=True)
    (config_dir / "dags" / "default.yaml").write_text("name: default\nnodes: []\nedges: []\n", encoding="utf-8")
    (config_dir / "nodes").mkdir(exist_ok=True)
    (config_dir / "skills").mkdir(exist_ok=True)
    return config_dir
