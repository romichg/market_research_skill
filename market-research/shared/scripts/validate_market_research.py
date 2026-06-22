#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def die(message: str, code: int = 2) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        die(f"Could not parse JSON {path}: {exc}")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
FINAL_REPORT_LOCATION_MESSAGE = "Final report directories must be under reports/SYMBOL/YYYY-MM-DD."
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
IGNORED_USAGE_PROVIDERS = {"input", "cli", "deterministic_classifier", "unavailable"}


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
        result["normalized"] = data_bundle / "normalized"
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


def load_sources(run_dir: Path, report: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    candidates = [run_dir / "sources.json"]
    if isinstance(report, dict):
        sources_file = report.get("sources_file")
        if isinstance(sources_file, str) and sources_file:
            candidates.append(Path(sources_file))
    for path in candidates:
        if not path.exists():
            continue
        payload = read_json(path)
        sources = payload.get("sources", [])
        if not isinstance(sources, list):
            return {}
        return {str(source.get("id")): source for source in sources if isinstance(source, dict) and source.get("id")}
    return {}


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


def collect_normalized_datapoints(normalized_dir: Path | None) -> list[dict[str, Any]]:
    if not isinstance(normalized_dir, Path) or not normalized_dir.exists():
        return []
    datapoints: list[dict[str, Any]] = []
    for path in sorted(normalized_dir.glob("*.json")):
        payload = read_json(path)
        collect_normalized_datapoints_from_payload(path.stem, path, payload, "", datapoints)
    return datapoints


def collect_normalized_datapoints_from_payload(namespace: str, artifact: Path, payload: Any, prefix: str, datapoints: list[dict[str, Any]]) -> None:
    if isinstance(payload, dict):
        if "value" in payload:
            status = payload.get("status", "ok")
            provider = payload.get("provider")
            if status == "ok" and provider not in IGNORED_USAGE_PROVIDERS:
                field_path = f"{namespace}.{prefix.rstrip('.')}"
                datapoints.append({
                    "artifact": str(artifact),
                    "namespace": namespace,
                    "field_path": field_path,
                    "field_name": prefix.rstrip(".").split(".")[-1] if prefix else namespace,
                    "value": payload.get("value"),
                    "provider": provider,
                    "source_url": payload.get("source_url"),
                    "raw_path": payload.get("raw_path"),
                    "status": status,
                })
            return
        for key, value in payload.items():
            collect_normalized_datapoints_from_payload(namespace, artifact, value, f"{prefix}{key}.", datapoints)
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            collect_normalized_datapoints_from_payload(namespace, artifact, value, f"{prefix}{index}.", datapoints)


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
        audited.append({
            **datapoint,
            "usage_status": "referenced" if reasons else "not_referenced",
            "reference_reasons": reasons,
        })
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
    issues = deterministic_bundle_issues(bundle) if bundle["bundle_type"] == "deterministic_data_bundle" else deterministic_issues(report, sources_by_id)
    counts = issue_counts(issues)
    blocking = sum(1 for issue in issues if issue["severity"] in {"critical", "moderate"} and issue["status"] == "open")
    gaps_path = bundle.get("gaps")
    gaps_payload = read_json(gaps_path) if isinstance(gaps_path, Path) and gaps_path.exists() else {}
    usage_audit = deterministic_data_usage_audit(bundle, report)
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
        f"{usage_audit['summary']['referenced']} referenced, "
        f"{usage_audit['summary']['not_referenced']} not referenced "
        f"out of {usage_audit['summary']['total_ok_datapoints']} normalized ok datapoints.",
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
