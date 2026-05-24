from __future__ import annotations

from cool_financial_research.schemas import IssueSeverity, ValidationStageOutput


def should_stop_validation(validation: ValidationStageOutput) -> tuple[bool, str]:
    data = validation.structured_data
    blocking = [
        issue
        for issue in data.issues
        if issue.severity in {IssueSeverity.critical, IssueSeverity.moderate}
    ]
    open_fixable = [issue for issue in blocking if issue.status == "open"]
    if not blocking and data.blocking_issue_count == 0:
        return True, "no_blocking_issues"
    if not open_fixable:
        return True, "only_unresolved_data_unavailable"
    return False, ""
