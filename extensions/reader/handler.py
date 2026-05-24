from __future__ import annotations

import re
from typing import Any

from stockimformation_types import HandlerContext

from _lib.models import AnalysisResult, RawItem


async def run(ctx: HandlerContext) -> list[dict[str, Any]]:
    payload = ctx.input.payload if isinstance(ctx.input.payload, list) else [ctx.input.payload]
    results: list[dict[str, Any]] = []
    for index, item in enumerate(payload, start=1):
        raw = RawItem.model_validate(item)
        results.append(_analyze_raw_item(raw, raw.id or index).model_dump(mode="json"))
    return results


def _analyze_raw_item(raw_item: RawItem, raw_item_id: int) -> AnalysisResult:
    text = f"{raw_item.title} {raw_item.content}"
    sentiment = _classify_sentiment(text)
    quote = raw_item.content[:160] or raw_item.title
    return AnalysisResult(
        raw_item_id=raw_item_id,
        summary=_summarize_text(raw_item.content or raw_item.title),
        keywords=_keywords(text),
        sentiment=sentiment,
        confidence=0.8 if sentiment != "neutral" else 0.55,
        source_quote=quote,
        source_url=raw_item.url,
        rationale=quote,
        contradiction=_has_contradiction(text),
    )


def _summarize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()[:200]


def _keywords(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z0-9\u4e00-\u9fff]{2,}", text)
    result: list[str] = []
    for word in words:
        if word not in result:
            result.append(word)
        if len(result) == 10:
            break
    return result


def _classify_sentiment(text: str) -> str:
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
    return any(word in lower for word in ("增长", "positive", "beat")) and any(word in lower for word in ("下跌", "negative", "miss"))
