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


class FakeClient:
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
