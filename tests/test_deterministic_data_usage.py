import importlib.util
import json
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


def test_early_stage_volatile_equity_promotes_selected_context_fields_to_review():
    module = load_module()
    hints = {
        "asset_type": "equity",
        "negative_eps": True,
        "high_realized_volatility": True,
        "micro_or_early_revenue": True,
    }

    assert module.classify_materiality("market_snapshot.latest_volume", "equity", hints) == "review"
    assert module.classify_materiality("equity_fundamentals.book_value", "equity", hints) == "review"
    assert module.classify_materiality("equity_fundamentals.operating_margin_ttm", "equity", hints) == "review"


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


def test_compare_usage_dispositions_flags_weak_required_rationale():
    module = load_module()
    requirements = {
        "datapoints": [
            {
                "field_path": "equity_fundamentals.ebitda",
                "materiality": "required",
                "field_name": "ebitda",
                "value": -57941000,
            }
        ]
    }
    report = {
        "deterministic_data_usage": [
            {
                "field_path": "equity_fundamentals.ebitda",
                "disposition": "used",
                "rationale": "Used in the report as part of identity, market snapshot, financial profile, valuation/performance context, or technical context.",
                "report_section": "Financials, Holdings, And Balance Sheet",
            }
        ]
    }

    comparison = module.compare_usage_dispositions(requirements, report)

    assert comparison["summary"]["weak_required"] == 1
    weak = comparison["weak_required"][0]
    assert weak["field_path"] == "equity_fundamentals.ebitda"
    assert weak["field_name"] == "ebitda"
    assert weak["materiality"] == "required"
    assert weak["disposition"] == "used"
    assert weak["report_section"] == "Financials, Holdings, And Balance Sheet"
    assert weak["weak_reason"] == "generic_rationale"
    assert weak["suggested_fix"] == "Mention the field or value and why it changed, supported, or did not change the investor view."


def test_compare_usage_dispositions_flags_repeated_boilerplate_rationales():
    module = load_module()
    requirements = {
        "datapoints": [
            {"field_path": "market_snapshot.fifty_two_week_high", "materiality": "required", "field_name": "fifty_two_week_high"},
            {"field_path": "market_snapshot.fifty_two_week_low", "materiality": "required", "field_name": "fifty_two_week_low"},
            {"field_path": "technical_signals.average_volume_30", "materiality": "review", "field_name": "average_volume_30"},
        ]
    }
    report = {
        "deterministic_data_usage": [
            {
                "field_path": item["field_path"],
                "disposition": "used",
                "rationale": f"{item['field_path']} was used to anchor WQTM market, liquidity, performance, or technical context for investors.",
                "report_section": "Market Snapshot And Technical Analysis",
            }
            for item in requirements["datapoints"]
        ]
    }

    comparison = module.compare_usage_dispositions(requirements, report)

    weak_reasons = {item["weak_reason"] for item in comparison["weak_required"] + comparison["weak_review"]}
    assert "boilerplate_rationale" in weak_reasons


def test_usage_audit_does_not_treat_raw_path_only_as_narrative_use(tmp_path):
    module = load_module()
    normalized = tmp_path / "normalized"
    normalized.mkdir()
    raw_path = "data/QUBT/2026-06-22/raw/alphavantage/example.json"
    (normalized / "equity_fundamentals.json").write_text(
        json.dumps(
            {
                "operating_margin_ttm": {
                    "value": -5.57,
                    "provider": "alphavantage",
                    "source_url": "https://example.test/overview",
                    "raw_path": raw_path,
                    "status": "ok",
                }
            }
        ),
        encoding="utf-8",
    )
    report_md = tmp_path / "report.md"
    report_md.write_text(f"Sources: `{raw_path}`.", encoding="utf-8")

    audit = module.deterministic_data_usage_audit(
        {"normalized": normalized, "report_markdown": report_md, "report_json": None},
        {},
    )

    item = audit["datapoints"][0]
    assert item["usage_status"] == "evidence_only_reference"
    assert "raw_path" in item["reference_reasons"]


def test_usage_audit_recognizes_scalar_companyfacts_revenue_value(tmp_path):
    # F7 / M5: a companyfacts DataPoint is a scalar "value" with sibling tag/fiscal_year/period_end/
    # filed_date/form keys (see companyfacts_point() in deterministic_research_collector.py). The
    # usage audit must still recognize that scalar value when the report corpus quotes it verbatim.
    module = load_module()
    normalized = tmp_path / "normalized"
    normalized.mkdir()
    (normalized / "equity_fundamentals.json").write_text(
        json.dumps(
            {
                "revenue": {
                    "value": 391035000000,
                    "provider": "sec",
                    "source_url": "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json",
                    "raw_path": "data/AAPL/2026-06-22/raw/sec/companyfacts.json",
                    "status": "ok",
                    "unit": "USD",
                    "as_of": "2025-09-27",
                    "period": "2025-09-27",
                    "tag": "Revenues",
                    "fiscal_year": 2025,
                    "period_end": "2025-09-27",
                    "filed_date": "2025-11-01",
                    "form": "10-K",
                }
            }
        ),
        encoding="utf-8",
    )
    report_md = tmp_path / "report.md"
    report_md.write_text("Fiscal 2025 revenue was 391035000000 per the 10-K filed with the SEC.", encoding="utf-8")

    audit = module.deterministic_data_usage_audit(
        {"normalized": normalized, "report_markdown": report_md, "report_json": None},
        {},
    )

    item = audit["datapoints"][0]
    assert item["field_path"] == "equity_fundamentals.revenue"
    assert "value" in item["reference_reasons"]
    assert item["usage_status"] == "narrative_used"


def test_usage_audit_single_digit_value_not_matched_by_coincidental_digit(tmp_path):
    # G4 over-match: a datapoint value of 8 must not match the 8 inside "1985" or "38.2"; a corpus
    # without a standalone 8 leaves the datapoint not_referenced so the audit keeps its teeth.
    module = load_module()
    normalized = tmp_path / "normalized"
    normalized.mkdir()
    (normalized / "equity_fundamentals.json").write_text(
        json.dumps(
            {
                "analyst_rating_hold": {
                    "value": 8,
                    "provider": "fmp",
                    "source_url": "https://example.test/ratings",
                    "raw_path": "data/AAPL/2026-06-22/raw/fmp/ratings.json",
                    "status": "ok",
                }
            }
        ),
        encoding="utf-8",
    )
    report_md = tmp_path / "report.md"
    report_md.write_text("Founded in 1985, the stock trades at a 38.2% premium.", encoding="utf-8")

    audit = module.deterministic_data_usage_audit(
        {"normalized": normalized, "report_markdown": report_md, "report_json": None},
        {},
    )

    item = audit["datapoints"][0]
    assert "value" not in item["reference_reasons"]
    assert item["usage_status"] == "not_referenced"


def test_usage_audit_matches_humanized_billion_revenue(tmp_path):
    # G4 under-match: a memo that writes "$391.0 billion" for a 391035000000 revenue must count as a
    # value reference via the humanized scaled token, not be scored not_referenced.
    module = load_module()
    normalized = tmp_path / "normalized"
    normalized.mkdir()
    (normalized / "equity_fundamentals.json").write_text(
        json.dumps(
            {
                "revenue": {
                    "value": 391035000000,
                    "provider": "sec",
                    "source_url": "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json",
                    "raw_path": "data/AAPL/2026-06-22/raw/sec/companyfacts.json",
                    "status": "ok",
                }
            }
        ),
        encoding="utf-8",
    )
    report_md = tmp_path / "report.md"
    report_md.write_text("Apple reported fiscal 2025 revenue of $391.0 billion.", encoding="utf-8")

    audit = module.deterministic_data_usage_audit(
        {"normalized": normalized, "report_markdown": report_md, "report_json": None},
        {},
    )

    item = audit["datapoints"][0]
    assert "value" in item["reference_reasons"]
    assert item["usage_status"] == "narrative_used"
