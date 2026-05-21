from __future__ import annotations

import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
import httpx

from stockimformation.config.entities import EntityStore
from stockimformation.config.schema import EntityConfig, SystemConfig, entity_ref
from stockimformation.models.entities import RawItem
from stockimformation.node.models import FunctionHandler, NodeInput

RECOVERABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def tags_for_source(entity_store: EntityStore, source: EntityConfig) -> list[str]:
    return [
        ref
        for ref in entity_store.related_refs(entity_ref(source, entity_store.entity_types))
        if ref.startswith("stock:")
    ]


async def fetch_rss_source(source: EntityConfig, tags: list[str]) -> list[RawItem]:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(str(source.attributes.get("url", "")))
        response.raise_for_status()
    return parse_rss(response.text, _source_name(source), tags)


async def fetch_web_source(source: EntityConfig, tags: list[str]) -> list[RawItem]:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(str(source.attributes.get("url", "")))
        response.raise_for_status()
    return parse_web(response.text, source, tags)


async def fetch_source_with_recovery(
    source: EntityConfig,
    tags: list[str],
    system: SystemConfig,
) -> tuple[list[RawItem], dict[str, object]]:
    attempt_limit = system.source_recovery_max_attempts if system.source_recovery_enabled else 0
    attempt_count = 0
    first_reason: str | None = None
    last_error: str | None = None
    fetcher = fetch_rss_source if source.type == "rss-source" else fetch_web_source
    while True:
        try:
            items = await fetcher(source, tags)
            if not items:
                raise ValueError(f"empty source result: {_source_name(source)}")
            status = "recovered" if attempt_count else "none"
            return items, _recovery_summary(status, attempt_count, first_reason, last_error)
        except Exception as exc:
            last_error = str(exc)
            recoverable_reason = _recoverable_reason(exc)
            if first_reason is None:
                first_reason = recoverable_reason
            if recoverable_reason is None:
                return [], _recovery_summary(
                    "escalated",
                    attempt_count,
                    None,
                    last_error,
                    escalated=True,
                    escalation_reason="non_recoverable",
                )
            if attempt_count >= attempt_limit:
                return [], _recovery_summary(
                    "escalated",
                    attempt_count,
                    recoverable_reason,
                    last_error,
                    escalated=True,
                    escalation_reason="recovery_exhausted",
                )
            attempt_count += 1


def parse_rss(content: str, source_name: str, tags: list[str]) -> list[RawItem]:
    feed = feedparser.parse(content)
    entity_tags = entity_tags_from_values(tags)
    items: list[RawItem] = []
    for entry in feed.entries:
        url = str(entry.get("link") or entry.get("id") or "")
        title = str(entry.get("title") or "").strip()
        body = str(entry.get("summary") or entry.get("description") or title).strip()
        if not url or not title:
            continue
        items.append(
            RawItem(
                url=url,
                title=title,
                content=body,
                source_name=source_name,
                source_type="rss",
                tags=entity_tags,
                published_at=_published_at(entry),
            )
        )
    return items


def parse_web(content: str, source: EntityConfig, tags: list[str]) -> list[RawItem]:
    entity_tags = entity_tags_from_values(tags)
    url = str(source.attributes.get("url", ""))
    regex = source.attributes.get("regex")
    source_name = _source_name(source)
    if not regex:
        title = _strip_html(content)[:120] or url
        return [
            RawItem(
                url=url,
                title=title,
                content=_strip_html(content),
                source_name=source_name,
                source_type="web",
                tags=entity_tags,
                published_at=datetime.now(timezone.utc),
            )
        ]
    match = re.search(str(regex), content, flags=re.DOTALL)
    if not match:
        raise ValueError(f"web rule did not match source: {source_name}")
    data = match.groupdict()
    title = _strip_html(data.get("title") or match.group(0))[:120]
    body = _strip_html(data.get("content") or match.group(0))
    url = data.get("url") or url
    return [
        RawItem(
            url=url,
            title=title,
            content=body,
            source_name=source_name,
            source_type="web",
            tags=entity_tags,
            published_at=datetime.now(timezone.utc),
        )
    ]


def make_fetch_handler(
    entity_store: EntityStore,
    source_type: str,
    system: SystemConfig | None = None,
) -> FunctionHandler:
    async def handler(node_input: NodeInput) -> list[dict[str, Any]]:
        source_names = node_input.payload.get("source_names", []) if isinstance(node_input.payload, dict) else []
        source_map = _source_map(entity_store)
        items: list[RawItem] = []
        failures = node_input.metadata.setdefault("failures", {})
        recovery = node_input.metadata.setdefault("source_recovery", {})
        for name in source_names:
            source = source_map[name]
            if source.type != f"{source_type}-source":
                continue
            tags = tags_for_source(entity_store, source)
            if system is None:
                fetched = (
                    await fetch_rss_source(source, tags)
                    if source.type == "rss-source"
                    else await fetch_web_source(source, tags)
                )
            else:
                fetched, summary = await fetch_source_with_recovery(source, tags, system)
                recovery[_source_name(source)] = summary
                if summary["recovery_status"] == "escalated":
                    failures[_source_name(source)] = str(summary["latest_failure_reason"])
            items.extend(fetched)
        return [item.model_dump(mode="json") for item in dedupe_raw_items(items)]

    return handler


def dedupe_raw_items(items: list[RawItem]) -> list[RawItem]:
    seen: set[str] = set()
    unique: list[RawItem] = []
    for item in items:
        if item.url in seen:
            continue
        seen.add(item.url)
        unique.append(item)
    return unique


def entity_tags_from_values(values: list[str]) -> list[str]:
    return [stock_tag(value) for value in values]


def stock_tag(value: str) -> str:
    return value if ":" in value else f"stock:{value}"


def _source_name(source: EntityConfig) -> str:
    return str(source.attributes.get("name") or source.id)


def _source_map(entity_store: EntityStore) -> dict[str, EntityConfig]:
    result: dict[str, EntityConfig] = {}
    for entity in entity_store.entities.entities:
        if entity.type not in {"rss-source", "web-source"}:
            continue
        result[_source_name(entity)] = entity
        result[entity_ref(entity, entity_store.entity_types)] = entity
    return result


def _published_at(entry: Any) -> datetime:
    value = entry.get("published") or entry.get("updated")
    if value:
        try:
            parsed = parsedate_to_datetime(str(value))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            pass
    return datetime.now(timezone.utc)


def _strip_html(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value)).strip()


def _recoverable_reason(exc: Exception) -> str | None:
    if isinstance(exc, (TimeoutError, httpx.TimeoutException)):
        return "timeout"
    if isinstance(exc, httpx.NetworkError):
        return "network"
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return f"http_{code}" if code in RECOVERABLE_STATUS_CODES else None
    message = str(exc).lower()
    if "empty source result" in message:
        return "empty"
    if "web rule did not match source" in message:
        return "parse"
    return None


def _recovery_summary(
    status: str,
    attempt_count: int,
    recoverable_reason: str | None,
    latest_failure_reason: str | None,
    escalated: bool = False,
    escalation_reason: str | None = None,
) -> dict[str, object]:
    return {
        "recovery_status": status,
        "attempt_count": attempt_count,
        "recoverable_reason": recoverable_reason,
        "latest_failure_reason": latest_failure_reason,
        "escalated": escalated,
        "escalation_reason": escalation_reason,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
