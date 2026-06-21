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
