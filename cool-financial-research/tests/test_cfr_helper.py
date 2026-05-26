from pathlib import Path
import subprocess

from cool_financial_research import openclaw_helper as mod


def validation_payload(issues, critical=0, moderate=0, minor=0):
    return {
        "symbol": "TST",
        "security_type": "equity",
        "stage": "validation",
        "iteration": 1,
        "markdown_report": "# Validation",
        "structured_data": {
            "symbol": "TST",
            "security_type": "equity",
            "validation_date": "2026-05-24",
            "overall_verdict": "pass_with_revisions",
            "recommendation_confidence": "medium",
            "critical_count": critical,
            "moderate_count": moderate,
            "minor_count": minor,
            "issues": issues,
            "unresolved_due_to_data_unavailable": [
                i for i in issues if i.get("status") == "unresolved_data_unavailable"
            ],
            "sources_checked": [],
            "data_freshness_audit": [],
            "data_gaps": [],
            "summary": "summary",
        },
    }


def issue(issue_id="I1", severity="critical", status="open"):
    return {
        "id": issue_id,
        "severity": severity,
        "section": "10",
        "issue": "bad DCF",
        "status": status,
        "required_fix": "Recompute from filings",
        "source_or_evidence": "10-K",
        "source_confidence": "high",
        "unresolved_reason": "not disclosed" if status == "unresolved_data_unavailable" else None,
    }


def research_payload(stage="research", fix_response=None):
    section = {
        "number": 1,
        "title": "Executive Summary",
        "facts": ["Fact"],
        "interpretation": ["Interpretation"],
        "quantitative_claims": [],
        "sources": [],
        "open_questions": [],
    }
    return {
        "symbol": "TST",
        "security_type": "equity",
        "stage": stage,
        "iteration": 0,
        "markdown_report": "# Report",
        "structured_data": {
            "symbol": "TST",
            "security_type": "equity",
            "analysis_date": "2026-05-24",
            "summary": "summary",
            "quality_control": {
                "primary_sources_preferred": True,
                "facts_interpretation_separated": True,
                "quant_claims_sourced_or_marked_unverified": True,
                "stale_data_flagged": True,
            },
            "sections": [dict(section, number=i, title=f"Section {i}") for i in range(1, 17)],
            "sources": [],
            "open_questions": [],
            "unresolved_issues": [],
            "fix_response": fix_response,
        },
    }


def test_stop_when_no_blocking_issues():
    result = mod.validation_stop_result(validation_payload([]))
    assert result["should_stop"] is True
    assert result["reason"] == "no_blocking_issues"


def test_cfr_helper_help_succeeds():
    result = subprocess.run(
        ["python3", "scripts/cfr_helper.py", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_continue_when_open_critical_issue_exists():
    payload = validation_payload([issue()], critical=1)
    result = mod.validation_stop_result(payload)
    assert result["should_stop"] is False
    assert result["open_fixable_blocking_issues"] == 1


def test_stop_when_blocking_issues_are_unresolved_data_unavailable():
    payload = validation_payload([issue("I2", "moderate", "unresolved_data_unavailable")], moderate=1)
    result = mod.validation_stop_result(payload)
    assert result["should_stop"] is True
    assert result["reason"] == "only_unresolved_data_unavailable"


def test_validation_counts_must_match_issue_list():
    payload = validation_payload([issue("I1", "critical", "open")], critical=0)
    errors = mod.validate_validation_counts(payload)
    assert any("critical_count" in e for e in errors)


def test_fix_response_must_cover_previous_open_blocking_ids():
    previous = validation_payload([issue("DCF-1", "critical", "open")], critical=1)
    fixed = research_payload(stage="fix", fix_response={"validation_iteration": 1, "addressed_issues": []})
    errors = mod.validate_fix_coverage(fixed, previous)
    assert any("DCF-1" in e for e in errors)


def test_fix_response_accepts_fixed_or_unresolved():
    previous = validation_payload([issue("DCF-1", "critical", "open")], critical=1)
    fixed = research_payload(
        stage="fix",
        fix_response={
            "validation_iteration": 1,
            "addressed_issues": [
                {"issue_id": "DCF-1", "status": "unresolved_data_unavailable", "explanation": "Primary data unavailable"}
            ],
        },
    )
    assert mod.validate_fix_coverage(fixed, previous) == []



def test_data_gap_assessment_ranks_retail_services_for_estimates_gap():
    payload = validation_payload([
        {
            **issue("EST-1", "moderate", "unresolved_data_unavailable"),
            "issue": "Analyst consensus estimates and price target distribution could not be verified from primary free sources",
            "required_fix": "Use a licensed consensus estimates source or mark unverified",
            "source_confidence": "unverified",
        }
    ], moderate=1)
    assessment = mod.assessment_from_validation(payload, symbol="TST")
    assert assessment["category_totals"]
    assert "consensus_estimates" in assessment["category_totals"]
    services = [s["service"] for s in assessment["service_rankings"]]
    assert any(s in services for s in ["Fiscal.ai", "TIKR", "Koyfin"])


def test_ledger_deduplicates_same_run_id():
    payload = validation_payload([
        {
            **issue("OPT-1", "critical", "open"),
            "issue": "Options flow, put/call skew, and gamma positioning are unverified",
            "source_confidence": "low",
        }
    ], critical=1)
    assessment = mod.assessment_from_validation(payload, symbol="TST")
    ledger = mod.load_ledger(Path("/tmp/does-not-exist-provider-ledger.json"))
    ledger, added1 = mod.merge_assessment_into_ledger(ledger, assessment, run_id="run-1")
    ledger, added2 = mod.merge_assessment_into_ledger(ledger, assessment, run_id="run-1")
    assert added1 is True
    assert added2 is False
    assert ledger["run_count"] == 1
    assert "options_derivatives" in ledger["category_totals"]


def test_decode_http_body_handles_gzip_magic_bytes():
    import gzip as _gzip
    payload = b'{"ok": true}'
    encoded = _gzip.compress(payload)
    assert mod.decode_http_body(encoded) == payload


def test_html_csv_detection_rejects_html():
    html = b"<!doctype html><html><body>not csv</body></html>"
    assert mod.looks_like_html(html, "text/html") is True
    assert mod.looks_like_csv(html, "text/csv") is False


def test_build_source_bundle_with_etf_override_proceeds_when_edgar_fails(tmp_path, monkeypatch, capsys):
    def fake_classify(*args, **kwargs):
        raise SystemExit(2)
    monkeypatch.setattr(mod, "classify_with_edgar", fake_classify)
    args = type("Args", (), {
        "symbol": "ECH",
        "output_root": str(tmp_path),
        "security_type": "etf",
        "sec_user_agent": "test-agent",
        "no_edgar_enrich": False,
        "issuer": "none",
        "ishares_product_id": None,
        "issuer_product_map": None,
        "url": None,
    })()
    mod.cmd_build_source_bundle(args)
    classification = mod.read_json(tmp_path / "ECH" / "source_bundle" / "classification.json")
    assert classification["security_type"] == "etf"
    manifest = mod.read_json(tmp_path / "ECH" / "run_manifest.json")
    assert any(i["category"] == "classification_fallback" for i in manifest["operational_issues"])


def test_preflight_shape_records_capabilities(tmp_path):
    status = mod.preflight_status(tmp_path)
    assert status["required"]["stdlib"] is True
    assert "pdf_text_extraction_available" in status["capabilities"]
    assert "optional_pdf_render_tools" in status


def test_render_pdf_optional_writes_html_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "module_available", lambda name: False)
    monkeypatch.setattr(mod.shutil, "which", lambda name: None)
    md = tmp_path / "report.md"
    pdf = tmp_path / "report.pdf"
    md.write_text("# Report\n\n- item\n", encoding="utf-8")
    args = type("Args", (), {"markdown_file": str(md), "pdf_file": str(pdf), "title": "Report", "optional": True})()
    mod.cmd_render_pdf(args)
    assert pdf.with_suffix(".html").exists()
    status = mod.read_json(pdf.with_suffix(".pdf-error.txt"))
    assert status["pdf_created"] is False
    assert status["html_created"] is True


def test_record_operational_issue_appends_manifest(tmp_path):
    out = tmp_path
    (out / "TST").mkdir()
    (out / "TST" / "run_manifest.json").write_text('{"symbol":"TST","files":[]}', encoding="utf-8")
    manifest = mod.append_operational_issue(out, "TST", {"stage": "test", "category": "source_wrong_content_type", "issue": "bad csv", "resolution": "use json"})
    assert manifest["operational_issues"][0]["category"] == "source_wrong_content_type"


def test_extract_holdings_rows_from_nested_issuer_json():
    payload = {
        "fund": {
            "holdings": [
                {"ticker": "AAA", "name": "AAA SA", "weightPercent": "12.5", "sector": "Financials", "country": "Chile"},
                {"ticker": "BBB", "name": "BBB SA", "weightPercent": "7.5", "sector": "Utilities", "country": "Chile"},
            ]
        }
    }
    rows = mod.extract_holdings_rows_from_json(payload)
    assert len(rows) == 2
    assert rows[0]["ticker"] == "AAA"
    assert rows[0]["weight"] == 12.5
    summary = mod.summarize_holdings_rows(rows, source="fixture")
    assert summary["top10_weight"] == 20.0
