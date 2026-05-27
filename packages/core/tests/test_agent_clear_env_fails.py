from pathlib import Path

import pytest

from stockimformation_core.grpc_client import RigGrpcClient


def test_agent_clear_env_fails_without_file_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    rig_dir = tmp_path / ".rig"
    rig_dir.mkdir()
    (rig_dir / "client.crt").write_text("human-cert", encoding="utf-8")
    (rig_dir / "client.key").write_text("human-key", encoding="utf-8")
    (rig_dir / "ca.crt").write_text("human-ca", encoding="utf-8")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.delenv("RIG_CLIENT_CERT", raising=False)
    monkeypatch.delenv("RIG_CLIENT_KEY", raising=False)
    monkeypatch.delenv("RIG_CA_CERT", raising=False)

    with pytest.raises(FileNotFoundError):
        RigGrpcClient("127.0.0.1:1")
