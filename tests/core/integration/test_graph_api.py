from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from edera_core.bootstrap import scan_extensions
from edera_core.storage import create_engine, init_db, session_factory, sqlite_url
from edera_core.pipeline import PipelineController
from edera_core.web.app import create_app


class FakeController(PipelineController):
    async def start(self, run_startup: bool = True) -> None:
        self.engine = create_engine(sqlite_url(self.config_dir / "web.db"))
        await init_db(self.engine)
        self.factory = session_factory(self.engine)
        self.scheduler.start()


def _copy_project_config(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    _copy_dir("config", root / "config")
    _copy_dir("schemas", root / "schemas")
    _copy_dir("extensions", root / "extensions")
    _copy_dir("prompts", root / "prompts")
    _copy_dir("skills", root / "skills")
    return root


def _copy_dir(source, target) -> None:
    from pathlib import Path

    source_path = Path(source)
    target.mkdir(parents=True)
    for path in source_path.rglob("*"):
        if "__pycache__" in path.parts:
            continue
        dest = target / path.relative_to(source_path)
        if path.is_dir():
            dest.mkdir()
        else:
            dest.write_text(path.read_text())


def _app(root):
    bootstrap = scan_extensions([root / "extensions"], root / "config")
    return create_app(
        root / "config",
        FakeController(root / "config"),
        handler_registry=bootstrap.handler_registry,
        run_startup=False,
    )


@pytest.mark.asyncio
async def test_handler_read_uses_registry_path(tmp_path) -> None:
    root = _copy_project_config(tmp_path)
    app = _app(root)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/graph/handlers/fetch-api")
    assert response.status_code == 200
    assert response.json()["code"] == (root / "extensions" / "api-fetcher" / "handler.py").read_text(
        encoding="utf-8"
    )


@pytest.mark.asyncio
async def test_handler_read_returns_404_for_missing_handler(tmp_path) -> None:
    root = _copy_project_config(tmp_path)
    app = _app(root)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/graph/handlers/missing-handler")
    assert response.status_code == 404
    assert response.json()["error"]["type"] == "not_found"


@pytest.mark.asyncio
async def test_handler_save_uses_registry_path(tmp_path) -> None:
    root = _copy_project_config(tmp_path)
    app = _app(root)
    code = "async def run(ctx):\n    return []\n"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.put("/api/graph/handlers/fetch-api", json={"code": code})
    assert response.status_code == 200
    assert (root / "extensions" / "api-fetcher" / "handler.py").read_text(encoding="utf-8") == code
    assert not (root / "extensions" / "fetch-api" / "handler.py").exists()


@pytest.mark.asyncio
async def test_graph_nodes_and_dags_return_200(tmp_path) -> None:
    root = _copy_project_config(tmp_path)
    app = _app(root)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        nodes = await client.get("/api/graph/nodes")
        dags = await client.get("/api/graph/dags")
    assert nodes.status_code == 200
    assert dags.status_code == 200
