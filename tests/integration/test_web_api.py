from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
import yaml
from httpx import ASGITransport, AsyncClient

from stockimformation.config.schema import SourceConfig
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
from stockimformation.services import collection
from stockimformation.web.app import create_app


class FakeController(PipelineController):
    async def start(self, run_startup: bool = True) -> None:
        self.engine = create_engine(sqlite_url(self.config_dir / "web.db"))
        await init_db(self.engine)
        self.factory = session_factory(self.engine)
        self.scheduler.start()

    async def start_run(self, trigger: str = "manual", dag_name: str = "default") -> str:
        async with self._locks[dag_name]:
            ctx = self.active_runs.get(dag_name)
            if ctx is not None and not ctx.task.done():
                raise RunAlreadyActiveError(ctx.cycle_id)
            cycle_id = "cycle-manual"
            task = asyncio.create_task(self._fake_run(cycle_id, trigger, dag_name))
            from stockimformation.pipeline import DagRunContext
            self.active_runs[dag_name] = DagRunContext(dag_name=dag_name, cycle_id=cycle_id, task=task)
            task.add_done_callback(lambda t: self._clear_finished_task(t, dag_name))
            return cycle_id

    async def _fake_run(self, cycle_id: str, trigger: str, dag_name: str = "default") -> None:
        async with self._factory()() as session:
            await create_pipeline_run(session, cycle_id, trigger, dag_name=dag_name)
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
        finally:
            await app.state.controller.shutdown()
    assert "events" in results_response.json()


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


@pytest.mark.asyncio
async def test_minimax_multi_source_llm_cycle_surfaces_web_features(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _copy_project_config(tmp_path)
    config_dir = root / "config"
    pi_bin = _write_fixture_pi(tmp_path)
    _write_minimax_multi_source_runtime(config_dir, tmp_path, pi_bin)
    monkeypatch.setenv("STOCKIMFORMATION_PI_BIN", str(pi_bin))
    fixture_by_source = {
        "minimax-docs": Path("tests/fixtures/minimax_text_chat.html").read_text(),
        "minimax-docs-index": Path("tests/fixtures/minimax_llms.txt").read_text(),
        "tonghuashun-minimax": Path("tests/fixtures/tonghuashun_minimax.html").read_text(),
    }
    monkeypatch.chdir(root)

    async def fixture_web_source(source: SourceConfig, stock_codes: list[str]) -> list[RawItem]:
        return collection.parse_web(fixture_by_source[source.name], source, stock_codes)

    monkeypatch.setattr(collection, "fetch_web_source", fixture_web_source)
    controller = PipelineController(config_dir)
    app = create_app(config_dir, controller, run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await controller.start(run_startup=False)
        try:
            cycle_id = await controller.run_now("manual")
            results = await client.get("/api/results")
            sources = await client.get("/api/sources/health")
            logs = await client.get("/api/sources/logs")
            pipeline_status = await client.get("/api/pipeline/status")
            advice = results.json()["advices"][0]
            advice_detail = await client.get(f"/api/advices/{advice['id']}")
            briefing = results.json()["briefing"]
            briefing_detail = await client.get(f"/api/briefings/{briefing['id']}")
        finally:
            await controller.shutdown()

    assert results.status_code == 200
    payload = results.json()
    expected_sources = ["minimax-docs", "minimax-docs-index", "tonghuashun-minimax"]
    expected_urls = [
        "https://platform.minimax.io/docs/api-reference/text-chat-openai",
        "https://platform.minimax.io/docs/llms.txt",
        "https://basic.10jqka.com.cn/176/HK0100/field.html",
    ]
    assert payload["briefing"]["cycle_id"] == cycle_id
    assert payload["advices"][0]["source_urls"] == expected_urls
    assert payload["advices"][0]["comparison"]["verdict"] == "unknown"
    assert payload["briefing"]["metadata_"]["configured_sources"] == expected_sources
    assert payload["failed_sources"] == {}
    assert advice_detail.status_code == 200
    assert [item["source_url"] for item in advice_detail.json()["analyses"]] == expected_urls
    assert "MiniMax-M2.7" in advice_detail.json()["raw_items"][0]["content"]
    assert "MINIMAX-WP" in advice_detail.json()["raw_items"][2]["title"]
    assert sources.status_code == 200
    health = {item["source_name"]: item for item in sources.json()["sources"]}
    assert set(health) == set(expected_sources)
    assert all(health[name]["latest_status"] == "succeeded" for name in expected_sources)
    assert all(health[name]["success_rate"] == 1.0 for name in expected_sources)
    assert logs.status_code == 200
    source_logs = {
        item["source_name"]: item for item in logs.json()["logs"] if item["source_name"] in expected_sources
    }
    assert set(source_logs) == set(expected_sources)
    assert all(item["pipeline_status"] == "succeeded" for item in source_logs.values())
    assert pipeline_status.status_code == 200
    assert pipeline_status.json()["recent_runs"][0]["status"] == "succeeded"
    assert briefing_detail.status_code == 200
    assert "minimax-docs" in briefing_detail.text


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
    _copy_dir(Path.cwd() / "handlers", root / "handlers")
    _copy_dir(Path.cwd() / "prompts", root / "prompts")
    _copy_dir(Path.cwd() / "skills", root / "skills")
    _copy_dir(Path.cwd() / "skill_handlers", root / "skill_handlers")
    return root


def _copy_dir(source: Path, target: Path) -> None:
    target.mkdir(parents=True)
    for path in source.rglob("*"):
        if "__pycache__" in path.parts:
            continue
        relative = path.relative_to(source)
        dest = target / relative
        if path.is_dir():
            dest.mkdir()
        else:
            dest.write_text(path.read_text())


def _write_fixture_pi(tmp_path: Path) -> Path:
    script = tmp_path / "pi"
    script.write_text(
        """#!/usr/bin/env python3
import json
import sys

payload = json.loads(sys.argv[-1])
items = payload["payload"]
results = []
for index, item in enumerate(items, start=1):
    content = item["content"]
    sentiment = "bearish" if "亏损" in content else "neutral"
    results.append({
        "raw_item_id": index,
        "summary": item["title"],
        "keywords": ["MiniMax", item["source_name"]],
        "sentiment": sentiment,
        "confidence": 0.72,
        "source_quote": content[:80],
        "source_url": item["url"],
        "rationale": "fixture llm output",
        "contradiction": False,
    })
print(json.dumps(results, ensure_ascii=False))
"""
    )
    script.chmod(0o755)
    return script


def _write_minimax_multi_source_runtime(config_dir: Path, tmp_path: Path, pi_bin: Path) -> None:
    config_dir.joinpath("system.toml").write_text(
        f"""
database_url = "sqlite+aiosqlite:///{tmp_path / "minimax.db"}"
schedule_minutes = 30
web_host = "127.0.0.1"
web_port = 8000
log_level = "INFO"
llm_timeout_seconds = 60
workspace_root = "{tmp_path / "workspace"}"
retention_count = 20
retention_hours = 24
""".lstrip()
    )
    config_dir.joinpath("portfolio.yaml").write_text(
        """
targets:
  - code: "00700.HK"
    name: "Tencent"
    holding:
      quantity: 100
      cost_price: 300
    sources:
      - minimax-docs
      - minimax-docs-index
      - tonghuashun-minimax
sources:
  - name: minimax-docs
    type: web
    url: https://platform.minimax.io/docs/api-reference/text-chat-openai
    regex: '<main[^>]*>.*?(?P<title>Text Chat \\(Compatible OpenAI API\\)).*?(?P<content>Bearer Auth.*?MiniMax-M2\\.7.*?)</main>'
  - name: minimax-docs-index
    type: web
    url: https://platform.minimax.io/docs/llms.txt
    regex: '(?P<title># MiniMax API Docs).*?(?P<content>Text Chat \\(Compatible OpenAI API\\).*?MiniMax-M2\\.7.*?)$'
  - name: tonghuashun-minimax
    type: web
    url: https://basic.10jqka.com.cn/176/HK0100/field.html
    regex: '(?P<title>MINIMAX-WP).*?(?P<content>亏损.*?)"'
""".lstrip()
    )
    dag_path = config_dir / "dags" / "default.yaml"
    dag = yaml.safe_load(dag_path.read_text())
    for node in dag["nodes"]:
        if node["type"] == "rss-fetcher":
            node["config"]["source_names"] = []
        if node["type"] == "web-scraper":
            node["config"]["source_names"] = [
                "minimax-docs",
                "minimax-docs-index",
                "tonghuashun-minimax",
            ]
    dag_path.write_text(yaml.safe_dump(dag, allow_unicode=True, sort_keys=False))


@pytest.mark.asyncio
async def test_web_graph_nodes_api_returns_prototypes(tmp_path: Path) -> None:
    root = _copy_project_config(tmp_path)
    app = create_app(root / "config", FakeController(root / "config"), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            response = await client.get("/api/graph/nodes")
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 200
    data = response.json()
    assert "prototypes" in data
    names = [p["name"] for p in data["prototypes"]]
    assert "rss-fetcher" in names
    assert "reader" in names
    assert "advisor" in names


@pytest.mark.asyncio
async def test_web_graph_dag_api_round_trip(tmp_path: Path) -> None:
    root = _copy_project_config(tmp_path)
    app = create_app(root / "config", FakeController(root / "config"), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            dag_response = await client.get("/api/graph/dag/default")
            state = dag_response.json()
            node_id = state["nodes"][0]["id"]
            state["ui"] = {"nodes": {node_id: {"x": 100, "y": 200}}}
            save_response = await client.put("/api/graph/dag/default", json=state)
        finally:
            await app.state.controller.shutdown()
    assert dag_response.status_code == 200
    assert state["name"] == "default"
    assert len(state["nodes"]) > 0
    assert len(state["edges"]) > 0
    assert save_response.status_code == 200
    saved = save_response.json()
    assert saved["dag"]["ui"]["nodes"][node_id]["x"] == 100


@pytest.mark.asyncio
async def test_web_graph_dag_save_rejects_cycle(tmp_path: Path) -> None:
    root = _copy_project_config(tmp_path)
    dag_path = root / "config" / "dags" / "default.yaml"
    original = dag_path.read_text()
    app = create_app(root / "config", FakeController(root / "config"), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            response = await client.put(
                "/api/graph/dag/default",
                json={
                    "nodes": [
                        {"id": "source-instance", "type": "rss-fetcher", "alias": "rss-fetcher", "config": {}},
                        {"id": "reader-instance", "type": "reader", "alias": "reader", "config": {}},
                    ],
                    "edges": [
                        {"from": "source-instance", "to": "reader-instance"},
                        {"from": "reader-instance", "to": "source-instance"},
                    ],
                },
            )
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 400
    assert response.json()["error"]["type"] == "config_error"
    assert dag_path.read_text() == original


@pytest.mark.asyncio
async def test_web_graph_dag_save_rejects_unknown_node(tmp_path: Path) -> None:
    root = _copy_project_config(tmp_path)
    dag_path = root / "config" / "dags" / "default.yaml"
    original = dag_path.read_text()
    app = create_app(root / "config", FakeController(root / "config"), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            response = await client.put(
                "/api/graph/dag/default",
                json={
                    "nodes": [
                        {"id": "source-instance", "type": "rss-fetcher", "alias": "rss-fetcher", "config": {}},
                        {"id": "missing-instance", "type": "missing-node", "alias": "missing-node", "config": {}},
                    ],
                    "edges": [{"from": "source-instance", "to": "missing-instance"}],
                },
            )
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 400
    assert "missing node config" in response.json()["error"]["message"]
    assert dag_path.read_text() == original


@pytest.mark.asyncio
async def test_web_graph_node_read_and_save(tmp_path: Path) -> None:
    root = _copy_project_config(tmp_path)
    app = create_app(root / "config", FakeController(root / "config"), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            read_response = await client.get("/api/graph/node/reader")
            node = read_response.json()["node"]
            node["timeout_seconds"] = 45.0
            save_response = await client.put("/api/graph/node/reader", json=node)
        finally:
            await app.state.controller.shutdown()
    assert read_response.status_code == 200
    assert node["name"] == "reader"
    assert save_response.status_code == 200
    assert save_response.json()["node"]["timeout_seconds"] == 45.0


@pytest.mark.asyncio
async def test_web_graph_node_save_rejects_invalid(tmp_path: Path) -> None:
    root = _copy_project_config(tmp_path)
    original = (root / "config" / "nodes" / "reader.yaml").read_text()
    app = create_app(root / "config", FakeController(root / "config"), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            response = await client.put(
                "/api/graph/node/reader",
                json={
                    "skills": ["summarize"],
                    "parameters": {"api_token": "secret123"},
                },
            )
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 400
    assert response.json()["error"]["type"] == "config_error"
    assert (root / "config" / "nodes" / "reader.yaml").read_text() == original


@pytest.mark.asyncio
async def test_web_graph_runtime_status_maps_nodes(tmp_path: Path) -> None:
    root = _copy_project_config(tmp_path)
    fetcher_id = "0194f7a6-7b17-7c01-b601-000000000001"
    reader_id = "0194f7a6-7b17-7c01-b601-000000000003"
    app = create_app(root / "config", FakeController(root / "config"), run_startup=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await app.state.controller.start(run_startup=False)
        try:
            async with app.state.controller._factory()() as session:
                await create_pipeline_run(session, "cycle-graph", "manual", [fetcher_id, reader_id])
                await mark_node_run(session, "cycle-graph", fetcher_id, "succeeded")
                await mark_node_run(session, "cycle-graph", reader_id, "failed", "timeout")
                await finish_pipeline_run(session, "cycle-graph", "failed")
                await session.commit()
            response = await client.get("/api/graph/runtime-status")
        finally:
            await app.state.controller.shutdown()
    assert response.status_code == 200
    statuses = response.json()["node_statuses"]
    assert set(statuses) == {fetcher_id, reader_id}
    assert "rss-fetcher" not in statuses
    assert "reader" not in statuses
    assert statuses[fetcher_id]["status"] == "succeeded"
    assert statuses[reader_id]["status"] == "failed"
    assert statuses[reader_id]["error"] == "timeout"
    assert statuses[reader_id]["cycle_id"] == "cycle-graph"
