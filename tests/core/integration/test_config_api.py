from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from edera_core.web.app import create_app


@pytest.mark.asyncio
async def test_config_routes_use_grpc_client() -> None:
    grpc = FakeGrpcClient()
    app = create_app(grpc)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        entities = await client.get("/api/config/entities")
        saved_entities = await client.post("/api/config/entities", json={"entities": []})
        system = await client.put("/api/config/system", json={"content": "schedule_minutes = 31"})
        relation = await client.post("/api/entity-relations", json={"entities": ["a", "b"], "type": "uses"})
        deleted = await client.delete("/api/entity-relations/rel-1")

    assert entities.json() == {"content": "entities: []\n"}
    assert saved_entities.json() == {"saved": "entities"}
    assert system.json() == {"saved": "system"}
    assert relation.json()["relation"]["type"] == "uses"
    assert deleted.json()["deleted"] is True
    assert grpc.calls == [
        ("config_read_entities",),
        ("config_save_entities", {"entities": []}),
        ("config_save_system", "schedule_minutes = 31"),
        ("config_create_entity_relation", {"entities": ["a", "b"], "type": "uses"}),
        ("config_delete_entity_relation", "rel-1"),
    ]


@pytest.mark.asyncio
async def test_entity_type_routes_use_grpc_client() -> None:
    grpc = FakeGrpcClient()
    app = create_app(grpc)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/config/entity-types", json={"name": "etf", "content": "display_name: ETF\n"})
        listed = await client.get("/api/config/entity-types")
        read = await client.get("/api/config/entity-types/etf")
        updated = await client.put("/api/config/entity-types/etf", json={"content": "display_name: ETF Fund\n"})
        deleted = await client.delete("/api/config/entity-types/etf?cascade=true")

    assert created.json()["created"] == "etf"
    assert listed.json()["types"]["stock"]["display_name"] == "Stock"
    assert read.json()["content"] == "display_name: ETF\n"
    assert updated.json()["saved"] == "etf"
    assert deleted.json()["deleted"] is True


@pytest.mark.asyncio
async def test_entity_routes_use_grpc_client() -> None:
    grpc = FakeGrpcClient()
    app = create_app(grpc)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listed = await client.get("/api/entities?type=stock")
        created = await client.post("/api/entities", json={"type": "stock", "attributes": {"code": "09988.HK"}})
        updated = await client.put("/api/entities/stock:09988.HK", json={"attributes": {"name": "Alibaba"}})
        deleted = await client.delete("/api/entities/stock:09988.HK")
        queried = await client.get("/api/entity-relations?entity=stock:09988.HK&type=uses-source")

    assert listed.json()["entities"][0]["type"] == "stock"
    assert created.json()["attributes"]["code"] == "09988.HK"
    assert updated.json()["entity"]["attributes"]["name"] == "Alibaba"
    assert deleted.json() == {"deleted": True}
    assert queried.json()["relations"][0]["id"] == "rel-1"


@pytest.mark.asyncio
async def test_portfolio_config_is_deprecated() -> None:
    app = create_app(FakeGrpcClient())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/config/portfolio")

    assert response.status_code == 404
    assert response.json()["error"]["type"] == "not_found"


class FakeGrpcClient:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []
        self.identity = "human:test"

    async def close(self) -> None:
        return None

    async def config_read_entities(self) -> dict[str, object]:
        self.calls.append(("config_read_entities",))
        return {"content": "entities: []\n"}

    async def config_save_entities(self, payload: dict[str, object]) -> dict[str, object]:
        self.calls.append(("config_save_entities", payload))
        return {"saved": "entities"}

    async def config_save_system(self, content: str) -> dict[str, object]:
        self.calls.append(("config_save_system", content))
        return {"saved": "system"}

    async def config_list_entity_types(self) -> dict[str, object]:
        return {"types": {"stock": {"display_name": "Stock"}}}

    async def config_create_entity_type(self, name: str, content: str) -> dict[str, object]:
        return {"created": name, "content": content}

    async def config_get_entity_type(self, name: str) -> dict[str, object]:
        return {"name": name, "content": "display_name: ETF\n"}

    async def config_save_entity_type(self, name: str, content: str) -> dict[str, object]:
        return {"saved": name, "content": content}

    async def config_delete_entity_type(self, name: str, cascade: bool = False) -> dict[str, object]:
        return {"deleted": True, "name": name, "cascade": cascade}

    async def config_create_entity_relation(self, payload: dict[str, object]) -> dict[str, object]:
        self.calls.append(("config_create_entity_relation", payload))
        return {"relation": {"id": "rel-1", **payload}}

    async def config_delete_entity_relation(self, relation_id: str) -> dict[str, object]:
        self.calls.append(("config_delete_entity_relation", relation_id))
        return {"deleted": True}

    async def entity_list(self, type_name: str | None = None) -> list[dict[str, object]]:
        return [{"id": "stock-1", "type": type_name or "stock", "attributes": {"code": "00100.HK"}}]

    async def entity_create(self, type_name: str, attributes: dict[str, object]) -> dict[str, object]:
        return {"id": f"{type_name}-new", "type": type_name, "attributes": attributes}

    async def entity_get(self, ref: str) -> dict[str, object]:
        return {"id": ref, "type": "stock", "attributes": {"code": "09988.HK"}}

    async def entity_update(self, ref: str, field: str, value: object) -> dict[str, object]:
        return {"id": ref, "type": "stock", "attributes": {"code": "09988.HK", field: value}}

    async def entity_delete(self, ref: str) -> dict[str, object]:
        return {"deleted": True}

    async def entity_search(self, expression: str, identity: str) -> list[dict[str, object]]:
        return [
            {
                "id": "rel-1",
                "attributes": {
                    "entities": ["stock:09988.HK", "source:rss"],
                    "relation_type": "uses-source",
                    "metadata": {"expression": expression, "identity": identity},
                },
            }
        ]
