#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


APPENDIX_HEADING_RE = re.compile(r"^##\s+.*(appendix|sources|evidence|data quality)", re.IGNORECASE)
INTERNAL_PROVENANCE_PATTERNS = [
    "deterministic bundle",
    "runtime/",
    "data/",
    "source_manifest.json",
    "sources.json",
    "normalized/",
    "raw/",
]
INTERNAL_PROVENANCE_MESSAGE = "skill-internal provenance belongs in an appendix unless it changes the investment interpretation"


def main_body(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if APPENDIX_HEADING_RE.search(line):
            break
        lines.append(line)
    return "\n".join(lines)


def lint_report_language(text: str) -> list[dict[str, str]]:
    body = main_body(text).lower()
    findings = []
    for pattern in INTERNAL_PROVENANCE_PATTERNS:
        if pattern in body:
            findings.append({"severity": "minor", "pattern": pattern, "message": INTERNAL_PROVENANCE_MESSAGE})
    return findings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lint investor-facing market research report language.")
    parser.add_argument("report_markdown")
    parser.add_argument("--json", action="store_true", help="Write findings as JSON.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    text = Path(args.report_markdown).read_text(encoding="utf-8", errors="ignore")
    findings = lint_report_language(text)
    if args.json:
        print(json.dumps({"findings": findings}, indent=2, sort_keys=True))
    else:
        for finding in findings:
            print(f"{finding['severity']}: {finding['message']} ({finding['pattern']})")
    raise SystemExit(1 if findings else 0)


if __name__ == "__main__":
    main()
