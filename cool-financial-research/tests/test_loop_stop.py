from cool_financial_research.schemas import (
    Issue,
    IssueSeverity,
    SecurityType,
    ValidationStageOutput,
    ValidationStructuredData,
)
from cool_financial_research.workflow import should_stop_validation


def validation_with_issues(issues, critical=0, moderate=0):
    return ValidationStageOutput(
        symbol="ABC",
        security_type=SecurityType.equity,
        iteration=1,
        markdown_report="# Validation",
        structured_data=ValidationStructuredData(
            symbol="ABC",
            security_type=SecurityType.equity,
            validation_date="2026-05-24",
            overall_verdict="pass_with_revisions",
            recommendation_confidence="medium",
            critical_count=critical,
            moderate_count=moderate,
            minor_count=0,
            issues=issues,
            summary="summary",
        ),
    )


def test_stops_when_no_blocking_issues():
    should_stop, reason = should_stop_validation(validation_with_issues([]))
    assert should_stop is True
    assert reason == "no_blocking_issues"


def test_continues_when_open_moderate_issue_exists():
    validation = validation_with_issues(
        [
            Issue(
                severity=IssueSeverity.moderate,
                section="Valuation",
                issue="DCF arithmetic does not tie out",
                status="open",
            )
        ],
        moderate=1,
    )
    should_stop, reason = should_stop_validation(validation)
    assert should_stop is False
    assert reason == ""


def test_stops_when_blocking_issue_is_unresolved_data_unavailable():
    validation = validation_with_issues(
        [
            Issue(
                severity=IssueSeverity.critical,
                section="SEC Filings",
                issue="Primary source unavailable",
                status="unresolved_data_unavailable",
            )
        ],
        critical=1,
    )
    should_stop, reason = should_stop_validation(validation)
    assert should_stop is True
    assert reason == "only_unresolved_data_unavailable"
