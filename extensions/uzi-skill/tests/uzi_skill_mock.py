from __future__ import annotations

from typing import Any


def preflight(ticker: str) -> dict[str, Any]:
    return {"ticker": ticker, "data": {"industry": "人工智能"}}


def fetch(ticker: str) -> dict[str, Any]:
    return {"ticker": ticker, "data": {"industry": "人工智能"}, "quality": "OK"}


def fetch_by_industry(industry: str) -> dict[str, Any]:
    return {"industry": industry, "quality": "OK"}


def passthrough(payload: Any) -> Any:
    return payload


def score(payload: Any) -> dict[str, Any]:
    return {"score": 80, "raw": payload}


def render(payload: Any) -> dict[str, Any]:
    return {"html": "<section>ok</section>", "payload": payload}


def assemble(payload: Any, *_args: Any) -> dict[str, Any]:
    return {"report_path": "/tmp/uzi-skill-report.html", "sections": payload}
