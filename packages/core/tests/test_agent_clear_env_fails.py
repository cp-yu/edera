from pathlib import Path

import pytest

from edera_core.grpc_client import GrpcClient


def test_agent_clear_env_fails_without_file_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    edera_dir = tmp_path / ".edera"
    edera_dir.mkdir()
    (edera_dir / "client.crt").write_text("human-cert", encoding="utf-8")
    (edera_dir / "client.key").write_text("human-key", encoding="utf-8")
    (edera_dir / "ca.crt").write_text("human-ca", encoding="utf-8")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.delenv("EDERA_CLIENT_CERT", raising=False)
    monkeypatch.delenv("EDERA_CLIENT_KEY", raising=False)
    monkeypatch.delenv("EDERA_CA_CERT", raising=False)
    monkeypatch.delenv("EDERA_DEV", raising=False)

    with pytest.raises(FileNotFoundError):
        GrpcClient("127.0.0.1:1")
