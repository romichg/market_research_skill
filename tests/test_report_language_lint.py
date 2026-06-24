from pathlib import Path
import importlib.util


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
