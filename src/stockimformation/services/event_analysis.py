from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from stockimformation.models.entities import AnalysisResult, EventRecord, RawItem

WINDOW_HOURS = 72
CLIMAX_THRESHOLD = 80
FADING_THRESHOLD = 18
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9\u4e00-\u9fff]{2,}")
EVENT_STATUSES = {"discovered", "verifying", "monitoring", "climax", "fading", "archived"}


@dataclass(frozen=True)
class EventUpsert:
    event_id: int | None
    stock_code: str
    title: str
    normalized_keywords: list[str]
    status: str
    heat_score: int
    heat_score_components: dict[str, Any]
    contradiction: bool
    evidence_analysis_ids: list[int]
    evidence_raw_item_ids: list[int]
    source_names: list[str]
    first_seen_at: datetime
    last_seen_at: datetime


@dataclass
class _Cluster:
    stock_code: str
    title: str
    tokens: set[str]
    analysis_ids: list[int]
    raw_item_ids: list[int]
    source_names: list[str]
    source_urls: list[str]
    sentiments: set[str]
    first_seen_at: datetime
    last_seen_at: datetime


def normalize_tokens(*parts: object) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    for part in parts:
        for token in _tokens_from_value(part):
            if token not in seen:
                seen.add(token)
                tokens.append(token)
    return tokens


def rebuild_event_records(
    raw_items: list[RawItem],
    analyses: list[AnalysisResult],
    existing_events: list[EventRecord],
) -> list[EventUpsert]:
    raw_by_id = {item.id: item for item in raw_items if item.id is not None}
    clusters = _build_clusters(raw_by_id, analyses)
    upserts: list[EventUpsert] = []
    matched_event_ids: set[int] = set()
    for cluster in clusters:
        match = _match_event(cluster, existing_events, matched_event_ids)
        if match is not None and match.id is not None:
            matched_event_ids.add(match.id)
        upserts.append(_event_upsert(cluster, match))
    return upserts


def apply_contradiction_flags(analyses: list[AnalysisResult], event: EventUpsert) -> None:
    if not event.contradiction:
        return
    ids = set(event.evidence_analysis_ids)
    for analysis in analyses:
        if analysis.id in ids:
            analysis.contradiction = True


def build_event_record(upsert: EventUpsert) -> EventRecord:
    return EventRecord(
        id=upsert.event_id,
        stock_code=upsert.stock_code,
        title=upsert.title,
        normalized_keywords=upsert.normalized_keywords,
        status=upsert.status,
        heat_score=upsert.heat_score,
        heat_score_components=upsert.heat_score_components,
        contradiction=upsert.contradiction,
        evidence_analysis_ids=upsert.evidence_analysis_ids,
        evidence_raw_item_ids=upsert.evidence_raw_item_ids,
        source_names=upsert.source_names,
        first_seen_at=upsert.first_seen_at,
        last_seen_at=upsert.last_seen_at,
    )


def _build_clusters(raw_by_id: dict[int, RawItem], analyses: list[AnalysisResult]) -> list[_Cluster]:
    ordered: list[tuple[AnalysisResult, RawItem]] = []
    for analysis in analyses:
        if analysis.id is None:
            continue
        raw = raw_by_id.get(analysis.raw_item_id)
        if raw is None:
            continue
        ordered.append((analysis, raw))
    ordered.sort(key=lambda item: (item[1].published_at, item[0].created_at, item[0].id or 0))
    clusters: list[_Cluster] = []
    for analysis, raw in ordered:
        aid = analysis.id
        if aid is None:
            continue
        stock_code = raw.stock_codes[0] if raw.stock_codes else ""
        if not stock_code.strip():
            continue
        seen_at = raw.published_at or analysis.created_at
        token_set = set(
            normalize_tokens(raw.title, raw.content, analysis.summary, analysis.keywords, analysis.source_quote)
        )
        cluster = _find_cluster(clusters, stock_code, token_set, seen_at)
        if cluster is None:
            clusters.append(
                _Cluster(
                    stock_code=stock_code,
                    title=_cluster_title(raw.title, analysis.summary),
                    tokens=set(token_set),
                    analysis_ids=[aid],
                    raw_item_ids=[raw.id or analysis.raw_item_id],
                    source_names=[raw.source_name],
                    source_urls=[analysis.source_url],
                    sentiments={analysis.sentiment},
                    first_seen_at=seen_at,
                    last_seen_at=seen_at,
                )
            )
            continue
        cluster.analysis_ids.append(aid)
        if raw.id is not None and raw.id not in cluster.raw_item_ids:
            cluster.raw_item_ids.append(raw.id)
        if raw.source_name not in cluster.source_names:
            cluster.source_names.append(raw.source_name)
        if analysis.source_url not in cluster.source_urls:
            cluster.source_urls.append(analysis.source_url)
        cluster.sentiments.add(analysis.sentiment)
        cluster.tokens.update(token_set)
        cluster.last_seen_at = max(cluster.last_seen_at, seen_at)
    return clusters


def _find_cluster(
    clusters: list[_Cluster],
    stock_code: str,
    tokens: set[str],
    seen_at: datetime,
) -> _Cluster | None:
    best: tuple[int, int, _Cluster] | None = None
    for index, cluster in enumerate(clusters):
        if cluster.stock_code != stock_code:
            continue
        if abs(_hours_between(cluster.last_seen_at, seen_at)) > WINDOW_HOURS:
            continue
        overlap = len(cluster.tokens & tokens)
        if overlap < 2:
            continue
        candidate = (overlap, -index, cluster)
        if best is None or candidate > best:
            best = candidate
    return best[2] if best else None


def _match_event(
    cluster: _Cluster,
    existing_events: list[EventRecord],
    matched_event_ids: set[int],
) -> EventRecord | None:
    best: tuple[int, int, EventRecord] | None = None
    for index, event in enumerate(existing_events):
        if event.id is None or event.id in matched_event_ids:
            continue
        if event.stock_code != cluster.stock_code or event.status == "archived":
            continue
        if abs(_hours_between(event.last_seen_at, cluster.last_seen_at)) > WINDOW_HOURS:
            continue
        overlap = len(set(event.normalized_keywords) & cluster.tokens)
        if overlap < 2:
            continue
        candidate = (overlap, -index, event)
        if best is None or candidate > best:
            best = candidate
    return best[2] if best else None


def _event_upsert(cluster: _Cluster, event: EventRecord | None) -> EventUpsert:
    analysis_ids = sorted(set(cluster.analysis_ids) | (set(event.evidence_analysis_ids) if event else set()))
    raw_item_ids = sorted(set(cluster.raw_item_ids) | (set(event.evidence_raw_item_ids) if event else set()))
    source_names = sorted(set(cluster.source_names) | (set(event.source_names) if event else set()))
    normalized_keywords = sorted(set(cluster.tokens) | (set(event.normalized_keywords) if event else set()))
    first_seen_at = min(cluster.first_seen_at, event.first_seen_at) if event else cluster.first_seen_at
    last_seen_at = max(cluster.last_seen_at, event.last_seen_at) if event else cluster.last_seen_at
    contradiction = _is_contradictory(
        cluster.sentiments,
        source_names=source_names,
        source_urls=cluster.source_urls,
        existing=event.contradiction if event else False,
    )
    heat_score, components = _heat_score(
        evidence_count=len(analysis_ids),
        source_diversity=len(source_names),
        first_seen_at=first_seen_at,
        last_seen_at=last_seen_at,
        contradiction=contradiction,
    )
    status = _event_status(
        heat_score=heat_score,
        evidence_count=len(analysis_ids),
        source_diversity=len(source_names),
        contradiction=contradiction,
        first_seen_at=first_seen_at,
        last_seen_at=last_seen_at,
        archived=bool(event and event.status == "archived"),
    )
    return EventUpsert(
        event_id=event.id if event else None,
        stock_code=cluster.stock_code,
        title=(event.title if event and event.title else cluster.title),
        normalized_keywords=normalized_keywords,
        status=status,
        heat_score=heat_score,
        heat_score_components=components,
        contradiction=contradiction,
        evidence_analysis_ids=analysis_ids,
        evidence_raw_item_ids=raw_item_ids,
        source_names=source_names,
        first_seen_at=first_seen_at,
        last_seen_at=last_seen_at,
    )


def _is_contradictory(
    sentiments: set[str],
    *,
    source_names: list[str],
    source_urls: list[str],
    existing: bool,
) -> bool:
    if existing:
        return True
    if len(set(source_names)) < 2 and len(set(source_urls)) < 2:
        return False
    return "bullish" in sentiments and "bearish" in sentiments


def _event_status(
    *,
    heat_score: int,
    evidence_count: int,
    source_diversity: int,
    contradiction: bool,
    first_seen_at: datetime,
    last_seen_at: datetime,
    archived: bool,
) -> str:
    if archived:
        return "archived"
    age_hours = max(0, int(_hours_between(first_seen_at, last_seen_at)))
    if heat_score >= CLIMAX_THRESHOLD:
        return "climax"
    if contradiction or source_diversity > 1:
        return "verifying"
    if evidence_count >= 2:
        return "monitoring"
    if age_hours >= WINDOW_HOURS or heat_score <= FADING_THRESHOLD and age_hours >= 24:
        return "fading"
    return "discovered"


def _heat_score(
    *,
    evidence_count: int,
    source_diversity: int,
    first_seen_at: datetime,
    last_seen_at: datetime,
    contradiction: bool,
) -> tuple[int, dict[str, Any]]:
    age_hours = max(0, int(_hours_between(first_seen_at, last_seen_at)))
    evidence_component = min(40, evidence_count * 12)
    source_component = min(24, max(0, (source_diversity - 1) * 12))
    recency_component = max(0, 24 - int(age_hours // 6) * 3)
    contradiction_component = 14 if contradiction else 0
    total = min(100, evidence_component + source_component + recency_component + contradiction_component)
    return total, {
        "evidence_count": evidence_component,
        "source_diversity": source_component,
        "recency": recency_component,
        "contradiction": contradiction_component,
        "total": total,
        "age_hours": age_hours,
    }


def _cluster_title(title: str, summary: str) -> str:
    clean_title = title.strip()
    if clean_title:
        return clean_title[:120]
    return summary.strip()[:120] or "事件"


def _tokens_from_value(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return _tokens_from_text(value)
    if isinstance(value, list):
        result_tokens: list[str] = []
        for item in value:
            result_tokens.extend(_tokens_from_value(item))
        return result_tokens
    if isinstance(value, dict):
        dict_tokens: list[str] = []
        for item in value.values():
            dict_tokens.extend(_tokens_from_value(item))
        return dict_tokens
    return _tokens_from_text(str(value))


def _tokens_from_text(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).lower()
    return [token.strip() for token in TOKEN_PATTERN.findall(normalized) if token.strip()]


def _hours_between(start: datetime, end: datetime) -> float:
    return (end - start).total_seconds() / 3600.0
