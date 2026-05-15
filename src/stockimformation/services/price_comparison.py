from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal, Mapping, SupportsFloat, SupportsIndex, cast

import yaml

from stockimformation.config.schema import SystemConfig
from stockimformation.models.entities import Advice

ComparisonVerdict = Literal["aligned", "diverged", "unknown"]


class PriceHistoryError(ValueError):
    pass


@dataclass(frozen=True)
class PricePoint:
    stock_code: str
    timestamp: datetime
    close: float


@dataclass(frozen=True)
class AdviceComparison:
    verdict: ComparisonVerdict
    horizon_days: int
    threshold_percent: float
    baseline_time: str | None = None
    baseline_price: float | None = None
    horizon_time: str | None = None
    horizon_price: float | None = None
    price_change_percent: float | None = None
    unknown_reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "verdict": self.verdict,
            "verdict_label": {"aligned": "一致", "diverged": "偏离", "unknown": "未知"}[
                self.verdict
            ],
            "horizon_days": self.horizon_days,
            "threshold_percent": self.threshold_percent,
            "baseline_time": self.baseline_time,
            "baseline_price": self.baseline_price,
            "horizon_time": self.horizon_time,
            "horizon_price": self.horizon_price,
            "price_change_percent": self.price_change_percent,
            "unknown_reason": self.unknown_reason,
        }


class PriceComparisonService:
    def __init__(
        self,
        prices: dict[str, list[PricePoint]],
        horizon_days: int,
        threshold_percent: float,
        unknown_reason: str | None = None,
    ) -> None:
        self.prices = prices
        self.horizon_days = horizon_days
        self.threshold_percent = threshold_percent
        self.unknown_reason = unknown_reason

    @classmethod
    def from_system(cls, system: SystemConfig, config_dir: Path) -> "PriceComparisonService":
        if system.price_history_path is None:
            return cls(
                {},
                system.price_comparison_horizon_days,
                system.price_comparison_threshold_percent,
                "price_history_not_configured",
            )
        path = system.price_history_path
        if not path.is_absolute():
            path = config_dir / path
        if not path.exists():
            return cls(
                {},
                system.price_comparison_horizon_days,
                system.price_comparison_threshold_percent,
                "price_history_file_missing",
            )
        try:
            prices = load_price_history(path)
        except PriceHistoryError:
            return cls(
                {},
                system.price_comparison_horizon_days,
                system.price_comparison_threshold_percent,
                "price_history_invalid",
            )
        if not prices:
            return cls(
                {},
                system.price_comparison_horizon_days,
                system.price_comparison_threshold_percent,
                "price_history_empty",
            )
        return cls(prices, system.price_comparison_horizon_days, system.price_comparison_threshold_percent)

    @classmethod
    def disabled(cls) -> "PriceComparisonService":
        return cls({}, 7, 1.0, "price_history_not_configured")

    def compare(self, advice: Advice) -> dict[str, object]:
        if self.unknown_reason is not None:
            return self._unknown(self.unknown_reason).to_dict()
        prices = self.prices.get(advice.stock_code)
        if not prices:
            return self._unknown("missing_stock_price").to_dict()

        anchor = _as_utc_naive(advice.data_window_end or advice.created_at)
        baseline = _first_at_or_after(prices, anchor)
        if baseline is None:
            return self._unknown("missing_baseline_price").to_dict()
        if baseline.close <= 0:
            return self._unknown("invalid_baseline_price").to_dict()

        target_time = baseline.timestamp + timedelta(days=self.horizon_days)
        horizon = _first_at_or_after(prices, target_time)
        if horizon is None:
            return self._unknown("missing_horizon_price").to_dict()

        change_percent = ((horizon.close - baseline.close) / baseline.close) * 100
        verdict = _verdict(advice.direction, change_percent, self.threshold_percent)
        return AdviceComparison(
            verdict=verdict,
            horizon_days=self.horizon_days,
            threshold_percent=self.threshold_percent,
            baseline_time=baseline.timestamp.isoformat(),
            baseline_price=baseline.close,
            horizon_time=horizon.timestamp.isoformat(),
            horizon_price=horizon.close,
            price_change_percent=round(change_percent, 4),
        ).to_dict()

    def _unknown(self, reason: str) -> AdviceComparison:
        return AdviceComparison(
            verdict="unknown",
            horizon_days=self.horizon_days,
            threshold_percent=self.threshold_percent,
            unknown_reason=reason,
        )


def load_price_history(path: Path) -> dict[str, list[PricePoint]]:
    rows = _yaml_rows(path) if path.suffix.lower() in {".yaml", ".yml"} else _csv_rows(path)
    prices: dict[str, list[PricePoint]] = {}
    for row in rows:
        point = _price_point(row)
        prices.setdefault(point.stock_code, []).append(point)
    for items in prices.values():
        items.sort(key=lambda item: item.timestamp)
    return prices


def _csv_rows(path: Path) -> list[Mapping[str, object]]:
    try:
        with path.open(newline="", encoding="utf-8") as file:
            return list(csv.DictReader(file))
    except OSError as exc:
        raise PriceHistoryError(str(exc)) from exc


def _yaml_rows(path: Path) -> list[Mapping[str, object]]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    except yaml.YAMLError as exc:
        raise PriceHistoryError(str(exc)) from exc
    if isinstance(data, dict):
        data = data.get("prices", [])
    if not isinstance(data, list):
        raise PriceHistoryError("price history must be a list")
    if not all(isinstance(item, dict) for item in data):
        raise PriceHistoryError("price rows must be mappings")
    return data


def _price_point(row: Mapping[str, object]) -> PricePoint:
    stock_code = _text(row, "stock_code")
    timestamp = _timestamp(_text(row, "timestamp"))
    close = _float_value(row, "close")
    return PricePoint(stock_code, timestamp, close)


def _text(row: Mapping[str, object], name: str) -> str:
    value = row.get(name)
    if not isinstance(value, str) or not value.strip():
        raise PriceHistoryError(f"missing {name}")
    return value.strip()


def _float_value(row: Mapping[str, object], name: str) -> float:
    value = row.get(name)
    if value is None:
        raise PriceHistoryError(f"missing {name}")
    try:
        return float(cast(str | SupportsFloat | SupportsIndex, value))
    except (TypeError, ValueError) as exc:
        raise PriceHistoryError(f"invalid {name}") from exc


def _timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PriceHistoryError("invalid timestamp") from exc
    return _as_utc_naive(parsed)


def _as_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _first_at_or_after(prices: list[PricePoint], timestamp: datetime) -> PricePoint | None:
    for price in prices:
        if price.timestamp >= timestamp:
            return price
    return None


def _verdict(direction: str, change_percent: float, threshold_percent: float) -> ComparisonVerdict:
    if direction == "hold":
        return "aligned" if abs(change_percent) <= threshold_percent else "diverged"
    if direction == "buy":
        return "aligned" if change_percent > threshold_percent else "diverged"
    if direction == "sell":
        return "aligned" if change_percent < -threshold_percent else "diverged"
    return "unknown"
