from cool_financial_research import __version__
from cool_financial_research.schemas import (
    Issue,
    IssueSeverity,
    ValidationStructuredData,
)
from cool_financial_research import charts, etf_holdings, ledger, pdf, source_bundle, xbrl


def test_version_is_v0_7():
    assert __version__ == "0.7.0"


def test_openclaw_support_modules_are_still_importable():
    assert callable(charts.cmd_generate_charts)
    assert callable(etf_holdings.extract_holdings_rows_from_json)
    assert callable(ledger.assessment_from_validation)
    assert callable(pdf.simple_markdown_to_html)
    assert callable(source_bundle.classify_with_edgar)
    assert callable(xbrl.latest_fact_by_tag)


def test_pydantic_validation_counts_match():
    issue = Issue(
        id="I1",
        severity=IssueSeverity.critical,
        section="10",
        issue="Bad valuation",
        status="open",
        required_fix="Recompute",
        source_or_evidence="10-K",
        source_confidence="high",
    )
    payload = dict(
        symbol="TST",
        security_type="equity",
        validation_date="2026-05-25",
        overall_verdict="pass_with_revisions",
        recommendation_confidence="medium",
        critical_count=1,
        moderate_count=0,
        minor_count=0,
        issues=[issue],
        unresolved_due_to_data_unavailable=[],
        sources_checked=[],
        data_freshness_audit=[],
        data_gaps=[],
        summary="summary",
    )
    model = ValidationStructuredData(**payload)
    assert model.open_fixable_blocking_issue_ids == ["I1"]
