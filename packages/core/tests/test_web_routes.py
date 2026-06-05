from __future__ import annotations

import httpx
import pytest

from edera_core.web.app import create_app


@pytest.mark.asyncio
async def test_results_summary_through_bff():
    app = create_app(FakeClient())

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/results", params={"stock_code": "AAPL"})

    assert response.status_code == 200
    payload = response.json()
    assert {"briefing", "briefings", "advices", "events", "event_details", "summary_items", "metadata_bar", "failed_sources"}.issubset(payload)
    assert payload["stock_code"] == "AAPL"


@pytest.mark.asyncio
async def test_default_dag_run_uses_parameterized_route():
    app = create_app(FakeClient())
    endpoints = {route.name for route in app.routes}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/dags/default/run")

    assert response.status_code == 200
    assert response.json() == {"run_id": "run-default-manual"}
    assert "api_default_dag_run" not in endpoints
    assert "api_default_dag_stop" not in endpoints


@pytest.mark.asyncio
async def test_node_history_requires_dag_name():
    app = create_app(FakeClient())
    endpoints = {route.name for route in app.routes}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        removed = await client.get("/api/nodes/node-a/history?limit=10")
        generic = await client.get("/api/history/dag/default/nodes/node-a?limit=10")

    assert removed.status_code == 404
    assert generic.status_code == 200
    assert generic.json() == {"history": [{"dag_name": "default", "node_id": "node-a", "run_id": "run-1", "limit": 10}]}
    assert "api_default_node_history" not in endpoints


@pytest.mark.asyncio
async def test_node_execution_logs_route_uses_grpc_filters():
    app = create_app(FakeClient())

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/node-logs", params={"run_id": "run-1", "node_id": "node-a", "limit": 5})
        outputs = await client.get("/api/node-outputs", params={"run_id": "run-1", "node_id": "node-a", "limit": 5})

    assert response.status_code == 200
    assert response.json() == {"logs": [{"run_id": "run-1", "node_id": "node-a", "kind": "summary", "limit": 5}]}
    assert outputs.status_code == 200
    assert outputs.json() == {"outputs": [{"run_id": "run-1", "node_id": "node-a", "payload": {"value": 1}}]}


@pytest.mark.asyncio
async def test_graph_runtime_status_route_forwards_run_id():
    app = create_app(FakeClient())

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/graph/runtime-status", params={"run_id": "child-1"})

    assert response.status_code == 200
    assert response.json() == {"run_id": "child-1"}


@pytest.mark.asyncio
async def test_child_run_route_forwards_parent_instance():
    app = create_app(FakeClient())

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/child-run", params={"parent_run_id": "parent-1", "parent_node_id": "node-x"})

    assert response.status_code == 200
    assert response.json() == {"child_run_id": "parent-1:node-x"}


class FakeClient:
    async def graph_runtime_status(self, run_id: str = "") -> dict[str, object]:
        return {"run_id": run_id}

    async def dag_run(self, name: str, payload: object | None = None) -> dict[str, object]:
        return {"run_id": f"run-{name}-manual"}

    async def query_child_run_for_parent(self, parent_run_id: str, parent_node_id: str) -> dict[str, object]:
        return {"child_run_id": f"{parent_run_id}:{parent_node_id}"}

    async def query_node_history(self, dag_name: str, node_id: str, limit: int = 50) -> dict[str, object]:
        return {"history": [{"dag_name": dag_name, "node_id": node_id, "run_id": "run-1", "limit": limit}]}

    async def query_node_logs(self, node_id: str = "", run_id: str = "", limit: int = 100) -> dict[str, object]:
        return {"logs": [{"run_id": run_id, "node_id": node_id, "kind": "summary", "limit": limit}]}

    async def query_node_outputs(self, node_id: str = "", run_id: str = "", limit: int = 100) -> dict[str, object]:
        return {"outputs": [{"run_id": run_id, "node_id": node_id, "payload": {"value": 1}}]}

    async def query_results_summary(self, stock_code="", direction="", created_from="", created_to=""):
        return {
            "stock_code": stock_code,
            "briefing": None,
            "briefings": [],
            "advices": [],
            "events": [],
            "event_details": {},
            "summary_items": [],
            "metadata_bar": {},
            "failed_sources": {},
        }

    async def close(self):
        return None
