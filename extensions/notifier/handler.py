from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from stockimformation_core.config.schema import RuntimeSettings
from stockimformation_types import HandlerContext

from _lib.models import Advice, Briefing


async def run(ctx: HandlerContext) -> list[dict[str, Any]]:
    payload = ctx.input.payload
    settings = ctx.entity_store.runtime
    if isinstance(payload, dict) and "content" in payload:
        briefing = Briefing.model_validate(payload)
        return [await _send_ntfy(settings, "周期简报"[:16], briefing.content, 3)]
    results: list[dict[str, Any]] = []
    for item in payload if isinstance(payload, list) else []:
        advice = Advice.model_validate(item)
        title, body, priority = _format_notification(advice)
        results.append(await _send_ntfy(settings, title, body, priority))
    if not results:
        results.append(await _send_ntfy(settings, "系统在线", "本周期无新信息，系统运行正常", 3))
    return results


def _priority_for_advice(advice: Advice) -> int:
    if advice.direction in {"buy", "sell"} and advice.confidence >= 0.75:
        return 5
    if advice.low_confidence:
        return 1
    return 3


def _format_notification(advice: Advice) -> tuple[str, str, int]:
    title = f"{advice.stock_name}{_direction_cn(advice.direction)}"[:16]
    body = (
        f"标的: {advice.stock_code} {advice.stock_name}\n"
        f"方向: {advice.direction}\n"
        f"核心原因: {advice.reason}\n"
        f"时间: {datetime.now(timezone.utc).isoformat()}\n"
        f"置信度: {advice.confidence:.2f}"
    )
    return title, body, _priority_for_advice(advice)


async def _send_ntfy(settings: RuntimeSettings, title: str, body: str, priority: int) -> dict[str, Any]:
    if not settings.ntfy_topic:
        return {"skipped": True, "reason": "missing ntfy topic", "title": title, "message": body}
    url = f"{settings.ntfy_url.rstrip('/')}/{settings.ntfy_topic}"
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(url, content=body, headers={"Title": title, "Priority": str(priority)})
        response.raise_for_status()
        return {"status_code": response.status_code, "title": title, "priority": priority}


def _direction_cn(direction: str) -> str:
    return {"buy": "买入", "sell": "卖出", "hold": "持有"}[direction]
