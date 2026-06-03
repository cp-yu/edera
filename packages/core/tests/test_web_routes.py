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


class FakeClient:
    async def dag_run(self, name: str, payload: object | None = None) -> dict[str, object]:
        return {"run_id": f"run-{name}-manual"}

    async def query_node_history(self, dag_name: str, node_id: str, limit: int = 50) -> dict[str, object]:
        return {"history": [{"dag_name": dag_name, "node_id": node_id, "run_id": "run-1", "limit": limit}]}

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
