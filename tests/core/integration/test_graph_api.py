from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from edera_core.web.app import create_app


@pytest.mark.asyncio
async def test_graph_routes_use_grpc_client() -> None:
    grpc = FakeGrpcClient()
    app = create_app(grpc)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        nodes = await client.get("/api/graph/nodes")
        dags = await client.get("/api/graph/dags")
        dag = await client.get("/api/graph/dag/default")
        saved = await client.put("/api/graph/dag/default", json={"nodes": [], "edges": [], "ui": {}})

    assert nodes.json()["nodes"][0]["name"] == "reader"
    assert dags.json()["dags"] == ["default"]
    assert dag.json()["name"] == "default"
    assert saved.json()["saved"] == "default"
    assert grpc.calls == [
        ("graph_list_node_types",),
        ("graph_list_dags",),
        ("graph_get_dag", "default"),
        ("graph_save_dag", "default", {"nodes": [], "edges": [], "ui": {}}),
    ]


@pytest.mark.asyncio
async def test_graph_handler_routes_use_grpc_client() -> None:
    grpc = FakeGrpcClient()
    app = create_app(grpc)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        read = await client.get("/api/graph/handlers/fetch-api")
        saved = await client.put("/api/graph/handlers/fetch-api", json={"code": "async def run(ctx): return []\n"})

    assert read.json()["code"] == "async def run(ctx): return []\n"
    assert saved.json()["saved"] == "fetch-api"


class FakeGrpcClient:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    async def close(self) -> None:
        return None

    async def graph_list_node_types(self) -> dict[str, object]:
        self.calls.append(("graph_list_node_types",))
        return {"nodes": [{"name": "reader"}]}

    async def graph_list_dags(self) -> dict[str, object]:
        self.calls.append(("graph_list_dags",))
        return {"dags": ["default"]}

    async def graph_get_dag(self, name: str) -> dict[str, object]:
        self.calls.append(("graph_get_dag", name))
        return {"name": name, "nodes": [], "edges": [], "ui": {}}

    async def graph_save_dag(self, name: str, payload: dict[str, object]) -> dict[str, object]:
        self.calls.append(("graph_save_dag", name, payload))
        return {"saved": name}

    async def graph_get_handler(self, name: str) -> dict[str, object]:
        return {"name": name, "code": "async def run(ctx): return []\n"}

    async def graph_save_handler(self, name: str, code: str) -> dict[str, object]:
        return {"saved": name, "code": code}
