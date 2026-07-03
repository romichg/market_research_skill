#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ALLOWED_PROVENANCE_SECTIONS = {
    "data issues and discrepancies",
    "sources and evidence",
    "evidence appendix",
    "appendix",
}
FORBIDDEN_MAIN_BODY_PATTERNS = [
    "saved",
    "deterministic",
    "artifact",
    "deterministic bundle",
    "runtime/",
    "data/",
    "local path",
    "normalized",
    "source_manifest.json",
    "manifest.json",
    "gaps.json",
    "sources.json",
    "normalized/",
    "raw/",
    "cache",
    "provider",
]
VENDOR_NAMES = [
    "alpha vantage",
    "fmp",
    "tiingo",
    "twelve data",
    "eodhd",
    "marketaux",
]
ETF_PROVENANCE_PHRASES = [
    "sponsor's",
    "sponsor page",
    "sponsor holdings download",
    "saved page",
    "saved source",
    "wrapper was doing its job",
]
TECHNICAL_DECISION_TERMS = [
    "sizing",
    "position",
    "invalidation",
    "entry",
    "confirm",
    "confirms",
    "confirmation",
    "breaks below",
    "break below",
    "reclaims",
    "reclaim",
    "limit order",
    "limit orders",
]
INTERNAL_PROVENANCE_MESSAGE = "skill-internal provenance belongs in an appendix unless it changes the investment interpretation"


def iter_sections(text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, list[str]]] = []
    current = "preamble"
    lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            sections.append((current, lines))
            current = line[3:].strip().lower()
            lines = []
            continue
        lines.append(line)
    sections.append((current, lines))
    return [(heading, "\n".join(body)) for heading, body in sections]


def section_allows_provenance(heading: str) -> bool:
    return heading in ALLOWED_PROVENANCE_SECTIONS or "sources" in heading or "evidence" in heading or "appendix" in heading


def lint_report_language(text: str) -> list[dict[str, str]]:
    findings = []
    for heading, section_text in iter_sections(text):
        if section_allows_provenance(heading):
            continue
        body = section_text.lower()
        for pattern in FORBIDDEN_MAIN_BODY_PATTERNS:
            if pattern in body:
                findings.append(
                    {
                        "severity": "minor",
                        "pattern": pattern,
                        "section": heading,
                        "message": INTERNAL_PROVENANCE_MESSAGE,
                    }
                )
        if any(vendor in body for vendor in VENDOR_NAMES):
            findings.append(
                {
                    "severity": "minor",
                    "pattern": "vendor-name-main-body",
                    "section": heading,
                    "message": "routine data-vendor names belong in Data Issues And Discrepancies or Sources And Evidence, not the main investment narrative",
                }
            )
    return findings


def lint_etf_narrative_language(text: str, report_json: dict[str, Any] | None = None) -> list[dict[str, str]]:
    if str((report_json or {}).get("security_type", "")).lower() != "etf":
        return []
    findings = []
    for heading, section_text in iter_sections(text):
        if section_allows_provenance(heading):
            continue
        body = section_text.lower()
        for phrase in ETF_PROVENANCE_PHRASES:
            if phrase in body:
                findings.append(
                    {
                        "severity": "minor",
                        "id": "etf-provenance-heavy-language",
                        "section": heading,
                        "message": "State ETF facts directly in main sections; keep source mechanics such as sponsor page/download wording in Sources And Evidence or Data Issues And Discrepancies.",
                    }
                )
                break
    return findings


def section_map(text: str) -> dict[str, str]:
    return {heading: body for heading, body in iter_sections(text)}


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def has_market_value(text: str) -> bool:
    lowered = text.lower()
    return any(
        term in lowered
        for term in [
            "market cap",
            "market value",
            "valuation range",
            "enterprise value",
            "net assets",
            "aum",
            "assets under management",
        ]
    )


def has_markdown_table(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines()]
    return any(line.startswith("|") and "---" in line for line in lines)


def lint_report_structure(text: str) -> list[dict[str, str]]:
    sections = section_map(text)
    findings: list[dict[str, str]] = []
    if "self-check" in sections:
        findings.append(
            {
                "severity": "minor",
                "id": "self-check-section",
                "section": "self-check",
                "message": "Self-check sections are internal workflow notes and should not appear in investor-facing reports.",
            }
        )
    bottom = sections.get("bottom line", "")
    if bottom:
        if word_count(bottom) < 80:
            findings.append(
                {
                    "severity": "minor",
                    "id": "bottom-line-too-short",
                    "section": "bottom line",
                    "message": "Bottom Line should read as an executive summary, not a compressed thesis.",
                }
            )
        if not has_market_value(bottom):
            findings.append(
                {
                    "severity": "minor",
                    "id": "bottom-line-missing-market-value",
                    "section": "bottom line",
                    "message": "Bottom Line should introduce market value, ETF net assets, or valuation range before judging valuation.",
                }
            )
    key_facts = sections.get("key facts", "")
    if key_facts and not has_markdown_table(key_facts):
        findings.append(
            {
                "severity": "minor",
                "id": "key-facts-not-table",
                "section": "key facts",
                "message": "Key Facts should be a compact table.",
            }
        )
    technical = sections.get("market snapshot and technical analysis", "")
    required_term_groups = [
        ["support"],
        ["resistance"],
        ["moving average", "moving-average", "moving averages", "moving-averages"],
        ["volume"],
        ["volatility"],
        ["trend"],
    ]
    technical_lower = technical.lower()
    if technical and sum(1 for group in required_term_groups if any(term in technical_lower for term in group)) < 4:
        findings.append(
            {
                "severity": "minor",
                "id": "technical-analysis-too-thin",
                "section": "market snapshot and technical analysis",
                "message": "Technical analysis should interpret support, resistance, moving averages, volume, volatility, and trend when price history exists.",
            }
        )
    return findings


def has_json_drawdown(report_json: dict[str, Any] | None) -> bool:
    if not isinstance(report_json, dict):
        return False
    for key in ["technical_analysis", "technical_snapshot"]:
        technical = report_json.get(key)
        if not isinstance(technical, dict):
            continue
        for field, value in technical.items():
            if "drawdown" in str(field).lower() and value not in (None, "", "Data not available"):
                return True
    return False


def has_holdings(report_json: dict[str, Any] | None) -> bool:
    if not isinstance(report_json, dict):
        return False
    for key in ["holdings", "portfolio_holdings", "etf_holdings"]:
        candidate = report_json.get(key)
        if isinstance(candidate, list) and candidate:
            return True
        if isinstance(candidate, dict):
            holdings = candidate.get("holdings") or candidate.get("top_holdings")
            if isinstance(holdings, list) and holdings:
                return True
    return False


def etf_holding_rows(report_json: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(report_json, dict):
        return []
    rows: list[dict[str, Any]] = []
    for key in ["holdings", "portfolio_holdings", "etf_holdings"]:
        candidate = report_json.get(key)
        if isinstance(candidate, list):
            rows.extend(row for row in candidate if isinstance(row, dict))
        elif isinstance(candidate, dict):
            for nested_key in ["holdings", "top_holdings", "top25", "top_25"]:
                nested = candidate.get(nested_key)
                if isinstance(nested, list):
                    rows.extend(row for row in nested if isinstance(row, dict))
    return rows


def collect_source_ids(value: Any) -> set[str]:
    source_ids: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"source_id", "source_ids"}:
                if isinstance(item, str):
                    source_ids.add(item.lower())
                elif isinstance(item, list):
                    source_ids.update(str(entry).lower() for entry in item)
            else:
                source_ids.update(collect_source_ids(item))
    elif isinstance(value, list):
        for item in value:
            source_ids.update(collect_source_ids(item))
    return source_ids


def has_holding_context_support(report_json: dict[str, Any] | None, report_path: Path | None) -> bool:
    source_ids = collect_source_ids(report_json)
    support_terms = [
        "classification",
        "company_profile",
        "company_profiles",
        "constituent_profile",
        "constituent_profiles",
        "holding_context",
        "holdings_context",
    ]
    if any(any(term in source_id for term in support_terms) for source_id in source_ids):
        return True
    if report_path is not None:
        sources_path = report_path.parent / "sources.json"
        if sources_path.exists():
            try:
                sources_text = sources_path.read_text(encoding="utf-8", errors="ignore").lower()
            except OSError:
                sources_text = ""
            if any(term in sources_text for term in support_terms):
                return True
    return False


def lint_etf_holding_context_support(
    text: str,
    report_json: dict[str, Any] | None = None,
    report_path: Path | None = None,
) -> list[dict[str, str]]:
    if str((report_json or {}).get("security_type", "")).lower() != "etf":
        return []
    rows = etf_holding_rows(report_json)
    if not rows:
        return []
    context_fields = ["business_outlook", "business", "outlook", "sector_or_industry", "industry", "sector"]
    rows_with_context = [
        row for row in rows if any(str(row.get(field, "")).strip() for field in context_fields)
    ]
    sections = section_map(text)
    snapshot = sections.get("portfolio companies snapshot", "").lower()
    markdown_has_context = "business" in snapshot or "outlook" in snapshot or "sector" in snapshot or "industry" in snapshot
    if not rows_with_context and not markdown_has_context:
        if len(rows) >= 10:
            return [
                {
                    "severity": "moderate",
                    "id": "etf-holding-company-context-too-thin",
                    "section": "portfolio companies snapshot",
                    "message": "ETF Portfolio Companies Snapshot should include investor-useful sector/industry, compact business/outlook, and price or technical context for major holdings when holdings are available.",
                }
            ]
        return []
    if has_holding_context_support(report_json, report_path):
        return []
    return [
        {
            "severity": "moderate",
            "id": "etf-holding-company-context-unsupported",
            "section": "portfolio companies snapshot",
            "message": "Holding-level sector, business, or outlook context needs cited company-level sources or a cited holdings-classification artifact; otherwise narrow the table to issuer-supported holding facts.",
        }
    ]


def lint_runtime_source_bundle_paths(text: str, report_path: Path | None = None) -> list[dict[str, str]]:
    if report_path is None:
        return []
    findings: list[dict[str, str]] = []
    report_source_bundle = report_path.parent / "source_bundle"
    if not report_source_bundle.exists():
        return findings
    for heading, section_text in iter_sections(text):
        if not section_allows_provenance(heading):
            continue
        for match in re.finditer(r"runtime/[^\s|`)]*/source_bundle/([^\s|`)]+)", section_text):
            filename = Path(match.group(1)).name
            if (report_source_bundle / filename).exists():
                findings.append(
                    {
                        "severity": "minor",
                        "id": "runtime-source-bundle-path",
                        "section": heading,
                        "message": "Sources And Evidence should point to the report-local source_bundle copy when it exists, not the runtime workspace path.",
                    }
                )
    return findings


def lint_report_quality(text: str, report_json: dict[str, Any] | None = None, report_path: Path | None = None) -> list[dict[str, str]]:
    findings = lint_report_language(text) + lint_etf_narrative_language(text, report_json) + lint_report_structure(text)
    for finding in findings:
        if "id" not in finding and finding.get("pattern") in FORBIDDEN_MAIN_BODY_PATTERNS:
            finding["id"] = "main-body-internal-language"
    sections = section_map(text)
    technical = sections.get("market snapshot and technical analysis", "")
    if technical and has_json_drawdown(report_json) and "drawdown" not in technical.lower():
        findings.append(
            {
                "severity": "minor",
                "id": "technical-analysis-missing-drawdown",
                "section": "market snapshot and technical analysis",
                "message": "Technical analysis should interpret drawdown when calculated drawdown data exists.",
            }
        )
    if technical and any(term in technical.lower() for term in ["support", "resistance", "volatility", "drawdown"]):
        technical_lower = technical.lower()
        if not any(term in technical_lower for term in TECHNICAL_DECISION_TERMS):
            findings.append(
                {
                    "severity": "minor",
                    "id": "technical-analysis-missing-decision-use",
                    "section": "market snapshot and technical analysis",
                    "message": "Technical analysis should translate support/resistance, volatility, or drawdown into sizing, entry, confirmation, or invalidation implications.",
                }
            )
    security_type = str((report_json or {}).get("security_type", "")).lower()
    risks = sections.get("risks and invalidation points", "")
    if security_type == "etf" and risks:
        risk_text = risks.lower()
        if "creation" not in risk_text and "redemption" not in risk_text and "authorized participant" not in risk_text:
            findings.append(
                {
                    "severity": "minor",
                    "id": "etf-risk-missing-creation-redemption",
                    "section": "risks and invalidation points",
                    "message": "ETF risks should address authorized participant and creation/redemption mechanics when material.",
                }
            )
        if "securities lending" not in risk_text and "securities-lending" not in risk_text:
            findings.append(
                {
                    "severity": "minor",
                    "id": "etf-risk-missing-securities-lending",
                    "section": "risks and invalidation points",
                    "message": "ETF risks should address securities-lending risk or state why it was not material or not found.",
                }
            )
    if security_type == "etf" and has_holdings(report_json) and "portfolio companies snapshot" not in sections:
        findings.append(
            {
                "severity": "minor",
                "id": "etf-missing-portfolio-companies-snapshot",
                "section": "portfolio companies snapshot",
                "message": "ETF reports should include a Portfolio Companies Snapshot when holdings are available.",
            }
        )
    findings.extend(lint_etf_holding_context_support(text, report_json, report_path))
    findings.extend(lint_runtime_source_bundle_paths(text, report_path))
    return findings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lint investor-facing market research report language.")
    parser.add_argument("report_markdown")
    parser.add_argument("--report-json", help="Optional report JSON sidecar for JSON-aware quality checks.")
    parser.add_argument("--json", action="store_true", help="Write findings as JSON.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    text = Path(args.report_markdown).read_text(encoding="utf-8", errors="ignore")
    report_json = json.loads(Path(args.report_json).read_text(encoding="utf-8")) if args.report_json else None
    findings = lint_report_quality(text, report_json, Path(args.report_markdown))
    if args.json:
        print(json.dumps({"findings": findings}, indent=2, sort_keys=True))
    else:
        for finding in findings:
            identifier = finding.get("pattern") or finding.get("id") or "finding"
            print(f"{finding['severity']}: {finding['message']} ({identifier})")
    raise SystemExit(1 if findings else 0)


if __name__ == "__main__":
    main()
