from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from stockimformation.config.entities import EntityStore
from stockimformation.models.entities import Advice, Briefing
from stockimformation.node.models import FunctionHandler, NodeInput

DISCLAIMER = "本系统产出仅供学习参考，不构成投资建议。"


def generate_briefing(
    cycle_id: str,
    advices: list[Advice],
    entity_store: EntityStore,
    failures: dict[str, str] | None = None,
    source_recovery: dict[str, object] | None = None,
) -> Briefing:
    failures = failures or {}
    source_recovery = source_recovery or {}
    lines: list[str] = [f"周期: {cycle_id}", ""]
    by_code = {advice.stock_code: advice for advice in advices}
    stocks = [entity for entity in entity_store.entities.entities if entity.type == "stock"]
    sources = [entity for entity in entity_store.entities.entities if entity.type in {"rss-source", "web-source"}]
    for target in stocks:
        code = str(target.attributes.get("code", ""))
        name = str(target.attributes.get("name", ""))
        advice = by_code.get(code)
        if advice is None:
            lines.append(f"{code} {name}: 本周期无新增信息")
            continue
        lines.append(
            f"{code} {name}: {advice.direction} "
            f"confidence={advice.confidence:.2f} {advice.reason}"
        )
    source_names = [str(source.attributes.get("name") or source.id) for source in sources]
    metadata = {
        "configured_sources": source_names,
        "successful_sources": [
            source_name for source_name in source_names if source_name not in failures
        ],
        "failed_sources": failures,
        "source_recovery": source_recovery,
        "escalated_sources": {
            source_name: summary
            for source_name, summary in source_recovery.items()
            if isinstance(summary, dict) and summary.get("escalated")
        },
        "data_window": {
            "start": min((advice.data_window_start for advice in advices), default=datetime.now(timezone.utc)),
            "end": max((advice.data_window_end for advice in advices), default=datetime.now(timezone.utc)),
        },
    }
    lines.extend(["", "元数据:", str(metadata), "", DISCLAIMER])
    return Briefing(cycle_id=cycle_id, content="\n".join(lines), metadata_=metadata)


def make_briefing_handler(entity_store: EntityStore) -> FunctionHandler:
    async def handler(node_input: NodeInput) -> dict[str, Any]:
        advices = [
            Advice.model_validate(item)
            for item in (node_input.payload if isinstance(node_input.payload, list) else [])
        ]
        briefing = generate_briefing(
            node_input.cycle_id,
            advices,
            entity_store,
            node_input.metadata.get("failures", {}),
            node_input.metadata.get("source_recovery", {}),
        )
        return briefing.model_dump(mode="json", by_alias=True)

    return handler
