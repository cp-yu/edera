from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from edera_core.web.app import create_app


class _FakeClient:
    def __init__(self) -> None:
        self.installs: list[tuple[str, bool]] = []

    async def extension_install(self, name: str, overwrite: bool = False) -> dict[str, object]:
        self.installs.append((name, overwrite))
        return {"overwrite": overwrite, "data_warning": "warn"} if overwrite else {"handlers": 1, "entities": 0}

    async def close(self) -> None:
        return None


@pytest.fixture()
def web_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("EDERA_DEV", "1")
    monkeypatch.setenv("EDERA_WEB_TOKEN", "")
    client = _FakeClient()
    return TestClient(create_app(client))  # type: ignore[arg-type]


def test_install_overwrite_passes_flag(web_client: TestClient) -> None:
    fake: _FakeClient = web_client.app.state.grpc_client

    response = web_client.post("/api/extensions/demo/install", json={"overwrite": True})

    assert response.status_code == 200
    body = response.json()
    assert body["overwrite"] is True
    assert body["data_warning"] == "warn"
    assert fake.installs == [("demo", True)]


def test_install_default_no_overwrite(web_client: TestClient) -> None:
    fake: _FakeClient = web_client.app.state.grpc_client

    response = web_client.post("/api/extensions/demo/install", json={})

    assert response.status_code == 200
    assert fake.installs == [("demo", False)]
