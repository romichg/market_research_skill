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
    findings = lint_report_language(text) + lint_report_structure(text)
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
