from __future__ import annotations

import re
from typing import Any

from stockimformation.models.entities import AnalysisResult, RawItem
from stockimformation.node.models import NodeInput


def analyze_raw_item(raw_item: RawItem, raw_item_id: int | None = None) -> AnalysisResult:
    text = f"{raw_item.title} {raw_item.content}"
    sentiment = classify_sentiment(text)
    summary = summarize_text(raw_item.content or raw_item.title)
    quote = raw_item.content[:160] or raw_item.title
    return AnalysisResult(
        raw_item_id=raw_item_id or raw_item.id or 0,
        summary=summary,
        keywords=keywords(text),
        sentiment=sentiment,
        confidence=0.8 if sentiment != "neutral" else 0.55,
        source_quote=quote,
        source_url=raw_item.url,
        rationale=quote,
        contradiction=_has_contradiction(text),
    )


async def analyze_handler(node_input: NodeInput) -> list[dict[str, Any]]:
    payload = node_input.payload if isinstance(node_input.payload, list) else [node_input.payload]
    results: list[dict[str, Any]] = []
    for index, item in enumerate(payload, start=1):
        raw = RawItem.model_validate(item)
        results.append(analyze_raw_item(raw, raw.id or index).model_dump(mode="json"))
    return results


def summarize_text(text: str) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    return clean[:200]


def keywords(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z0-9\u4e00-\u9fff]{2,}", text)
    result: list[str] = []
    for word in words:
        if word not in result:
            result.append(word)
        if len(result) == 10:
            break
    return result


def classify_sentiment(text: str) -> str:
    lower = text.lower()
    positive = ("增长", "利好", "上调", "盈利", "buy", "positive", "beat", "surge")
    negative = ("下跌", "利空", "亏损", "监管", "sell", "negative", "miss", "drop")
    pos = any(word in lower for word in positive)
    neg = any(word in lower for word in negative)
    if pos and not neg:
        return "bullish"
    if neg and not pos:
        return "bearish"
    return "neutral"


def _has_contradiction(text: str) -> bool:
    lower = text.lower()
    return any(word in lower for word in ("增长", "positive", "beat")) and any(
        word in lower for word in ("下跌", "negative", "miss")
    )
