#!/usr/bin/env python3
"""Reconcile report source IDs with final sources.json."""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from script_utils import read_json, sha256_file, write_json


DETERMINISTIC_ALIASES = {
    "det_identity": "normalized/identity.json",
    "deterministic_identity": "normalized/identity.json",
    "det_market_snapshot": "normalized/market_snapshot.json",
    "deterministic_market_snapshot": "normalized/market_snapshot.json",
    "det_technical_signals": "normalized/technical_signals.json",
    "deterministic_technical_signals": "normalized/technical_signals.json",
    "det_prices_daily": "normalized/prices_daily.json",
    "deterministic_prices_daily": "normalized/prices_daily.json",
    "market_prices": "normalized/prices_daily.json",
    "det_etf_profile": "normalized/etf_profile.json",
    "deterministic_etf_profile": "normalized/etf_profile.json",
    "det_etf_holdings": "normalized/etf_holdings.json",
    "deterministic_etf_holdings": "normalized/etf_holdings.json",
    "det_news": "normalized/news.json",
    "deterministic_news": "normalized/news.json",
    "deterministic_manifest": "manifest.json",
    "deterministic_source_manifest": "source_manifest.json",
    "deterministic_gaps": "gaps.json",
    "deterministic_data_usage": "deterministic_data_usage.json",
}

SOURCE_ID_KEYS = {"source_id", "source_ids", "source_ids_cited"}


def source_ids_from_markdown(text: str) -> set[str]:
    found: set[str] = set()
    for source_id in DETERMINISTIC_ALIASES:
        if re.search(rf"(?<![A-Za-z0-9_-]){re.escape(source_id)}(?![A-Za-z0-9_-])", text):
            found.add(source_id)
    return found


def source_ids_from_report_json(report: dict[str, Any]) -> set[str]:
    found: set[str] = set()

    def visit(value: Any, key: str | None = None) -> None:
        if isinstance(value, dict):
            for child_key, child_value in value.items():
                visit(child_value, str(child_key))
        elif isinstance(value, list):
            for item in value:
                visit(item, key)
        elif isinstance(value, str) and (key in SOURCE_ID_KEYS or (key and "source" in key)):
            if value in DETERMINISTIC_ALIASES or key in SOURCE_ID_KEYS:
                found.add(value)

    visit(report)
    return found


def material_source_ids_from_report_json(report: dict[str, Any]) -> set[str]:
    found: set[str] = set()
    material_sections = ["material_claims", "risks", "catalysts"]
    for section in material_sections:
        values = report.get(section)
        if not isinstance(values, list):
            continue
        for item in values:
            if not isinstance(item, dict):
                continue
            for key in SOURCE_ID_KEYS:
                value = item.get(key)
                if isinstance(value, str):
                    found.add(value)
                elif isinstance(value, list):
                    found.update(str(child) for child in value if isinstance(child, str))
    return found


def load_registered_source_ids(sources_path: Path) -> set[str]:
    if not sources_path.exists():
        return set()
    payload = read_json(sources_path)
    sources = payload.get("sources", []) if isinstance(payload, dict) else []
    return {
        str(source.get("id") or source.get("source_id"))
        for source in sources
        if isinstance(source, dict) and (source.get("id") or source.get("source_id"))
    }


def deterministic_artifact_for_source_id(source_id: str, data_dir: Path) -> Path | None:
    rel = DETERMINISTIC_ALIASES.get(source_id)
    if not rel:
        return None
    path = data_dir / rel
    return path if path.exists() else None


def deterministic_source_record(source_id: str, artifact: Path, data_dir: Path) -> dict[str, Any]:
    title = source_id.replace("_", " ").title()
    return {
        "id": source_id,
        "title": title,
        "kind": "deterministic_artifact",
        "source_date": data_dir.name,
        "accessed_date": datetime.now(timezone.utc).date().isoformat(),
        "local_artifact": str(artifact),
        "sha256": sha256_file(artifact),
        "size_bytes": artifact.stat().st_size,
        "confidence": "high",
        "notes": "Field-level provider/source URL/raw-path provenance is preserved inside the deterministic artifact and source_manifest.json.",
    }


def cited_source_ids(report_dir: Path) -> set[str]:
    ids: set[str] = set()
    for md_path in sorted(report_dir.glob("*-research.md")):
        ids.update(source_ids_from_markdown(md_path.read_text(encoding="utf-8", errors="ignore")))
    for json_path in sorted(report_dir.glob("*-research.json")):
        payload = read_json(json_path)
        if isinstance(payload, dict):
            ids.update(source_ids_from_report_json(payload))
    return ids


def runtime_sources_path_for(report_dir: Path, runtime_dir: Path | None = None) -> Path:
    """Locate runtime/sources.json for a report.

    `runtime_dir` may already point at the dated SYMBOL/AS_OF directory (where sources.json
    lives) or at the coarser SYMBOL-level directory (as producer_self_check.py's
    `--runtime-dir` conventionally does), so both layouts are tried before falling back to
    the default SYMBOL/AS_OF layout derived from `report_dir`.
    """
    candidates: list[Path] = []
    if runtime_dir is not None:
        candidates.append(runtime_dir / "sources.json")
        candidates.append(runtime_dir / report_dir.name / "sources.json")
    candidates.append(
        report_dir.parent.parent.parent / "runtime" / report_dir.parent.name / report_dir.name / "sources.json"
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def unmirrored_runtime_source_ids(report_dir: Path, runtime_dir: Path | None = None) -> set[str]:
    """Source ids captured procedurally in runtime/sources.json but never copied into the report-facing sources.json."""
    runtime_sources_path = runtime_sources_path_for(report_dir, runtime_dir)
    runtime_ids = load_registered_source_ids(runtime_sources_path)
    if not runtime_ids:
        return set()
    report_ids = load_registered_source_ids(report_dir / "sources.json")
    return runtime_ids - report_ids


def reconcile_report_sources(
    report_dir: Path,
    data_dir: Path | None = None,
    fix: bool = False,
    runtime_dir: Path | None = None,
) -> dict[str, Any]:
    data_dir = data_dir or report_dir.parent.parent.parent / "data" / report_dir.parent.name / report_dir.name
    sources_path = report_dir / "sources.json"
    registered = load_registered_source_ids(sources_path)
    cited = cited_source_ids(report_dir)
    deterministic_missing = sorted(
        source_id
        for source_id in cited - registered
        if deterministic_artifact_for_source_id(source_id, data_dir) is not None
    )
    added: list[str] = []
    if fix and deterministic_missing:
        payload = read_json(sources_path) if sources_path.exists() else {"sources": []}
        sources = payload.setdefault("sources", [])
        if not isinstance(sources, list):
            sources = []
            payload["sources"] = sources
        for source_id in deterministic_missing:
            artifact = deterministic_artifact_for_source_id(source_id, data_dir)
            if artifact is None:
                continue
            sources.append(deterministic_source_record(source_id, artifact, data_dir))
            added.append(source_id)
        write_json(sources_path, payload)
    return {
        "report_dir": str(report_dir),
        "data_dir": str(data_dir),
        "cited_ids": sorted(cited),
        "registered_ids": sorted(registered),
        "missing_ids": deterministic_missing,
        "added_ids": added,
        "unmirrored_runtime_ids": sorted(unmirrored_runtime_source_ids(report_dir, runtime_dir)),
    }


def source_registry_issues(report_dir: Path, data_dir: Path | None = None, runtime_dir: Path | None = None) -> list[dict[str, Any]]:
    result = reconcile_report_sources(report_dir, data_dir, fix=False, runtime_dir=runtime_dir)
    issues = []
    material_json_ids: set[str] = set()
    for json_path in sorted(report_dir.glob("*-research.json")):
        payload = read_json(json_path)
        if isinstance(payload, dict):
            material_json_ids.update(material_source_ids_from_report_json(payload))
    for source_id in result["missing_ids"]:
        severity = "moderate" if source_id in material_json_ids else "minor"
        issues.append(
            {
                "id": f"source-registry-missing-{source_id.replace('_', '-')}",
                "severity": severity,
                "status": "open",
                "description": f"Report cites deterministic source_id {source_id!r}, but final sources.json does not register it.",
            }
        )
    for source_id in result["unmirrored_runtime_ids"]:
        issues.append(
            {
                "id": f"source-registry-unmirrored-{source_id.replace('_', '-')}",
                "severity": "minor",
                "status": "open",
                "description": f"Source_id {source_id!r} is registered in runtime/sources.json but was never mirrored into the report-facing sources.json.",
            }
        )
    return issues


def cmd_check(args: argparse.Namespace) -> None:
    result = reconcile_report_sources(
        Path(args.report_dir),
        Path(args.data_dir) if args.data_dir else None,
        fix=False,
        runtime_dir=Path(args.runtime_dir) if args.runtime_dir else None,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["missing_ids"]:
        raise SystemExit(1)


def cmd_fix(args: argparse.Namespace) -> None:
    result = reconcile_report_sources(
        Path(args.report_dir),
        Path(args.data_dir) if args.data_dir else None,
        fix=True,
        runtime_dir=Path(args.runtime_dir) if args.runtime_dir else None,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Reconcile final report sources.json with cited deterministic source IDs.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, func in [("check", cmd_check), ("fix", cmd_fix)]:
        command = sub.add_parser(name)
        command.add_argument("report_dir")
        command.add_argument("--data-dir")
        command.add_argument("--runtime-dir")
        command.set_defaults(func=func)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
