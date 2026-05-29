# Codex Market Research Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build two Codex-installable skills: `market-research` for helper-assisted equity/ETF research and `validate-market-research` for fresh-context validation of frozen research bundles.

**Architecture:** Create a small Codex-native skill package in this repo, with deterministic helpers kept optional and procedural instructions kept authoritative. The producer helper gathers/classifies/extracts/scaffolds and degrades gracefully; the validator helper discovers artifacts and checks schema/issue consistency while Codex performs judgment validation.

**Tech Stack:** Codex skills (`SKILL.md`, `agents/openai.yaml`, `references/`, `scripts/`), Python 3.10+ standard library, JSON Schema files, pytest for helper tests, official skill validation scripts.

---

## File Structure

- Create `market-research/SKILL.md`: producer workflow, fallback rules, source hierarchy, artifact contract.
- Create `market-research/agents/openai.yaml`: UI metadata generated from the finished skill.
- Create `market-research/scripts/market_research_helper.py`: optional deterministic helper CLI.
- Create `market-research/references/source-policy.md`: source quality and citation rules.
- Create `market-research/references/equity-research.md`: equity/ADR report checklist.
- Create `market-research/references/etf-research.md`: ETF report checklist, including BlackRock/iShares handling.
- Create `market-research/references/report-template.md`: concise markdown and JSON artifact expectations.
- Create `market-research/schemas/research-output.schema.json`: simplified research JSON schema.
- Create `market-research/schemas/validation-output.schema.json`: validation JSON schema shared with validator.
- Create `validate-market-research/SKILL.md`: fresh-context validation workflow.
- Create `validate-market-research/agents/openai.yaml`: UI metadata generated from the finished skill.
- Create `validate-market-research/scripts/validate_market_research.py`: artifact discovery and deterministic validation helper.
- Create `validate-market-research/references/investment-validation.md`: validation checklist.
- Create `tests/test_market_research_helper.py`: producer helper tests.
- Create `tests/test_validate_market_research.py`: validator helper tests.

## Task 1: Scaffold Skill Directories

**Files:**
- Create: `market-research/`
- Create: `validate-market-research/`

- [ ] **Step 1: Initialize producer skill**

Run:

```bash
python3 /home/rom/.codex/skills/.system/skill-creator/scripts/init_skill.py market-research --path /home/rom/src/market_research_skill --resources scripts,references --interface display_name="Market Research" --interface short_description="Research public equities and ETFs with helper-assisted source gathering and graceful fallback." --interface default_prompt="Research the symbol provided by the user using public/free sources, write cited markdown and JSON artifacts, and disclose data gaps."
```

Expected: `market-research/` exists with `SKILL.md`, `agents/openai.yaml`, `scripts/`, and `references/`.

- [ ] **Step 2: Initialize validator skill**

Run:

```bash
python3 /home/rom/.codex/skills/.system/skill-creator/scripts/init_skill.py validate-market-research --path /home/rom/src/market_research_skill --resources scripts,references --interface display_name="Validate Market Research" --interface short_description="Validate frozen public-market research bundles in a fresh context." --interface default_prompt="Validate the research bundle path provided by the user, write validation markdown and JSON artifacts, and report blocking issues."
```

Expected: `validate-market-research/` exists with `SKILL.md`, `agents/openai.yaml`, `scripts/`, and `references/`.

- [ ] **Step 3: Remove generated placeholder resource files**

Run:

```bash
find market-research validate-market-research -name 'example.*' -print
```

Expected: If example placeholder files exist, delete only those generated placeholders. Do not delete `agents/openai.yaml`.

- [ ] **Step 4: Commit scaffold**

Run:

```bash
git add market-research validate-market-research
git commit -m "Scaffold Codex market research skills"
```

Expected: Commit succeeds.

## Task 2: Implement Producer Helper Core

**Files:**
- Create: `market-research/scripts/market_research_helper.py`
- Create: `tests/test_market_research_helper.py`

- [ ] **Step 1: Write failing tests for symbol safety and run initialization**

Create `tests/test_market_research_helper.py` with:

```python
import json
import subprocess
import sys
from pathlib import Path

HELPER = Path(__file__).resolve().parents[1] / "market-research" / "scripts" / "market_research_helper.py"


def run_helper(*args, cwd=None):
    return subprocess.run(
        [sys.executable, str(HELPER), *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def test_init_run_creates_manifest(tmp_path):
    result = run_helper("init-run", "aapl", "--output-root", str(tmp_path))
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    run_dir = tmp_path / "AAPL"
    assert payload["symbol"] == "AAPL"
    assert Path(payload["run_dir"]) == run_dir
    manifest = json.loads((run_dir / "run_manifest.json").read_text())
    assert manifest["symbol"] == "AAPL"
    assert manifest["helper_errors"] == []
    assert manifest["procedural_gap_fills"] == []


def test_invalid_symbol_rejected(tmp_path):
    result = run_helper("init-run", "../AAPL", "--output-root", str(tmp_path))
    assert result.returncode != 0
    assert "Invalid symbol" in result.stderr
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest tests/test_market_research_helper.py -q
```

Expected: FAIL because `market_research_helper.py` is missing or does not implement `init-run`.

- [ ] **Step 3: Implement minimal helper CLI**

Create `market-research/scripts/market_research_helper.py` with:

```python
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


def cmd_init_run(args: argparse.Namespace) -> None:
    symbol = normalize_symbol(args.symbol)
    out = run_dir(Path(args.output_root), symbol)
    source_bundle = out / "source_bundle"
    source_bundle.mkdir(parents=True, exist_ok=True)
    manifest = {
        "symbol": symbol,
        "created_at": utc_now(),
        "updated_at": utc_now(),
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Best-effort deterministic helper for the Codex market-research skill.")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init-run", help="Create a run directory and manifest.")
    init.add_argument("symbol")
    init.add_argument("--output-root", default="./market-research-runs")
    init.set_defaults(func=cmd_init_run)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```bash
pytest tests/test_market_research_helper.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit producer helper core**

Run:

```bash
git add market-research/scripts/market_research_helper.py tests/test_market_research_helper.py
git commit -m "Add market research helper core"
```

Expected: Commit succeeds.

## Task 3: Add Classification, Source Recording, And Research Context

**Files:**
- Modify: `market-research/scripts/market_research_helper.py`
- Modify: `tests/test_market_research_helper.py`

- [ ] **Step 1: Add failing tests for manual classification, source recording, sparse context, and procedural fills**

Append to `tests/test_market_research_helper.py`:

```python
def test_classify_manual_updates_manifest(tmp_path):
    run_helper("init-run", "vti", "--output-root", str(tmp_path))
    result = run_helper("classify", "VTI", "--output-root", str(tmp_path), "--security-type", "etf", "--name", "Vanguard Total Stock Market ETF")
    assert result.returncode == 0, result.stderr
    classification = json.loads((tmp_path / "VTI" / "source_bundle" / "classification.json").read_text())
    assert classification["security_type"] == "etf"
    assert classification["source"] == "manual"
    manifest = json.loads((tmp_path / "VTI" / "run_manifest.json").read_text())
    assert manifest["security_type"] == "etf"


def test_record_source_and_prepare_sparse_context(tmp_path):
    run_helper("init-run", "ECH", "--output-root", str(tmp_path))
    run_helper("classify", "ECH", "--output-root", str(tmp_path), "--security-type", "etf", "--name", "iShares MSCI Chile ETF")
    result = run_helper(
        "record-source",
        "ECH",
        "--output-root",
        str(tmp_path),
        "--id",
        "issuer_page",
        "--title",
        "iShares ECH product page",
        "--url",
        "https://www.ishares.com/us/products/239618/",
        "--kind",
        "issuer_product_page",
    )
    assert result.returncode == 0, result.stderr
    result = run_helper("prepare-research-context", "ECH", "--output-root", str(tmp_path))
    assert result.returncode == 0, result.stderr
    context = json.loads((tmp_path / "ECH" / "research_context.json").read_text())
    assert context["symbol"] == "ECH"
    assert context["context_quality"]["is_sparse"] is True
    assert "expense_ratio" in context["context_quality"]["missing_material_fields"]


def test_record_gap_fill_updates_context_and_manifest(tmp_path):
    run_helper("init-run", "ECH", "--output-root", str(tmp_path))
    run_helper("classify", "ECH", "--output-root", str(tmp_path), "--security-type", "etf")
    result = run_helper(
        "record-gap-fill",
        "ECH",
        "--output-root",
        str(tmp_path),
        "--field",
        "expense_ratio",
        "--value",
        "0.59%",
        "--source-id",
        "issuer_fact_sheet",
        "--confidence",
        "high",
        "--note",
        "Procedurally filled from issuer fact sheet.",
    )
    assert result.returncode == 0, result.stderr
    context = json.loads((tmp_path / "ECH" / "research_context.json").read_text())
    assert context["data_points"][0]["key"] == "expense_ratio"
    manifest = json.loads((tmp_path / "ECH" / "run_manifest.json").read_text())
    assert manifest["procedural_gap_fills"][0]["field"] == "expense_ratio"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest tests/test_market_research_helper.py -q
```

Expected: FAIL because the new commands are missing.

- [ ] **Step 3: Implement helper commands**

Modify `market-research/scripts/market_research_helper.py` to add:

```python
ETF_REQUIRED_FIELDS = ["fund_name", "expense_ratio", "benchmark", "holdings_summary"]
EQUITY_REQUIRED_FIELDS = ["company_name", "latest_annual_filing", "revenue", "net_income"]


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
    out = ensure_run(Path(args.output_root), symbol)
    context = build_context(Path(args.output_root), symbol)
    write_context_files(out, context)
    update_manifest(Path(args.output_root), symbol, research_context=str(out / "research_context.json"))
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
    context["data_points"] = [p for p in context.get("data_points", []) if p.get("key") != args.field]
    context["data_points"].append(point)
    write_context_files(out, build_context(output_root, symbol) | {"data_points": context["data_points"]})
    manifest = read_json(out / "run_manifest.json")
    fills = manifest.get("procedural_gap_fills", [])
    fills.append({"field": args.field, "value": args.value, "source_id": args.source_id, "confidence": args.confidence, "note": args.note, "recorded_at": utc_now()})
    update_manifest(output_root, symbol, procedural_gap_fills=fills)
    print(json.dumps(point, indent=2, sort_keys=True))
```

Also add parser subcommands:

```python
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
```

- [ ] **Step 4: Run tests and fix any syntax issues**

Run:

```bash
pytest tests/test_market_research_helper.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit context helper**

Run:

```bash
git add market-research/scripts/market_research_helper.py tests/test_market_research_helper.py
git commit -m "Add research context helper commands"
```

Expected: Commit succeeds.

## Task 4: Add BlackRock/iShares Structured Extraction

**Files:**
- Modify: `market-research/scripts/market_research_helper.py`
- Modify: `tests/test_market_research_helper.py`

- [ ] **Step 1: Add failing test with a small BlackRock-like payload**

Append to `tests/test_market_research_helper.py`:

```python
def test_extract_blackrock_payload_promotes_key_fields(tmp_path):
    payload = {
        "fundHeader": {
            "fundName": "iShares MSCI Chile ETF",
            "ticker": "ECH",
            "benchmark": "MSCI Chile IMI 25/50 Index",
        },
        "keyFundFacts": {
            "netExpenseRatio": "0.59%",
            "inceptionDate": "2007-11-12",
        },
        "performance": {
            "asOfDate": "2026-03-31",
            "oneYear": "12.3%",
        },
        "exposureBreakdowns": {
            "country": [{"name": "Chile", "weight": "99.1%"}],
            "sector": [{"name": "Financials", "weight": "28.4%"}],
        },
        "componentsByNameMap": {
            "holdings": {
                "containersByNameMap": {
                    "all": {
                        "dataPointsByNameMap": {
                            "issueName": {"value": ["Banco de Chile"]},
                            "ticker": {"value": ["CHILE"]},
                            "holdingPercent": {"value": ["8.1"]},
                            "sectorName": {"value": ["Financials"]},
                            "countryOfRisk": {"value": ["Chile"]},
                        }
                    }
                }
            }
        },
    }
    source_path = tmp_path / "blackrock_product.json"
    source_path.write_text(json.dumps(payload), encoding="utf-8")
    run_helper("init-run", "ECH", "--output-root", str(tmp_path))
    run_helper("classify", "ECH", "--output-root", str(tmp_path), "--security-type", "etf")
    result = run_helper(
        "extract-blackrock",
        "ECH",
        "--output-root",
        str(tmp_path),
        "--json-file",
        str(source_path),
        "--source-id",
        "blackrock_product_api",
    )
    assert result.returncode == 0, result.stderr
    context = json.loads((tmp_path / "ECH" / "research_context.json").read_text())
    by_key = {point["key"]: point for point in context["data_points"]}
    assert by_key["fund_name"]["value"] == "iShares MSCI Chile ETF"
    assert by_key["expense_ratio"]["value"] == "0.59%"
    assert by_key["benchmark"]["value"] == "MSCI Chile IMI 25/50 Index"
    assert by_key["holdings_summary"]["value"]["top_holdings"][0]["name"] == "Banco de Chile"
    assert context["context_quality"]["is_sparse"] is False
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
pytest tests/test_market_research_helper.py::test_extract_blackrock_payload_promotes_key_fields -q
```

Expected: FAIL because `extract-blackrock` is missing.

- [ ] **Step 3: Implement BlackRock extractor**

Add helper functions:

```python
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
    data_points = [p for p in context.get("data_points", []) if p.get("key") not in {point["key"] for point in points}]
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
```

Add parser subcommand:

```python
    blackrock = sub.add_parser("extract-blackrock", help="Promote BlackRock/iShares product API JSON into research context.")
    blackrock.add_argument("symbol")
    blackrock.add_argument("--output-root", default="./market-research-runs")
    blackrock.add_argument("--json-file", required=True)
    blackrock.add_argument("--source-id", default="blackrock_product_api")
    blackrock.set_defaults(func=cmd_extract_blackrock)
```

- [ ] **Step 4: Run helper tests**

Run:

```bash
pytest tests/test_market_research_helper.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit BlackRock extraction**

Run:

```bash
git add market-research/scripts/market_research_helper.py tests/test_market_research_helper.py
git commit -m "Promote BlackRock ETF data into research context"
```

Expected: Commit succeeds.

## Task 5: Add Schemas And Validator Helper

**Files:**
- Create: `market-research/schemas/research-output.schema.json`
- Create: `market-research/schemas/validation-output.schema.json`
- Create: `validate-market-research/scripts/validate_market_research.py`
- Create: `tests/test_validate_market_research.py`

- [ ] **Step 1: Add failing validator tests**

Create `tests/test_validate_market_research.py` with:

```python
import json
import subprocess
import sys
from pathlib import Path

VALIDATOR = Path(__file__).resolve().parents[1] / "validate-market-research" / "scripts" / "validate_market_research.py"


def run_validator(*args):
    return subprocess.run([sys.executable, str(VALIDATOR), *args], text=True, capture_output=True, check=False)


def test_validator_discovers_research_bundle(tmp_path):
    run_dir = tmp_path / "AAPL"
    run_dir.mkdir()
    (run_dir / "run_manifest.json").write_text(json.dumps({"symbol": "AAPL"}), encoding="utf-8")
    (run_dir / "AAPL-research.md").write_text("# AAPL Research\n", encoding="utf-8")
    (run_dir / "AAPL-research.json").write_text(json.dumps({"symbol": "AAPL", "security_type": "equity", "material_claims": [], "data_gaps": []}), encoding="utf-8")
    result = run_validator(str(run_dir))
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["symbol"] == "AAPL"
    assert payload["blocking_issue_count"] == 0
    assert (run_dir / "AAPL-validation.json").exists()
    assert (run_dir / "AAPL-validation.md").exists()


def test_validator_flags_missing_json(tmp_path):
    run_dir = tmp_path / "MSFT"
    run_dir.mkdir()
    (run_dir / "MSFT-research.md").write_text("# MSFT Research\n", encoding="utf-8")
    result = run_validator(str(run_dir))
    assert result.returncode != 0
    assert "research JSON" in result.stderr
```

- [ ] **Step 2: Run validator tests and verify failure**

Run:

```bash
pytest tests/test_validate_market_research.py -q
```

Expected: FAIL because validator script is missing.

- [ ] **Step 3: Create simplified schemas**

Create `market-research/schemas/research-output.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Market Research Output",
  "type": "object",
  "required": ["symbol", "security_type", "material_claims", "data_gaps"],
  "properties": {
    "symbol": {"type": "string"},
    "security_type": {"enum": ["equity", "adr", "etf"]},
    "as_of_date": {"type": "string"},
    "material_claims": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["claim", "source_id", "confidence"],
        "properties": {
          "claim": {"type": "string"},
          "source_id": {"type": "string"},
          "source_date": {"type": ["string", "null"]},
          "accessed_date": {"type": ["string", "null"]},
          "confidence": {"enum": ["high", "medium", "low", "unverified"]},
          "verification_status": {"enum": ["verified", "unverified", "data_not_available"]}
        },
        "additionalProperties": true
      }
    },
    "data_gaps": {"type": "array", "items": {"type": "object"}}
  },
  "additionalProperties": true
}
```

Create `market-research/schemas/validation-output.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Market Research Validation Output",
  "type": "object",
  "required": ["symbol", "issues", "issue_counts", "blocking_issue_count"],
  "properties": {
    "symbol": {"type": "string"},
    "issues": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "severity", "status", "description"],
        "properties": {
          "id": {"type": "string"},
          "severity": {"enum": ["critical", "moderate", "minor"]},
          "status": {"enum": ["open", "resolved", "unresolved_data_unavailable"]},
          "description": {"type": "string"}
        },
        "additionalProperties": true
      }
    },
    "issue_counts": {
      "type": "object",
      "required": ["critical", "moderate", "minor"],
      "properties": {
        "critical": {"type": "integer"},
        "moderate": {"type": "integer"},
        "minor": {"type": "integer"}
      }
    },
    "blocking_issue_count": {"type": "integer"},
    "data_gaps": {"type": "array", "items": {"type": "object"}}
  },
  "additionalProperties": true
}
```

- [ ] **Step 4: Implement validator helper**

Create `validate-market-research/scripts/validate_market_research.py`:

```python
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
    for index, claim in enumerate(report.get("material_claims", []) if isinstance(report.get("material_claims"), list) else []):
        if not claim.get("source_id"):
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
```

- [ ] **Step 5: Run validator tests**

Run:

```bash
pytest tests/test_validate_market_research.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit schemas and validator helper**

Run:

```bash
git add market-research/schemas validate-market-research/scripts/validate_market_research.py tests/test_validate_market_research.py
git commit -m "Add market research validation helper"
```

Expected: Commit succeeds.

## Task 6: Write Producer Skill References And SKILL.md

**Files:**
- Modify: `market-research/SKILL.md`
- Create: `market-research/references/source-policy.md`
- Create: `market-research/references/equity-research.md`
- Create: `market-research/references/etf-research.md`
- Create: `market-research/references/report-template.md`

- [ ] **Step 1: Write source policy reference**

Create `market-research/references/source-policy.md` with source hierarchy, citation rules, stale-data rules, and the helper failure ladder from the spec.

- [ ] **Step 2: Write equity research reference**

Create `market-research/references/equity-research.md` with sections for business overview, filings, financials, capital allocation, valuation context, risks, data gaps, and required primary sources.

- [ ] **Step 3: Write ETF research reference**

Create `market-research/references/etf-research.md` with sections for sponsor/product facts, index methodology, fees, holdings, exposures, performance, liquidity, tax/structure notes, risks, and BlackRock/iShares product ID handling.

- [ ] **Step 4: Write report template reference**

Create `market-research/references/report-template.md` with the required markdown sections and minimal JSON example:

```json
{
  "symbol": "AAPL",
  "security_type": "equity",
  "as_of_date": "2026-05-29",
  "material_claims": [
    {
      "claim": "Example sourced quantitative claim.",
      "source_id": "latest_10k",
      "source_date": "2025-09-27",
      "accessed_date": "2026-05-29",
      "confidence": "high",
      "verification_status": "verified"
    }
  ],
  "data_gaps": []
}
```

- [ ] **Step 5: Replace producer SKILL.md**

Write `market-research/SKILL.md` with frontmatter:

```yaml
---
name: market-research
description: Research US-listed equities, ADRs, and ETFs from a ticker symbol using public/free sources; create cited markdown and JSON artifacts; use deterministic helper scripts when useful but gracefully fall back to procedural research when helpers fail or are sparse. Use when Codex is asked for investment, equity, stock, ADR, ETF, fund, issuer, holdings, valuation, risk, or market research on a symbol.
---
```

The body must instruct Codex to:

- Run helpers first when practical.
- Inspect `research_context.json` before writing.
- Use targeted procedural gap filling for partial helper success.
- Prefer primary sources.
- Keep facts separate from interpretation.
- Write `market-research-runs/<SYMBOL>/` artifacts.
- Disclose data gaps and helper failures.
- Recommend fresh-context validation through `validate-market-research`.

- [ ] **Step 6: Commit producer instructions**

Run:

```bash
git add market-research/SKILL.md market-research/references
git commit -m "Write market research skill instructions"
```

Expected: Commit succeeds.

## Task 7: Write Validator Skill Reference And SKILL.md

**Files:**
- Modify: `validate-market-research/SKILL.md`
- Create: `validate-market-research/references/investment-validation.md`

- [ ] **Step 1: Write investment validation reference**

Create `validate-market-research/references/investment-validation.md` with checks for source support, stale data, unsupported quantitative claims, omitted risks, internal contradictions, ETF exposure/fee/performance support, equity valuation support, and issue severity definitions.

- [ ] **Step 2: Replace validator SKILL.md**

Write `validate-market-research/SKILL.md` with frontmatter:

```yaml
---
name: validate-market-research
description: Validate frozen market research bundles for equities, ADRs, and ETFs in a fresh Codex context; inspect cited artifacts and public sources; write validation markdown and JSON without editing the original report. Use when Codex is asked to validate, review, audit, or check an investment research report or a market-research run directory.
---
```

The body must instruct Codex to:

- Use only the run directory, cited sources, and sources inspected in the current context.
- Treat the report as claims to test.
- Run the validation helper for deterministic artifact checks.
- Perform judgment validation manually.
- Write `<SYMBOL>-validation.md/json`.
- Never edit the producer report.
- Report blocking critical/moderate issue counts.

- [ ] **Step 3: Commit validator instructions**

Run:

```bash
git add validate-market-research/SKILL.md validate-market-research/references/investment-validation.md
git commit -m "Write market research validation skill instructions"
```

Expected: Commit succeeds.

## Task 8: Validate Skill Metadata And Full Test Suite

**Files:**
- Modify if needed: `market-research/agents/openai.yaml`
- Modify if needed: `validate-market-research/agents/openai.yaml`

- [ ] **Step 1: Regenerate UI metadata**

Run:

```bash
python3 /home/rom/.codex/skills/.system/skill-creator/scripts/generate_openai_yaml.py market-research --interface display_name="Market Research" --interface short_description="Research public equities and ETFs with helper-assisted source gathering and graceful fallback." --interface default_prompt="Research the symbol provided by the user using public/free sources, write cited markdown and JSON artifacts, and disclose data gaps."
python3 /home/rom/.codex/skills/.system/skill-creator/scripts/generate_openai_yaml.py validate-market-research --interface display_name="Validate Market Research" --interface short_description="Validate frozen public-market research bundles in a fresh context." --interface default_prompt="Validate the research bundle path provided by the user, write validation markdown and JSON artifacts, and report blocking issues."
```

Expected: Both `agents/openai.yaml` files reflect the final skill behavior.

- [ ] **Step 2: Run skill quick validation**

Run:

```bash
python3 /home/rom/.codex/skills/.system/skill-creator/scripts/quick_validate.py market-research
python3 /home/rom/.codex/skills/.system/skill-creator/scripts/quick_validate.py validate-market-research
```

Expected: Both validations pass.

- [ ] **Step 3: Run full tests**

Run:

```bash
pytest -q
```

Expected: All tests pass.

- [ ] **Step 4: Commit validation cleanup**

Run:

```bash
git add market-research validate-market-research tests
git commit -m "Validate Codex market research skills"
```

Expected: Commit succeeds if files changed.

## Task 9: Smoke Test Helper Workflows

**Files:**
- Runtime output only under `/tmp/market-research-smoke`

- [ ] **Step 1: Smoke test ETF sparse-to-filled context**

Run:

```bash
rm -rf /tmp/market-research-smoke
python3 market-research/scripts/market_research_helper.py init-run ECH --output-root /tmp/market-research-smoke
python3 market-research/scripts/market_research_helper.py classify ECH --output-root /tmp/market-research-smoke --security-type etf --name "iShares MSCI Chile ETF"
python3 market-research/scripts/market_research_helper.py record-source ECH --output-root /tmp/market-research-smoke --id issuer_page --title "iShares ECH product page" --url "https://www.ishares.com/us/products/239618/" --kind issuer_product_page
python3 market-research/scripts/market_research_helper.py prepare-research-context ECH --output-root /tmp/market-research-smoke
```

Expected: `/tmp/market-research-smoke/ECH/research_context.json` exists and marks context sparse until fields are filled.

- [ ] **Step 2: Smoke test validator helper**

Create a minimal `/tmp/market-research-smoke/ECH/ECH-research.json` and `/tmp/market-research-smoke/ECH/ECH-research.md`, then run:

```bash
python3 validate-market-research/scripts/validate_market_research.py /tmp/market-research-smoke/ECH
```

Expected: `ECH-validation.md` and `ECH-validation.json` are created.

- [ ] **Step 3: Commit final smoke-test notes if docs changed**

Run:

```bash
git status --short
```

Expected: Only intended repo files are changed. Do not commit `/tmp` smoke outputs.

