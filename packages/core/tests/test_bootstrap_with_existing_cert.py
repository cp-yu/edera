from pathlib import Path

import pytest

from edera_core.cli import main


def test_client_init_bootstraps_with_existing_cert(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class FakeClient:
        def __init__(
            self,
            address: str | None = None,
            data_dir: Path | None = None,
            allow_insecure: bool = False,
            force_insecure: bool = False,
        ) -> None:
            assert address == "localhost:9090"
            assert not allow_insecure
            assert force_insecure

        async def init_client(self, common_name: str) -> dict[str, str]:
            assert common_name == "human:default"
            return {"client_cert_pem": "new-cert", "client_key_pem": "new-key", "ca_cert_pem": "new-ca"}

        async def close(self) -> None:
            return None

    edera_dir = tmp_path / ".edera"
    edera_dir.mkdir()
    (edera_dir / "client.crt").write_text("old-cert", encoding="utf-8")
    (edera_dir / "client.key").write_text("old-key", encoding="utf-8")
    (edera_dir / "ca.crt").write_text("old-ca", encoding="utf-8")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)
    monkeypatch.setattr("sys.argv", ["edera", "client", "init", "--server", "localhost:9090"])

    main()

    assert (edera_dir / "client.crt").read_text(encoding="utf-8") == "new-cert"
