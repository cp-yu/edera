from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
import httpx

from edera_core.config.schema import EntityConfig, SystemConfig, entity_ref
from edera_types import EntityStoreProtocol

from _lib.models import RawItem

RECOVERABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def tags_for_source(entity_store: EntityStoreProtocol, source: EntityConfig) -> list[str]:
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


async def fetch_api_source(source: EntityConfig, tags: list[str]) -> list[RawItem]:
    base_url = str(source.attributes.get("base_url") or "")
    if not base_url:
        raise ValueError(f"missing api base_url: {_source_name(source)}")
    params = source.attributes.get("params", {})
    if not isinstance(params, dict):
        raise ValueError(f"api params must be object: {_source_name(source)}")
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(base_url, params=params)
        response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict) or data.get("code") != 200:
        raise ValueError(f"api source returned error: {_source_name(source)}")
    records = data.get("data")
    if not isinstance(records, list):
        raise ValueError(f"api source data must be list: {_source_name(source)}")
    return parse_api(records, source, tags)


async def fetch_with_recovery(
    source: EntityConfig,
    tags: list[str],
    system: SystemConfig,
) -> tuple[list[RawItem], dict[str, object]]:
    attempt_limit = system.source_recovery_max_attempts if system.source_recovery_enabled else 0
    attempt_count = 0
    first_reason: str | None = None
    last_error: str | None = None
    fetcher = _fetcher_for_source(source)
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
                return [], _recovery_summary("escalated", attempt_count, None, last_error, True, "non_recoverable")
            if attempt_count >= attempt_limit:
                return [], _recovery_summary("escalated", attempt_count, recoverable_reason, last_error, True, "recovery_exhausted")
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
        items.append(RawItem(url=url, title=title, content=body, source_name=source_name, source_type="rss", tags=entity_tags, published_at=_published_at(entry)))
    return items


def parse_web(content: str, source: EntityConfig, tags: list[str]) -> list[RawItem]:
    entity_tags = entity_tags_from_values(tags)
    url = str(source.attributes.get("url", ""))
    regex = source.attributes.get("regex")
    source_name = _source_name(source)
    if not regex:
        title = _strip_html(content)[:120] or url
        return [RawItem(url=url, title=title, content=_strip_html(content), source_name=source_name, source_type="web", tags=entity_tags, published_at=datetime.now(timezone.utc))]
    match = re.search(str(regex), content, flags=re.DOTALL)
    if not match:
        raise ValueError(f"web rule did not match source: {source_name}")
    data = match.groupdict()
    title = _strip_html(data.get("title") or match.group(0))[:120]
    body = _strip_html(data.get("content") or match.group(0))
    return [RawItem(url=data.get("url") or url, title=title, content=body, source_name=source_name, source_type="web", tags=entity_tags, published_at=datetime.now(timezone.utc))]


def parse_api(records: list[object], source: EntityConfig, tags: list[str]) -> list[RawItem]:
    entity_tags = entity_tags_from_values(tags)
    source_name = _source_name(source)
    items: list[RawItem] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        title = str(record.get("title") or "").strip()
        url = str(record.get("url") or record.get("id") or "").strip()
        if not title or not url:
            continue
        items.append(RawItem(url=url, title=title, content=_api_content(record, title), source_name=source_name, source_type="api", tags=entity_tags, published_at=_api_published_at(record)))
    return items


def dedupe_raw_items(items: list[RawItem]) -> list[RawItem]:
    seen: set[str] = set()
    unique: list[RawItem] = []
    for item in items:
        if item.url in seen:
            continue
        seen.add(item.url)
        unique.append(item)
    return unique


def source_map(entity_store: EntityStoreProtocol) -> dict[str, EntityConfig]:
    result: dict[str, EntityConfig] = {}
    for entity in entity_store.query():
        if entity.type not in {"rss-source", "web-source", "api-source"}:
            continue
        result[_source_name(entity)] = entity
        result[entity_ref(entity, entity_store.entity_types)] = entity
    return result


def fetcher_for_source(source: EntityConfig) -> Callable[[EntityConfig, list[str]], Any]:
    return _fetcher_for_source(source)


def entity_tags_from_values(values: list[str]) -> list[str]:
    return [value if ":" in value else f"stock:{value}" for value in values]


def _fetcher_for_source(source: EntityConfig) -> Callable[[EntityConfig, list[str]], Any]:
    if source.type == "rss-source":
        return fetch_rss_source
    if source.type == "web-source":
        return fetch_web_source
    if source.type == "api-source":
        return fetch_api_source
    raise ValueError(f"unsupported source type: {source.type}")


def _source_name(source: EntityConfig) -> str:
    return str(source.attributes.get("name") or source.id)


def _published_at(entry: Any) -> datetime:
    value = entry.get("published") or entry.get("updated")
    if value:
        try:
            parsed = parsedate_to_datetime(str(value))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            pass
    return datetime.now(timezone.utc)


def _api_content(record: dict[str, Any], title: str) -> str:
    extra = record.get("extra")
    if isinstance(extra, dict):
        for key in ("content", "desc", "brief"):
            value = extra.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return title


def _api_published_at(record: dict[str, Any]) -> datetime:
    extra = record.get("extra")
    value = record.get("pubDate")
    if value is None and isinstance(extra, dict):
        value = extra.get("date")
    if isinstance(value, int | float):
        return datetime.fromtimestamp(value / 1000, timezone.utc)
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
    if message.startswith("api source data must be list") or message.startswith("api source returned error"):
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
