#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SYMBOL_RE = re.compile(r"^[A-Z0-9.\-]{1,12}$")
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


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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
    manifest = read_json(path)
    manifest.update(updates)
    manifest["updated_at"] = utc_now()
    write_json(path, manifest)
    return manifest


def cmd_init_run(args: argparse.Namespace) -> None:
    symbol = normalize_symbol(args.symbol)
    out = run_dir(Path(args.output_root), symbol)
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
    payload = load_sources(out)
    source = {
        "id": args.id,
        "title": args.title,
        "url": args.url,
        "kind": args.kind,
        "accessed_at": utc_now(),
        "source_date": args.source_date,
        "confidence": args.confidence,
    }
    payload["sources"] = [s for s in payload["sources"] if s.get("id") != args.id]
    payload["sources"].append(source)
    write_json(out / "sources.json", payload)
    print(json.dumps(source, indent=2, sort_keys=True))


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
    data_points = previous.get("data_points", [])
    keys = {p.get("key") for p in data_points}
    required = context_required_fields(classification.get("security_type") or manifest.get("security_type"))
    missing = [field for field in required if field not in keys]
    sources = load_sources(out)
    return {
        "symbol": symbol,
        "created_at": previous.get("created_at") or utc_now(),
        "updated_at": utc_now(),
        "classification": classification,
        "sources": sources.get("sources", []),
        "data_points": data_points,
        "context_quality": {
            "required_material_fields": required,
            "missing_material_fields": missing,
            "is_sparse": bool(missing),
        },
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
    context = build_context(output_root, symbol)
    point = {
        "key": args.field,
        "label": args.field.replace("_", " ").title(),
        "value": args.value,
        "source_id": args.source_id,
        "confidence": args.confidence,
        "note": args.note,
        "filled_by": "procedural",
        "recorded_at": utc_now(),
    }
    data_points = [p for p in context.get("data_points", []) if p.get("key") != args.field]
    data_points.append(point)
    context["data_points"] = data_points
    keys = {p.get("key") for p in data_points}
    required = context["context_quality"]["required_material_fields"]
    context["context_quality"] = {
        "required_material_fields": required,
        "missing_material_fields": [field for field in required if field not in keys],
        "is_sparse": any(field not in keys for field in required),
    }
    write_context_files(out, context)
    manifest = read_json(out / "run_manifest.json")
    fills = manifest.get("procedural_gap_fills", [])
    fills.append({"field": args.field, "value": args.value, "source_id": args.source_id, "confidence": args.confidence, "note": args.note, "recorded_at": utc_now()})
    update_manifest(output_root, symbol, procedural_gap_fills=fills, research_context=str(out / "research_context.json"))
    print(json.dumps(point, indent=2, sort_keys=True))


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
    context = merge_data_points(output_root, symbol, points)
    print(json.dumps({"added": [point["key"] for point in points], "is_sparse": context["context_quality"]["is_sparse"]}, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Best-effort deterministic helper for the Codex market-research skill.")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init-run", help="Create a run directory and manifest.")
    init.add_argument("symbol")
    init.add_argument("--output-root", default="./market-research-runs")
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
    source.add_argument("--confidence", choices=["high", "medium", "low"], default="medium")
    source.set_defaults(func=cmd_record_source)

    context = sub.add_parser("prepare-research-context", help="Build compact research context.")
    context.add_argument("symbol")
    context.add_argument("--output-root", default="./market-research-runs")
    context.set_defaults(func=cmd_prepare_research_context)

    fill = sub.add_parser("record-gap-fill", help="Record a targeted procedural gap fill.")
    fill.add_argument("symbol")
    fill.add_argument("--output-root", default="./market-research-runs")
    fill.add_argument("--field", required=True)
    fill.add_argument("--value", required=True)
    fill.add_argument("--source-id", required=True)
    fill.add_argument("--confidence", choices=["high", "medium", "low"], default="medium")
    fill.add_argument("--note", default="")
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
