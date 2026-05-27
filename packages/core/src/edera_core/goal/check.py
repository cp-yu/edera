from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

P1_FRS = [
    "FR1",
    "FR2",
    "FR3",
    "FR4",
    "FR7",
    "FR11",
    "FR15",
    "FR18",
    "FR19",
    "FR20",
    "FR21",
    "FR22",
    "FR26",
    "FR27",
    "FR29",
    "FR30",
    "FR31",
    "FR32",
    "FR46",
]

FR_REQUIREMENTS = {
    "FR1": ("source-collection", "test_parse_rss_creates_raw_items"),
    "FR2": ("source-collection", "test_parse_web_regex_rule"),
    "FR3": ("source-collection", "test_system_config_schedule_is_30_minutes"),
    "FR4": ("source-collection", "test_dedupe_raw_items_by_url"),
    "FR7": ("information-analysis", "test_analysis_summary_keywords_sentiment"),
    "FR11": ("information-analysis", "test_analysis_requires_traceability"),
    "FR15": ("trade-advisory", "test_generate_buy_sell_hold_advice"),
    "FR18": ("trade-advisory", "test_advice_rejects_missing_evidence"),
    "FR19": ("notification-delivery", "test_priority_mapping"),
    "FR20": ("notification-delivery", "test_notification_summary_format"),
    "FR21": ("notification-delivery", "test_high_priority_contains_action"),
    "FR22": ("notification-delivery", "test_empty_cycle_status_notification"),
    "FR26": ("briefing-generation", "test_briefing_groups_targets"),
    "FR27": ("briefing-generation", "test_briefing_metadata_sources"),
    "FR29": ("config-management", "test_load_portfolio_holdings"),
    "FR30": ("config-management", "test_source_association"),
    "FR31": ("config-management", "test_rss_source_config"),
    "FR32": ("config-management", "test_web_source_rule_config"),
    "FR46": ("briefing-generation", "test_briefing_contains_disclaimer"),
}


@dataclass(frozen=True)
class GateReport:
    ok: bool
    blockers: list[str]
    mapping: dict[str, tuple[str, str]]


def run_goal_gate(prd_validation_report: Path) -> GateReport:
    blockers: list[str] = []
    missing = [fr for fr in P1_FRS if fr not in FR_REQUIREMENTS]
    if missing:
        blockers.append(f"missing P1 mapping: {', '.join(missing)}")
    if _critical_prd_status(prd_validation_report):
        blockers.append("PRD validation overallStatus is Critical")
    return GateReport(ok=not blockers, blockers=blockers, mapping=FR_REQUIREMENTS)


def _critical_prd_status(path: Path) -> bool:
    if not path.exists():
        return False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("overallStatus:"):
            return "Critical" in line
    return False
