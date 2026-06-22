#!/usr/bin/env python3
"""Deterministic data usage requirements and post-report usage checks."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


IGNORED_USAGE_PROVIDERS = {"input", "cli", "deterministic_classifier", "unavailable"}

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


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def classify_materiality(field_path: str, asset_type: str | None = None) -> str:
    namespace, _, field_tail = field_path.partition(".")
    field_name = field_tail.split(".")[-1]
    if field_path in REQUIRED_FIELD_PATHS or any(field_path.startswith(prefix) for prefix in REQUIRED_FIELD_PREFIXES):
        return "required"
    if asset_type in {"etf", "fund"} and namespace in {"market_snapshot", "etf_holdings"}:
        return "required"
    if field_name in REVIEW_FIELD_NAMES or namespace in REVIEW_NAMESPACES:
        return "review"
    if namespace == "technical_signals":
        return "review"
    return "context"


def build_usage_requirements(normalized_dir: Path, asset_type: str | None = None) -> dict[str, Any]:
    datapoints = []
    summary = {"total_ok_datapoints": 0, "required": 0, "review": 0, "context": 0}
    for datapoint in collect_normalized_datapoints(normalized_dir):
        materiality = classify_materiality(datapoint["field_path"], asset_type)
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


def compare_usage_dispositions(requirements: dict[str, Any], report: Any) -> dict[str, Any]:
    dispositions = report_usage_dispositions(report)
    required_items = [item for item in requirements.get("datapoints", []) if item.get("materiality") == "required"]
    review_items = [item for item in requirements.get("datapoints", []) if item.get("materiality") == "review"]
    missing_required = [item for item in required_items if item.get("field_path") not in dispositions]
    missing_review = [item for item in review_items if item.get("field_path") not in dispositions]
    return {
        "summary": {
            "total_required": len(required_items),
            "dispositioned_required": len(required_items) - len(missing_required),
            "missing_required": len(missing_required),
            "total_review": len(review_items),
            "dispositioned_review": len(review_items) - len(missing_review),
            "missing_review": len(missing_review),
        },
        "missing_required": missing_required,
        "missing_review": missing_review,
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


def value_tokens(value: Any) -> list[str]:
    if value is None:
        return []
    tokens = [str(value)]
    if isinstance(value, float):
        tokens.append(f"{value:g}")
        tokens.append(f"{value:.2f}")
    return [token.lower() for token in tokens if token]


def datapoint_reference_reasons(datapoint: dict[str, Any], corpus: str) -> list[str]:
    checks = [
        ("field_path", datapoint.get("field_path")),
        ("field_name", datapoint.get("field_name")),
        ("raw_path", datapoint.get("raw_path")),
        ("source_url", datapoint.get("source_url")),
    ]
    reasons = [reason for reason, value in checks if isinstance(value, str) and value and value.lower() in corpus]
    if any(token in corpus for token in value_tokens(datapoint.get("value"))):
        reasons.append("value")
    return sorted(set(reasons))


def deterministic_data_usage_audit(bundle: dict[str, Any], report: Any) -> dict[str, Any]:
    datapoints = collect_normalized_datapoints(bundle.get("normalized"))
    corpus = report_reference_corpus(bundle.get("report_markdown"), bundle.get("report_json"), report)
    audited = []
    for datapoint in datapoints:
        reasons = datapoint_reference_reasons(datapoint, corpus)
        audited.append(
            {
                **datapoint,
                "usage_status": "referenced" if reasons else "not_referenced",
                "reference_reasons": reasons,
            }
        )
    referenced = sum(1 for item in audited if item["usage_status"] == "referenced")
    not_referenced = sum(1 for item in audited if item["usage_status"] == "not_referenced")
    return {
        "summary": {
            "total_ok_datapoints": len(audited),
            "referenced": referenced,
            "not_referenced": not_referenced,
        },
        "datapoints": audited,
    }
