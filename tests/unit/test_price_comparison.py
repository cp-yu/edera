from datetime import datetime, timezone
from pathlib import Path

from stockimformation.config.schema import SystemConfig
from stockimformation.models.entities import Advice
from stockimformation.services.price_comparison import PriceComparisonService, load_price_history


def test_price_history_loads_csv_and_yaml(tmp_path: Path) -> None:
    csv_path = tmp_path / "prices.csv"
    yaml_path = tmp_path / "prices.yaml"
    csv_path.write_text(
        "stock_code,timestamp,close\n00700.HK,2026-01-01T00:00:00+00:00,100\n",
        encoding="utf-8",
    )
    yaml_path.write_text(
        """
prices:
  - stock_code: 00700.HK
    timestamp: "2026-01-02T00:00:00+00:00"
    close: 101
""".lstrip(),
        encoding="utf-8",
    )
    assert load_price_history(csv_path)["00700.HK"][0].close == 100
    assert load_price_history(yaml_path)["00700.HK"][0].close == 101


def test_buy_sell_hold_verdict_matrix(tmp_path: Path) -> None:
    cases = [
        ("buy", 104, "aligned"),
        ("buy", 99.5, "diverged"),
        ("sell", 96, "aligned"),
        ("sell", 104, "diverged"),
        ("hold", 100.5, "aligned"),
        ("hold", 104, "diverged"),
    ]
    for direction, horizon, expected in cases:
        comparison = _service(tmp_path, 100, horizon).compare(_advice(direction))
        assert comparison["verdict"] == expected


def test_buy_sell_hold_unknown_without_stock_price(tmp_path: Path) -> None:
    service = _service(tmp_path, 100, 104)
    for direction in ("buy", "sell", "hold"):
        comparison = service.compare(_advice(direction, "600519.SH"))
        assert comparison["verdict"] == "unknown"
        assert comparison["unknown_reason"] == "missing_stock_price"


def test_comparison_unknown_without_price_history(tmp_path: Path) -> None:
    system = SystemConfig(price_history_path=tmp_path / "missing.csv")
    comparison = PriceComparisonService.from_system(system, tmp_path).compare(_advice("buy"))
    assert comparison["verdict"] == "unknown"
    assert comparison["unknown_reason"] == "price_history_file_missing"


def test_comparison_unknown_for_malformed_history(tmp_path: Path) -> None:
    path = tmp_path / "prices.csv"
    path.write_text("stock_code,timestamp\n00700.HK,2026-01-01T00:00:00+00:00\n", encoding="utf-8")
    system = SystemConfig(price_history_path=path)
    comparison = PriceComparisonService.from_system(system, tmp_path).compare(_advice("buy"))
    assert comparison["verdict"] == "unknown"
    assert comparison["unknown_reason"] == "price_history_invalid"


def _service(tmp_path: Path, baseline: float, horizon: float) -> PriceComparisonService:
    path = tmp_path / "prices.csv"
    path.write_text(
        "\n".join(
            [
                "stock_code,timestamp,close",
                f"00700.HK,{_dt(1).isoformat()},{baseline}",
                f"00700.HK,{_dt(8).isoformat()},{horizon}",
            ]
        ),
        encoding="utf-8",
    )
    system = SystemConfig(price_history_path=path)
    return PriceComparisonService.from_system(system, tmp_path)


def _advice(direction: str, stock_code: str = "00700.HK") -> Advice:
    return Advice(
        stock_code=stock_code,
        stock_name="Tencent",
        direction=direction,
        confidence=0.55,
        reason="reason",
        evidence=[1],
        source_quotes=["quote"],
        source_urls=["https://example.com/a"],
        portfolio_snapshot={"quantity": 1},
        created_at=_dt(1),
        data_window_start=_dt(1),
        data_window_end=_dt(1),
    )


def _dt(day: int) -> datetime:
    return datetime(2026, 1, day, tzinfo=timezone.utc)
