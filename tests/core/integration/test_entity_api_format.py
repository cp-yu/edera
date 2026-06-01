from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from edera_core.web.app import create_app


@pytest.mark.asyncio
async def test_entities_list_returns_wrapped_format():
    grpc = FakeGrpcClient()
    app = create_app(grpc)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/entities")
    body = resp.json()
    assert isinstance(body, dict)
    assert "entities" in body
    assert isinstance(body["entities"], list)
    assert len(body["entities"]) == 1
    assert body["entities"][0]["id"] == "stock-test"


@pytest.mark.asyncio
async def test_entities_list_with_type_filter():
    grpc = FakeGrpcClient()
    app = create_app(grpc)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/entities?type=stock")
    body = resp.json()
    assert "entities" in body
    assert grpc.entity_list_type == "stock"


@pytest.mark.asyncio
async def test_entity_relations_returns_wrapped_format():
    grpc = FakeGrpcClient()
    app = create_app(grpc)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/entity-relations")
    body = resp.json()
    assert isinstance(body, dict)
    assert "relations" in body
    assert isinstance(body["relations"], list)
    assert len(body["relations"]) == 2
    rel = body["relations"][0]
    assert rel["id"] == "rel-1"
    assert rel["type"] == "reflects"
    assert rel["entities"] == ["stock:A", "stock:B"]


@pytest.mark.asyncio
async def test_entity_relation_types_returns_wrapped_format():
    grpc = FakeGrpcClient()
    app = create_app(grpc)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/entity-relations/types")
    body = resp.json()
    assert isinstance(body, dict)
    assert "types" in body
    assert isinstance(body["types"], list)
    assert body["types"] == ["reflects", "uses-source"]


class FakeGrpcClient:
    identity: str | None = "human:test"

    def __init__(self) -> None:
        self.entity_list_type: str | None = None

    async def close(self) -> None:
        return None

    async def entity_list(self, type_name: str | None = None) -> list[dict[str, object]]:
        self.entity_list_type = type_name
        return [{"id": "stock-test", "type": "stock", "ref": "stock:TEST", "attributes": {"code": "TEST"}}]

    async def entity_search(self, expression: str, identity: str) -> list[dict[str, object]]:
        return [
            {
                "id": "rel-1",
                "type": "relation",
                "attributes": {
                    "relation_type": "reflects",
                    "entities": ["stock:A", "stock:B"],
                    "metadata": {},
                },
            },
            {
                "id": "rel-2",
                "type": "relation",
                "attributes": {
                    "relation_type": "uses-source",
                    "entities": ["stock:A", "rss-source:hn"],
                    "metadata": {},
                },
            },
        ]
