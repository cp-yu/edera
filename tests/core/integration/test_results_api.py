from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from edera_core.web.app import create_app


@pytest.mark.asyncio
async def test_results_routes_use_grpc_client() -> None:
    grpc = FakeGrpcClient()
    app = create_app(grpc)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        results = await client.get("/api/results?stock_code=00700.HK&direction=buy")
        latest = await client.get("/api/briefings/latest")
        briefings = await client.get("/api/briefings?limit=5")
        briefing = await client.get("/api/briefings/briefing-1")
        advices = await client.get("/api/advices?stock_code=00700.HK")
        advice = await client.get("/api/advices/advice-1")

    assert results.json()["stock_code"] == "00700.HK"
    assert latest.json()["briefing"]["id"] == "briefing-1"
    assert briefings.json()["limit"] == 5
    assert briefing.json()["briefing"]["id"] == "briefing-1"
    assert advices.json()["stock_code"] == "00700.HK"
    assert advice.json()["advice"]["id"] == "advice-1"
    assert grpc.calls[0] == ("query_results_summary", "00700.HK", "buy", "", "")


class FakeGrpcClient:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    async def close(self) -> None:
        return None

    async def query_results_summary(self, stock_code="", direction="", created_from="", created_to="") -> dict[str, object]:
        self.calls.append(("query_results_summary", stock_code, direction, created_from, created_to))
        return {"stock_code": stock_code, "direction": direction, "briefing": None, "advices": []}

    async def query_latest_briefing(self) -> dict[str, object]:
        return {"briefing": {"id": "briefing-1"}}

    async def query_list_briefings(self, created_from="", created_to="", limit=50) -> dict[str, object]:
        return {"briefings": [{"id": "briefing-1"}], "limit": limit}

    async def query_get_briefing(self, briefing_id: str) -> dict[str, object]:
        return {"briefing": {"id": briefing_id}}

    async def query_list_advices(self, stock_code="", direction="", created_from="", created_to="", limit=50) -> dict[str, object]:
        return {"advices": [{"id": "advice-1"}], "stock_code": stock_code}

    async def query_get_advice(self, advice_id: str) -> dict[str, object]:
        return {"advice": {"id": advice_id}}
