from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from edera_core.pipeline import PipelineController
from edera_core.storage import create_engine, init_db, session_factory, sqlite_url
from edera_core.storage.repository import store_node_output_entities
from edera_core.web.app import create_app


class FakeController(PipelineController):
    async def start(self, run_startup: bool = True) -> None:
        self.engine = create_engine(sqlite_url(self.config_dir / "web.db"))
        await init_db(self.engine)
        self.factory = session_factory(self.engine)
        self.scheduler.start()


@pytest.mark.asyncio
async def test_results_api_returns_entity_backed_payloads(tmp_path) -> None:
    app = create_app(tmp_path, FakeController(tmp_path), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            async with app.state.controller._factory()() as session:
                briefing = (
                    await store_node_output_entities(
                        session,
                        "cycle-1",
                        "briefing-node",
                        "briefing",
                        {
                            "cycle_id": "cycle-1",
                            "content": "briefing content",
                            "metadata": {
                                "failed_sources": {"rss": "timeout"},
                                "data_window": {"start": "2026-05-01", "end": "2026-05-02"},
                            },
                            "created_at": "2026-05-02T03:04:05+00:00",
                        },
                    )
                )[0]
                advice = (
                    await store_node_output_entities(
                        session,
                        "cycle-1",
                        "advice-node",
                        "advice",
                        {
                            "stock_code": "00700.HK",
                            "stock_name": "Tencent",
                            "direction": "buy",
                            "confidence": 0.8,
                            "reason": "reason",
                            "evidence": [],
                            "source_quotes": [],
                            "source_urls": ["https://example.test/news"],
                            "portfolio_snapshot": {},
                            "low_confidence": False,
                            "created_at": "2026-05-02T03:05:05+00:00",
                            "data_window_start": "2026-05-01T00:00:00+00:00",
                            "data_window_end": "2026-05-02T00:00:00+00:00",
                        },
                    )
                )[0]
                await session.commit()

            results = await client.get("/api/results")
            latest_briefing = await client.get("/api/briefings/latest")
            briefings = await client.get("/api/briefings")
            advices = await client.get("/api/advices")
            briefing_detail = await client.get(f"/api/briefings/{briefing.entity_id}")
            advice_detail = await client.get(f"/api/advices/{advice.entity_id}")
        finally:
            await app.state.controller.shutdown()

    assert results.status_code == 200
    payload = results.json()
    assert payload["briefing"] == {
        "id": briefing.entity_id,
        "cycle_id": "cycle-1",
        "content": "briefing content",
        "metadata": {
            "failed_sources": {"rss": "timeout"},
            "data_window": {"start": "2026-05-01", "end": "2026-05-02"},
        },
        "created_at": "2026-05-02T03:04:05+00:00",
    }
    assert "metadata_" not in payload["briefing"]
    assert payload["metadata_bar"]["failed_count"] == 1
    assert payload["metadata_bar"]["window"] == "2026-05-01 至 2026-05-02"
    assert payload["advices"][0]["id"] == advice.entity_id

    assert latest_briefing.status_code == 200
    assert latest_briefing.json()["briefing"]["id"] == briefing.entity_id
    assert briefings.status_code == 200
    assert briefings.json()["briefings"][0]["metadata"]["failed_sources"] == {"rss": "timeout"}
    assert advices.status_code == 200
    assert advices.json()["advices"][0]["id"] == advice.entity_id
    assert briefing_detail.status_code == 200
    assert briefing_detail.json()["briefing"]["id"] == briefing.entity_id
    assert advice_detail.status_code == 200
    assert advice_detail.json()["advice"]["id"] == advice.entity_id


@pytest.mark.asyncio
async def test_results_api_detail_missing_entity_returns_json_error(tmp_path) -> None:
    app = create_app(tmp_path, FakeController(tmp_path), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            response = await client.get("/api/briefings/missing-entity")
        finally:
            await app.state.controller.shutdown()

    assert response.status_code == 404
    assert response.json()["error"]["type"] == "not_found"
