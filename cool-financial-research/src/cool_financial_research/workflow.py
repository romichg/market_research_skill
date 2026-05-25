from __future__ import annotations

from cool_financial_research.schemas import IssueSeverity, ValidationStageOutput


def should_stop_validation(validation: ValidationStageOutput) -> tuple[bool, str]:
    data = validation.structured_data
    blocking = [
        issue
        for issue in data.issues
        if issue.severity in {IssueSeverity.critical, IssueSeverity.moderate}
    ]
    if not blocking and data.blocking_issue_count == 0:
        return True, "no_blocking_issues"
    if blocking and all(issue.status == "unresolved_data_unavailable" for issue in blocking):
        return True, "only_unresolved_data_unavailable"
    return False, ""
