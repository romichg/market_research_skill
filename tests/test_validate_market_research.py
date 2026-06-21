import json
import subprocess
import sys
from pathlib import Path

VALIDATOR = Path(__file__).resolve().parents[1] / "market-research" / "shared" / "scripts" / "validate_market_research.py"


def run_validator(*args):
    return subprocess.run([sys.executable, str(VALIDATOR), *args], text=True, capture_output=True, check=False)


def complete_research_payload(symbol="AAPL", security_type="equity"):
    return {
        "symbol": symbol,
        "security_type": security_type,
        "as_of_date": "2026-06-01",
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


def test_validator_discovers_research_bundle(tmp_path):
    run_dir = tmp_path / "reports" / "AAPL" / "2026-06-01"
    run_dir.mkdir(parents=True)
    (run_dir / "run_manifest.json").write_text(json.dumps({"symbol": "AAPL"}), encoding="utf-8")
    (run_dir / "AAPL-research.md").write_text("# AAPL Research\n", encoding="utf-8")
    (run_dir / "AAPL-research.json").write_text(json.dumps(complete_research_payload()), encoding="utf-8")
    result = run_validator(str(run_dir))
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["symbol"] == "AAPL"
    assert payload["blocking_issue_count"] == 0
    assert payload["scaffold"] is True
    assert (run_dir / "AAPL-validation-scaffold.json").exists()
    assert (run_dir / "AAPL-validation-scaffold.md").exists()
    markdown = (run_dir / "AAPL-validation-scaffold.md").read_text(encoding="utf-8")
    assert "Deterministic Validation Scaffold" in markdown
    validation = json.loads((run_dir / "AAPL-validation-scaffold.json").read_text(encoding="utf-8"))
    assert validation["scaffold"] is True
    assert validation["sources_inspected"] == []


def test_validator_accepts_reports_dir_when_project_parent_is_named_runtime(tmp_path):
    project = tmp_path / "runtime" / "project"
    run_dir = project / "reports" / "AAPL" / "2026-06-01"
    run_dir.mkdir(parents=True)
    (run_dir / "AAPL-research.md").write_text("# AAPL Research\n", encoding="utf-8")
    (run_dir / "AAPL-research.json").write_text(json.dumps(complete_research_payload()), encoding="utf-8")

    result = run_validator(str(run_dir))

    assert result.returncode == 0, result.stderr
    assert (run_dir / "AAPL-validation-scaffold.json").exists()


def test_validator_rejects_runtime_research_bundle(tmp_path):
    run_dir = tmp_path / "runtime" / "AAPL" / "2026-06-01"
    run_dir.mkdir(parents=True)
    (run_dir / "AAPL-research.md").write_text("# AAPL Research\n", encoding="utf-8")
    (run_dir / "AAPL-research.json").write_text(json.dumps({"symbol": "AAPL", "security_type": "equity", "material_claims": [], "data_gaps": []}), encoding="utf-8")

    result = run_validator(str(run_dir))

    assert result.returncode != 0
    assert "Final report directories must be under reports/SYMBOL/YYYY-MM-DD" in result.stderr
    assert not (run_dir / "AAPL-validation-scaffold.json").exists()


def test_validator_flags_missing_json(tmp_path):
    run_dir = tmp_path / "MSFT"
    run_dir.mkdir()
    (run_dir / "MSFT-research.md").write_text("# MSFT Research\n", encoding="utf-8")
    result = run_validator(str(run_dir))
    assert result.returncode != 0
    assert "research JSON" in result.stderr


def test_validator_refuses_to_overwrite_existing_judgment_validation_without_force(tmp_path):
    run_dir = tmp_path / "reports" / "AAPL" / "2026-06-01"
    run_dir.mkdir(parents=True)
    (run_dir / "AAPL-research.md").write_text("# AAPL Research\n", encoding="utf-8")
    (run_dir / "AAPL-research.json").write_text(json.dumps(complete_research_payload()), encoding="utf-8")
    existing = run_dir / "AAPL-validation.md"
    existing.write_text("# AAPL Validation\n\nHuman judgment validation.\n", encoding="utf-8")
    result = run_validator(str(run_dir), "--output-prefix", str(run_dir / "AAPL-validation"))
    assert result.returncode != 0
    assert "Refusing to overwrite" in result.stderr
    assert existing.read_text(encoding="utf-8") == "# AAPL Validation\n\nHuman judgment validation.\n"


def test_validator_flags_claim_source_missing_from_sources_json(tmp_path):
    run_dir = tmp_path / "reports" / "ECH" / "2026-06-01"
    run_dir.mkdir(parents=True)
    (run_dir / "ECH-research.md").write_text("# ECH Research\n", encoding="utf-8")
    (run_dir / "ECH-research.json").write_text(
        json.dumps(
            {
                **complete_research_payload("ECH", "etf"),
                "material_claims": [{"claim": "Expense ratio is 0.59%.", "source_id": "issuer_fact_sheet", "confidence": "high"}],
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "sources.json").write_text(json.dumps({"sources": []}), encoding="utf-8")
    result = run_validator(str(run_dir))
    assert result.returncode == 0, result.stderr
    validation = json.loads((run_dir / "ECH-validation-scaffold.json").read_text(encoding="utf-8"))
    assert validation["issues"][0]["id"] == "claim-0-source-missing"
    assert validation["issues"][0]["severity"] == "moderate"


def test_validator_flags_missing_expanded_research_json_sections(tmp_path):
    run_dir = tmp_path / "reports" / "AAPL" / "2026-06-01"
    run_dir.mkdir(parents=True)
    (run_dir / "AAPL-research.md").write_text("# AAPL Research\n", encoding="utf-8")
    payload = complete_research_payload()
    del payload["technical_analysis"]
    del payload["calculation_audit"]
    (run_dir / "AAPL-research.json").write_text(json.dumps(payload), encoding="utf-8")

    result = run_validator(str(run_dir))

    assert result.returncode == 0, result.stderr
    validation = json.loads((run_dir / "AAPL-validation-scaffold.json").read_text(encoding="utf-8"))
    issues = {issue["id"]: issue for issue in validation["issues"]}
    assert issues["schema-technical_analysis"]["severity"] == "critical"
    assert issues["schema-calculation_audit"]["severity"] == "critical"


def test_validator_reports_non_object_research_json_without_required_field_cascade(tmp_path):
    run_dir = tmp_path / "reports" / "AAPL" / "2026-06-01"
    run_dir.mkdir(parents=True)
    (run_dir / "AAPL-research.md").write_text("# AAPL Research\n", encoding="utf-8")
    (run_dir / "AAPL-research.json").write_text("[]", encoding="utf-8")

    result = run_validator(str(run_dir))

    assert result.returncode == 0, result.stderr
    validation = json.loads((run_dir / "AAPL-validation-scaffold.json").read_text(encoding="utf-8"))
    issues = validation["issues"]
    assert issues == [
        {
            "id": "schema-report-shape",
            "severity": "critical",
            "status": "open",
            "description": "Research JSON must be an object.",
        }
    ]


def test_validator_fresh_context_instruction_for_complete_json_avoids_parallel_thesis(tmp_path):
    run_dir = tmp_path / "reports" / "AAPL" / "2026-06-01"
    run_dir.mkdir(parents=True)
    (run_dir / "AAPL-research.md").write_text("# AAPL Research\n", encoding="utf-8")
    (run_dir / "AAPL-research.json").write_text(json.dumps(complete_research_payload()), encoding="utf-8")

    result = run_validator(str(run_dir))

    assert result.returncode == 0, result.stderr
    validation = json.loads((run_dir / "AAPL-validation-scaffold.json").read_text(encoding="utf-8"))
    assert "without creating a parallel research thesis" in validation["fresh_context_instruction"]


def test_validator_discovers_deterministic_bundle_without_research_json(tmp_path):
    run_dir = tmp_path / "data" / "AAPL" / "2026-06-01"
    reports_dir = tmp_path / "reports" / "AAPL" / "2026-06-01"
    normalized = run_dir / "normalized"
    normalized.mkdir(parents=True)
    (run_dir / "research_input_pack.md").write_text("# AAPL Deterministic Research Input Pack\n", encoding="utf-8")
    (run_dir / "manifest.json").write_text(json.dumps({"symbol": "AAPL", "asset_type": "equity"}), encoding="utf-8")
    (run_dir / "source_manifest.json").write_text(json.dumps({"sources": [{"provider": "sec", "raw_path": str(run_dir / "raw" / "sec" / "x.json"), "status": "ok"}]}), encoding="utf-8")
    (run_dir / "gaps.json").write_text(json.dumps({"gaps": [{"field": "short_interest", "status": "unavailable_free_source"}]}), encoding="utf-8")
    (normalized / "identity.json").write_text(
        json.dumps({"company_name": {"value": "Apple Inc", "provider": "sec", "raw_path": str(run_dir / "raw" / "sec" / "x.json"), "source_url": "https://data.sec.gov/x"}}),
        encoding="utf-8",
    )

    result = run_validator(str(run_dir))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["symbol"] == "AAPL"
    assert payload["scaffold"] is True
    assert payload["validation_json"] == str(reports_dir / "AAPL-validation-scaffold.json")
    assert not (run_dir / "AAPL-validation-scaffold.json").exists()
    validation = json.loads((reports_dir / "AAPL-validation-scaffold.json").read_text(encoding="utf-8"))
    assert validation["bundle_type"] == "deterministic_data_bundle"
    assert validation["data_gaps"] == [{"field": "short_interest", "status": "unavailable_free_source"}]


def test_validator_accepts_data_dir_when_project_parent_is_named_runtime(tmp_path):
    project = tmp_path / "runtime" / "project"
    run_dir = project / "data" / "AAPL" / "2026-06-01"
    reports_dir = project / "reports" / "AAPL" / "2026-06-01"
    normalized = run_dir / "normalized"
    normalized.mkdir(parents=True)
    (run_dir / "research_input_pack.md").write_text("# AAPL Deterministic Research Input Pack\n", encoding="utf-8")
    (run_dir / "manifest.json").write_text(json.dumps({"symbol": "AAPL", "asset_type": "equity"}), encoding="utf-8")
    (run_dir / "source_manifest.json").write_text(json.dumps({"sources": []}), encoding="utf-8")
    (run_dir / "gaps.json").write_text(json.dumps({"gaps": []}), encoding="utf-8")
    (normalized / "identity.json").write_text(json.dumps({"asset_type": {"value": "equity", "provider": "cli", "raw_path": "", "source_url": ""}}), encoding="utf-8")

    result = run_validator(str(run_dir))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["validation_json"] == str(reports_dir / "AAPL-validation-scaffold.json")
    assert (reports_dir / "AAPL-validation-scaffold.json").exists()


def test_validator_rejects_runtime_output_prefix_for_deterministic_bundle(tmp_path):
    run_dir = tmp_path / "data" / "AAPL" / "2026-06-01"
    normalized = run_dir / "normalized"
    normalized.mkdir(parents=True)
    (run_dir / "research_input_pack.md").write_text("# AAPL Deterministic Research Input Pack\n", encoding="utf-8")
    (run_dir / "manifest.json").write_text(json.dumps({"symbol": "AAPL", "asset_type": "equity"}), encoding="utf-8")
    (run_dir / "source_manifest.json").write_text(json.dumps({"sources": []}), encoding="utf-8")
    (run_dir / "gaps.json").write_text(json.dumps({"gaps": []}), encoding="utf-8")
    (normalized / "identity.json").write_text(json.dumps({"asset_type": {"value": "equity", "provider": "cli", "raw_path": "", "source_url": ""}}), encoding="utf-8")
    runtime_prefix = tmp_path / "runtime" / "AAPL" / "2026-06-01" / "AAPL-validation-scaffold"

    result = run_validator(str(run_dir), "--output-prefix", str(runtime_prefix))

    assert result.returncode != 0
    assert "Validation output prefixes must be under reports/SYMBOL/YYYY-MM-DD" in result.stderr
    assert not runtime_prefix.with_suffix(".json").exists()
    assert not runtime_prefix.with_suffix(".md").exists()


def test_validator_accepts_explicit_reports_output_prefix_for_deterministic_bundle(tmp_path):
    run_dir = tmp_path / "data" / "AAPL" / "2026-06-01"
    normalized = run_dir / "normalized"
    normalized.mkdir(parents=True)
    (run_dir / "research_input_pack.md").write_text("# AAPL Deterministic Research Input Pack\n", encoding="utf-8")
    (run_dir / "manifest.json").write_text(json.dumps({"symbol": "AAPL", "asset_type": "equity"}), encoding="utf-8")
    (run_dir / "source_manifest.json").write_text(json.dumps({"sources": []}), encoding="utf-8")
    (run_dir / "gaps.json").write_text(json.dumps({"gaps": []}), encoding="utf-8")
    (normalized / "identity.json").write_text(json.dumps({"asset_type": {"value": "equity", "provider": "cli", "raw_path": "", "source_url": ""}}), encoding="utf-8")
    reports_prefix = tmp_path / "reports" / "AAPL" / "2026-06-01" / "custom-validation-scaffold"

    result = run_validator(str(run_dir), "--output-prefix", str(reports_prefix))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["validation_json"] == str(reports_prefix.with_suffix(".json"))
    assert reports_prefix.with_suffix(".json").exists()
    assert reports_prefix.with_suffix(".md").exists()


def test_validator_discovers_latest_nested_deterministic_bundle(tmp_path):
    symbol_dir = tmp_path / "data" / "AAPL"
    reports_dir = tmp_path / "reports" / "AAPL" / "2026-06-01"
    old_run = symbol_dir / "2026-05-01"
    new_run = symbol_dir / "2026-06-01"
    for run_dir in [old_run, new_run]:
        normalized = run_dir / "normalized"
        normalized.mkdir(parents=True)
        (run_dir / "research_input_pack.md").write_text("# AAPL Deterministic Research Input Pack\n", encoding="utf-8")
        (run_dir / "manifest.json").write_text(json.dumps({"symbol": "AAPL", "asset_type": "equity"}), encoding="utf-8")
        (run_dir / "source_manifest.json").write_text(json.dumps({"sources": []}), encoding="utf-8")
        (run_dir / "gaps.json").write_text(json.dumps({"gaps": [{"field": run_dir.name, "status": "unavailable_free_source"}]}), encoding="utf-8")
        (normalized / "identity.json").write_text(json.dumps({"asset_type": {"value": "equity", "provider": "cli", "raw_path": "", "source_url": ""}}), encoding="utf-8")

    result = run_validator(str(symbol_dir))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["validation_json"] == str(reports_dir / "AAPL-validation-scaffold.json")
    assert not (new_run / "AAPL-validation-scaffold.json").exists()
    validation = json.loads((reports_dir / "AAPL-validation-scaffold.json").read_text(encoding="utf-8"))
    assert validation["report_markdown"] == str(new_run / "research_input_pack.md")
    assert validation["data_gaps"] == [{"field": "2026-06-01", "status": "unavailable_free_source"}]


def test_validator_flags_deterministic_values_missing_provenance(tmp_path):
    run_dir = tmp_path / "data" / "AAPL" / "2026-06-01"
    reports_dir = tmp_path / "reports" / "AAPL" / "2026-06-01"
    normalized = run_dir / "normalized"
    normalized.mkdir(parents=True)
    (run_dir / "research_input_pack.md").write_text("# AAPL Deterministic Research Input Pack\n", encoding="utf-8")
    (run_dir / "manifest.json").write_text(json.dumps({"symbol": "AAPL", "asset_type": "equity"}), encoding="utf-8")
    (run_dir / "source_manifest.json").write_text(json.dumps({"sources": []}), encoding="utf-8")
    (run_dir / "gaps.json").write_text(json.dumps({"gaps": []}), encoding="utf-8")
    (normalized / "market_snapshot.json").write_text(json.dumps({"latest_close": {"value": 123.45, "provider": "tiingo"}}), encoding="utf-8")

    result = run_validator(str(run_dir))

    assert result.returncode == 0, result.stderr
    assert not (run_dir / "AAPL-validation-scaffold.json").exists()
    validation = json.loads((reports_dir / "AAPL-validation-scaffold.json").read_text(encoding="utf-8"))
    issue_ids = {issue["id"] for issue in validation["issues"]}
    assert "normalized-market_snapshot-latest_close-source_url" in issue_ids
    assert "normalized-market_snapshot-latest_close-raw_path" in issue_ids


def test_validator_accepts_cli_asset_type_override_without_source_url(tmp_path):
    run_dir = tmp_path / "data" / "SPY" / "2026-06-01"
    reports_dir = tmp_path / "reports" / "SPY" / "2026-06-01"
    normalized = run_dir / "normalized"
    normalized.mkdir(parents=True)
    (run_dir / "research_input_pack.md").write_text("# SPY Deterministic Research Input Pack\n", encoding="utf-8")
    (run_dir / "manifest.json").write_text(json.dumps({"symbol": "SPY", "asset_type": "etf"}), encoding="utf-8")
    (run_dir / "source_manifest.json").write_text(json.dumps({"sources": []}), encoding="utf-8")
    (run_dir / "gaps.json").write_text(json.dumps({"gaps": []}), encoding="utf-8")
    (normalized / "identity.json").write_text(json.dumps({"asset_type": {"value": "etf", "provider": "cli", "raw_path": "", "source_url": ""}}), encoding="utf-8")

    result = run_validator(str(run_dir))

    assert result.returncode == 0, result.stderr
    assert not (run_dir / "SPY-validation-scaffold.json").exists()
    validation = json.loads((reports_dir / "SPY-validation-scaffold.json").read_text(encoding="utf-8"))
    assert validation["blocking_issue_count"] == 0


def test_validator_rejects_non_data_deterministic_bundle(tmp_path):
    run_dir = tmp_path / "frozen_bundle"
    normalized = run_dir / "normalized"
    normalized.mkdir(parents=True)
    (run_dir / "research_input_pack.md").write_text("# SPY Deterministic Research Input Pack\n", encoding="utf-8")
    (run_dir / "manifest.json").write_text(json.dumps({"symbol": "SPY", "asset_type": "etf"}), encoding="utf-8")
    (run_dir / "source_manifest.json").write_text(json.dumps({"sources": []}), encoding="utf-8")
    (run_dir / "gaps.json").write_text(json.dumps({"gaps": []}), encoding="utf-8")
    (normalized / "identity.json").write_text(json.dumps({"asset_type": {"value": "etf", "provider": "cli", "raw_path": "", "source_url": ""}}), encoding="utf-8")

    result = run_validator(str(run_dir))

    assert result.returncode != 0
    assert "Deterministic bundles must be under data/SYMBOL/YYYY-MM-DD" in result.stderr
    assert not (run_dir / "SPY-validation-scaffold.json").exists()


def test_validator_rejects_runtime_deterministic_bundle(tmp_path):
    run_dir = tmp_path / "runtime" / "SPY" / "2026-06-01"
    normalized = run_dir / "normalized"
    normalized.mkdir(parents=True)
    (run_dir / "research_input_pack.md").write_text("# SPY Deterministic Research Input Pack\n", encoding="utf-8")
    (run_dir / "manifest.json").write_text(json.dumps({"symbol": "SPY", "asset_type": "etf"}), encoding="utf-8")
    (run_dir / "source_manifest.json").write_text(json.dumps({"sources": []}), encoding="utf-8")
    (run_dir / "gaps.json").write_text(json.dumps({"gaps": []}), encoding="utf-8")
    (normalized / "identity.json").write_text(json.dumps({"asset_type": {"value": "etf", "provider": "cli", "raw_path": "", "source_url": ""}}), encoding="utf-8")

    result = run_validator(str(run_dir))

    assert result.returncode != 0
    assert "Deterministic bundles must be under data/SYMBOL/YYYY-MM-DD" in result.stderr
    assert not (run_dir / "SPY-validation-scaffold.json").exists()
