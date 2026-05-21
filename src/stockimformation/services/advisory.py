from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from stockimformation.config.entities import EntityStore
from stockimformation.config.schema import EntityConfig
from stockimformation.models.entities import Advice, AnalysisResult
from stockimformation.node.models import FunctionHandler, NodeInput


def generate_advice(
    target: EntityConfig,
    analyses: list[AnalysisResult],
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> Advice:
    now = datetime.now(timezone.utc)
    window_start = window_start or now
    window_end = window_end or now
    relevant = [item for item in analyses if item.source_quote and item.source_url]
    bullish = sum(1 for item in relevant if item.sentiment == "bullish")
    bearish = sum(1 for item in relevant if item.sentiment == "bearish")
    raw_holding = target.attributes.get("holding")
    holding = raw_holding if isinstance(raw_holding, dict) else {"quantity": 0}
    if not relevant:
        direction = "hold"
        confidence = 0.35
        reason = "本周期无新增信息"
        evidence = [0]
        quotes = ["本周期无新增信息"]
        urls = ["about:blank"]
    elif bearish > bullish and (holding.get("quantity") or 0) > 0:
        direction = "sell"
        confidence = min(0.95, 0.55 + bearish * 0.15)
        reason = "利空信号占优且当前持仓暴露存在风险"
        evidence, quotes, urls = _evidence(relevant)
    elif bullish > bearish and not (holding.get("quantity") or 0):
        direction = "buy"
        confidence = min(0.95, 0.55 + bullish * 0.15)
        reason = "利好信号占优且当前未持仓"
        evidence, quotes, urls = _evidence(relevant)
    else:
        direction = "hold"
        confidence = 0.55
        reason = "信号不足以支持买入或卖出"
        evidence, quotes, urls = _evidence(relevant)
    return Advice(
        stock_code=str(target.attributes.get("code", "")),
        stock_name=str(target.attributes.get("name", "")),
        direction=direction,
        confidence=confidence,
        reason=reason,
        evidence=evidence,
        source_quotes=quotes,
        source_urls=urls,
        portfolio_snapshot=holding | {"watch_only": raw_holding is None},
        low_confidence=confidence < 0.5,
        data_window_start=window_start,
        data_window_end=window_end,
    )


def make_advice_handler(entity_store: EntityStore) -> FunctionHandler:
    async def handler(node_input: NodeInput) -> list[dict[str, Any]]:
        analyses = [
            AnalysisResult.model_validate(item)
            for item in (node_input.payload if isinstance(node_input.payload, list) else [])
        ]
        return [
            generate_advice(target, analyses).model_dump(mode="json")
            for target in entity_store.entities.entities
            if target.type == "stock"
        ]

    return handler


def _evidence(analyses: list[AnalysisResult]) -> tuple[list[int], list[str], list[str]]:
    return (
        [item.id or item.raw_item_id for item in analyses],
        [item.source_quote for item in analyses],
        [item.source_url for item in analyses],
    )
