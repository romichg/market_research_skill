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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def discover(run_dir: Path, report_md: str | None, report_json: str | None) -> dict[str, Any]:
    if not run_dir.exists() or not run_dir.is_dir():
        die(f"Run directory not found: {run_dir}")
    md_path = Path(report_md) if report_md else next(iter(sorted(run_dir.glob("*-research.md"))), None)
    json_path = Path(report_json) if report_json else next(iter(sorted(run_dir.glob("*-research.json"))), None)
    deterministic_md = run_dir / "research_input_pack.md"
    manifest_path = run_dir / "manifest.json"
    if deterministic_md.exists() and manifest_path.exists() and report_md is None and report_json is None:
        manifest = read_json(manifest_path)
        symbol = str(manifest.get("symbol") or run_dir.parent.name).upper()
        return {
            "bundle_type": "deterministic_data_bundle",
            "symbol": symbol,
            "report_markdown": deterministic_md,
            "report_json": None,
            "manifest": manifest_path,
            "source_manifest": run_dir / "source_manifest.json",
            "gaps": run_dir / "gaps.json",
            "normalized": run_dir / "normalized",
        }
    if md_path is None or not md_path.exists():
        die("Could not find research markdown artifact.")
    if json_path is None or not json_path.exists():
        die("Could not find research JSON artifact.")
    payload = read_json(json_path)
    symbol = str(payload.get("symbol") or md_path.name.split("-")[0]).upper()
    return {
        "bundle_type": "legacy_research_report",
        "symbol": symbol,
        "report_markdown": md_path,
        "report_json": json_path,
    }


def issue_counts(issues: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "critical": sum(1 for issue in issues if issue.get("severity") == "critical"),
        "moderate": sum(1 for issue in issues if issue.get("severity") == "moderate"),
        "minor": sum(1 for issue in issues if issue.get("severity") == "minor"),
    }


def load_sources(run_dir: Path) -> dict[str, dict[str, Any]]:
    path = run_dir / "sources.json"
    if not path.exists():
        return {}
    payload = read_json(path)
    sources = payload.get("sources", [])
    if not isinstance(sources, list):
        return {}
    return {str(source.get("id")): source for source in sources if isinstance(source, dict) and source.get("id")}


def deterministic_issues(report: dict[str, Any], sources_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for field in ["symbol", "security_type", "material_claims", "data_gaps"]:
        if field not in report:
            issues.append({"id": f"schema-{field}", "severity": "critical", "status": "open", "description": f"Research JSON missing required field: {field}"})
    claims = report.get("material_claims", [])
    if isinstance(claims, list):
        for index, claim in enumerate(claims):
            if isinstance(claim, dict) and not claim.get("source_id"):
                issues.append({"id": f"claim-{index}-source", "severity": "moderate", "status": "open", "description": "Material claim is missing source_id."})
            elif isinstance(claim, dict) and claim.get("source_id") not in sources_by_id:
                issues.append({"id": f"claim-{index}-source-missing", "severity": "moderate", "status": "open", "description": f"Material claim cites source_id {claim.get('source_id')!r}, but that source is missing from sources.json."})
    return issues


def deterministic_bundle_issues(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for field in ["manifest", "source_manifest", "gaps", "normalized"]:
        path = bundle.get(field)
        if not isinstance(path, Path) or not path.exists():
            issues.append({"id": f"bundle-{field}-missing", "severity": "critical", "status": "open", "description": f"Deterministic bundle missing {field} artifact."})
    normalized = bundle.get("normalized")
    if isinstance(normalized, Path) and normalized.exists():
        for path in sorted(normalized.glob("*.json")):
            payload = read_json(path)
            issues.extend(normalized_value_issues(path.stem, payload))
    source_manifest = bundle.get("source_manifest")
    if isinstance(source_manifest, Path) and source_manifest.exists():
        payload = read_json(source_manifest)
        sources = payload.get("sources", [])
        if not isinstance(sources, list):
            issues.append({"id": "source-manifest-shape", "severity": "critical", "status": "open", "description": "source_manifest.json must contain a sources array."})
        else:
            for index, source in enumerate(sources):
                if not isinstance(source, dict):
                    continue
                raw_path = source.get("raw_path")
                if not raw_path:
                    issues.append({"id": f"source-{index}-raw_path", "severity": "moderate", "status": "open", "description": "Source manifest entry is missing raw_path."})
                elif not Path(raw_path).exists():
                    issues.append({"id": f"source-{index}-raw_path-missing", "severity": "minor", "status": "open", "description": f"Source manifest raw_path does not exist locally: {raw_path}"})
    return issues


def normalized_value_issues(namespace: str, payload: Any, prefix: str = "") -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        if "value" in payload:
            status = payload.get("status", "ok")
            provider = payload.get("provider")
            if status == "ok" and provider not in {"input", "cli", "deterministic_classifier", "unavailable"}:
                for field in ["provider", "source_url", "raw_path"]:
                    if payload.get(field) in (None, ""):
                        issue_id = f"normalized-{namespace}-{prefix.rstrip('.')}-{field}".replace("..", ".").replace(".", "-")
                        issues.append({"id": issue_id, "severity": "moderate", "status": "open", "description": f"Normalized value {namespace}.{prefix.rstrip('.')} is missing provenance field {field}."})
            return issues
        for key, value in payload.items():
            child_prefix = f"{prefix}{key}."
            issues.extend(normalized_value_issues(namespace, value, child_prefix))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            issues.extend(normalized_value_issues(namespace, value, f"{prefix}{index}."))
    return issues


def prevent_accidental_overwrite(out_prefix: Path, force: bool) -> None:
    if force:
        return
    md_path = out_prefix.with_suffix(".md")
    json_path = out_prefix.with_suffix(".json")
    if not md_path.exists() and not json_path.exists():
        return
    if out_prefix.name.endswith("-validation-scaffold"):
        return
    die(f"Refusing to overwrite existing validation artifacts at {out_prefix}. Use --force or write to a scaffold output prefix.")


def cmd_validate(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir)
    bundle = discover(run_dir, args.report_md, args.report_json)
    symbol = bundle["symbol"]
    md_path = bundle["report_markdown"]
    json_path = bundle.get("report_json")
    report = read_json(json_path) if isinstance(json_path, Path) else {}
    sources_by_id = load_sources(run_dir)
    issues = deterministic_bundle_issues(bundle) if bundle["bundle_type"] == "deterministic_data_bundle" else deterministic_issues(report, sources_by_id)
    counts = issue_counts(issues)
    blocking = sum(1 for issue in issues if issue["severity"] in {"critical", "moderate"} and issue["status"] == "open")
    gaps_path = bundle.get("gaps")
    gaps_payload = read_json(gaps_path) if isinstance(gaps_path, Path) and gaps_path.exists() else {}
    validation = {
        "symbol": symbol,
        "created_at": utc_now(),
        "scaffold": True,
        "bundle_type": bundle["bundle_type"],
        "report_markdown": str(md_path),
        "report_json": str(json_path) if isinstance(json_path, Path) else None,
        "issues": issues,
        "issue_counts": counts,
        "blocking_issue_count": blocking,
        "data_gaps": gaps_payload.get("gaps", report.get("data_gaps", [])),
        "sources_inspected": [],
        "fresh_context_instruction": "Use this helper output as deterministic lint only; validate non-deterministic claims and cited-source interpretation without rerunning successful deterministic provider collection.",
    }
    out_prefix = Path(args.output_prefix) if args.output_prefix else run_dir / f"{symbol}-validation-scaffold"
    prevent_accidental_overwrite(out_prefix, args.force)
    write_json(out_prefix.with_suffix(".json"), validation)
    lines = [
        f"# {symbol} Deterministic Validation Scaffold",
        "",
        "This file is deterministic lint output only. It is not a completed judgment validation.",
        "",
        f"Blocking issues: {blocking}",
        "",
    ]
    for issue in issues:
        lines.append(f"- {issue['id']} [{issue['severity']} / {issue['status']}]: {issue['description']}")
    out_prefix.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"symbol": symbol, "validation_json": str(out_prefix.with_suffix(".json")), "validation_markdown": str(out_prefix.with_suffix(".md")), "blocking_issue_count": blocking, "scaffold": True}, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic validation helper for market-research bundles.")
    parser.add_argument("run_dir")
    parser.add_argument("--report-md")
    parser.add_argument("--report-json")
    parser.add_argument("--output-prefix")
    parser.add_argument("--force", action="store_true", help="Overwrite existing validation artifacts.")
    parser.set_defaults(func=cmd_validate)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
