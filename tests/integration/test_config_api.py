import pytest
import yaml
from httpx import ASGITransport, AsyncClient

from stockimformation.models import create_engine, init_db, session_factory, sqlite_url
from stockimformation.pipeline import PipelineController
from stockimformation.web.app import create_app


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
    _copy_dir("handlers", root / "handlers")
    _copy_dir("prompts", root / "prompts")
    _copy_dir("skills", root / "skills")
    _copy_dir("skill_handlers", root / "skill_handlers")
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


@pytest.mark.asyncio
async def test_get_entities(tmp_path) -> None:
    root = _copy_project_config(tmp_path)
    app = create_app(root / "config", FakeController(root / "config"), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            response = await client.get("/api/config/entities")
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 200
    payload = yaml.safe_load(response.json()["content"])
    assert payload["entities"]


@pytest.mark.asyncio
async def test_get_entities_missing_file(tmp_path) -> None:
    root = _copy_project_config(tmp_path)
    (root / "config" / "entities.yaml").unlink()
    app = create_app(root / "config", FakeController(root / "config"), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/config/entities")
    assert response.status_code == 404
    assert response.json()["error"]["type"] == "not_found"


@pytest.mark.asyncio
async def test_save_entities(tmp_path) -> None:
    root = _copy_project_config(tmp_path)
    app = create_app(root / "config", FakeController(root / "config"), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            payload = yaml.safe_load((await client.get("/api/config/entities")).json()["content"])
            response = await client.post("/api/config/entities", json={"entities": payload["entities"]})
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_relations(tmp_path) -> None:
    root = _copy_project_config(tmp_path)
    app = create_app(root / "config", FakeController(root / "config"), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            response = await client.get("/api/config/entity-relations")
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 200
    payload = yaml.safe_load(response.json()["content"])
    assert payload["relations"]


@pytest.mark.asyncio
async def test_get_relations_missing_file(tmp_path) -> None:
    root = _copy_project_config(tmp_path)
    (root / "config" / "entity-relations.yaml").unlink()
    app = create_app(root / "config", FakeController(root / "config"), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/config/entity-relations")
    assert response.status_code == 404
    assert response.json()["error"]["type"] == "not_found"


@pytest.mark.asyncio
async def test_save_relations(tmp_path) -> None:
    root = _copy_project_config(tmp_path)
    app = create_app(root / "config", FakeController(root / "config"), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            payload = yaml.safe_load((await client.get("/api/config/entity-relations")).json()["content"])
            response = await client.post("/api/config/entity-relations", json={"relations": payload["relations"]})
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_query_entity_relations(tmp_path) -> None:
    root = _copy_project_config(tmp_path)
    app = create_app(root / "config", FakeController(root / "config"), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            response = await client.get("/api/entity-relations?entity=stock:00700.HK&type=uses-source")
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 200
    payload = response.json()
    assert payload["relations"]
    assert {entity["ref"] for entity in payload["entities"]}


@pytest.mark.asyncio
async def test_query_entity_relations_matches_uuid_refs(tmp_path) -> None:
    root = _copy_project_config(tmp_path)
    relations_path = root / "config" / "entity-relations.yaml"
    payload = yaml.safe_load(relations_path.read_text())
    payload["relations"][0]["entities"][0] = "stock-00700-hk"
    relations_path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False))
    app = create_app(root / "config", FakeController(root / "config"), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            response = await client.get("/api/entity-relations?entity=stock:00700.HK&type=uses-source")
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 200
    assert response.json()["relations"][0]["entities"][0] == "stock:00700.HK"


@pytest.mark.asyncio
async def test_portfolio_deprecated(tmp_path) -> None:
    root = _copy_project_config(tmp_path)
    app = create_app(root / "config", FakeController(root / "config"), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            response = await client.get("/api/config/portfolio")
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 404
