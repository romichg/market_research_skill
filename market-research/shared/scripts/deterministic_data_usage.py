#!/usr/bin/env python3
"""Deterministic data usage requirements and post-report usage checks."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from script_utils import read_json


IGNORED_USAGE_PROVIDERS = {"input", "cli", "deterministic_classifier", "unavailable"}
WEAK_RATIONALE_SUGGESTED_FIX = "Mention the field or value and why it changed, supported, or did not change the investor view."

REQUIRED_FIELD_PATHS = {
    "identity.asset_type",
    "identity.company_name",
    "identity.exchange",
    "identity.sic",
    "market_snapshot.latest_close",
    "market_snapshot.market_capitalization",
    "market_snapshot.fifty_two_week_high",
    "market_snapshot.fifty_two_week_low",
    "market_snapshot.pe_ratio",
    "equity_fundamentals.revenue",
    "equity_fundamentals.revenue_ttm",
    "equity_fundamentals.gross_profit_ttm",
    "equity_fundamentals.ebitda",
    "equity_fundamentals.net_income",
    "equity_fundamentals.eps",
    "equity_fundamentals.profit_margin",
    "equity_fundamentals.shares_outstanding",
    "technical_signals.sma_50",
    "technical_signals.sma_200",
    "technical_signals.return_1m",
    "technical_signals.return_1y",
    "technical_signals.average_volume_30",
}

REVIEW_FIELD_NAMES = {
    "analyst_rating",
    "analyst_target_price",
    "analyst_target_price_high",
    "analyst_target_price_low",
    "analyst_target_price_mean",
    "analyst_target_price_median",
    "beta",
    "dividend_yield",
    "earnings_date",
    "ex_dividend_date",
    "forward_pe",
}

REQUIRED_FIELD_PREFIXES = (
    "etf_holdings.holdings.",
    "etf_holdings.top_holdings.",
    "etf_profile.",
)

REVIEW_NAMESPACES = {"news", "equity_events", "equity_insiders"}

EARLY_STAGE_REVIEW_FIELD_PATHS = {
    "market_snapshot.latest_volume",
    "equity_fundamentals.book_value",
    "equity_fundamentals.operating_margin_ttm",
    "equity_fundamentals.return_on_assets_ttm",
    "equity_fundamentals.return_on_equity_ttm",
    "equity_fundamentals.quarterly_revenue_growth_yoy",
}

GENERIC_RATIONALE_PHRASES = {
    "used in the report",
    "used in the report as part of identity, market snapshot, financial profile, valuation/performance context, or technical context",
    "not material",
}


def collect_normalized_datapoints(normalized_dir: Path | None) -> list[dict[str, Any]]:
    if not isinstance(normalized_dir, Path) or not normalized_dir.exists():
        return []
    datapoints: list[dict[str, Any]] = []
    for path in sorted(normalized_dir.glob("*.json")):
        collect_normalized_datapoints_from_payload(path.stem, path, read_json(path), "", datapoints)
    return datapoints


def collect_normalized_datapoints_from_payload(namespace: str, artifact: Path, payload: Any, prefix: str, datapoints: list[dict[str, Any]]) -> None:
    if isinstance(payload, dict):
        if "value" in payload:
            status = payload.get("status", "ok")
            provider = payload.get("provider")
            if status == "ok" and provider not in IGNORED_USAGE_PROVIDERS:
                field_name = prefix.rstrip(".").split(".")[-1] if prefix else namespace
                datapoints.append(
                    {
                        "artifact": str(artifact),
                        "namespace": namespace,
                        "field_path": f"{namespace}.{prefix.rstrip('.')}",
                        "field_name": field_name,
                        "value": payload.get("value"),
                        "provider": provider,
                        "source_url": payload.get("source_url"),
                        "raw_path": payload.get("raw_path"),
                        "status": status,
                    }
                )
            return
        for key, value in payload.items():
            collect_normalized_datapoints_from_payload(namespace, artifact, value, f"{prefix}{key}.", datapoints)
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            collect_normalized_datapoints_from_payload(namespace, artifact, value, f"{prefix}{index}.", datapoints)


def is_early_stage_volatile_equity(asset_type: str | None, lifecycle_hints: dict[str, Any] | None = None) -> bool:
    if asset_type != "equity" or not isinstance(lifecycle_hints, dict):
        return False
    hint_names = ["negative_eps", "negative_ebitda", "high_realized_volatility", "micro_or_early_revenue", "recent_revenue_step_up"]
    return sum(1 for name in hint_names if lifecycle_hints.get(name) is True) >= 2


def classify_materiality(field_path: str, asset_type: str | None = None, lifecycle_hints: dict[str, Any] | None = None) -> str:
    namespace, _, field_tail = field_path.partition(".")
    field_name = field_tail.split(".")[-1]
    if field_path in REQUIRED_FIELD_PATHS or any(field_path.startswith(prefix) for prefix in REQUIRED_FIELD_PREFIXES):
        return "required"
    if is_early_stage_volatile_equity(asset_type, lifecycle_hints) and field_path in EARLY_STAGE_REVIEW_FIELD_PATHS:
        return "review"
    if asset_type in {"etf", "fund"} and namespace in {"market_snapshot", "etf_holdings"}:
        return "required"
    if field_name in REVIEW_FIELD_NAMES or namespace in REVIEW_NAMESPACES:
        return "review"
    if namespace == "technical_signals":
        return "review"
    return "context"


def build_usage_requirements(normalized_dir: Path, asset_type: str | None = None, lifecycle_hints: dict[str, Any] | None = None) -> dict[str, Any]:
    datapoints = []
    summary = {"total_ok_datapoints": 0, "required": 0, "review": 0, "context": 0}
    for datapoint in collect_normalized_datapoints(normalized_dir):
        materiality = classify_materiality(datapoint["field_path"], asset_type, lifecycle_hints)
        item = {
            **datapoint,
            "materiality": materiality,
            "required_disposition": materiality in {"required", "review"},
        }
        datapoints.append(item)
        summary["total_ok_datapoints"] += 1
        summary[materiality] += 1
    return {
        "version": "deterministic-data-usage-v1",
        "asset_type": asset_type,
        "summary": summary,
        "datapoints": datapoints,
    }


def report_usage_dispositions(report: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(report, dict):
        return {}
    entries = report.get("deterministic_data_usage")
    if not isinstance(entries, list):
        return {}
    dispositions = {}
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get("field_path"), str):
            dispositions[entry["field_path"]] = entry
    return dispositions


def weak_usage_rationale(entry: dict[str, Any], requirement: dict[str, Any]) -> str | None:
    rationale = str(entry.get("rationale") or "").strip()
    disposition = entry.get("disposition")
    field_name = str(requirement.get("field_name") or "").lower()
    if len(rationale) < 24:
        return "rationale_too_short"
    if rationale.lower().rstrip(".") in GENERIC_RATIONALE_PHRASES:
        return "generic_rationale"
    if disposition == "used" and not entry.get("report_section"):
        return "used_without_report_section"
    if disposition == "used" and field_name and field_name not in rationale.lower() and field_name.replace("_", " ") not in rationale.lower():
        return "rationale_not_field_specific"
    return None


def rationale_template(rationale: str, field_path: str | None = None, field_name: str | None = None) -> str:
    template = rationale.lower()
    for value in [field_path, field_name, (field_name or "").replace("_", " ")]:
        if value:
            template = template.replace(str(value).lower(), "<field>")
    template = re.sub(r"\s+", " ", template).strip().rstrip(".")
    return template


def boilerplate_rationale_paths(requirements: list[dict[str, Any]], dispositions: dict[str, dict[str, Any]]) -> set[str]:
    by_template: dict[str, list[str]] = {}
    for requirement in requirements:
        field_path = requirement.get("field_path")
        entry = dispositions.get(field_path)
        if not entry:
            continue
        rationale = str(entry.get("rationale") or "")
        template = rationale_template(rationale, str(field_path), str(requirement.get("field_name") or ""))
        if "was used to anchor" not in template:
            continue
        by_template.setdefault(template, []).append(str(field_path))
    return {field_path for paths in by_template.values() if len(paths) >= 2 for field_path in paths}


def compare_usage_dispositions(requirements: dict[str, Any], report: Any) -> dict[str, Any]:
    dispositions = report_usage_dispositions(report)
    required_items = [item for item in requirements.get("datapoints", []) if item.get("materiality") == "required"]
    review_items = [item for item in requirements.get("datapoints", []) if item.get("materiality") == "review"]
    boilerplate_paths = boilerplate_rationale_paths(required_items + review_items, dispositions)
    missing_required = [item for item in required_items if item.get("field_path") not in dispositions]
    missing_review = [item for item in review_items if item.get("field_path") not in dispositions]
    weak_required = []
    weak_review = []
    for bucket, items in [(weak_required, required_items), (weak_review, review_items)]:
        for item in items:
            field_path = item.get("field_path")
            entry = dispositions.get(field_path)
            if not entry:
                continue
            weak_reason = weak_usage_rationale(entry, item)
            if not weak_reason and field_path in boilerplate_paths:
                weak_reason = "boilerplate_rationale"
            if weak_reason:
                bucket.append(
                    {
                        **item,
                        "disposition": entry.get("disposition"),
                        "report_section": entry.get("report_section"),
                        "weak_reason": weak_reason,
                        "suggested_fix": WEAK_RATIONALE_SUGGESTED_FIX,
                    }
                )
    return {
        "summary": {
            "total_required": len(required_items),
            "dispositioned_required": len(required_items) - len(missing_required),
            "missing_required": len(missing_required),
            "weak_required": len(weak_required),
            "total_review": len(review_items),
            "dispositioned_review": len(review_items) - len(missing_review),
            "missing_review": len(missing_review),
            "weak_review": len(weak_review),
        },
        "missing_required": missing_required,
        "missing_review": missing_review,
        "weak_required": weak_required,
        "weak_review": weak_review,
    }


def report_reference_corpus(md_path: Path | None, json_path: Path | None, report: Any) -> str:
    parts: list[str] = []
    if isinstance(md_path, Path) and md_path.exists():
        parts.append(md_path.read_text(encoding="utf-8", errors="ignore"))
    if isinstance(json_path, Path) and json_path.exists():
        parts.append(json_path.read_text(encoding="utf-8", errors="ignore"))
    elif report:
        parts.append(json.dumps(report, sort_keys=True))
    return "\n".join(parts).lower()


def humanized_scaled_tokens(value: float) -> list[str]:
    """Conservative humanized-number tokens for a large numeric value.

    A memo that (correctly) writes "$391.0 billion" for a 391035000000 revenue should still count as
    a value reference. Scale the value to millions/billions/trillions and render one- and two-decimal
    forms; the scaled decimal is specific enough to avoid coincidental matches. The integer form is
    added only when the scaled value is a whole number of at least 10, so a bare single-digit token
    (e.g. "5" from a 5M value) never matches unrelated text (G4).
    """
    tokens: list[str] = []
    magnitude = abs(value)
    for scale in (1_000_000_000_000, 1_000_000_000, 1_000_000):
        if magnitude >= scale:
            scaled = value / scale
            tokens.append(f"{scaled:.1f}")
            tokens.append(f"{scaled:.2f}")
            if scaled == int(scaled) and abs(scaled) >= 10:
                tokens.append(str(int(scaled)))
    return tokens


def numeric_value_tokens(value: float) -> list[str]:
    tokens: list[str] = []
    if float(value).is_integer():
        tokens.append(str(int(value)))
    tokens.append(f"{value:g}")
    tokens.append(f"{value:.2f}")
    tokens.extend(humanized_scaled_tokens(value))
    return [token.lower() for token in tokens if token]


def value_referenced_in_corpus(value: Any, corpus: str) -> bool:
    """Whether a DataPoint value appears in the report corpus.

    Numeric values are matched with digit boundaries so a bare "8" does not match inside "1985" or
    "38.2"; non-numeric string values keep plain substring containment (G4).
    """
    if value is None or isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        # Digit boundaries so a bare "8" does not match inside "1985" or "38.2", while still allowing a
        # decimal quoted at a sentence end ("123.45."). Reject only an adjacent digit, or a "." that
        # introduces further digits (i.e. the token is part of a larger number), not sentence punctuation.
        for token in numeric_value_tokens(float(value)):
            if re.search(rf"(?<!\d)(?<!\d\.){re.escape(token)}(?!\d)(?!\.\d)", corpus):
                return True
        return False
    text = str(value).strip().lower()
    return bool(text) and text in corpus


def datapoint_reference_reasons(datapoint: dict[str, Any], corpus: str) -> list[str]:
    checks = [
        ("field_path", datapoint.get("field_path")),
        ("field_name", datapoint.get("field_name")),
        ("raw_path", datapoint.get("raw_path")),
        ("source_url", datapoint.get("source_url")),
    ]
    reasons = [reason for reason, value in checks if isinstance(value, str) and value and value.lower() in corpus]
    if value_referenced_in_corpus(datapoint.get("value"), corpus):
        reasons.append("value")
    return sorted(set(reasons))


def usage_status_from_reasons(reasons: list[str]) -> str:
    if "value" in reasons:
        return "narrative_used"
    if any(reason in reasons for reason in ["field_path", "field_name", "raw_path", "source_url"]):
        return "evidence_only_reference"
    return "not_referenced"


def deterministic_data_usage_audit(bundle: dict[str, Any], report: Any) -> dict[str, Any]:
    datapoints = collect_normalized_datapoints(bundle.get("normalized"))
    corpus = report_reference_corpus(bundle.get("report_markdown"), bundle.get("report_json"), report)
    audited = []
    for datapoint in datapoints:
        reasons = datapoint_reference_reasons(datapoint, corpus)
        usage_status = usage_status_from_reasons(reasons)
        audited.append(
            {
                **datapoint,
                "usage_status": usage_status,
                "reference_reasons": reasons,
            }
        )
    narrative_used = sum(1 for item in audited if item["usage_status"] == "narrative_used")
    evidence_only_reference = sum(1 for item in audited if item["usage_status"] == "evidence_only_reference")
    referenced = narrative_used + evidence_only_reference
    not_referenced = sum(1 for item in audited if item["usage_status"] == "not_referenced")
    return {
        "summary": {
            "total_ok_datapoints": len(audited),
            "referenced": referenced,
            "narrative_used": narrative_used,
            "evidence_only_reference": evidence_only_reference,
            "not_referenced": not_referenced,
        },
        "datapoints": audited,
    }
