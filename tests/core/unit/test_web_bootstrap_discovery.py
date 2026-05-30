from __future__ import annotations

import json
from pathlib import Path

import pytest

from edera_core.web.__main__ import _bff_grpc_client


@pytest.mark.asyncio
async def test_edera_web_bootstrap_discovery(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[tuple[str | None, dict[str, object]]] = []

    class FakeClient:
        def __init__(self, address: str | None = None, **kwargs: object) -> None:
            calls.append((address, kwargs))

        async def init_client(self, common_name: str) -> dict[str, str]:
            assert common_name == "bff:web-console"
            return {"client_cert_pem": "cert", "client_key_pem": "key", "ca_cert_pem": "ca"}

        async def close(self) -> None:
            return None

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "bootstrap.json").write_text(json.dumps({"host": "127.0.0.1", "port": 9123}), encoding="utf-8")
    monkeypatch.setenv("EDERA_DATA_DIR", str(data_dir))
    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.delenv("EDERA_DEV", raising=False)
    monkeypatch.setattr("edera_core.web.__main__.GrpcClient", FakeClient)

    client = await _bff_grpc_client()

    assert isinstance(client, FakeClient)
    assert calls == [
        ("127.0.0.1:9123", {"force_insecure": True}),
        (
            "127.0.0.1:9090",
            {
                "client_cert_pem": "cert",
                "client_key_pem": "key",
                "ca_cert_pem": "ca",
            },
        ),
    ]


@pytest.mark.asyncio
async def test_edera_web_missing_status_fails_fast(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EDERA_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.delenv("EDERA_DEV", raising=False)

    with pytest.raises(RuntimeError, match="bootstrap status unavailable"):
        await _bff_grpc_client()


@pytest.mark.asyncio
async def test_edera_web_invalid_status_fails_fast(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "bootstrap.json").write_text(json.dumps({"host": "0.0.0.0", "port": "9091"}), encoding="utf-8")
    monkeypatch.setenv("EDERA_DATA_DIR", str(data_dir))
    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.delenv("EDERA_DEV", raising=False)

    with pytest.raises(RuntimeError, match="bootstrap status unavailable"):
        await _bff_grpc_client()
