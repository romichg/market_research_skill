#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import deterministic_data_usage as usage_contract
import report_language_lint
import source_registry_reconcile
from script_utils import read_json, write_json


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def die(message: str, code: int = 2) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


def is_deterministic_bundle(path: Path) -> bool:
    return (
        (path / "research_input_pack.md").exists()
        and (path / "manifest.json").exists()
        and (path / "source_manifest.json").exists()
        and (path / "gaps.json").exists()
        and (path / "normalized").exists()
    )


DETERMINISTIC_BUNDLE_LOCATION_MESSAGE = (
    "Deterministic bundles must be under data/SYMBOL/YYYY-MM-DD. "
    "Place or copy deterministic bundles under data/SYMBOL/YYYY-MM-DD, "
    "or pass a final report directory under reports."
)
FINAL_REPORT_LOCATION_MESSAGE = (
    "Final report directories must be under reports/SYMBOL/YYYY-MM-DD. "
    "For final report validation, pass reports/SYMBOL/YYYY-MM-DD as run_dir. "
    "Use data/SYMBOL/YYYY-MM-DD only for deterministic scaffold lint."
)
VALIDATION_OUTPUT_LOCATION_MESSAGE = "Validation output prefixes must be under reports/SYMBOL/YYYY-MM-DD for the validated symbol/date."
REQUIRED_RESEARCH_FIELDS = [
    "symbol",
    "security_type",
    "as_of_date",
    "material_claims",
    "data_gaps",
    "technical_analysis",
    "valuation_or_performance",
    "decision_factors",
    "risks",
    "catalysts",
    "source_coverage",
    "calculation_audit",
]
FRESH_CONTEXT_INSTRUCTION = "Use this helper output as deterministic lint only; validate cited sources, procedural calculations, markdown/JSON agreement, and conclusions from saved artifacts without creating a parallel research thesis."


def is_date_component(value: str) -> bool:
    return re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is not None


def is_canonical_data_bundle_path(path: Path, symbol: str) -> bool:
    return (
        is_date_component(path.name)
        and path.parent.name.upper() == symbol.upper()
        and path.parent.parent.name == "data"
    )


def is_canonical_data_symbol_dir(path: Path) -> bool:
    return path.parent.name == "data"


def ensure_canonical_data_bundle_path(path: Path, symbol: str) -> None:
    if not is_canonical_data_bundle_path(path, symbol):
        die(DETERMINISTIC_BUNDLE_LOCATION_MESSAGE)


def is_canonical_report_dir_path(path: Path, symbol: str) -> bool:
    return (
        is_date_component(path.name)
        and path.parent.name.upper() == symbol.upper()
        and path.parent.parent.name == "reports"
    )


def ensure_canonical_report_dir_path(path: Path, symbol: str) -> None:
    if not is_canonical_report_dir_path(path, symbol):
        die(FINAL_REPORT_LOCATION_MESSAGE)


def deterministic_bundle_result(run_dir: Path) -> dict[str, Any]:
    manifest_path = run_dir / "manifest.json"
    manifest = read_json(manifest_path)
    symbol = str(manifest.get("symbol") or run_dir.parent.name).upper()
    ensure_canonical_data_bundle_path(run_dir, symbol)
    return {
        "bundle_type": "deterministic_data_bundle",
        "symbol": symbol,
        "run_dir": run_dir,
        "report_markdown": run_dir / "research_input_pack.md",
        "report_json": None,
        "manifest": manifest_path,
        "source_manifest": run_dir / "source_manifest.json",
        "gaps": run_dir / "gaps.json",
        "normalized": run_dir / "normalized",
        "deterministic_data_usage_requirements": run_dir / "deterministic_data_usage.json",
    }


def discover(run_dir: Path, report_md: str | None, report_json: str | None) -> dict[str, Any]:
    if not run_dir.exists() or not run_dir.is_dir():
        die(f"Run directory not found: {run_dir}")
    md_path = Path(report_md) if report_md else next(iter(sorted(run_dir.glob("*-research.md"))), None)
    json_path = Path(report_json) if report_json else next(iter(sorted(run_dir.glob("*-research.json"))), None)
    if report_md is None and report_json is None:
        if is_deterministic_bundle(run_dir):
            return deterministic_bundle_result(run_dir)
        nested = [path for path in run_dir.iterdir() if path.is_dir() and is_deterministic_bundle(path)]
        if nested:
            if not is_canonical_data_symbol_dir(run_dir):
                die(DETERMINISTIC_BUNDLE_LOCATION_MESSAGE)
            dated_nested = [path for path in nested if is_date_component(path.name)]
            if not dated_nested:
                die(DETERMINISTIC_BUNDLE_LOCATION_MESSAGE)
            return deterministic_bundle_result(sorted(dated_nested, key=lambda path: path.name)[-1])
    if md_path is None or not md_path.exists():
        die("Could not find research markdown artifact.")
    if json_path is None or not json_path.exists():
        die("Could not find research JSON artifact.")
    payload = read_json(json_path)
    symbol_value = payload.get("symbol") if isinstance(payload, dict) else None
    symbol = str(symbol_value or md_path.name.split("-")[0]).upper()
    ensure_canonical_report_dir_path(run_dir, symbol)
    result = {
        "bundle_type": "legacy_research_report",
        "symbol": symbol,
        "report_markdown": md_path,
        "report_json": json_path,
    }
    data_bundle = deterministic_bundle_for_report_dir(run_dir, payload if isinstance(payload, dict) else None, symbol)
    if data_bundle:
        result["deterministic_bundle_dir"] = data_bundle
        result["manifest"] = data_bundle / "manifest.json"
        result["source_manifest"] = data_bundle / "source_manifest.json"
        result["gaps"] = data_bundle / "gaps.json"
        result["normalized"] = data_bundle / "normalized"
        result["deterministic_data_usage_requirements"] = data_bundle / "deterministic_data_usage.json"
    return result


def deterministic_bundle_for_report_dir(report_dir: Path, report: dict[str, Any] | None, symbol: str) -> Path | None:
    candidates: list[Path] = []
    if isinstance(report, dict):
        bundle = report.get("deterministic_bundle")
        if isinstance(bundle, dict) and isinstance(bundle.get("bundle_dir"), str):
            candidates.append(Path(bundle["bundle_dir"]))
    if is_canonical_report_dir_path(report_dir, symbol):
        repo_root = report_dir.parent.parent.parent
        candidates.append(repo_root / "data" / symbol / report_dir.name)
    for candidate in candidates:
        if candidate.exists() and is_deterministic_bundle(candidate):
            return candidate
    return None


def issue_counts(issues: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "critical": sum(1 for issue in issues if issue.get("severity") == "critical"),
        "moderate": sum(1 for issue in issues if issue.get("severity") == "moderate"),
        "minor": sum(1 for issue in issues if issue.get("severity") == "minor"),
    }


def source_file_candidates(run_dir: Path, report: dict[str, Any] | None = None) -> list[Path]:
    candidates = [run_dir / "sources.json"]
    if isinstance(report, dict):
        sources_file = report.get("sources_file")
        if isinstance(sources_file, str) and sources_file:
            candidates.append(Path(sources_file))
        procedural_runtime = report.get("procedural_runtime")
        if isinstance(procedural_runtime, dict):
            runtime_sources = procedural_runtime.get("sources_file")
            if isinstance(runtime_sources, str) and runtime_sources:
                candidates.append(Path(runtime_sources))
    seen: set[str] = set()
    unique: list[Path] = []
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def load_sources(run_dir: Path, report: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    resolved: dict[str, dict[str, Any]] = {}
    for path in source_file_candidates(run_dir, report):
        if not path.exists():
            continue
        payload = read_json(path)
        sources = payload.get("sources", [])
        if not isinstance(sources, list):
            continue
        for source in sources:
            if isinstance(source, dict) and source.get("id"):
                resolved[str(source["id"])] = source
    return resolved


def load_deterministic_sources(bundle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    source_manifest = bundle.get("source_manifest")
    if not isinstance(source_manifest, Path) or not source_manifest.exists():
        return {}
    payload = read_json(source_manifest)
    sources = payload.get("sources", [])
    if not isinstance(sources, list):
        return {}
    resolved: dict[str, dict[str, Any]] = {}
    for source in sources:
        if not isinstance(source, dict):
            continue
        source_id = source.get("id") or source.get("source_id")
        if source_id:
            resolved[str(source_id)] = source
    return resolved


def claim_has_existing_source_artifact(claim: dict[str, Any]) -> bool:
    artifact = claim.get("source_artifact")
    return isinstance(artifact, str) and bool(artifact) and Path(artifact).exists()


def deterministic_issues(report: Any, sources_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if not isinstance(report, dict):
        return [{"id": "schema-report-shape", "severity": "critical", "status": "open", "description": "Research JSON must be an object."}]
    for field in REQUIRED_RESEARCH_FIELDS:
        if field not in report:
            issues.append({"id": f"schema-{field}", "severity": "critical", "status": "open", "description": f"Research JSON missing required field: {field}"})
    claims = report.get("material_claims", [])
    if isinstance(claims, list):
        for index, claim in enumerate(claims):
            if isinstance(claim, dict) and not claim.get("source_id"):
                issues.append({"id": f"claim-{index}-source", "severity": "moderate", "status": "open", "description": "Material claim is missing source_id."})
            elif isinstance(claim, dict) and claim.get("source_id") not in sources_by_id and not claim_has_existing_source_artifact(claim):
                issues.append({"id": f"claim-{index}-source-missing", "severity": "moderate", "status": "open", "description": f"Material claim cites source_id {claim.get('source_id')!r}, but that source is missing from sources.json."})
    return issues


def report_quality_scaffold_issues(report: Any, markdown_text: str) -> list[dict[str, Any]]:
    if not isinstance(report, dict):
        return []
    if str(report.get("security_type", "")).lower() != "etf":
        return []
    if not report_language_lint.has_holdings(report):
        return []
    sections = report_language_lint.section_map(markdown_text)
    if "portfolio companies snapshot" in sections:
        return []
    return [
        {
            "id": "etf-missing-portfolio-companies-snapshot",
            "severity": "minor",
            "status": "open",
            "description": "ETF report JSON includes holdings, but the Markdown report lacks a Portfolio Companies Snapshot section. For ETFs with 25 or fewer holdings, cover all holdings; otherwise cover the top 25 by portfolio weight.",
        }
    ]


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


def load_usage_requirements(bundle: dict[str, Any]) -> dict[str, Any]:
    requirements_path = bundle.get("deterministic_data_usage_requirements")
    if isinstance(requirements_path, Path) and requirements_path.exists():
        payload = read_json(requirements_path)
        if isinstance(payload, dict):
            return payload
    normalized = bundle.get("normalized")
    if isinstance(normalized, Path) and normalized.exists():
        manifest_path = bundle.get("manifest")
        asset_type = None
        if isinstance(manifest_path, Path) and manifest_path.exists():
            manifest = read_json(manifest_path)
            if isinstance(manifest, dict):
                asset_type = manifest.get("asset_type")
        return usage_contract.build_usage_requirements(normalized, asset_type)
    return {"version": "deterministic-data-usage-v1", "summary": {}, "datapoints": []}


def usage_disposition_issues(comparison: dict[str, Any]) -> list[dict[str, Any]]:
    issues = []
    for item in comparison.get("missing_required", []):
        field_path = item.get("field_path", "unknown")
        safe_field_path = str(field_path).replace(".", "-").replace("_", "_")
        issues.append(
            {
                "id": f"deterministic-usage-missing-required-{safe_field_path}",
                "severity": "moderate",
                "status": "open",
                "description": f"Report JSON does not disposition required deterministic datapoint: {field_path}.",
            }
        )
    weak_required = summarize_weak_usage(comparison.get("weak_required", []), "required")
    if weak_required:
        issues.append(weak_required)
    weak_review = summarize_weak_usage(comparison.get("weak_review", []), "review")
    if weak_review:
        issues.append(weak_review)
    return issues


def summarize_weak_usage(items: list[dict[str, Any]], materiality: str) -> dict[str, Any] | None:
    if not items:
        return None
    sample = ", ".join(str(item.get("field_path", "unknown")) for item in items[:8])
    extra = "" if len(items) <= 8 else f", and {len(items) - 8} more"
    return {
        "id": f"deterministic-usage-weak-{materiality}-summary",
        "severity": "minor",
        "status": "open",
        "description": (
            f"{len(items)} {materiality} deterministic datapoints have weak report JSON usage rationales. "
            f"Use field-specific rationales and report sections. Sample: {sample}{extra}."
        ),
    }


def gap_issues(gaps_payload: dict[str, Any], report_corpus: str) -> list[dict[str, Any]]:
    issues = []
    gaps = gaps_payload.get("gaps") if isinstance(gaps_payload, dict) else []
    if not isinstance(gaps, list):
        return issues
    for gap in gaps:
        if not isinstance(gap, dict):
            continue
        if gap.get("field") != "filing_section_extracts":
            continue
        disclosed = any(term in report_corpus for term in ["filing-section", "filing section", "sec_filing_sections"])
        issues.append(
            {
                "id": "filing-section-extracts-missing",
                "severity": "minor" if disclosed else "moderate",
                "status": "open",
                "description": "Deterministic bundle lacks SEC filing-section extracts. Remediation targets: add extraction or explicit unavailable status in market-research/shared/scripts/deterministic_research_collector.py; require report disclosure in market-research/researcher/references/report-template.md; verifier should treat undisclosed filing-specific risk limitations as moderate.",
            }
        )
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


def default_output_prefix(bundle: dict[str, Any], artifact_run_dir: Path, symbol: str) -> Path:
    if bundle["bundle_type"] == "deterministic_data_bundle":
        ensure_canonical_data_bundle_path(artifact_run_dir, symbol)
        repo_root = artifact_run_dir.parent.parent.parent
        return repo_root / "reports" / symbol / artifact_run_dir.name / f"{symbol}-validation-scaffold"
    return artifact_run_dir / f"{symbol}-validation-scaffold"


def expected_validation_output_dir(bundle: dict[str, Any], artifact_run_dir: Path, symbol: str) -> Path:
    if bundle["bundle_type"] == "deterministic_data_bundle":
        ensure_canonical_data_bundle_path(artifact_run_dir, symbol)
        repo_root = artifact_run_dir.parent.parent.parent
        return repo_root / "reports" / symbol / artifact_run_dir.name
    ensure_canonical_report_dir_path(artifact_run_dir, symbol)
    return artifact_run_dir


def ensure_validation_output_prefix(out_prefix: Path, bundle: dict[str, Any], artifact_run_dir: Path, symbol: str) -> None:
    expected_dir = expected_validation_output_dir(bundle, artifact_run_dir, symbol)
    if out_prefix.parent.resolve(strict=False) != expected_dir.resolve(strict=False):
        die(VALIDATION_OUTPUT_LOCATION_MESSAGE)


def ensure_scaffold_output_prefix(out_prefix: Path) -> None:
    if not out_prefix.name.endswith("-validation-scaffold"):
        die("Deterministic lint output must use a -validation-scaffold output prefix; reserve -validation for completed fresh verifier judgments.")


def cmd_validate(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir)
    bundle = discover(run_dir, args.report_md, args.report_json)
    artifact_run_dir = bundle.get("run_dir", run_dir)
    symbol = bundle["symbol"]
    md_path = bundle["report_markdown"]
    json_path = bundle.get("report_json")
    report = read_json(json_path) if isinstance(json_path, Path) else {}
    sources_by_id = load_sources(run_dir, report if isinstance(report, dict) else None)
    sources_by_id.update(load_deterministic_sources(bundle))
    issues = deterministic_bundle_issues(bundle) if bundle["bundle_type"] == "deterministic_data_bundle" else deterministic_issues(report, sources_by_id)
    if bundle["bundle_type"] != "deterministic_data_bundle":
        markdown_text = md_path.read_text(encoding="utf-8", errors="ignore")
        issues.extend(report_quality_scaffold_issues(report, markdown_text))
        deterministic_bundle_dir = bundle.get("deterministic_bundle_dir")
        if isinstance(deterministic_bundle_dir, Path):
            issues.extend(source_registry_reconcile.source_registry_issues(run_dir, deterministic_bundle_dir))
    gaps_path = bundle.get("gaps")
    gaps_payload = read_json(gaps_path) if isinstance(gaps_path, Path) and gaps_path.exists() else {}
    usage_audit = usage_contract.deterministic_data_usage_audit(bundle, report)
    usage_requirements = load_usage_requirements(bundle)
    usage_dispositions = usage_contract.compare_usage_dispositions(usage_requirements, report)
    issues.extend(usage_disposition_issues(usage_dispositions))
    issues.extend(gap_issues(gaps_payload, usage_contract.report_reference_corpus(md_path, json_path, report)))
    counts = issue_counts(issues)
    blocking = sum(1 for issue in issues if issue["severity"] in {"critical", "moderate"} and issue["status"] == "open")
    validation = {
        "symbol": symbol,
        "created_at": utc_now(),
        "scaffold": True,
        "validation_level": "deterministic_lint",
        "requires_fresh_verifier": True,
        "bundle_type": bundle["bundle_type"],
        "report_markdown": str(md_path),
        "report_json": str(json_path) if isinstance(json_path, Path) else None,
        "issues": issues,
        "issue_counts": counts,
        "blocking_issue_count": blocking,
        "data_gaps": gaps_payload.get("gaps", report.get("data_gaps", []) if isinstance(report, dict) else []),
        "deterministic_data_usage": usage_audit,
        "deterministic_data_usage_dispositions": usage_dispositions,
        "sources_inspected": [],
        "fresh_context_instruction": FRESH_CONTEXT_INSTRUCTION,
    }
    out_prefix = Path(args.output_prefix) if args.output_prefix else default_output_prefix(bundle, artifact_run_dir, symbol)
    ensure_validation_output_prefix(out_prefix, bundle, artifact_run_dir, symbol)
    prevent_accidental_overwrite(out_prefix, args.force)
    ensure_scaffold_output_prefix(out_prefix)
    write_json(out_prefix.with_suffix(".json"), validation)
    lines = [
        f"# {symbol} Deterministic Validation Scaffold",
        "",
        "This file is deterministic lint output only. It is not a completed judgment validation and still requires a fresh verifier pass.",
        "",
        f"Blocking issues: {blocking}",
        "",
        "Deterministic data usage: "
        f"{usage_audit['summary']['narrative_used']} narrative-used, "
        f"{usage_audit['summary']['evidence_only_reference']} evidence-only references, "
        f"{usage_audit['summary']['not_referenced']} not referenced "
        f"out of {usage_audit['summary']['total_ok_datapoints']} normalized ok datapoints.",
        "",
        "Deterministic data disposition gaps: "
        f"{usage_dispositions['summary']['missing_required']} missing required, "
        f"{usage_dispositions['summary']['missing_review']} missing review.",
        "",
    ]
    for issue in issues:
        lines.append(f"- {issue['id']} [{issue['severity']} / {issue['status']}]: {issue['description']}")
    out_prefix.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "symbol": symbol,
        "validation_json": str(out_prefix.with_suffix(".json")),
        "validation_markdown": str(out_prefix.with_suffix(".md")),
        "blocking_issue_count": blocking,
        "scaffold": True,
        "validation_level": "deterministic_lint",
        "requires_fresh_verifier": True,
    }, indent=2))


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
