from __future__ import annotations

from typing import Any

from edera_types import HandlerContext

from _lib.http_fetch import dedupe_raw_items, fetch_with_recovery, source_map, tags_for_source


async def run(ctx: HandlerContext) -> list[dict[str, Any]]:
    max_items = _positive_int(ctx.params.get("max_items_per_source"))
    source_names = ctx.input.payload.get("source_names", []) if isinstance(ctx.input.payload, dict) else []
    sources = source_map(ctx.entity_store)
    items = []
    failures = ctx.input.metadata.setdefault("failures", {})
    recovery = ctx.input.metadata.setdefault("source_recovery", {})
    for name in source_names:
        source = sources[name]
        if source.type != "api-source":
            continue
        fetched, summary = await fetch_with_recovery(source, tags_for_source(ctx.entity_store, source), ctx.entity_store.system)
        source_name = str(source.attributes.get("name") or source.id)
        recovery[source_name] = summary
        if summary["recovery_status"] == "escalated":
            failures[source_name] = str(summary["latest_failure_reason"])
        items.extend(fetched[:max_items] if max_items is not None else fetched)
    return [item.model_dump(mode="json") for item in dedupe_raw_items(items)]


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value > 0 else None
