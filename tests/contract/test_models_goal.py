from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from stockimformation.goal import run_goal_gate
from stockimformation.models.entities import Advice, AnalysisResult


def test_llm_output_schema() -> None:
    result = AnalysisResult(
        raw_item_id=1,
        summary="summary",
        keywords=["profit"],
        sentiment="bullish",
        confidence=0.8,
        source_quote="quote",
        source_url="https://example.com/a",
    )
    assert result.source_url


def test_analysis_result_trace_fields_required() -> None:
    with pytest.raises(ValidationError):
        AnalysisResult.model_validate(
            {
                "raw_item_id": 1,
                "summary": "summary",
                "keywords": ["profit"],
                "sentiment": "bullish",
                "confidence": 0.8,
                "source_quote": "",
                "source_url": "https://example.com/a",
            }
        )


def test_advice_audit_fields_required() -> None:
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        Advice.model_validate(
            {
                "stock_code": "00700.HK",
                "stock_name": "Tencent",
                "direction": "buy",
                "confidence": 0.8,
                "reason": "reason",
                "evidence": [],
                "source_quotes": [],
                "source_urls": [],
                "portfolio_snapshot": {"quantity": 0},
                "data_window_start": now,
                "data_window_end": now,
            }
        )


def test_credentials_not_committed() -> None:
    gitignore = Path(".gitignore").read_text()
    assert ".env" in gitignore
    assert Path(".env.example").exists()


def test_goal_gate_p1_mapping() -> None:
    report = run_goal_gate(Path("_bmad-output/planning-artifacts/prd-validation-report.md"))
    assert report.ok
    assert len(report.mapping) == 19
    assert "FR46" in report.mapping


def test_goal_gate_blocks_critical_prd_report(tmp_path: Path) -> None:
    report_path = tmp_path / "prd-validation-report.md"
    report_path.write_text("---\noverallStatus: 'Critical'\n---\n")
    report = run_goal_gate(report_path)
    assert not report.ok
    assert report.blockers == ["PRD validation overallStatus is Critical"]
