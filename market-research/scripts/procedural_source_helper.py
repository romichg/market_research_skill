#!/usr/bin/env python3
"""Procedural source helper for manual evidence capture and gap filling.

Maintains legacy run directories, source registries, copied artifacts,
classification notes, procedural data points, and issuer-payload promotion.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SYMBOL_RE = re.compile(r"^[A-Z0-9.\-]{1,12}$")
SOURCE_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ETF_REQUIRED_FIELDS = ["fund_name", "expense_ratio", "benchmark", "holdings_summary"]
EQUITY_REQUIRED_FIELDS = ["company_name", "latest_annual_filing", "revenue", "net_income"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def die(message: str, code: int = 2) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


def normalize_symbol(symbol: str) -> str:
    value = symbol.strip().upper()
    if not SYMBOL_RE.fullmatch(value):
        die(f"Invalid symbol: {symbol!r}")
    return value


def validate_source_date(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    if not SOURCE_DATE_RE.fullmatch(value):
        die(f"Invalid source date {value!r}; expected YYYY-MM-DD.")
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        die(f"Invalid source date {value!r}; expected a real calendar date.")
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@contextlib.contextmanager
def file_lock(path: Path):
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_dir(output_root: Path, symbol: str) -> Path:
    return output_root / symbol


def manifest_path(output_root: Path, symbol: str) -> Path:
    return run_dir(output_root, symbol) / "run_manifest.json"


def ensure_run(output_root: Path, symbol: str) -> Path:
    out = run_dir(output_root, symbol)
    if not (out / "run_manifest.json").exists():
        die(f"Run directory not initialized for {symbol}; run init-run first.")
    return out


def update_manifest(output_root: Path, symbol: str, **updates: Any) -> dict[str, Any]:
    path = manifest_path(output_root, symbol)
    with file_lock(path):
        manifest = read_json(path)
        manifest.update(updates)
        manifest["updated_at"] = utc_now()
        write_json(path, manifest)
    return manifest


def append_manifest_gap_fills(output_root: Path, symbol: str, fill_args: list[dict[str, Any]], recorded_at: str, research_context: Path) -> dict[str, Any]:
    path = manifest_path(output_root, symbol)
    with file_lock(path):
        manifest = read_json(path)
        fills = manifest.get("procedural_gap_fills", [])
        fills.extend({**item, "recorded_at": recorded_at} for item in fill_args)
        manifest["procedural_gap_fills"] = fills
        manifest["research_context"] = str(research_context)
        manifest["updated_at"] = utc_now()
        write_json(path, manifest)
    return manifest


def append_manifest_source_gap(output_root: Path, symbol: str, gap: dict[str, Any]) -> dict[str, Any]:
    path = manifest_path(output_root, symbol)
    with file_lock(path):
        manifest = read_json(path)
        gaps = [item for item in manifest.get("source_gaps", []) if item.get("source_id") != gap.get("source_id")]
        gaps.append(gap)
        manifest["source_gaps"] = gaps
        manifest["updated_at"] = utc_now()
        write_json(path, manifest)
    return manifest


def cmd_init_run(args: argparse.Namespace) -> None:
    symbol = normalize_symbol(args.symbol)
    out = run_dir(Path(args.output_root), symbol)
    manifest = out / "run_manifest.json"
    if manifest.exists() and not args.force:
        die(f"Run directory already initialized for {symbol}; pass --force to overwrite.")
    source_bundle = out / "source_bundle"
    source_bundle.mkdir(parents=True, exist_ok=True)
    now = utc_now()
    manifest = {
        "symbol": symbol,
        "created_at": now,
        "updated_at": now,
        "status": "initialized",
        "security_type": None,
        "helper_errors": [],
        "source_gaps": [],
        "procedural_gap_fills": [],
        "files": {
            "source_bundle": str(source_bundle),
        },
    }
    write_json(out / "run_manifest.json", manifest)
    print(json.dumps({"symbol": symbol, "run_dir": str(out), "manifest": str(out / "run_manifest.json")}, indent=2))


def cmd_classify(args: argparse.Namespace) -> None:
    symbol = normalize_symbol(args.symbol)
    output_root = Path(args.output_root)
    out = ensure_run(output_root, symbol)
    classification = {
        "symbol": symbol,
        "security_type": args.security_type,
        "name": args.name,
        "source": "manual",
        "confidence": args.confidence,
        "notes": [args.note] if args.note else [],
    }
    write_json(out / "source_bundle" / "classification.json", classification)
    update_manifest(output_root, symbol, security_type=args.security_type, classification=str(out / "source_bundle" / "classification.json"))
    print(json.dumps(classification, indent=2, sort_keys=True))


def load_sources(out: Path) -> dict[str, Any]:
    path = out / "sources.json"
    if path.exists():
        return read_json(path)
    return {"sources": []}


def cmd_record_source(args: argparse.Namespace) -> None:
    symbol = normalize_symbol(args.symbol)
    out = ensure_run(Path(args.output_root), symbol)
    source = {
        "id": args.id,
        "title": args.title,
        "url": args.url,
        "kind": args.kind,
        "accessed_at": utc_now(),
        "source_date": validate_source_date(args.source_date),
        "confidence": args.confidence,
    }
    if args.artifact:
        artifact = copy_source_artifact(out, args.id, Path(args.artifact), args.allow_type_mismatch)
        source["local_artifact"] = str(artifact)
        source["artifact_sha256"] = sha256_file(artifact)
        source["artifact_size_bytes"] = artifact.stat().st_size
    sources_path = out / "sources.json"
    with file_lock(sources_path):
        payload = load_sources(out)
        payload["sources"] = [s for s in payload["sources"] if s.get("id") != args.id]
        payload["sources"].append(source)
        write_json(sources_path, payload)
    print(json.dumps(source, indent=2, sort_keys=True))


def cmd_record_source_gap(args: argparse.Namespace) -> None:
    symbol = normalize_symbol(args.symbol)
    output_root = Path(args.output_root)
    ensure_run(output_root, symbol)
    gap = {
        "source_id": args.source_id,
        "attempted_url": args.attempted_url,
        "reason": args.reason,
        "replacement_source_id": args.replacement_source_id,
        "severity": args.severity,
        "recorded_at": utc_now(),
    }
    append_manifest_source_gap(output_root, symbol, gap)
    print(json.dumps(gap, indent=2, sort_keys=True))


def safe_artifact_name(source_id: str, artifact: Path) -> str:
    safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", source_id).strip("._") or "source"
    return f"{safe_id}{artifact.suffix.lower()}"


def artifact_looks_like_html(path: Path) -> bool:
    sample = path.read_bytes()[:4096].lstrip().lower()
    return sample.startswith(b"<!doctype html") or sample.startswith(b"<html") or b"<html" in sample[:512]


def artifact_looks_like_pdf(path: Path) -> bool:
    return path.read_bytes()[:8].startswith(b"%PDF-")


def artifact_looks_like_json(path: Path) -> bool:
    try:
        json.loads(path.read_text(encoding="utf-8"))
        return True
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False


def validate_artifact_type(path: Path, allow_type_mismatch: bool) -> None:
    suffix = path.suffix.lower()
    if suffix == ".csv" and artifact_looks_like_html(path) and not allow_type_mismatch:
        die(f"Artifact {path} has .csv extension but looks like HTML; inspect the source or pass --allow-type-mismatch.")
    if suffix == ".pdf" and not artifact_looks_like_pdf(path) and not allow_type_mismatch:
        die(f"Artifact {path} has .pdf extension but does not look like a PDF; inspect the source or pass --allow-type-mismatch.")
    if suffix == ".json" and not artifact_looks_like_json(path) and not allow_type_mismatch:
        die(f"Artifact {path} has .json extension but is not valid JSON; inspect the source or pass --allow-type-mismatch.")


def copy_source_artifact(out: Path, source_id: str, artifact: Path, allow_type_mismatch: bool) -> Path:
    if not artifact.exists() or not artifact.is_file():
        die(f"Source artifact not found: {artifact}")
    validate_artifact_type(artifact, allow_type_mismatch)
    target = out / "source_bundle" / safe_artifact_name(source_id, artifact)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(artifact, target)
    return target


def context_required_fields(security_type: str | None) -> list[str]:
    if security_type == "etf":
        return ETF_REQUIRED_FIELDS
    return EQUITY_REQUIRED_FIELDS


def build_context(output_root: Path, symbol: str) -> dict[str, Any]:
    out = ensure_run(output_root, symbol)
    manifest = read_json(out / "run_manifest.json")
    classification_path = out / "source_bundle" / "classification.json"
    classification = read_json(classification_path) if classification_path.exists() else {}
    context_path = out / "research_context.json"
    previous = read_json(context_path) if context_path.exists() else {}
    sources = load_sources(out)
    data_points = merge_context_points(previous.get("data_points", []), derived_context_points(out, classification, sources))
    keys = {p.get("key") for p in data_points}
    required = context_required_fields(classification.get("security_type") or manifest.get("security_type"))
    missing = [field for field in required if field not in keys]
    return {
        "symbol": symbol,
        "created_at": previous.get("created_at") or utc_now(),
        "updated_at": utc_now(),
        "classification": classification,
        "sources": sources.get("sources", []),
        "source_gaps": manifest.get("source_gaps", []),
        "data_points": data_points,
        "context_quality": {
            "required_material_fields": required,
            "missing_material_fields": missing,
            "is_sparse": bool(missing),
        },
    }


def merge_context_points(existing: list[dict[str, Any]], derived: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key = {point.get("key"): point for point in derived if point.get("key")}
    for point in existing:
        key = point.get("key")
        if key:
            by_key[key] = point
    return list(by_key.values())


def derived_context_points(out: Path, classification: dict[str, Any], sources_payload: dict[str, Any]) -> list[dict[str, Any]]:
    security_type = classification.get("security_type")
    if security_type == "equity":
        return derived_equity_points(out, classification, sources_payload)
    if security_type == "etf":
        return derived_etf_points(classification)
    return []


def derived_etf_points(classification: dict[str, Any]) -> list[dict[str, Any]]:
    if classification.get("name"):
        return [context_point("fund_name", classification["name"], "classification", "medium")]
    return []


def derived_equity_points(out: Path, classification: dict[str, Any], sources_payload: dict[str, Any]) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    name = classification.get("name")
    companyfacts_path = out / "source_bundle" / "sec_companyfacts.json"
    companyfacts = read_json(companyfacts_path) if companyfacts_path.exists() else {}
    if not name:
        name = companyfacts.get("entityName")
    if name:
        points.append(context_point("company_name", name, "classification", "medium"))
    annual_source = latest_annual_filing_source(sources_payload)
    if annual_source:
        points.append(
            context_point(
                "latest_annual_filing",
                annual_source.get("title"),
                str(annual_source.get("id")),
                str(annual_source.get("confidence", "medium")),
            )
        )
    revenue = latest_companyfacts_usd_fact(companyfacts, ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"])
    if revenue:
        points.append(context_point("revenue", revenue, "sec_companyfacts", "high"))
    net_income = latest_companyfacts_usd_fact(companyfacts, ["NetIncomeLoss", "ProfitLoss"])
    if net_income:
        points.append(context_point("net_income", net_income, "sec_companyfacts", "high"))
    return points


def latest_source_by_kind(sources_payload: dict[str, Any], kinds: set[str]) -> dict[str, Any] | None:
    sources = sources_payload.get("sources", [])
    candidates = [source for source in sources if isinstance(source, dict) and source.get("kind") in kinds]
    if not candidates:
        return None
    return sorted(candidates, key=lambda source: str(source.get("source_date") or source.get("accessed_at") or ""))[-1]


def latest_annual_filing_source(sources_payload: dict[str, Any]) -> dict[str, Any] | None:
    direct = latest_source_by_kind(sources_payload, {"sec_10k", "sec_annual_report"})
    if direct:
        return direct
    sources = sources_payload.get("sources", [])
    candidates = [
        source
        for source in sources
        if isinstance(source, dict)
        and source.get("kind") == "sec_filing"
        and "10-k" in f"{source.get('id', '')} {source.get('title', '')}".lower()
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda source: str(source.get("source_date") or source.get("accessed_at") or ""))[-1]


def latest_companyfacts_usd_fact(companyfacts: dict[str, Any], names: list[str]) -> dict[str, Any] | None:
    facts = nested_get(companyfacts, "facts", "us-gaap")
    if not isinstance(facts, dict):
        return None
    candidates: list[dict[str, Any]] = []
    for name in names:
        values = nested_get(facts, name, "units", "USD")
        if not isinstance(values, list):
            continue
        annual = [item for item in values if isinstance(item, dict) and item.get("form") == "10-K" and item.get("fp") == "FY" and "val" in item]
        candidates.extend({**item, "_tag": name} for item in annual)
    if not candidates:
        return None
    item = sorted(candidates, key=lambda row: (int(row.get("fy") or 0), str(row.get("end") or ""), str(row.get("filed") or "")))[-1]
    return {
        "tag": item.get("_tag"),
        "value": item.get("val"),
        "fy": item.get("fy"),
        "period_end": item.get("end"),
        "filed": item.get("filed"),
        "form": item.get("form"),
    }


def write_context_files(out: Path, context: dict[str, Any]) -> None:
    write_json(out / "research_context.json", context)
    lines = [
        f"# {context['symbol']} Research Context",
        "",
        f"Security type: {context.get('classification', {}).get('security_type') or 'unknown'}",
        f"Sparse: {context['context_quality']['is_sparse']}",
        "",
        "## Data Points",
    ]
    for point in context.get("data_points", []):
        lines.append(f"- {point.get('key')}: {point.get('value')} (source: {point.get('source_id')}, confidence: {point.get('confidence')})")
    lines.extend(["", "## Missing Material Fields"])
    for field in context["context_quality"]["missing_material_fields"]:
        lines.append(f"- {field}")
    lines.extend(["", "## Source Gaps"])
    for gap in context.get("source_gaps", []):
        replacement = f"; replacement: {gap.get('replacement_source_id')}" if gap.get("replacement_source_id") else ""
        lines.append(f"- {gap.get('source_id')}: {gap.get('reason')} ({gap.get('attempted_url')}{replacement})")
    (out / "research_context.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def cmd_prepare_research_context(args: argparse.Namespace) -> None:
    symbol = normalize_symbol(args.symbol)
    output_root = Path(args.output_root)
    out = ensure_run(output_root, symbol)
    context = build_context(output_root, symbol)
    write_context_files(out, context)
    update_manifest(output_root, symbol, research_context=str(out / "research_context.json"))
    print(json.dumps({"context": str(out / "research_context.json"), "is_sparse": context["context_quality"]["is_sparse"]}, indent=2))


def cmd_record_gap_fill(args: argparse.Namespace) -> None:
    symbol = normalize_symbol(args.symbol)
    output_root = Path(args.output_root)
    out = ensure_run(output_root, symbol)
    fills = resolve_gap_fill_args(args)
    recorded_at = utc_now()
    with file_lock(out / "research_context.json"):
        context = build_context(output_root, symbol)
        points = [
            {
                "key": fill_args["field"],
                "label": fill_args["field"].replace("_", " ").title(),
                "value": fill_args["value"],
                "source_id": fill_args["source_id"],
                "confidence": fill_args["confidence"],
                "note": fill_args["note"],
                "filled_by": "procedural",
                "recorded_at": recorded_at,
            }
            for fill_args in fills
        ]
        replaced = {point["key"] for point in points}
        data_points = [p for p in context.get("data_points", []) if p.get("key") not in replaced]
        data_points.extend(points)
        context["data_points"] = data_points
        keys = {p.get("key") for p in data_points}
        required = context["context_quality"]["required_material_fields"]
        context["context_quality"] = {
            "required_material_fields": required,
            "missing_material_fields": [field for field in required if field not in keys],
            "is_sparse": any(field not in keys for field in required),
        }
        write_context_files(out, context)
    append_manifest_gap_fills(output_root, symbol, fills, recorded_at, out / "research_context.json")
    if len(points) == 1:
        print(json.dumps(points[0], indent=2, sort_keys=True))
    else:
        print(json.dumps({"recorded_fields": [point["key"] for point in points], "points": points}, indent=2, sort_keys=True))


def resolve_gap_fill_args(args: argparse.Namespace) -> list[dict[str, Any]]:
    payload: dict[str, Any] | list[Any] = {}
    if args.json_file and args.stdin_json:
        die("Use only one of --json-file or --stdin-json.")
    if args.json_file:
        payload = read_json(Path(args.json_file))
    elif args.stdin_json:
        try:
            payload = json.loads(sys.stdin.read())
        except json.JSONDecodeError as exc:
            die(f"Could not parse stdin JSON: {exc}")

    if isinstance(payload, list):
        return [normalize_gap_fill_payload(item, args) for item in payload]
    return [normalize_gap_fill_payload(payload, args)]


def normalize_gap_fill_payload(payload: Any, args: argparse.Namespace) -> dict[str, Any]:
    if not isinstance(payload, dict):
        die("record-gap-fill JSON input must be an object or an array of objects.")
    field = payload.get("field", args.field)
    value = payload.get("value", args.value)
    source_id = payload.get("source_id", args.source_id)
    confidence = payload.get("confidence", args.confidence)
    note = payload.get("note", args.note)
    missing = [name for name, item in {"field": field, "value": value, "source_id": source_id}.items() if item in (None, "")]
    if missing:
        die(f"record-gap-fill missing required input: {', '.join(missing)}")
    if confidence not in {"high", "medium", "low"}:
        die("record-gap-fill confidence must be one of: high, medium, low")
    return {
        "field": str(field),
        "value": value,
        "source_id": str(source_id),
        "confidence": str(confidence),
        "note": "" if note is None else str(note),
    }


def nested_get(payload: dict[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def first_present(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def blackrock_holdings_summary(payload: dict[str, Any]) -> dict[str, Any] | None:
    data = nested_get(payload, "componentsByNameMap", "holdings", "containersByNameMap", "all", "dataPointsByNameMap")
    if not isinstance(data, dict):
        return None

    def values(key: str) -> list[Any]:
        item = data.get(key)
        if isinstance(item, dict) and isinstance(item.get("value"), list):
            return item["value"]
        return []

    names = values("issueName")
    tickers = values("ticker")
    weights = values("holdingPercent")
    sectors = values("sectorName")
    countries = values("countryOfRisk")
    rows = []
    for index, weight in enumerate(weights[:25]):
        rows.append({
            "name": names[index] if index < len(names) else None,
            "ticker": tickers[index] if index < len(tickers) else None,
            "weight": weight,
            "sector": sectors[index] if index < len(sectors) else None,
            "country": countries[index] if index < len(countries) else None,
        })
    if not rows:
        return None
    return {"top_holdings": rows, "holding_count_sampled": len(rows)}


def iter_blackrock_datapoint_maps(payload: Any):
    if isinstance(payload, dict):
        data_points = payload.get("dataPointsByNameMap")
        if isinstance(data_points, dict):
            yield data_points
        for value in payload.values():
            yield from iter_blackrock_datapoint_maps(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from iter_blackrock_datapoint_maps(item)


def collect_blackrock_datapoints(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    data: dict[str, dict[str, Any]] = {}
    for data_points in iter_blackrock_datapoint_maps(payload):
        for key, value in data_points.items():
            if key not in data and isinstance(value, dict):
                data[key] = value
    return data


def blackrock_value(data_points: dict[str, dict[str, Any]], *keys: str) -> Any:
    for key in keys:
        point = data_points.get(key)
        if not point:
            continue
        value = first_present(point.get("formattedValue"), point.get("value"))
        if value not in (None, "", [], {}):
            return value
    return None


def blackrock_rich_value(data_points: dict[str, dict[str, Any]], *keys: str) -> dict[str, Any] | None:
    for key in keys:
        point = data_points.get(key)
        if not point:
            continue
        value = first_present(point.get("formattedValue"), point.get("value"))
        if value in (None, "", [], {}):
            continue
        return {
            "value": point.get("value"),
            "formatted": point.get("formattedValue"),
            "as_of": point.get("formattedAsOfDate") or point.get("asOfDate"),
            "label": point.get("label"),
        }
    return None


def blackrock_component_holdings_summary(payload: dict[str, Any]) -> dict[str, Any] | None:
    holdings_payload = payload.get("TopHoldingsV3")
    if not isinstance(holdings_payload, dict):
        return None
    rows = []
    for row in holdings_payload.get("topHoldings", []):
        if not isinstance(row, dict):
            continue
        rows.append({
            "name": row.get("holdingsName") or row.get("name"),
            "ticker": row.get("ticker"),
            "weight": row.get("holdingPercent") or row.get("weight"),
        })
    if not rows:
        return None
    return {
        "as_of": holdings_payload.get("holdingsAsOfDate"),
        "top_holdings": rows,
        "holding_count_sampled": len(rows),
    }


def blackrock_component_points(payload: dict[str, Any], source_id: str) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    data_points = collect_blackrock_datapoints(payload)
    fund_header = payload.get("FundHeaderV3") if isinstance(payload.get("FundHeaderV3"), dict) else {}
    fund_name = first_present(fund_header.get("fundName"), payload.get("fundName"))
    if not fund_name:
        for component in payload.values():
            if isinstance(component, dict):
                fund_name = first_present(component.get("fundName"), fund_name)
    if fund_name:
        points.append(context_point("fund_name", fund_name, source_id))
    benchmark = blackrock_value(data_points, "indexSeriesName", "indexName")
    if benchmark:
        points.append(context_point("benchmark", benchmark, source_id))
    expense = blackrock_value(data_points, "netExpenseRatio", "expenseRatio", "qgrs", "grs")
    if expense:
        points.append(context_point("expense_ratio", expense, source_id))
    net_assets = blackrock_rich_value(data_points, "totalNetAssetsFundLevel", "totalNetAssets")
    if net_assets:
        points.append(context_point("net_assets", net_assets, source_id))
    nav = blackrock_rich_value(data_points, "navAmount", "marketPrice")
    if nav:
        points.append(context_point("nav_or_market_snapshot", nav, source_id))
    holdings = blackrock_component_holdings_summary(payload)
    if holdings:
        points.append(context_point("holdings_summary", holdings, source_id))
    return points


def context_point(key: str, value: Any, source_id: str, confidence: str = "high") -> dict[str, Any]:
    return {
        "key": key,
        "label": key.replace("_", " ").title(),
        "value": value,
        "source_id": source_id,
        "confidence": confidence,
        "recorded_at": utc_now(),
    }


def merge_data_points(output_root: Path, symbol: str, points: list[dict[str, Any]]) -> dict[str, Any]:
    out = ensure_run(output_root, symbol)
    context = build_context(output_root, symbol)
    replacing = {point["key"] for point in points}
    data_points = [p for p in context.get("data_points", []) if p.get("key") not in replacing]
    data_points.extend(points)
    context["data_points"] = data_points
    keys = {p.get("key") for p in data_points}
    required = context_required_fields(context.get("classification", {}).get("security_type"))
    context["context_quality"] = {
        "required_material_fields": required,
        "missing_material_fields": [field for field in required if field not in keys],
        "is_sparse": any(field not in keys for field in required),
    }
    write_context_files(out, context)
    update_manifest(output_root, symbol, research_context=str(out / "research_context.json"))
    return context


def cmd_extract_blackrock(args: argparse.Namespace) -> None:
    symbol = normalize_symbol(args.symbol)
    output_root = Path(args.output_root)
    ensure_run(output_root, symbol)
    payload = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
    fund_header = payload.get("fundHeader") if isinstance(payload.get("fundHeader"), dict) else {}
    facts = payload.get("keyFundFacts") if isinstance(payload.get("keyFundFacts"), dict) else {}
    performance = payload.get("performance") if isinstance(payload.get("performance"), dict) else {}
    exposure = payload.get("exposureBreakdowns") if isinstance(payload.get("exposureBreakdowns"), dict) else {}
    points = []
    fund_name = first_present(fund_header.get("fundName"), fund_header.get("fund_name"))
    if fund_name:
        points.append(context_point("fund_name", fund_name, args.source_id))
    benchmark = first_present(fund_header.get("benchmark"), facts.get("benchmark"))
    if benchmark:
        points.append(context_point("benchmark", benchmark, args.source_id))
    expense = first_present(facts.get("netExpenseRatio"), facts.get("expenseRatio"), facts.get("totalExpenseRatio"))
    if expense:
        points.append(context_point("expense_ratio", expense, args.source_id))
    inception = first_present(facts.get("inceptionDate"), fund_header.get("inceptionDate"))
    if inception:
        points.append(context_point("inception_date", inception, args.source_id))
    if performance:
        points.append(context_point("performance", performance, args.source_id))
    if exposure:
        points.append(context_point("exposure_breakdowns", exposure, args.source_id))
    holdings = blackrock_holdings_summary(payload)
    if holdings:
        points.append(context_point("holdings_summary", holdings, args.source_id))
    points.extend(point for point in blackrock_component_points(payload, args.source_id) if point["key"] not in {existing["key"] for existing in points})
    context = merge_data_points(output_root, symbol, points)
    print(json.dumps({"added": [point["key"] for point in points], "is_sparse": context["context_quality"]["is_sparse"]}, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Procedural source registry and gap-fill helper for the Codex market-research skill.")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init-run", help="Create a run directory and manifest.")
    init.add_argument("symbol")
    init.add_argument("--output-root", default="./market-research-runs")
    init.add_argument("--force", action="store_true", help="Overwrite an existing initialized run manifest.")
    init.set_defaults(func=cmd_init_run)

    classify = sub.add_parser("classify", help="Record manual/best-effort classification.")
    classify.add_argument("symbol")
    classify.add_argument("--output-root", default="./market-research-runs")
    classify.add_argument("--security-type", choices=["equity", "adr", "etf"], required=True)
    classify.add_argument("--name")
    classify.add_argument("--confidence", choices=["high", "medium", "low"], default="medium")
    classify.add_argument("--note")
    classify.set_defaults(func=cmd_classify)

    source = sub.add_parser("record-source", help="Record a cited source.")
    source.add_argument("symbol")
    source.add_argument("--output-root", default="./market-research-runs")
    source.add_argument("--id", required=True)
    source.add_argument("--title", required=True)
    source.add_argument("--url", required=True)
    source.add_argument("--kind", required=True)
    source.add_argument("--source-date")
    source.add_argument("--artifact", help="Optional downloaded/local artifact to copy into source_bundle.")
    source.add_argument("--allow-type-mismatch", action="store_true", help="Record artifact even if extension and content sniffing disagree.")
    source.add_argument("--confidence", choices=["high", "medium", "low"], default="medium")
    source.set_defaults(func=cmd_record_source)

    source_gap = sub.add_parser("record-source-gap", help="Record a failed or incomplete public-source capture.")
    source_gap.add_argument("symbol")
    source_gap.add_argument("--output-root", default="./market-research-runs")
    source_gap.add_argument("--source-id", required=True)
    source_gap.add_argument("--attempted-url", required=True)
    source_gap.add_argument("--reason", required=True)
    source_gap.add_argument("--replacement-source-id")
    source_gap.add_argument("--severity", choices=["low", "medium", "high"], default="medium")
    source_gap.set_defaults(func=cmd_record_source_gap)

    context = sub.add_parser("prepare-research-context", help="Build compact research context.")
    context.add_argument("symbol")
    context.add_argument("--output-root", default="./market-research-runs")
    context.set_defaults(func=cmd_prepare_research_context)

    fill = sub.add_parser("record-gap-fill", help="Record a targeted procedural gap fill.")
    fill.add_argument("symbol")
    fill.add_argument("--output-root", default="./market-research-runs")
    fill.add_argument("--field")
    fill.add_argument("--value")
    fill.add_argument("--source-id")
    fill.add_argument("--confidence", choices=["high", "medium", "low"], default="medium")
    fill.add_argument("--note", default="")
    fill.add_argument("--json-file", help="Read field/value/source_id/confidence/note from a JSON object or array of objects.")
    fill.add_argument("--stdin-json", action="store_true", help="Read field/value/source_id/confidence/note from stdin JSON object or array.")
    fill.set_defaults(func=cmd_record_gap_fill)

    blackrock = sub.add_parser("extract-blackrock", help="Promote BlackRock/iShares product API JSON into research context.")
    blackrock.add_argument("symbol")
    blackrock.add_argument("--output-root", default="./market-research-runs")
    blackrock.add_argument("--json-file", required=True)
    blackrock.add_argument("--source-id", default="blackrock_product_api")
    blackrock.set_defaults(func=cmd_extract_blackrock)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
