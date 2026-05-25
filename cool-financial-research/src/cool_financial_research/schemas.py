from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict, field_validator


class SecurityType(str, Enum):
    equity = "equity"
    adr = "adr"
    etf = "etf"


class IssueSeverity(str, Enum):
    critical = "critical"
    moderate = "moderate"
    minor = "minor"


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    url: str | None = None
    document_type: str | None = None
    publication_date: str | None = None
    accessed_date: str | None = None
    confidence: Literal["high", "medium", "low", "unverified"] = "unverified"
    notes: str | None = None


class ReportSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: int
    title: str
    facts: list[str] = Field(default_factory=list)
    interpretation: list[str] = Field(default_factory=list)
    quantitative_claims: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class Issue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    severity: IssueSeverity
    section: str
    issue: str
    required_fix: str | None = None
    source_or_evidence: str | None = None
    status: Literal["open", "fixed", "unresolved_data_unavailable", "deferred"] = "open"


class ResearchStructuredData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    security_type: SecurityType
    name: str | None = None
    exchange: str | None = None
    analysis_date: str
    recommendation: str | None = None
    conviction: Literal["low", "medium", "high", "unverified"] | None = None
    summary: str
    sections: list[ReportSection]
    sources: list[Source]
    open_questions: list[str] = Field(default_factory=list)
    data_quality_notes: list[str] = Field(default_factory=list)


class StageOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    security_type: SecurityType
    stage: Literal["research", "validation", "fix", "final"]
    iteration: int = 0
    markdown_report: str
    structured_data: ResearchStructuredData


class ValidationStructuredData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    security_type: SecurityType
    validation_date: str
    overall_verdict: Literal["pass", "pass_with_revisions", "fail"]
    recommendation_confidence: Literal["low", "medium", "high"]
    critical_count: int = 0
    moderate_count: int = 0
    minor_count: int = 0
    issues: list[Issue] = Field(default_factory=list)
    unresolved_due_to_data_unavailable: list[Issue] = Field(default_factory=list)
    sources_checked: list[Source] = Field(default_factory=list)
    summary: str

    @field_validator("critical_count", "moderate_count", "minor_count")
    @classmethod
    def non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("issue counts cannot be negative")
        return value

    @property
    def blocking_issue_count(self) -> int:
        return self.critical_count + self.moderate_count

    @property
    def has_fixable_blocking_issues(self) -> bool:
        return any(
            issue.severity in {IssueSeverity.critical, IssueSeverity.moderate}
            and issue.status == "open"
            for issue in self.issues
        )


class ValidationStageOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    security_type: SecurityType
    stage: Literal["validation"] = "validation"
    iteration: int
    markdown_report: str
    structured_data: ValidationStructuredData


class SecurityClassification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    security_type: SecurityType
    name: str | None = None
    exchange: str | None = None
    cik: str | None = None
    is_adr: bool = False
    confidence: Literal["high", "medium", "low"]
    source: str
    notes: list[str] = Field(default_factory=list)


class RunManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    security_type: SecurityType
    name: str | None = None
    exchange: str | None = None
    cik: str | None = None
    max_iterations: int
    iterations_completed: int
    stopped_reason: Literal[
        "no_blocking_issues",
        "only_unresolved_data_unavailable",
        "max_iterations_reached",
        "classification_error",
        "runtime_error",
    ]
    files: list[str]
    models: dict[str, str]
    unresolved_issues_summary: list[str] = Field(default_factory=list)
