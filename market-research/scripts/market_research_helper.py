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
