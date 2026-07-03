#!/usr/bin/env python3
"""Producer-owned pre-verifier self-check for final market-research reports."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import deterministic_data_usage
import report_language_lint
import source_registry_reconcile
import validate_market_research
from script_utils import read_json, write_json


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def issue_from_lint(finding: dict[str, str]) -> dict[str, Any]:
    identifier = finding.get("id") or finding.get("pattern") or "report-quality"
    return {
        "id": identifier,
        "severity": finding.get("severity", "minor"),
        "status": "open",
        "section": finding.get("section"),
        "description": finding.get("message", "Report quality finding."),
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        f"# {payload['symbol']} Producer Self-Check",
        "",
        f"Created at: {payload['created_at']}",
        "",
        f"Blocking issues: {payload['blocking_issue_count']}",
        "",
        f"Auto-fixed deterministic source IDs: {', '.join(payload['auto_fixed_ids']) if payload['auto_fixed_ids'] else 'none'}",
        "",
        "## Issues",
        "",
    ]
    if not payload["issues"]:
        lines.append("- None.")
    else:
        for issue in payload["issues"]:
            lines.append(f"- {issue['id']} [{issue['severity']} / {issue['status']}]: {issue['description']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def run_self_check(report_dir: Path, data_dir: Path | None, runtime_dir: Path, fix_safe: bool = False) -> dict[str, Any]:
    bundle = validate_market_research.discover(report_dir, None, None)
    symbol = str(bundle["symbol"]).upper()
    if data_dir is None:
        candidate = bundle.get("deterministic_bundle_dir")
        data_dir = candidate if isinstance(candidate, Path) else None
    issues: list[dict[str, Any]] = []
    auto_fixed_ids: list[str] = []

    if isinstance(data_dir, Path) and data_dir.exists():
        if fix_safe:
            reconcile = source_registry_reconcile.reconcile_report_sources(report_dir, data_dir, fix=True, runtime_dir=runtime_dir)
            auto_fixed_ids.extend(reconcile["added_ids"])
        issues.extend(source_registry_reconcile.source_registry_issues(report_dir, data_dir, runtime_dir=runtime_dir))

    report_json_path = bundle.get("report_json")
    report = read_json(report_json_path) if isinstance(report_json_path, Path) else {}
    sources_by_id = validate_market_research.load_sources(report_dir, report if isinstance(report, dict) else None)
    sources_by_id.update(validate_market_research.load_deterministic_sources(bundle))
    issues.extend(validate_market_research.deterministic_issues(report, sources_by_id))

    usage_requirements = validate_market_research.load_usage_requirements(bundle)
    usage_dispositions = deterministic_data_usage.compare_usage_dispositions(usage_requirements, report)
    issues.extend(validate_market_research.usage_disposition_issues(usage_dispositions))

    markdown_path = bundle["report_markdown"]
    markdown = markdown_path.read_text(encoding="utf-8", errors="ignore")
    issues.extend(issue_from_lint(finding) for finding in report_language_lint.lint_report_quality(markdown, report, markdown_path))

    blocking = sum(
        1
        for issue in issues
        if str(issue.get("status", "open")).lower() == "open"
        and str(issue.get("severity", "")).lower() in {"critical", "moderate"}
    )
    payload = {
        "symbol": symbol,
        "created_at": utc_now(),
        "report_dir": str(report_dir),
        "data_dir": str(data_dir) if isinstance(data_dir, Path) else None,
        "runtime_dir": str(runtime_dir),
        "auto_fixed_ids": auto_fixed_ids,
        "issues": issues,
        "issue_counts": validate_market_research.issue_counts(issues),
        "blocking_issue_count": blocking,
    }
    runtime_dir.mkdir(parents=True, exist_ok=True)
    write_json(runtime_dir / "producer-self-check.json", payload)
    write_markdown(runtime_dir / "producer-self-check.md", payload)
    return payload


def cmd_check(args: argparse.Namespace) -> None:
    payload = run_self_check(
        Path(args.report_dir),
        Path(args.data_dir) if args.data_dir else None,
        Path(args.runtime_dir),
        fix_safe=args.fix_safe,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    raise SystemExit(1 if payload["blocking_issue_count"] else 0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run producer self-checks before verifier handoff.")
    parser.add_argument("report_dir")
    parser.add_argument("--data-dir")
    parser.add_argument("--runtime-dir", required=True)
    parser.add_argument("--fix-safe", action="store_true", help="Auto-register deterministic source IDs backed by existing artifacts.")
    parser.set_defaults(func=cmd_check)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
