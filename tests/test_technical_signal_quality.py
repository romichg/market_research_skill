from pathlib import Path
import importlib.util


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "market-research" / "shared" / "scripts" / "deterministic_research_collector.py"


def load_module():
    spec = importlib.util.spec_from_file_location("collector", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def rows(n=260):
    return [
        {"date": f"2025-01-{(i % 28) + 1:02d}", "adjusted_close": 100 + i * 0.1, "volume": 1_000_000 + i * 1000}
        for i in range(n)
    ]


def test_technical_signals_include_investor_expected_fields():
    c = load_module()
    out = c.technicals_from_prices(rows(), "test", Path("raw.json"), "source")
    for key in [
        "rsi_14",
        "macd_12_26_9",
        "realized_volatility_30",
        "relative_volume_30_vs_90",
        "trend_classification",
    ]:
        assert key in out
        assert out[key]["status"] == "ok"


def test_full_year_history_labels_window_fields_ok():
    c = load_module()
    out = c.technicals_from_prices(rows(260), "test", Path("raw.json"), "source")
    assert out["fifty_two_week_high"]["status"] == "ok"
    assert out["fifty_two_week_low"]["status"] == "ok"
    assert out["average_volume_90"]["status"] == "ok"


def test_short_history_labels_window_fields_as_available_history():
    c = load_module()
    out = c.technicals_from_prices(rows(40), "test", Path("raw.json"), "source")
    # Values are still populated from available history, but the status makes the short window explicit.
    assert out["fifty_two_week_high"]["status"] == "available_history"
    assert out["fifty_two_week_high"]["value"] is not None
    assert out["fifty_two_week_low"]["status"] == "available_history"
    assert out["average_volume_90"]["status"] == "available_history"
    assert out["average_volume_30"]["status"] == "ok"


def test_market_snapshot_full_history_labels_52w_ok(tmp_path):
    c = load_module()
    snap = c.normalize_market_snapshot(tmp_path, "AAPL", rows(260), None, "test", "source", providers=["tiingo"])
    assert snap["fifty_two_week_high"]["status"] == "ok"
    assert snap["fifty_two_week_low"]["status"] == "ok"


def test_market_snapshot_short_history_labels_52w_available_history(tmp_path):
    # G3: with fewer than 252 sessions the snapshot 52-week points reflect available history only and
    # must carry the same available_history label technicals_from_prices uses, not an implied full range.
    c = load_module()
    snap = c.normalize_market_snapshot(tmp_path, "AAPL", rows(40), None, "test", "source", providers=["tiingo"])
    assert snap["fifty_two_week_high"]["status"] == "available_history"
    assert snap["fifty_two_week_high"]["value"] is not None
    assert snap["fifty_two_week_low"]["status"] == "available_history"
