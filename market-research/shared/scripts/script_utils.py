"""Shared primitives for market-research helper scripts."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

SYMBOL_RE = re.compile(r"^(?=.*[A-Z0-9])[A-Z0-9][A-Z0-9.\-]{0,11}$")
AS_OF_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def die(message: str, code: int = 2) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


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
