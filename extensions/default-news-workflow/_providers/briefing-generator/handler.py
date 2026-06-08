from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from edera_types import HandlerContext

from _lib.models import Advice, Briefing

DISCLAIMER = "本系统产出仅供学习参考，不构成投资建议。"


async def run(ctx: HandlerContext) -> dict[str, Any]:
    advices = [
        Advice.model_validate(item)
        for item in (ctx.input.payload if isinstance(ctx.input.payload, list) else [])
    ]
    lines: list[str] = [f"运行: {ctx.input.run_id}", ""]
    by_code = {advice.stock_code: advice for advice in advices}
    stocks = ctx.entity_store.query("stock")
    sources = [
        entity
        for entity in ctx.entity_store.query()
        if entity.type in {"rss-source", "web-source", "api-source"}
    ]
    for target in stocks:
        code = str(target.attributes.get("code", ""))
        name = str(target.attributes.get("name", ""))
        advice = by_code.get(code)
        if advice is None:
            lines.append(f"{code} {name}: 本周期无新增信息")
            continue
        lines.append(f"{code} {name}: {advice.direction} confidence={advice.confidence:.2f} {advice.reason}")
    failures = ctx.input.metadata.get("failures", {})
    source_names = [str(source.attributes.get("name") or source.id) for source in sources]
    metadata = {
        "configured_sources": source_names,
        "successful_sources": [source_name for source_name in source_names if source_name not in failures],
        "failed_sources": failures,
        "data_window": {
            "start": min((advice.data_window_start for advice in advices), default=datetime.now(timezone.utc)),
            "end": max((advice.data_window_end for advice in advices), default=datetime.now(timezone.utc)),
        },
    }
    lines.extend(["", "元数据:", str(metadata), "", DISCLAIMER])
    briefing = Briefing(run_id=ctx.input.run_id, content="\n".join(lines), metadata=metadata)
    return briefing.model_dump(mode="json", by_alias=True)
