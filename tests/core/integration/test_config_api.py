import pytest
import yaml
from httpx import ASGITransport, AsyncClient

from stockimformation_core.storage import create_engine, init_db, session_factory, sqlite_url
from stockimformation_core.pipeline import PipelineController
from stockimformation_core.web.app import create_app


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
async def test_save_system_config(tmp_path) -> None:
    root = _copy_project_config(tmp_path)
    app = create_app(root / "config", FakeController(root / "config"), run_startup=False)
    content = (root / "config" / "system.toml").read_text().replace("schedule_minutes = 30", "schedule_minutes = 31")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            response = await client.put("/api/config/system", json={"content": content})
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 200
    assert "schedule_minutes = 31" in (root / "config" / "system.toml").read_text()


@pytest.mark.asyncio
async def test_create_dag(tmp_path) -> None:
    root = _copy_project_config(tmp_path)
    app = create_app(root / "config", FakeController(root / "config"), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            created = await client.post("/api/graph/dag", json={"name": "weekly-report"})
            duplicate = await client.post("/api/graph/dag", json={"name": "weekly-report"})
            invalid = await client.post("/api/graph/dag", json={"name": "Weekly Report"})
        finally:
            await app.state.controller.shutdown()
    assert created.status_code == 201
    assert created.json()["dag"] == {"name": "weekly-report", "nodes": [], "edges": [], "ui": {}}
    assert (root / "config" / "dags" / "weekly-report.yaml").exists()
    assert duplicate.status_code == 409
    assert invalid.status_code == 400


@pytest.mark.asyncio
async def test_list_dags_includes_configured_dags(tmp_path) -> None:
    root = _copy_project_config(tmp_path)
    (root / "config" / "dags" / "extra-dag.yaml").write_text(
        "name: extra-dag\nnodes: []\nedges: []\n",
        encoding="utf-8",
    )
    app = create_app(root / "config", FakeController(root / "config"), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            response = await client.get("/api/graph/dags")
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 200
    assert "extra-dag" in response.json()["dags"]


@pytest.mark.asyncio
async def test_source_health_accepts_resource_entity_with_id_business_key(tmp_path) -> None:
    root = _copy_project_config(tmp_path)
    app = create_app(root / "config", FakeController(root / "config"), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            response = await client.get("/api/sources/health")
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 200
    assert response.json()["sources"]


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
            response = await client.get("/api/entity-relations?entity=stock:00100.HK&type=uses-source")
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
    payload["relations"][0]["entities"][0] = "stock-hk0100"
    relations_path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False))
    app = create_app(root / "config", FakeController(root / "config"), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            response = await client.get("/api/entity-relations?entity=stock:00100.HK&type=uses-source")
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 200
    assert response.json()["relations"][0]["entities"][0] == "stock:00100.HK"


@pytest.mark.asyncio
async def test_entity_type_crud(tmp_path) -> None:
    root = _copy_project_config(tmp_path)
    app = create_app(root / "config", FakeController(root / "config"), run_startup=False)
    content = """
display_name: ETF
business_id_field: code
display_template: "{code}"
schema:
  type: object
  required:
    - code
  properties:
    code:
      type: string
field_permissions:
  code: read-only
validate: true
""".lstrip()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            created = await client.post("/api/config/entity-types", json={"name": "etf", "content": content})
            listed = await client.get("/api/config/entity-types")
            read = await client.get("/api/config/entity-types/etf")
            updated = await client.put("/api/config/entity-types/etf", json={"content": content.replace("ETF", "ETF 基金")})
            deleted = await client.delete("/api/config/entity-types/etf")
        finally:
            await app.state.controller.shutdown()
    assert created.status_code == 200
    assert "stock" in listed.json()["types"]
    assert read.json()["content"] == content
    assert updated.status_code == 200
    assert deleted.json()["deleted"] is True


@pytest.mark.asyncio
async def test_entity_type_read_system_schema(tmp_path) -> None:
    root = _copy_project_config(tmp_path)
    app = create_app(root / "config", FakeController(root / "config"), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/config/entity-types/node")
        missing = await client.get("/api/config/entity-types/unknown")
    assert response.status_code == 200
    assert "system_protected: true" in response.json()["content"]
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_entity_type_update_protected(tmp_path) -> None:
    root = _copy_project_config(tmp_path)
    app = create_app(root / "config", FakeController(root / "config"), run_startup=False)
    content = (root / "config" / "schemas" / "node.yaml").read_text()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.put("/api/config/entity-types/node", json={"content": content})
    assert response.status_code == 403
    assert "system protected" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_entity_type_delete_protected(tmp_path) -> None:
    root = _copy_project_config(tmp_path)
    app = create_app(root / "config", FakeController(root / "config"), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete("/api/config/entity-types/node")
    assert response.status_code == 403
    assert "system protected" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_entity_type_delete_requires_cascade_for_instances(tmp_path) -> None:
    root = _copy_project_config(tmp_path)
    entities = yaml.safe_load((root / "config" / "entities.yaml").read_text())["entities"]
    expected_count = sum(1 for entity in entities if entity["type"] == "stock")
    app = create_app(root / "config", FakeController(root / "config"), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            blocked = await client.delete("/api/config/entity-types/stock")
            deleted = await client.delete("/api/config/entity-types/stock?cascade=true")
            stocks = await client.get("/api/entities?type=stock")
        finally:
            await app.state.controller.shutdown()
    assert blocked.status_code == 409
    assert blocked.json()["instance_count"] == expected_count
    assert deleted.status_code == 200
    assert stocks.json()["entities"] == []


@pytest.mark.asyncio
async def test_entity_instance_crud(tmp_path) -> None:
    root = _copy_project_config(tmp_path)
    app = create_app(root / "config", FakeController(root / "config"), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            created = await client.post("/api/entities", json={"type": "stock", "attributes": {"code": "09988.HK", "name": "Alibaba"}})
            entity = created.json()["entity"]
            updated = await client.put(
                f"/api/entities/{entity['id']}",
                json={"attributes": {"code": "CHANGED", "name": "Alibaba Group"}},
            )
            deleted = await client.delete(f"/api/entities/{entity['id']}")
        finally:
            await app.state.controller.shutdown()
    assert created.status_code == 200
    assert updated.json()["entity"]["attributes"]["code"] == "09988.HK"
    assert updated.json()["entity"]["attributes"]["name"] == "Alibaba Group"
    assert deleted.json() == {"deleted": True, "relations_removed": 0}


@pytest.mark.asyncio
async def test_web_api_entity_crud(tmp_path) -> None:
    await test_entity_instance_crud(tmp_path)


@pytest.mark.asyncio
async def test_entity_relation_crud(tmp_path) -> None:
    root = _copy_project_config(tmp_path)
    app = create_app(root / "config", FakeController(root / "config"), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            listed = await client.get("/api/entity-relations")
            types = await client.get("/api/entity-relations/types")
            created = await client.post(
                "/api/entity-relations",
                json={"entities": ["stock:600519.SH", "api-source:github"], "type": "uses-source"},
            )
            duplicate = await client.post(
                "/api/entity-relations",
                json={"entities": ["stock:600519.SH", "api-source:github"], "type": "uses-source"},
            )
            deleted = await client.delete(f"/api/entity-relations/{created.json()['relation']['id']}")
        finally:
            await app.state.controller.shutdown()
    assert listed.status_code == 200
    assert all(relation["id"] for relation in listed.json()["relations"])
    assert "uses-source" in types.json()["types"]
    assert created.status_code == 200
    assert duplicate.status_code == 409
    assert deleted.json()["deleted"] is True


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
