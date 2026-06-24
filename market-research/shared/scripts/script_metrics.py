"""Small opt-in metrics sidecar support for CLI helper scripts."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


def start_timer() -> float:
    return time.perf_counter()


def add_metrics_arg(parser: Any) -> None:
    parser.add_argument("--metrics-json", help="Optional path for elapsed-time and command metrics JSON.")


def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    return value


def write_metrics(path: str | None, *, start: float, **payload: Any) -> None:
    if not path:
        return
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    body = {key: _jsonable(value) for key, value in payload.items()}
    body["elapsed_seconds"] = round(time.perf_counter() - start, 6)
    tmp_path = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    tmp_path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(output)
