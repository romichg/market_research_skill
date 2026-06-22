import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "market-research" / "shared" / "scripts" / "deterministic_data_usage.py"


def load_module():
    spec = importlib.util.spec_from_file_location("deterministic_data_usage", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_usage_requirements_classify_material_datapoints(tmp_path):
    module = load_module()
    normalized = tmp_path / "normalized"
    normalized.mkdir()
    (normalized / "market_snapshot.json").write_text(
        """{
          "latest_close": {"value": 123.45, "status": "ok", "provider": "tiingo", "source_url": "https://example.test/prices", "raw_path": "raw/price.json"},
          "beta": {"value": 1.2, "status": "ok", "provider": "alphavantage", "source_url": "https://example.test/overview", "raw_path": "raw/overview.json"},
          "input_symbol": {"value": "AAPL", "status": "ok", "provider": "input", "source_url": "", "raw_path": "."}
        }""",
        encoding="utf-8",
    )
    (normalized / "equity_fundamentals.json").write_text(
        """{
          "revenue_ttm": {"value": 1000, "status": "ok", "provider": "alphavantage", "source_url": "https://example.test/overview", "raw_path": "raw/overview.json"},
          "analyst_target_price": {"value": 150.0, "status": "ok", "provider": "alphavantage", "source_url": "https://example.test/overview", "raw_path": "raw/overview.json"}
        }""",
        encoding="utf-8",
    )

    requirements = module.build_usage_requirements(normalized, "equity")

    by_path = {item["field_path"]: item for item in requirements["datapoints"]}
    assert requirements["summary"]["total_ok_datapoints"] == 4
    assert by_path["market_snapshot.latest_close"]["materiality"] == "required"
    assert by_path["equity_fundamentals.revenue_ttm"]["materiality"] == "required"
    assert by_path["market_snapshot.beta"]["materiality"] == "review"
    assert by_path["equity_fundamentals.analyst_target_price"]["materiality"] == "review"
    assert "market_snapshot.input_symbol" not in by_path


def test_compare_usage_dispositions_flags_missing_required():
    module = load_module()
    requirements = {
        "datapoints": [
            {"field_path": "market_snapshot.latest_close", "materiality": "required"},
            {"field_path": "market_snapshot.beta", "materiality": "review"},
        ]
    }
    report = {
        "deterministic_data_usage": [
            {"field_path": "market_snapshot.beta", "disposition": "intentionally_omitted_not_material", "rationale": "Not central."}
        ]
    }

    comparison = module.compare_usage_dispositions(requirements, report)

    assert comparison["summary"]["missing_required"] == 1
    assert comparison["missing_required"][0]["field_path"] == "market_snapshot.latest_close"
