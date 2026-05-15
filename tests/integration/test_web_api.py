from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from stockimformation.models import (
    Advice,
    AnalysisResult,
    Briefing,
    RawItem,
    create_engine,
    init_db,
    session_factory,
    sqlite_url,
)
from stockimformation.models.repository import (
    create_pipeline_run,
    finish_pipeline_run,
    mark_node_run,
    store_cycle_outputs,
)
from stockimformation.pipeline import PipelineController, RunAlreadyActiveError
from stockimformation.web.app import create_app


class FakeController(PipelineController):
    async def start(self, run_startup: bool = True) -> None:
        self.engine = create_engine(sqlite_url(self.config_dir / "web.db"))
        await init_db(self.engine)
        self.factory = session_factory(self.engine)
        self.scheduler.start()

    async def start_run(self, trigger: str = "manual") -> str:
        async with self._lock:
            if self.current_task is not None and not self.current_task.done():
                raise RunAlreadyActiveError(self.current_cycle_id or "unknown")
            cycle_id = "cycle-manual"
            self.current_cycle_id = cycle_id
            self.current_task = asyncio.create_task(self._fake_run(cycle_id, trigger))
            self.current_task.add_done_callback(self._clear_finished_task)
            return cycle_id

    async def _fake_run(self, cycle_id: str, trigger: str) -> None:
        async with self._factory()() as session:
            await create_pipeline_run(session, cycle_id, trigger)
            await session.commit()
        await asyncio.sleep(60)


@pytest.mark.asyncio
async def test_web_pipeline_api_run_conflict_pause_resume_stop(tmp_path: Path) -> None:
    app = create_app(tmp_path, FakeController(tmp_path), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            first = await client.post("/api/pipeline/run")
            second = await client.post("/api/pipeline/run")
            paused = await client.post("/api/pipeline/pause")
            resumed = await client.post("/api/pipeline/resume")
            stopped = await client.post("/api/pipeline/stop")
        finally:
            await app.state.controller.shutdown()
    assert first.status_code == 200
    assert first.json()["cycle_id"] == "cycle-manual"
    assert second.status_code == 409
    assert paused.json()["scheduler_paused"] is True
    assert resumed.json()["scheduler_paused"] is False
    assert stopped.json() == {"stopped": True, "cycle_id": "cycle-manual"}


@pytest.mark.asyncio
async def test_web_pipeline_stop_without_active_run(tmp_path: Path) -> None:
    app = create_app(tmp_path, FakeController(tmp_path), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            response = await client.post("/api/pipeline/stop")
        finally:
            await app.state.controller.shutdown()
    assert response.json() == {"stopped": False, "cycle_id": None}


@pytest.mark.asyncio
async def test_web_results_empty_state(tmp_path: Path) -> None:
    app = create_app(tmp_path, FakeController(tmp_path), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            response = await client.get("/api/results")
        finally:
            await app.state.controller.shutdown()
    assert response.json() == {
        "briefing": None,
        "metadata_bar": {
            "cycle_id": "无",
            "created_at": "",
            "window": "无数据窗口",
            "failed_count": 0,
            "degraded": False,
            "disclaimer": "本系统产出仅供学习参考，不构成投资建议。",
        },
        "briefings": [],
        "advices": [],
        "events": [],
        "event_details": {},
        "summary_items": [],
        "failed_sources": {},
    }


@pytest.mark.asyncio
async def test_web_latest_briefing_api_exposes_version_fields(tmp_path: Path) -> None:
    app = create_app(tmp_path, FakeController(tmp_path), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            async with app.state.controller._factory()() as session:
                briefing = Briefing(cycle_id="cycle-version", content="briefing", created_at=_dt(2))
                session.add(briefing)
                await session.commit()
                briefing_id = briefing.id
            response = await client.get("/api/briefings/latest")
        finally:
            await app.state.controller.shutdown()
    payload = response.json()["briefing"]
    assert response.status_code == 200
    assert payload["id"] == briefing_id
    assert payload["created_at"] == _dt(2).replace(tzinfo=None).isoformat()


@pytest.mark.asyncio
async def test_web_results_page_mounts_auto_refresh_config(tmp_path: Path) -> None:
    app = create_app(tmp_path, FakeController(tmp_path), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            async with app.state.controller._factory()() as session:
                briefing = Briefing(cycle_id="cycle-refresh", content="briefing", created_at=_dt(2))
                session.add(briefing)
                await session.commit()
                briefing_id = briefing.id
            response = await client.get("/results?stock_code=00700.HK")
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 200
    assert 'id="result-auto-refresh"' in response.text
    assert f'data-briefing-id="{briefing_id}"' in response.text
    assert f'data-briefing-created-at="{_dt(2).replace(tzinfo=None).isoformat()}"' in response.text
    assert 'data-interval-ms="15000"' in response.text


@pytest.mark.asyncio
async def test_web_results_event_and_advice_context(tmp_path: Path) -> None:
    app = create_app(tmp_path, FakeController(tmp_path), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            async with app.state.controller._factory()() as session:
                await store_cycle_outputs(
                    session,
                    [_raw_item("https://example.com/event")],
                    [
                        AnalysisResult(
                            raw_item_id=1,
                            summary="event summary",
                            keywords=["tencent", "growth"],
                            sentiment="bullish",
                            confidence=0.9,
                            source_quote="growth",
                            source_url="https://example.com/event",
                        )
                    ],
                    [
                        Advice(
                            stock_code="00700.HK",
                            stock_name="Tencent",
                            direction="buy",
                            confidence=0.8,
                            reason="reason",
                            evidence=[1],
                            source_quotes=["growth"],
                            source_urls=["https://example.com/event"],
                            portfolio_snapshot={"quantity": 1},
                            created_at=_dt(1),
                            data_window_start=_dt(1),
                            data_window_end=_dt(1),
                        )
                    ],
                    None,
                )
                await session.commit()
            results_response = await client.get("/api/results")
            advice_response = await client.get("/results/advices/1")
            result_page = await client.get("/results")
        finally:
            await app.state.controller.shutdown()
    assert "events" in results_response.json()
    assert "事件" in result_page.text
    assert "事件证据" in advice_response.text


@pytest.mark.asyncio
async def test_web_results_empty_page_keeps_auto_refresh_config(tmp_path: Path) -> None:
    app = create_app(tmp_path, FakeController(tmp_path), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            response = await client.get("/results")
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 200
    assert "暂无简报。" in response.text
    assert 'id="result-auto-refresh"' in response.text
    assert 'data-briefing-id=""' in response.text
    assert 'data-briefing-created-at=""' in response.text
    assert 'data-interval-ms="15000"' in response.text


@pytest.mark.asyncio
async def test_web_advice_detail_exposes_minimax_evidence(tmp_path: Path) -> None:
    minimax_url = "https://platform.minimax.io/docs/api-reference/text-chat-openai"
    app = create_app(tmp_path, FakeController(tmp_path), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            async with app.state.controller._factory()() as session:
                await store_cycle_outputs(
                    session,
                    [_raw_item(minimax_url)],
                    [_analysis(minimax_url)],
                    [_advice(minimax_url)],
                    None,
                )
                await session.commit()
            response = await client.get("/api/advices/1")
        finally:
            await app.state.controller.shutdown()
    payload = response.json()
    assert response.status_code == 200
    assert payload["advice"]["source_urls"] == [minimax_url]
    assert payload["advice"]["comparison"]["verdict"] == "unknown"
    assert payload["analyses"][0]["source_url"] == minimax_url
    assert payload["raw_items"][0]["url"] == minimax_url


@pytest.mark.asyncio
async def test_web_briefing_history_api_filters_and_details(tmp_path: Path) -> None:
    app = create_app(tmp_path, FakeController(tmp_path), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            async with app.state.controller._factory()() as session:
                older = Briefing(cycle_id="old", content="old", created_at=_dt(1))
                newer = Briefing(cycle_id="new", content="new", created_at=_dt(2))
                session.add(older)
                session.add(newer)
                await session.commit()
                newer_id = newer.id
            list_response = await client.get(
                "/api/briefings",
                params={"created_from": _dt(2).isoformat()},
            )
            detail_response = await client.get(f"/api/briefings/{newer_id}")
            missing_response = await client.get("/api/briefings/999")
        finally:
            await app.state.controller.shutdown()
    briefings = list_response.json()["briefings"]
    assert [item["cycle_id"] for item in briefings] == ["new"]
    assert detail_response.json()["briefing"]["cycle_id"] == "new"
    assert missing_response.status_code == 404
    assert missing_response.json()["error"]["type"] == "not_found"


@pytest.mark.asyncio
async def test_web_advices_api_filters_by_stock_direction_and_time(tmp_path: Path) -> None:
    app = create_app(tmp_path, FakeController(tmp_path), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            async with app.state.controller._factory()() as session:
                session.add(_advice_at("00700.HK", "hold", _dt(1)))
                session.add(_advice_at("600519.SH", "buy", _dt(2)))
                await session.commit()
            response = await client.get(
                "/api/advices",
                params={
                    "stock_code": "600519.SH",
                    "direction": "buy",
                    "created_from": _dt(2).isoformat(),
                },
            )
        finally:
            await app.state.controller.shutdown()
    advices = response.json()["advices"]
    assert len(advices) == 1
    assert advices[0]["stock_code"] == "600519.SH"
    assert advices[0]["direction"] == "buy"
    assert advices[0]["comparison"]["verdict"] == "unknown"


@pytest.mark.asyncio
async def test_web_results_api_includes_configured_price_comparison(tmp_path: Path) -> None:
    _write_price_config(tmp_path, "prices.csv")
    (tmp_path / "prices.csv").write_text(
        "\n".join(
            [
                "stock_code,timestamp,close",
                f"600519.SH,{_dt(2).isoformat()},100",
                f"600519.SH,{_dt(9).isoformat()},104",
            ]
        ),
        encoding="utf-8",
    )
    app = create_app(tmp_path, FakeController(tmp_path), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            async with app.state.controller._factory()() as session:
                session.add(_advice_at("600519.SH", "buy", _dt(2)))
                await session.commit()
            response = await client.get("/api/results")
        finally:
            await app.state.controller.shutdown()
    advice = response.json()["advices"][0]
    summary = response.json()["summary_items"][0]
    assert advice["comparison"]["verdict"] == "aligned"
    assert advice["comparison"]["price_change_percent"] == 4.0
    assert summary["comparison"]["verdict_label"] == "一致"


@pytest.mark.asyncio
async def test_web_advice_detail_page_shows_comparison(tmp_path: Path) -> None:
    _write_price_config(tmp_path, "prices.csv")
    (tmp_path / "prices.csv").write_text(
        "\n".join(
            [
                "stock_code,timestamp,close",
                f"600519.SH,{_dt(2).isoformat()},100",
                f"600519.SH,{_dt(9).isoformat()},104",
            ]
        ),
        encoding="utf-8",
    )
    app = create_app(tmp_path, FakeController(tmp_path), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            async with app.state.controller._factory()() as session:
                session.add(_advice_at("600519.SH", "sell", _dt(2)))
                await session.commit()
            response = await client.get("/results/advices/1")
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 200
    assert "价格复盘" in response.text
    assert "复盘 偏离" in response.text
    assert "4.00%" in response.text


@pytest.mark.asyncio
async def test_web_result_deeplink_pages_and_not_found(tmp_path: Path) -> None:
    minimax_url = "https://platform.minimax.io/docs/api-reference/text-chat-openai"
    app = create_app(tmp_path, FakeController(tmp_path), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            async with app.state.controller._factory()() as session:
                briefing = Briefing(cycle_id="cycle", content="briefing")
                session.add(briefing)
                await store_cycle_outputs(
                    session,
                    [_raw_item(minimax_url)],
                    [_analysis(minimax_url)],
                    [_advice(minimax_url)],
                    None,
                )
                await session.commit()
                briefing_id = briefing.id
            briefing_page = await client.get(f"/results/briefings/{briefing_id}")
            advice_page = await client.get("/results/advices/1")
            missing_briefing = await client.get("/results/briefings/999")
            missing_advice = await client.get("/results/advices/999")
        finally:
            await app.state.controller.shutdown()
    assert briefing_page.status_code == 200
    assert "briefing" in briefing_page.text
    assert advice_page.status_code == 200
    assert minimax_url in advice_page.text
    assert missing_briefing.status_code == 404
    assert "简报不存在" in missing_briefing.text
    assert missing_advice.status_code == 404
    assert "建议不存在" in missing_advice.text


@pytest.mark.asyncio
async def test_web_results_summary_inbox_metadata_and_states(tmp_path: Path) -> None:
    app = create_app(tmp_path, FakeController(tmp_path), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            async with app.state.controller._factory()() as session:
                session.add(
                    Briefing(
                        cycle_id="cycle-summary",
                        content="briefing",
                        metadata_={
                            "data_window": {
                                "start": _dt(1).isoformat(),
                                "end": _dt(2).isoformat(),
                            },
                            "failed_sources": {"sample-web": "timeout"},
                        },
                        created_at=_dt(2),
                    )
                )
                session.add(_advice_at("600519.SH", "buy", _dt(2)))
                session.add(_advice_at("00700.HK", "hold", _dt(1), low_confidence=True))
                await session.commit()
            response = await client.get("/results")
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 200
    assert "cycle-summary" in response.text
    assert "失败源 1" in response.text
    assert "仅供学习参考，不构成投资建议" in response.text
    assert "summary-item state-buy" in response.text
    assert "summary-item state-low-confidence" in response.text
    assert "买入" in response.text
    assert "低置信度" in response.text


@pytest.mark.asyncio
async def test_web_source_health_api_logs_and_page(tmp_path: Path) -> None:
    _write_portfolio(tmp_path)
    app = create_app(tmp_path, FakeController(tmp_path), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            async with app.state.controller._factory()() as session:
                await create_pipeline_run(session, "cycle-1", "manual", ["sample-web"])
                await mark_node_run(session, "cycle-1", "sample-web", "running")
                await mark_node_run(session, "cycle-1", "sample-web", "failed", "timeout")
                await finish_pipeline_run(session, "cycle-1", "failed", "boom")
                session.add(
                    Briefing(
                        cycle_id="cycle-1",
                        content="briefing",
                        metadata_={
                            "failed_sources": {"sample-web": "source timeout"},
                            "source_recovery": {
                                "sample-web": {
                                    "recovery_status": "escalated",
                                    "attempt_count": 2,
                                    "recoverable_reason": "timeout",
                                    "latest_failure_reason": "source timeout",
                                    "escalated": True,
                                    "escalation_reason": "recovery_exhausted",
                                    "updated_at": _dt(1).isoformat(),
                                }
                            },
                        },
                    )
                )
                await session.commit()
            health_response = await client.get("/api/sources/health")
            logs_response = await client.get(
                "/api/sources/logs",
                params={"source_name": "sample-web"},
            )
            page_response = await client.get("/sources")
            handoff_response = await client.post("/api/sources/sample-web/repair-task")
            reject_response = await client.post("/api/sources/minimax-docs/repair-task")
            health_after_handoff = await client.get("/api/sources/health")
        finally:
            await app.state.controller.shutdown()
    health = health_response.json()["sources"]
    sample_web = next(source for source in health if source["source_name"] == "sample-web")
    minimax = next(source for source in health if source["source_name"] == "minimax-docs")
    assert sample_web["latest_status"] == "failed"
    assert sample_web["success_rate"] == 0.0
    assert sample_web["recovery_status"] == "escalated"
    assert sample_web["attempt_count"] == 2
    assert sample_web["escalated"] is True
    assert sample_web["latest_failure_reason"] == "source timeout"
    assert minimax["latest_status"] == "unknown"
    logs = logs_response.json()["logs"]
    assert len(logs) == 1
    assert logs[0]["source_name"] == "sample-web"
    assert logs[0]["pipeline_status"] == "failed"
    assert page_response.status_code == 200
    assert "信息源健康" in page_response.text
    assert "source timeout" in page_response.text
    assert "recovery_exhausted" in page_response.text
    assert 'aria-current="page"' in page_response.text
    assert 'scope="col">信息源' in page_response.text
    handoff = handoff_response.json()
    assert handoff_response.status_code == 200
    assert handoff["source_name"] == "sample-web"
    assert Path(handoff["task_path"]).exists()
    assert reject_response.status_code == 400
    assert reject_response.json()["error"]["type"] == "source_not_escalated"
    updated_sample_web = next(
        source for source in health_after_handoff.json()["sources"] if source["source_name"] == "sample-web"
    )
    assert updated_sample_web["repair_task"]["task_id"] == handoff["task_id"]


@pytest.mark.asyncio
async def test_web_config_page_lists_analysis_tuning_entries(tmp_path: Path) -> None:
    root = _copy_project_config(tmp_path)
    app = create_app(root / "config", FakeController(root / "config"), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            response = await client.get("/config")
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 200
    assert "分析参数" in response.text
    assert "保存后仅影响后续运行" in response.text
    assert "reader" in response.text
    assert "advisor" in response.text
    assert "briefing-generator" in response.text
    assert "rss-fetcher" in response.text
    assert "source_names" in response.text
    assert "parameters" in response.text


@pytest.mark.asyncio
async def test_web_config_page_lists_portfolio_entries(tmp_path: Path) -> None:
    root = _copy_project_config(tmp_path)
    app = create_app(root / "config", FakeController(root / "config"), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            response = await client.get("/config")
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 200
    assert "标的与信息源" in response.text
    assert "00700.HK" in response.text
    assert "sample-rss" in response.text
    assert "portfolio JSON" in response.text
    assert "保存标的与信息源" in response.text


@pytest.mark.asyncio
async def test_web_config_api_saves_valid_analysis_parameters(tmp_path: Path) -> None:
    root = _copy_project_config(tmp_path)
    app = create_app(root / "config", FakeController(root / "config"), run_startup=False)
    content = (root / "config" / "nodes" / "reader.yaml").read_text().replace(
        "parameters: {}\n",
        "parameters:\n  confidence_threshold: 0.62\n",
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            response = await client.put(
                "/api/config/node/reader",
                json={"content": content},
            )
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 200
    assert "confidence_threshold" in response.json()["file"]["content"]


@pytest.mark.asyncio
async def test_web_config_api_saves_valid_portfolio(tmp_path: Path) -> None:
    root = _copy_project_config(tmp_path)
    app = create_app(root / "config", FakeController(root / "config"), run_startup=False)
    payload = _portfolio_payload()
    _targets(payload)[0]["holding"]["quantity"] = 200
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            response = await client.put("/api/config/portfolio", json=payload)
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 200
    saved = (root / "config" / "portfolio.yaml").read_text()
    assert "quantity: 200.0" in saved
    assert response.json()["portfolio"]["targets"][0]["holding"]["quantity"] == 200.0


@pytest.mark.asyncio
async def test_web_config_api_rejects_invalid_portfolio(tmp_path: Path) -> None:
    root = _copy_project_config(tmp_path)
    app = create_app(root / "config", FakeController(root / "config"), run_startup=False)
    original = (root / "config" / "portfolio.yaml").read_text()
    payload = _portfolio_payload()
    _targets(payload)[0]["holding"]["quantity"] = -1
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            response = await client.put("/api/config/portfolio", json=payload)
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 400
    assert response.json()["error"]["type"] == "config_error"
    assert (root / "config" / "portfolio.yaml").read_text() == original


@pytest.mark.asyncio
async def test_web_config_api_rejects_missing_source_reference(tmp_path: Path) -> None:
    root = _copy_project_config(tmp_path)
    app = create_app(root / "config", FakeController(root / "config"), run_startup=False)
    original = (root / "config" / "portfolio.yaml").read_text()
    payload = _portfolio_payload()
    _targets(payload)[0]["sources"] = ["missing-source"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            response = await client.put("/api/config/portfolio", json=payload)
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 400
    assert "missing-source" in response.json()["error"]["message"]
    assert (root / "config" / "portfolio.yaml").read_text() == original


@pytest.mark.asyncio
async def test_web_config_api_rejects_unsupported_analysis_parameter(tmp_path: Path) -> None:
    root = _copy_project_config(tmp_path)
    app = create_app(root / "config", FakeController(root / "config"), run_startup=False)
    original = (root / "config" / "nodes" / "reader.yaml").read_text()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            response = await client.put(
                "/api/config/node/reader",
                json={"content": f"{original}\nunsupported_parameter: 1\n"},
            )
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 400
    assert response.json()["error"]["type"] == "config_error"
    assert (root / "config" / "nodes" / "reader.yaml").read_text() == original


@pytest.mark.asyncio
async def test_web_config_api_keeps_generic_skill_editing(tmp_path: Path) -> None:
    root = _copy_project_config(tmp_path)
    app = create_app(root / "config", FakeController(root / "config"), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            response = await client.put(
                "/api/config/skill/fetch-rss/skill.md",
                json={"content": "# skill\n"},
            )
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 200
    assert (root / "skills" / "fetch-rss" / "skill.md").read_text() == "# skill\n"


def _raw_item(url: str) -> RawItem:
    return RawItem(
        url=url,
        title="MiniMax Text Chat",
        content="MiniMax OpenAI compatible chat completions use Bearer Auth and MiniMax-M2.7",
        source_name="minimax-docs",
        source_type="web",
        stock_codes=["00700.HK"],
        published_at=datetime.now(timezone.utc),
    )


def _analysis(url: str) -> AnalysisResult:
    return AnalysisResult(
        raw_item_id=1,
        summary="MiniMax OpenAI compatible chat completions",
        keywords=["MiniMax", "OpenAI", "Bearer"],
        sentiment="neutral",
        confidence=0.55,
        source_quote="MiniMax OpenAI compatible chat completions use Bearer Auth",
        source_url=url,
    )


def _advice(url: str) -> Advice:
    now = datetime.now(timezone.utc)
    return _advice_at("00700.HK", "hold", now, url)


def _advice_at(
    stock_code: str,
    direction: str,
    now: datetime,
    url: str = "https://example.com/a",
    low_confidence: bool = False,
) -> Advice:
    return Advice(
        stock_code=stock_code,
        stock_name=stock_code,
        direction=direction,
        confidence=0.55,
        reason="信号不足以支持买入或卖出",
        evidence=[1],
        source_quotes=["MiniMax OpenAI compatible chat completions use Bearer Auth"],
        source_urls=[url],
        portfolio_snapshot={"quantity": 100, "watch_only": False},
        low_confidence=low_confidence,
        created_at=now,
        data_window_start=now,
        data_window_end=now,
    )


def _dt(day: int) -> datetime:
    return datetime(2026, 1, day, tzinfo=timezone.utc)


def _write_portfolio(path: Path) -> None:
    path.joinpath("system.toml").write_text(
        f"""
database_url = "sqlite+aiosqlite:///{path / "web.db"}"
schedule_minutes = 30
web_host = "127.0.0.1"
web_port = 8000
log_level = "INFO"
llm_timeout_seconds = 60
workspace_root = "{path / "workspace"}"
retention_count = 20
retention_hours = 24
""".lstrip()
    )
    _write_sample_portfolio(path)


def _write_price_config(path: Path, price_path: str) -> None:
    path.joinpath("system.toml").write_text(
        f"""
database_url = "sqlite+aiosqlite:///{path / "web.db"}"
schedule_minutes = 30
web_host = "127.0.0.1"
web_port = 8000
log_level = "INFO"
llm_timeout_seconds = 60
workspace_root = "{path / "workspace"}"
retention_count = 20
retention_hours = 24
price_history_path = "{price_path}"
price_comparison_horizon_days = 7
price_comparison_threshold_percent = 1
""".lstrip()
    )
    _write_sample_portfolio(path)


def _write_sample_portfolio(path: Path) -> None:
    path.joinpath("portfolio.yaml").write_text(
        """
targets:
  - code: "00700.HK"
    name: "Tencent"
    sources:
      - sample-web
      - minimax-docs
sources:
  - name: sample-web
    type: web
    url: https://example.com/announcements.html
  - name: minimax-docs
    type: web
    url: https://platform.minimax.io/docs/api-reference/text-chat-openai
""".lstrip()
    )


def _portfolio_payload() -> dict[str, object]:
    return {
        "targets": [
            {
                "code": "00700.HK",
                "name": "Tencent",
                "holding": {"quantity": 100, "cost_price": 300},
                "sources": ["sample-rss"],
            }
        ],
        "sources": [
            {
                "name": "sample-rss",
                "type": "rss",
                "url": "https://example.com/feed.xml",
            }
        ],
    }


def _targets(payload: dict[str, object]) -> list[dict[str, Any]]:
    return payload["targets"]  # type: ignore[return-value]


def _copy_project_config(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    _copy_dir(Path.cwd() / "config", root / "config")
    _copy_dir(Path.cwd() / "skills", root / "skills")
    return root


def _copy_dir(source: Path, target: Path) -> None:
    target.mkdir(parents=True)
    for path in source.rglob("*"):
        relative = path.relative_to(source)
        dest = target / relative
        if path.is_dir():
            dest.mkdir()
        else:
            dest.write_text(path.read_text())
