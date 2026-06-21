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


def test_default_endpoint_plan_includes_all_configured_price_fallbacks():
    c = load_module()
    plan = c.default_endpoint_plan(["sec", "tiingo", "eodhd", "alphavantage", "fmp", "twelve_data", "marketaux"])
    assert "prices" in plan["tiingo"]
    assert "prices" in plan["eodhd"]
    assert "prices" in plan["alphavantage"]
    assert "prices" in plan["twelve_data"]
