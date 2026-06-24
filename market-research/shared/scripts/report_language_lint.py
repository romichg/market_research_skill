#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


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
    "source_manifest.json",
    "manifest.json",
    "gaps.json",
    "sources.json",
    "normalized/",
    "raw/",
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
                findings.append({"severity": "minor", "pattern": pattern, "message": INTERNAL_PROVENANCE_MESSAGE})
        if any(vendor in body for vendor in VENDOR_NAMES):
            findings.append(
                {
                    "severity": "minor",
                    "pattern": "vendor-name-main-body",
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
    return any(term in lowered for term in ["market cap", "market value", "valuation range", "enterprise value"])


def has_markdown_table(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines()]
    return any(line.startswith("|") and "---" in line for line in lines)


def lint_report_structure(text: str) -> list[dict[str, str]]:
    sections = section_map(text)
    findings: list[dict[str, str]] = []
    bottom = sections.get("bottom line", "")
    if bottom:
        if word_count(bottom) < 80:
            findings.append(
                {
                    "severity": "minor",
                    "id": "bottom-line-too-short",
                    "message": "Bottom Line should read as an executive summary, not a compressed thesis.",
                }
            )
        if not has_market_value(bottom):
            findings.append(
                {
                    "severity": "minor",
                    "id": "bottom-line-missing-market-value",
                    "message": "Bottom Line should introduce market value or valuation range before judging valuation.",
                }
            )
    key_facts = sections.get("key facts", "")
    if key_facts and not has_markdown_table(key_facts):
        findings.append({"severity": "minor", "id": "key-facts-not-table", "message": "Key Facts should be a compact table."})
    technical = sections.get("market snapshot and technical analysis", "")
    required_terms = ["support", "resistance", "moving average", "volume", "volatility", "trend"]
    if technical and sum(1 for term in required_terms if term in technical.lower()) < 4:
        findings.append(
            {
                "severity": "minor",
                "id": "technical-analysis-too-thin",
                "message": "Technical analysis should interpret support, resistance, moving averages, volume, volatility, and trend when price history exists.",
            }
        )
    return findings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lint investor-facing market research report language.")
    parser.add_argument("report_markdown")
    parser.add_argument("--json", action="store_true", help="Write findings as JSON.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    text = Path(args.report_markdown).read_text(encoding="utf-8", errors="ignore")
    findings = lint_report_language(text) + lint_report_structure(text)
    if args.json:
        print(json.dumps({"findings": findings}, indent=2, sort_keys=True))
    else:
        for finding in findings:
            print(f"{finding['severity']}: {finding['message']} ({finding['pattern']})")
    raise SystemExit(1 if findings else 0)


if __name__ == "__main__":
    main()
