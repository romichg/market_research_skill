import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "market-research" / "shared" / "scripts" / "producer_self_check.py"


def run_self_check(report_dir, data_dir, runtime_dir, *extra):
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(report_dir),
            "--data-dir",
            str(data_dir),
            "--runtime-dir",
            str(runtime_dir),
            *extra,
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def complete_payload(symbol="QTUM", security_type="etf", data_dir=None):
    payload = {
        "symbol": symbol,
        "security_type": security_type,
        "as_of_date": "2026-07-01",
        "material_claims": [],
        "data_gaps": [],
        "technical_analysis": {},
        "valuation_or_performance": {},
        "decision_factors": {},
        "risks": [],
        "catalysts": [],
        "source_coverage": {},
        "calculation_audit": [],
    }
    if data_dir is not None:
        payload["deterministic_bundle"] = {"bundle_dir": str(data_dir)}
    return payload


def write_bundle(data_dir, symbol="QTUM", datapoints=None):
    normalized = data_dir / "normalized"
    normalized.mkdir(parents=True)
    (data_dir / "research_input_pack.md").write_text(f"# {symbol} Pack\n", encoding="utf-8")
    (data_dir / "manifest.json").write_text(json.dumps({"symbol": symbol, "asset_type": "etf"}), encoding="utf-8")
    (data_dir / "source_manifest.json").write_text(json.dumps({"sources": []}), encoding="utf-8")
    (data_dir / "gaps.json").write_text(json.dumps({"gaps": []}), encoding="utf-8")
    (normalized / "identity.json").write_text(json.dumps({"asset_type": {"value": "etf"}, "company_name": {"value": "Fund"}}), encoding="utf-8")
    (normalized / "market_snapshot.json").write_text(json.dumps({"latest_close": {"value": 10.0}}), encoding="utf-8")
    (normalized / "technical_signals.json").write_text(json.dumps({"sma_50": {"value": 9.5}, "sma_200": {"value": 8.5}}), encoding="utf-8")
    if datapoints is not None:
        (data_dir / "deterministic_data_usage.json").write_text(
            json.dumps({"version": "deterministic-data-usage-v1", "datapoints": datapoints}),
            encoding="utf-8",
        )


def test_self_check_blocks_missing_required_deterministic_usage_dispositions(tmp_path):
    report_dir = tmp_path / "reports" / "QTUM" / "2026-07-01"
    data_dir = tmp_path / "data" / "QTUM" / "2026-07-01"
    runtime_dir = tmp_path / "runtime" / "QTUM" / "2026-07-01"
    report_dir.mkdir(parents=True)
    datapoints = [
        {"field_path": "identity.asset_type", "field_name": "asset_type", "materiality": "required"},
        {"field_path": "identity.company_name", "field_name": "company_name", "materiality": "required"},
        {"field_path": "market_snapshot.latest_close", "field_name": "latest_close", "materiality": "required"},
        {"field_path": "technical_signals.sma_50", "field_name": "sma_50", "materiality": "required"},
        {"field_path": "technical_signals.sma_200", "field_name": "sma_200", "materiality": "required"},
    ]
    write_bundle(data_dir, "QTUM", datapoints)
    (report_dir / "QTUM-research.md").write_text("# QTUM Research\n", encoding="utf-8")
    (report_dir / "QTUM-research.json").write_text(json.dumps(complete_payload("QTUM", "etf", data_dir)), encoding="utf-8")
    (report_dir / "sources.json").write_text(json.dumps({"sources": []}), encoding="utf-8")

    result = run_self_check(report_dir, data_dir, runtime_dir)

    assert result.returncode == 1
    payload = json.loads((runtime_dir / "producer-self-check.json").read_text(encoding="utf-8"))
    issue_ids = {issue["id"] for issue in payload["issues"]}
    assert "deterministic-usage-missing-required-identity-asset_type" in issue_ids
    assert payload["blocking_issue_count"] >= 1


def test_self_check_auto_fixes_safe_deterministic_source_records(tmp_path):
    report_dir = tmp_path / "reports" / "ECH" / "2026-07-02"
    data_dir = tmp_path / "data" / "ECH" / "2026-07-02"
    runtime_dir = tmp_path / "runtime" / "ECH" / "2026-07-02"
    report_dir.mkdir(parents=True)
    write_bundle(data_dir, "ECH", [])
    payload = complete_payload("ECH", "etf", data_dir)
    payload["material_claims"] = [
        {"claim": "Technical signals were mixed.", "source_id": "deterministic_technical_signals"}
    ]
    payload["deterministic_data_usage"] = []
    (report_dir / "ECH-research.md").write_text("# ECH Research\n", encoding="utf-8")
    (report_dir / "ECH-research.json").write_text(json.dumps(payload), encoding="utf-8")
    (report_dir / "sources.json").write_text(json.dumps({"sources": []}), encoding="utf-8")

    result = run_self_check(report_dir, data_dir, runtime_dir, "--fix-safe")

    assert result.returncode == 0, result.stderr
    payload = json.loads((runtime_dir / "producer-self-check.json").read_text(encoding="utf-8"))
    sources = json.loads((report_dir / "sources.json").read_text(encoding="utf-8"))["sources"]
    assert any(source["id"] == "deterministic_technical_signals" for source in sources)
    assert payload["auto_fixed_ids"] == ["deterministic_technical_signals"]
    assert payload["blocking_issue_count"] == 0


def test_self_check_surfaces_report_quality_findings_before_verifier(tmp_path):
    report_dir = tmp_path / "reports" / "EWW" / "2026-07-02"
    data_dir = tmp_path / "data" / "EWW" / "2026-07-02"
    runtime_dir = tmp_path / "runtime" / "EWW" / "2026-07-02"
    report_dir.mkdir(parents=True)
    write_bundle(data_dir, "EWW", [])
    markdown = """# EWW Research

## Bottom Line

EWW has about $1.8 billion of net assets and gives investors targeted Mexico exposure. The sponsor holdings download showed 39 securities and a concentrated country portfolio.

## Market Snapshot And Technical Analysis

Support, resistance, moving averages, trend, volume, volatility, and drawdown are listed without using them for the investment decision.

## Risks And Invalidation Points

Creation/redemption, authorized participant, securities lending, premium/discount, tracking, tax, withholding, liquidity, closure, and concentration risks are discussed.
"""
    report_json = complete_payload("EWW", "etf", data_dir)
    report_json["technical_analysis"] = {"max_drawdown_available": -0.31}
    (report_dir / "EWW-research.md").write_text(markdown, encoding="utf-8")
    (report_dir / "EWW-research.json").write_text(json.dumps(report_json), encoding="utf-8")
    (report_dir / "sources.json").write_text(json.dumps({"sources": []}), encoding="utf-8")

    result = run_self_check(report_dir, data_dir, runtime_dir)

    assert result.returncode == 0
    payload = json.loads((runtime_dir / "producer-self-check.json").read_text(encoding="utf-8"))
    issue_ids = {issue["id"] for issue in payload["issues"]}
    assert "etf-provenance-heavy-language" in issue_ids
    assert "technical-analysis-missing-decision-use" in issue_ids
