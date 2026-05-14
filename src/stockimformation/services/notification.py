from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from stockimformation.config.schema import RuntimeSettings
from stockimformation.models.entities import Advice, Briefing
from stockimformation.node.models import FunctionHandler, NodeInput


def priority_for_advice(advice: Advice) -> int:
    if advice.direction in {"buy", "sell"} and advice.confidence >= 0.75:
        return 5
    if advice.low_confidence:
        return 1
    return 3


def format_notification(advice: Advice) -> tuple[str, str, int]:
    title = f"{advice.stock_name}{_direction_cn(advice.direction)}"[:16]
    body = (
        f"标的: {advice.stock_code} {advice.stock_name}\n"
        f"方向: {advice.direction}\n"
        f"核心原因: {advice.reason}\n"
        f"时间: {datetime.now(timezone.utc).isoformat()}\n"
        f"置信度: {advice.confidence:.2f}"
    )
    return title, body, priority_for_advice(advice)


async def send_ntfy(settings: RuntimeSettings, title: str, body: str, priority: int) -> dict[str, Any]:
    if not settings.ntfy_topic:
        return {"skipped": True, "reason": "missing ntfy topic", "title": title, "message": body}
    url = f"{settings.ntfy_url.rstrip('/')}/{settings.ntfy_topic}"
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(url, content=body, headers={"Title": title, "Priority": str(priority)})
        response.raise_for_status()
        return {"status_code": response.status_code, "title": title, "priority": priority}


def make_notify_handler(settings: RuntimeSettings) -> FunctionHandler:
    async def handler(node_input: NodeInput) -> list[dict[str, Any]]:
        payload = node_input.payload
        if isinstance(payload, dict) and "content" in payload:
            briefing = Briefing.model_validate(payload)
            return [
                await send_ntfy(settings, "周期简报"[:16], briefing.content, 3),
            ]
        results: list[dict[str, Any]] = []
        for item in payload if isinstance(payload, list) else []:
            advice = Advice.model_validate(item)
            title, body, priority = format_notification(advice)
            results.append(await send_ntfy(settings, title, body, priority))
        if not results:
            results.append(await send_ntfy(settings, "系统在线", "本周期无新信息，系统运行正常", 3))
        return results

    return handler


def _direction_cn(direction: str) -> str:
    return {"buy": "买入", "sell": "卖出", "hold": "持有"}[direction]
