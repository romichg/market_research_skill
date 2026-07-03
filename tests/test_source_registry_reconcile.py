import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "market-research" / "shared" / "scripts" / "source_registry_reconcile.py"
VALIDATOR = ROOT / "market-research" / "shared" / "scripts" / "validate_market_research.py"


def load_module():
    spec = importlib.util.spec_from_file_location("source_registry_reconcile", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_report_and_data(tmp_path):
    report_dir = tmp_path / "reports" / "EWW" / "2026-07-01"
    data_dir = tmp_path / "data" / "EWW" / "2026-07-01"
    normalized = data_dir / "normalized"
    report_dir.mkdir(parents=True)
    normalized.mkdir(parents=True)
    (normalized / "prices_daily.json").write_text(json.dumps({"prices": []}), encoding="utf-8")
    (normalized / "technical_signals.json").write_text(json.dumps({"latest_close": {"value": 22.5}}), encoding="utf-8")
    (data_dir / "manifest.json").write_text(json.dumps({"symbol": "EWW", "as_of": "2026-07-01"}), encoding="utf-8")
    (data_dir / "source_manifest.json").write_text(json.dumps({"sources": []}), encoding="utf-8")
    (data_dir / "gaps.json").write_text(json.dumps({"gaps": []}), encoding="utf-8")
    (data_dir / "research_input_pack.md").write_text("# EWW Deterministic Research Input Pack\n", encoding="utf-8")
    (report_dir / "EWW-research.md").write_text(
        """# EWW Research

## Sources And Evidence

| Source ID | Use |
| --- | --- |
| det_prices_daily | Price history |
""",
        encoding="utf-8",
    )
    (report_dir / "EWW-research.json").write_text(
        json.dumps(
            {
                "symbol": "EWW",
                "security_type": "etf",
                "as_of_date": "2026-07-01",
                "deterministic_bundle": {"bundle_dir": str(data_dir)},
                "material_claims": [{"claim": "EWW closed at $22.50.", "source_id": "det_technical_signals"}],
                "data_gaps": [],
                "technical_analysis": {},
                "valuation_or_performance": {},
                "decision_factors": {},
                "risks": [],
                "catalysts": [],
                "source_coverage": {},
                "calculation_audit": [],
            }
        ),
        encoding="utf-8",
    )
    (report_dir / "sources.json").write_text(json.dumps({"sources": []}), encoding="utf-8")
    return report_dir, data_dir


def test_source_registry_reconcile_fixes_all_template_deterministic_aliases(tmp_path):
    module = load_module()
    report_dir = tmp_path / "reports" / "EWW" / "2026-07-02"
    data_dir = tmp_path / "data" / "EWW" / "2026-07-02"
    normalized = data_dir / "normalized"
    report_dir.mkdir(parents=True)
    normalized.mkdir(parents=True)
    for name in ["identity", "etf_profile", "etf_holdings"]:
        (normalized / f"{name}.json").write_text(json.dumps({"field": {"value": name}}), encoding="utf-8")
    for name in ["gaps", "source_manifest", "deterministic_data_usage", "manifest"]:
        (data_dir / f"{name}.json").write_text(json.dumps({}), encoding="utf-8")
    (data_dir / "research_input_pack.md").write_text("# EWW Pack\n", encoding="utf-8")
    (report_dir / "EWW-research.md").write_text(
        """# EWW Research

## Sources And Evidence

deterministic_identity deterministic_etf_profile deterministic_etf_holdings deterministic_gaps deterministic_source_manifest deterministic_data_usage
""",
        encoding="utf-8",
    )
    (report_dir / "EWW-research.json").write_text(
        json.dumps(
            {
                "symbol": "EWW",
                "security_type": "etf",
                "as_of_date": "2026-07-02",
                "deterministic_bundle": {"bundle_dir": str(data_dir)},
                "material_claims": [],
                "source_coverage": {
                    "deterministic_source_ids": [
                        "deterministic_identity",
                        "deterministic_etf_profile",
                        "deterministic_etf_holdings",
                        "deterministic_gaps",
                        "deterministic_source_manifest",
                        "deterministic_data_usage",
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    (report_dir / "sources.json").write_text(json.dumps({"sources": []}), encoding="utf-8")

    result = module.reconcile_report_sources(report_dir, data_dir, fix=True)

    assert set(result["added_ids"]) == {
        "deterministic_identity",
        "deterministic_etf_profile",
        "deterministic_etf_holdings",
        "deterministic_gaps",
        "deterministic_source_manifest",
        "deterministic_data_usage",
    }
    sources = json.loads((report_dir / "sources.json").read_text(encoding="utf-8"))["sources"]
    by_id = {source["id"]: source for source in sources}
    assert by_id["deterministic_identity"]["local_artifact"].endswith("normalized/identity.json")
    assert by_id["deterministic_gaps"]["local_artifact"].endswith("gaps.json")
    assert by_id["deterministic_source_manifest"]["local_artifact"].endswith("source_manifest.json")
    assert by_id["deterministic_data_usage"]["local_artifact"].endswith("deterministic_data_usage.json")


def test_source_registry_reconcile_scans_source_id_lists_recursively():
    module = load_module()
    report = {
        "source_coverage": {
            "deterministic_source_ids": ["deterministic_gaps", "deterministic_etf_profile"]
        },
        "calculation_audit": [
            {"inputs": [{"source_ids": ["deterministic_prices_daily"]}]}
        ],
    }

    assert module.source_ids_from_report_json(report) == {
        "deterministic_gaps",
        "deterministic_etf_profile",
        "deterministic_prices_daily",
    }


def test_source_registry_reconcile_fixes_missing_deterministic_ids(tmp_path):
    module = load_module()
    report_dir, data_dir = write_report_and_data(tmp_path)

    result = module.reconcile_report_sources(report_dir, data_dir, fix=True)

    assert result["missing_ids"] == ["det_prices_daily", "det_technical_signals"]
    assert set(result["added_ids"]) == {"det_prices_daily", "det_technical_signals"}
    sources = json.loads((report_dir / "sources.json").read_text(encoding="utf-8"))["sources"]
    by_id = {source["id"]: source for source in sources}
    assert by_id["det_prices_daily"]["local_artifact"].endswith("normalized/prices_daily.json")
    assert by_id["det_technical_signals"]["sha256"]


def test_source_registry_reconcile_check_cli_exits_nonzero_for_missing_ids(tmp_path):
    report_dir, data_dir = write_report_and_data(tmp_path)

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "check", str(report_dir), "--data-dir", str(data_dir)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["missing_ids"] == ["det_prices_daily", "det_technical_signals"]


def test_unmirrored_runtime_source_ids_flags_procedural_sources_missing_from_report(tmp_path):
    module = load_module()
    report_dir = tmp_path / "reports" / "ECH" / "2026-07-03"
    report_dir.mkdir(parents=True)
    (report_dir / "sources.json").write_text(
        json.dumps({"sources": [{"id": "stockanalysis_overview"}]}), encoding="utf-8"
    )
    runtime_dated_dir = tmp_path / "runtime" / "ECH" / "2026-07-03"
    runtime_dated_dir.mkdir(parents=True)
    (runtime_dated_dir / "sources.json").write_text(
        json.dumps({"sources": [{"id": "stockanalysis_overview"}, {"id": "globalx_copx_product_page"}]}),
        encoding="utf-8",
    )

    # Default lookup derives runtime/SYMBOL/AS_OF from report_dir.
    assert module.unmirrored_runtime_source_ids(report_dir) == {"globalx_copx_product_page"}

    # A coarser SYMBOL-level --runtime-dir (as producer_self_check.py conventionally passes) also resolves.
    coarse_runtime_dir = tmp_path / "runtime" / "ECH"
    assert module.unmirrored_runtime_source_ids(report_dir, coarse_runtime_dir) == {"globalx_copx_product_page"}


def test_source_registry_issues_includes_unmirrored_runtime_sources(tmp_path):
    report_dir, data_dir = write_report_and_data(tmp_path)
    module = load_module()
    runtime_dir = tmp_path / "runtime" / "EWW" / "2026-07-01"
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "sources.json").write_text(
        json.dumps({"sources": [{"id": "procedural_only_source"}]}), encoding="utf-8"
    )

    issues = module.source_registry_issues(report_dir, data_dir, runtime_dir=runtime_dir)

    issue_ids = {issue["id"] for issue in issues}
    assert "source-registry-unmirrored-procedural-only-source" in issue_ids


def test_validator_surfaces_missing_source_registry_ids(tmp_path):
    report_dir, data_dir = write_report_and_data(tmp_path)

    result = subprocess.run(
        [sys.executable, str(VALIDATOR), str(report_dir)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    validation = json.loads((report_dir / "EWW-validation-scaffold.json").read_text(encoding="utf-8"))
    issue_ids = {issue["id"] for issue in validation["issues"]}
    assert "source-registry-missing-det-technical-signals" in issue_ids
