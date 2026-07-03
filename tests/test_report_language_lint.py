from pathlib import Path
import importlib.util
import json


ROOT = Path(__file__).resolve().parents[1]
LINT = ROOT / "market-research" / "shared" / "scripts" / "report_language_lint.py"


def load_module():
    spec = importlib.util.spec_from_file_location("report_language_lint", LINT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_investor_reports_do_not_use_internal_frozen_language():
    offenders = []
    for path in (ROOT / "reports").glob("*/*/*-research.md"):
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        if "frozen" in text or "freeze" in text:
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_report_language_lint_rejects_skill_internal_paths_in_main_body():
    module = load_module()
    text = """# QUBT Research

## Bottom Line

Primary evidence consists of the deterministic bundle under `data/QUBT/2026-06-23/`.

## Evidence Appendix

`data/QUBT/2026-06-23/source_manifest.json`
"""

    findings = module.lint_report_language(text)

    assert any("skill-internal provenance belongs in an appendix" in finding["message"] for finding in findings)


def test_report_language_lint_allows_internal_paths_in_appendix():
    module = load_module()
    text = """# QUBT Research

## Bottom Line

The investment case depends on contract conversion.

## Evidence Appendix

`data/QUBT/2026-06-23/source_manifest.json`
"""

    findings = module.lint_report_language(text)

    assert findings == []


def test_report_language_lint_rejects_saved_deterministic_artifact_language_in_main_body():
    module = load_module()
    text = """# QUBT Research

## Bottom Line

The latest saved 10-Q and deterministic artifact show the company has cash.

## Data Issues And Discrepancies

Provider conflicts are discussed here.

## Sources And Evidence

Local artifacts are listed here.
"""

    findings = module.lint_report_language(text)

    patterns = {finding["pattern"] for finding in findings}
    assert "saved" in patterns
    assert "deterministic" in patterns
    assert "artifact" in patterns


def test_report_language_lint_rejects_routine_vendor_names_in_main_body():
    module = load_module()
    text = """# QUBT Research

## Valuation

Alpha Vantage reported one market cap and FMP reported another.

## Data Issues And Discrepancies

The market-cap discrepancy is explained here.
"""

    findings = module.lint_report_language(text)

    assert any(finding["pattern"] == "vendor-name-main-body" for finding in findings)


def test_report_language_lint_allows_vendor_names_in_data_issues():
    module = load_module()
    text = """# QUBT Research

## Valuation

Market capitalization is best read as a range.

## Data Issues And Discrepancies

Alpha Vantage and FMP disagreed on market capitalization.

## Sources And Evidence

Provider details are recorded here.
"""

    findings = module.lint_report_language(text)

    assert findings == []


def test_report_language_lint_flags_short_bottom_line_without_market_value():
    module = load_module()
    text = """# QUBT Research

## Bottom Line

QUBT is speculative.

## Key Facts

| Item | Latest / Current | Why It Matters |
| --- | --- | --- |
| Security | US-listed equity | Defines exposure |
"""

    findings = module.lint_report_structure(text)

    ids = {finding["id"] for finding in findings}
    assert "bottom-line-too-short" in ids
    assert "bottom-line-missing-market-value" in ids


def test_report_language_lint_accepts_etf_net_assets_in_bottom_line():
    module = load_module()
    text = """# ECH Research

## Bottom Line

ECH is a single-country ETF with about $1.03 billion of net assets, 25 holdings, concentrated Chile exposure, and a clear portfolio role for investors who want targeted country risk. The valuation case depends on portfolio multiples, NAV behavior, liquidity, premium/discount control, and whether the top holdings can keep supporting returns. The main risks are country concentration, currency, commodity exposure, ETF trading mechanics, and drawdown behavior.
"""

    findings = module.lint_report_structure(text)

    ids = {finding["id"] for finding in findings}
    assert "bottom-line-missing-market-value" not in ids


def test_report_language_lint_rejects_self_check_sections():
    module = load_module()
    text = """# ECH Research

## Bottom Line

ECH is a single-country ETF with market value context and enough words to satisfy the summary threshold. This paragraph discusses the exposure, valuation context, trading setup, risks, and monitoring triggers with enough detail for an investor-facing executive summary.

## Self-Check

I checked the workflow outputs.
"""

    findings = module.lint_report_structure(text)

    assert any(finding.get("id") == "self-check-section" for finding in findings)


def test_report_language_lint_requires_key_facts_table_and_technical_analysis_terms():
    module = load_module()
    text = """# QUBT Research

## Bottom Line

This is a long enough executive summary paragraph with market cap context of $2 billion and enough words to avoid the short-summary finding. It explains the business, risk, valuation, and monitoring questions for the investor in a concise way. It continues with enough context about liquidity, commercialization, expected evidence, and the main operating questions to satisfy the summary length requirement for this structural test.

## Key Facts

- Security: US-listed equity

## Market Snapshot And Technical Analysis

The stock moved recently.
"""

    findings = module.lint_report_structure(text)

    ids = {finding["id"] for finding in findings}
    assert "key-facts-not-table" in ids
    assert "technical-analysis-too-thin" in ids


def test_report_language_lint_rejects_qubt_style_main_body_provenance():
    module = load_module()
    text = """# QUBT Research

## Bottom Line

The latest deterministic adjusted close was $10.76, with a primary normalized market capitalization.

## Market Snapshot And Technical Analysis

| Metric | Value | Evidence |
| --- | ---: | --- |
| Latest adjusted close | $10.76 | Deterministic Tiingo normalized prices |
| Latest quote volume | 21.44M shares | Twelve Data quote |

## Data Issues And Discrepancies

Provider details are discussed here.
"""

    findings = module.lint_report_language(text)

    patterns = [finding.get("pattern") for finding in findings]
    assert patterns.count("deterministic") >= 1


def test_report_quality_lint_flags_runtime_source_bundle_when_report_copy_exists(tmp_path):
    module = load_module()
    report_dir = tmp_path / "reports" / "QTUP" / "2026-07-01"
    report_dir.mkdir(parents=True)
    report = report_dir / "QTUP-research.md"
    copied = report_dir / "source_bundle" / "qtup_prospectus.pdf"
    copied.parent.mkdir()
    copied.write_bytes(b"prospectus")
    text = f"""# QTUP Research

## Sources And Evidence

| Source ID | Evidence |
| --- | --- |
| qtup_prospectus | runtime/market-research-batch-20260701/QTUP/2026-07-01/source_bundle/{copied.name} |
"""
    report.write_text(text, encoding="utf-8")

    findings = module.lint_report_quality(text, {}, report_path=report)

    assert any(finding.get("id") == "runtime-source-bundle-path" for finding in findings)


def test_report_language_lint_cli_prints_structural_findings(tmp_path):
    report = tmp_path / "report.md"
    report.write_text(
        """# ABC Research

## Bottom Line

ABC is speculative.
""",
        encoding="utf-8",
    )

    import subprocess

    result = subprocess.run(
        ["python3", str(LINT), str(report)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert result.returncode == 1
    assert "bottom-line-too-short" in result.stdout
    assert "Traceback" not in result.stderr


def test_report_quality_lint_flags_internal_language_before_evidence_sections():
    module = load_module()
    text = """# ECH Research

## Bottom Line

The latest deterministic close came from the deterministic bundle.

## Sources And Evidence

The deterministic bundle is listed for auditability.
"""

    findings = module.lint_report_quality(text, {})

    assert any(finding.get("id") == "main-body-internal-language" for finding in findings)


def test_report_quality_lint_flags_missing_drawdown_when_json_has_drawdown():
    module = load_module()
    text = """# ECH Research

## Market Snapshot And Technical Analysis

Trend, moving averages, volume, volatility, support, and resistance are discussed.
"""
    report_json = {"technical_analysis": {"max_drawdown_available": -0.370986}}

    findings = module.lint_report_quality(text, report_json)

    assert any(finding.get("id") == "technical-analysis-missing-drawdown" for finding in findings)


def test_report_quality_lint_flags_etf_risk_checklist_gaps():
    module = load_module()
    text = """# ECH Research

## Risks And Invalidation Points

The main risks are country, currency, concentration, premium/discount, tracking, tax, withholding, liquidity, and closure risk.
"""
    report_json = {"security_type": "etf"}

    findings = module.lint_report_quality(text, report_json)

    assert any(finding.get("id") == "etf-risk-missing-creation-redemption" for finding in findings)
    assert any(finding.get("id") == "etf-risk-missing-securities-lending" for finding in findings)


def test_report_quality_lint_requires_etf_portfolio_companies_snapshot_when_holdings_exist():
    module = load_module()
    text = """# ECH Research

## Risks And Invalidation Points

Creation/redemption, authorized participant, securities lending, premium/discount, tracking, tax, withholding, liquidity, closure, and concentration risks are discussed.
"""
    report_json = {
        "security_type": "etf",
        "holdings": [{"name": "Banco de Chile", "weight": 0.08}],
    }

    findings = module.lint_report_quality(text, report_json)

    assert any(finding.get("id") == "etf-missing-portfolio-companies-snapshot" for finding in findings)


def test_report_quality_lint_flags_unsupported_etf_holding_business_context(tmp_path):
    module = load_module()
    report = tmp_path / "reports" / "QTUM" / "2026-07-02" / "QTUM-research.md"
    report.parent.mkdir(parents=True)
    report.write_text(
        """# QTUM Research

## Portfolio Companies Snapshot

| Holding | Weight | Sector / Industry | Business And Outlook |
| --- | ---: | --- | --- |
| Horizon Quantum | 2.47% | Quantum software | Pure-play quantum exposure. |
""",
        encoding="utf-8",
    )
    report_json = {
        "security_type": "etf",
        "etf_holdings": {
            "top25": [
                {
                    "name": "Horizon Quantum",
                    "weight": "2.47%",
                    "sector_or_industry": "Quantum software",
                    "business_outlook": "Pure-play quantum exposure.",
                }
            ],
            "source_ids": ["sponsor_full_holdings"],
        },
    }

    findings = module.lint_report_quality(report.read_text(encoding="utf-8"), report_json, report)

    assert any(
        finding.get("id") == "etf-holding-company-context-unsupported"
        and finding.get("severity") == "moderate"
        for finding in findings
    )


def test_report_quality_lint_accepts_cited_etf_holding_classification_context(tmp_path):
    module = load_module()
    report = tmp_path / "reports" / "QTUM" / "2026-07-02" / "QTUM-research.md"
    report.parent.mkdir(parents=True)
    report.write_text(
        """# QTUM Research

## Portfolio Companies Snapshot

| Holding | Weight | Sector / Industry | Business And Outlook |
| --- | ---: | --- | --- |
| Horizon Quantum | 2.47% | Quantum software | Pure-play quantum exposure. |
""",
        encoding="utf-8",
    )
    report_json = {
        "security_type": "etf",
        "etf_holdings": {
            "top25": [
                {
                    "name": "Horizon Quantum",
                    "weight": "2.47%",
                    "sector_or_industry": "Quantum software",
                    "business_outlook": "Pure-play quantum exposure.",
                    "source_ids": ["holdings_classification"],
                }
            ]
        },
    }

    findings = module.lint_report_quality(report.read_text(encoding="utf-8"), report_json, report)

    assert not any(finding.get("id") == "etf-holding-company-context-unsupported" for finding in findings)


def test_report_quality_lint_flags_thin_etf_holding_context(tmp_path):
    module = load_module()
    report = tmp_path / "reports" / "QTUM" / "2026-07-02" / "QTUM-research.md"
    report.parent.mkdir(parents=True)
    report.write_text(
        """# QTUM Research

## Portfolio Companies Snapshot

| Holding | Weight |
| --- | ---: |
| Holding 1 | 2.47% |
""",
        encoding="utf-8",
    )
    report_json = {
        "security_type": "etf",
        "etf_holdings": {
            "top25": [{"name": f"Holding {index}", "weight": "1.00%"} for index in range(25)]
        },
    }

    findings = module.lint_report_quality(report.read_text(encoding="utf-8"), report_json, report)

    assert any(
        finding.get("id") == "etf-holding-company-context-too-thin"
        and finding.get("severity") == "moderate"
        for finding in findings
    )


def test_report_language_lint_cli_uses_report_json_for_etf_snapshot_check(tmp_path):
    report = tmp_path / "ECH-research.md"
    report_json = tmp_path / "ECH-research.json"
    report.write_text(
        """# ECH Research

## Bottom Line

ECH has market value context and enough words to avoid the short summary finding. This paragraph describes the fund, the portfolio, the valuation context, major risks, and monitoring considerations in ordinary investor-facing language for a compact regression test.

## Key Facts

| Item | Latest / Current | Why It Matters |
| --- | --- | --- |
| Security | ETF | Defines exposure |

## Market Snapshot And Technical Analysis

Trend, support, resistance, moving averages, volume, volatility, and drawdown are discussed.

## Risks And Invalidation Points

Creation/redemption, authorized participant, securities lending, premium/discount, tracking, tax, withholding, liquidity, closure, and concentration risks are discussed.
""",
        encoding="utf-8",
    )
    report_json.write_text(json.dumps({"security_type": "etf", "holdings": [{"name": "Banco de Chile", "weight": 0.08}]}), encoding="utf-8")

    import subprocess

    result = subprocess.run(
        ["python3", str(LINT), str(report), "--report-json", str(report_json)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert result.returncode == 1
    assert "etf-missing-portfolio-companies-snapshot" in result.stdout
