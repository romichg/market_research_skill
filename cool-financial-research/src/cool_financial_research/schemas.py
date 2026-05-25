"""Pydantic developer models for the v0.6 research/validation JSON contract.

The OpenClaw skill still treats the JSON Schema files under ./schemas as the
portable contract. These models mirror that stricter contract for local tests,
editor help, and developer ergonomics. They are deliberately not imported by the
stdlib-only helper path, so the skill can still run helper commands without a
Pydantic install.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SecurityType(str, Enum):
    equity = "equity"
    adr = "adr"
    etf = "etf"


class Stage(str, Enum):
    research = "research"
    validation = "validation"
    fix = "fix"
    final = "final"


class IssueSeverity(str, Enum):
    critical = "critical"
    moderate = "moderate"
    minor = "minor"


class Confidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"
    unverified = "unverified"


class SourceType(str, Enum):
    primary = "primary"
    secondary = "secondary"
    paid_licensed = "paid_licensed"
    unverified = "unverified"


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    url: str | None = None
    document_type: str | None = None
    publication_date: str | None = None
    accessed_date: str | None = None
    confidence: Confidence
    primary_or_secondary: SourceType | None = None
    notes: str | None = None


class QuantitativeClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_text: str
    value: str | int | float | None = None
    as_of_date: str | None = None
    source_id: str | None
    source_date: str | None = None
    accessed_date: str | None = None
    confidence: Confidence
    verification_status: Literal["verified_primary", "verified_secondary", "unverified", "not_available"]
    stale: bool
    staleness_reason: str | None = None
    fact_or_interpretation: Literal["fact", "interpretation"] | None = None


class QualityControl(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary_sources_preferred: bool
    facts_interpretation_separated: bool
    quant_claims_sourced_or_marked_unverified: bool
    stale_data_flagged: bool
    notes: list[str] = Field(default_factory=list)


class ReportSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: int = Field(ge=1, le=16)
    title: str
    facts: list[str]
    interpretation: list[str]
    quantitative_claims: list[QuantitativeClaim]
    sources: list[Source]
    open_questions: list[str]


class UnresolvedIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    severity: IssueSeverity
    section: str
    issue: str
    status: Literal["unresolved_data_unavailable"]
    reason: str
    recommended_next_step: str | None = None


class FixResponseItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue_id: str
    status: Literal["fixed", "unresolved_data_unavailable"]
    explanation: str
    source_id: str | None = None


class FixResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validation_iteration: int = Field(ge=1)
    addressed_issues: list[FixResponseItem]


class PaidDataRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service: str
    reason: str
    related_data_gap_categories: list[str]
    confidence: Confidence


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
    quality_control: QualityControl
    sections: list[ReportSection] = Field(min_length=16)
    sources: list[Source]
    open_questions: list[str]
    unresolved_issues: list[UnresolvedIssue]
    data_quality_notes: list[str] = Field(default_factory=list)
    fix_response: FixResponse | None = None
    paid_data_recommendations: list[PaidDataRecommendation] | None = None


class ResearchOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    security_type: SecurityType
    stage: Literal["research", "fix", "final"]
    iteration: int = Field(ge=0)
    markdown_report: str
    structured_data: ResearchStructuredData


class Issue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    severity: IssueSeverity
    section: str
    issue: str
    status: Literal["open", "unresolved_data_unavailable", "deferred"]
    required_fix: str | None
    source_or_evidence: str | None
    source_confidence: Confidence
    unresolved_reason: str | None = None


class FreshnessItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data_point: str
    value_in_report: str | int | float | None
    source_id: str | None
    as_of_date: str | None
    freshness_threshold_days: int | None = None
    within_threshold: bool
    verified: Literal["yes", "no", "unverified"]
    notes: str | None = None


class DataGap(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Literal[
        "fundamentals_valuation",
        "consensus_estimates",
        "transcripts_kpis",
        "etf_fund_analytics",
        "options_derivatives",
        "short_interest_borrow",
        "market_data_technicals",
        "ownership_insider",
        "supply_chain_tariff",
        "news_sentiment",
        "other",
    ]
    severity: IssueSeverity
    affected_sections: list[str]
    description: str
    why_free_sources_were_insufficient: str
    potential_paid_services: list[str]
    expected_quality_lift: Literal["high", "medium", "low"]
    related_issue_ids: list[str] = Field(default_factory=list)


class ValidationStructuredData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    security_type: SecurityType
    validation_date: str
    overall_verdict: Literal["pass", "pass_with_revisions", "fail"]
    recommendation_confidence: Literal["low", "medium", "high"]
    critical_count: int = Field(ge=0)
    moderate_count: int = Field(ge=0)
    minor_count: int = Field(ge=0)
    issues: list[Issue]
    unresolved_due_to_data_unavailable: list[Issue]
    sources_checked: list[Source]
    data_freshness_audit: list[FreshnessItem]
    data_gaps: list[DataGap]
    summary: str

    @model_validator(mode="after")
    def issue_counts_must_match(self) -> "ValidationStructuredData":
        counts = {"critical": 0, "moderate": 0, "minor": 0}
        for issue in self.issues:
            counts[issue.severity.value] += 1
        expected = {
            "critical": self.critical_count,
            "moderate": self.moderate_count,
            "minor": self.minor_count,
        }
        if counts != expected:
            raise ValueError(f"issue counts do not match issue list: expected={expected}, actual={counts}")
        return self

    @property
    def open_fixable_blocking_issue_ids(self) -> list[str]:
        return [
            issue.id
            for issue in self.issues
            if issue.severity in {IssueSeverity.critical, IssueSeverity.moderate} and issue.status == "open"
        ]

    @property
    def has_fixable_blocking_issues(self) -> bool:
        return bool(self.open_fixable_blocking_issue_ids)


class ValidationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    security_type: SecurityType
    stage: Literal["validation"]
    iteration: int = Field(ge=1)
    markdown_report: str
    structured_data: ValidationStructuredData


class SecurityClassification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    security_type: SecurityType
    name: str | None = None
    exchange: str | None = None
    cik: str | None = None
    is_adr: bool
    confidence: Literal["high", "medium", "low"]
    source: str
    notes: list[str] = Field(default_factory=list)


class OperationalIssue(BaseModel):
    model_config = ConfigDict(extra="allow")

    stage: str
    category: str
    issue: str
    severity: Literal["info", "warning", "error"] = "warning"
    resolution: str | None = None


class ArtifactCompliance(BaseModel):
    model_config = ConfigDict(extra="allow")

    expected_markdown: str | None = None
    expected_json: str | None = None
    markdown_exists: bool | None = None
    json_exists: bool | None = None
    schema_valid: bool | None = None
    artifact_source: Literal["child", "repair-child", "parent-recovered", "unknown"] | None = None
    repair_attempts: int = 0


class RunManifest(BaseModel):
    model_config = ConfigDict(extra="allow")

    symbol: str
    security_type: SecurityType | None = None
    name: str | None = None
    exchange: str | None = None
    cik: str | None = None
    max_iterations: int | None = None
    iterations_completed: int | None = None
    stopped_reason: str | None = None
    files: list[str]
    models: dict[str, str] = Field(default_factory=dict)
    unresolved_issues_summary: list[Any] = Field(default_factory=list)
    operational_issues: list[OperationalIssue] = Field(default_factory=list)
    artifact_compliance: dict[str, ArtifactCompliance] = Field(default_factory=dict)
