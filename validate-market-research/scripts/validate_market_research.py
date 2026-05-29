#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def die(message: str, code: int = 2) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        die(f"Could not parse JSON {path}: {exc}")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def discover(run_dir: Path, report_md: str | None, report_json: str | None) -> tuple[str, Path, Path]:
    if not run_dir.exists() or not run_dir.is_dir():
        die(f"Run directory not found: {run_dir}")
    md_path = Path(report_md) if report_md else next(iter(sorted(run_dir.glob("*-research.md"))), None)
    json_path = Path(report_json) if report_json else next(iter(sorted(run_dir.glob("*-research.json"))), None)
    if md_path is None or not md_path.exists():
        die("Could not find research markdown artifact.")
    if json_path is None or not json_path.exists():
        die("Could not find research JSON artifact.")
    payload = read_json(json_path)
    symbol = str(payload.get("symbol") or md_path.name.split("-")[0]).upper()
    return symbol, md_path, json_path


def issue_counts(issues: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "critical": sum(1 for issue in issues if issue.get("severity") == "critical"),
        "moderate": sum(1 for issue in issues if issue.get("severity") == "moderate"),
        "minor": sum(1 for issue in issues if issue.get("severity") == "minor"),
    }


def deterministic_issues(report: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for field in ["symbol", "security_type", "material_claims", "data_gaps"]:
        if field not in report:
            issues.append({"id": f"schema-{field}", "severity": "critical", "status": "open", "description": f"Research JSON missing required field: {field}"})
    claims = report.get("material_claims", [])
    if isinstance(claims, list):
        for index, claim in enumerate(claims):
            if isinstance(claim, dict) and not claim.get("source_id"):
                issues.append({"id": f"claim-{index}-source", "severity": "moderate", "status": "open", "description": "Material claim is missing source_id."})
    return issues


def cmd_validate(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir)
    symbol, md_path, json_path = discover(run_dir, args.report_md, args.report_json)
    report = read_json(json_path)
    issues = deterministic_issues(report)
    counts = issue_counts(issues)
    blocking = sum(1 for issue in issues if issue["severity"] in {"critical", "moderate"} and issue["status"] == "open")
    validation = {
        "symbol": symbol,
        "created_at": utc_now(),
        "report_markdown": str(md_path),
        "report_json": str(json_path),
        "issues": issues,
        "issue_counts": counts,
        "blocking_issue_count": blocking,
        "data_gaps": report.get("data_gaps", []),
        "fresh_context_instruction": "Use this helper output as deterministic lint only; perform independent source and reasoning validation before accepting the report.",
    }
    out_prefix = Path(args.output_prefix) if args.output_prefix else run_dir / f"{symbol}-validation"
    write_json(out_prefix.with_suffix(".json"), validation)
    lines = [f"# {symbol} Validation", "", f"Blocking issues: {blocking}", ""]
    for issue in issues:
        lines.append(f"- {issue['id']} [{issue['severity']} / {issue['status']}]: {issue['description']}")
    out_prefix.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"symbol": symbol, "validation_json": str(out_prefix.with_suffix(".json")), "validation_markdown": str(out_prefix.with_suffix(".md")), "blocking_issue_count": blocking}, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic validation helper for market-research bundles.")
    parser.add_argument("run_dir")
    parser.add_argument("--report-md")
    parser.add_argument("--report-json")
    parser.add_argument("--output-prefix")
    parser.set_defaults(func=cmd_validate)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
