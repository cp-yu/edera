from __future__ import annotations

import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
import httpx

from stockimformation.config.schema import PortfolioConfig, SourceConfig, SystemConfig
from stockimformation.models.entities import RawItem
from stockimformation.node.models import FunctionHandler, NodeInput

RECOVERABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def stock_codes_for_source(portfolio: PortfolioConfig, source_name: str) -> list[str]:
    return [target.code for target in portfolio.targets if source_name in target.sources]


async def fetch_rss_source(source: SourceConfig, stock_codes: list[str]) -> list[RawItem]:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(str(source.url))
        response.raise_for_status()
    return parse_rss(response.text, source.name, stock_codes)


async def fetch_web_source(source: SourceConfig, stock_codes: list[str]) -> list[RawItem]:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(str(source.url))
        response.raise_for_status()
    return parse_web(response.text, source, stock_codes)


async def fetch_source_with_recovery(
    source: SourceConfig,
    stock_codes: list[str],
    system: SystemConfig,
) -> tuple[list[RawItem], dict[str, object]]:
    attempt_limit = system.source_recovery_max_attempts if system.source_recovery_enabled else 0
    attempt_count = 0
    first_reason: str | None = None
    last_error: str | None = None
    fetcher = fetch_rss_source if source.type == "rss" else fetch_web_source
    while True:
        try:
            items = await fetcher(source, stock_codes)
            if not items:
                raise ValueError(f"empty source result: {source.name}")
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


def parse_rss(content: str, source_name: str, stock_codes: list[str]) -> list[RawItem]:
    feed = feedparser.parse(content)
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
                stock_codes=stock_codes,
                published_at=_published_at(entry),
            )
        )
    return items


def parse_web(content: str, source: SourceConfig, stock_codes: list[str]) -> list[RawItem]:
    if not source.regex:
        title = _strip_html(content)[:120] or str(source.url)
        return [
            RawItem(
                url=str(source.url),
                title=title,
                content=_strip_html(content),
                source_name=source.name,
                source_type="web",
                stock_codes=stock_codes,
                published_at=datetime.now(timezone.utc),
            )
        ]
    match = re.search(source.regex, content, flags=re.DOTALL)
    if not match:
        raise ValueError(f"web rule did not match source: {source.name}")
    data = match.groupdict()
    title = _strip_html(data.get("title") or match.group(0))[:120]
    body = _strip_html(data.get("content") or match.group(0))
    url = data.get("url") or str(source.url)
    return [
        RawItem(
            url=url,
            title=title,
            content=body,
            source_name=source.name,
            source_type="web",
            stock_codes=stock_codes,
            published_at=datetime.now(timezone.utc),
        )
    ]


def make_fetch_handler(
    portfolio: PortfolioConfig,
    source_type: str,
    system: SystemConfig | None = None,
) -> FunctionHandler:
    async def handler(node_input: NodeInput) -> list[dict[str, Any]]:
        source_names = node_input.payload.get("source_names", []) if isinstance(node_input.payload, dict) else []
        source_map = portfolio.source_map()
        items: list[RawItem] = []
        failures = node_input.metadata.setdefault("failures", {})
        recovery = node_input.metadata.setdefault("source_recovery", {})
        for name in source_names:
            source = source_map[name]
            if source.type != source_type:
                continue
            codes = stock_codes_for_source(portfolio, source.name)
            if system is None:
                fetched = (
                    await fetch_rss_source(source, codes)
                    if source.type == "rss"
                    else await fetch_web_source(source, codes)
                )
            else:
                fetched, summary = await fetch_source_with_recovery(source, codes, system)
                recovery[source.name] = summary
                if summary["recovery_status"] == "escalated":
                    failures[source.name] = str(summary["latest_failure_reason"])
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
