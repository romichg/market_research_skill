"""Shared primitives for market-research helper scripts."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SYMBOL_RE = re.compile(r"^(?=.*[A-Z0-9])[A-Z0-9][A-Z0-9.\-]{0,11}$")
AS_OF_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def die(message: str, code: int = 2) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def nested_get(payload: dict[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


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


def normalize_symbol(symbol: str) -> str:
    value = symbol.strip().upper()
    if not SYMBOL_RE.fullmatch(value):
        die(f"Invalid symbol: {symbol!r}")
    return value


def validate_as_of(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    if not AS_OF_RE.fullmatch(value):
        die(f"Invalid as-of {value!r}; expected YYYY-MM-DD.")
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        die(f"Invalid as-of {value!r}; expected a real calendar date.")
    return value


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        die(f"JSON file not found: {path}")
    except json.JSONDecodeError as exc:
        die(f"Could not parse JSON {path}: {exc}")


def write_json(path: Path, payload: Any, *, atomic: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if not atomic:
        path.write_text(text, encoding="utf-8")
        return
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
