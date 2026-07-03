#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import venv

PYTHON_PREREQS = {"jsonschema": "jsonschema"}
DEFAULT_VENV_DIR = ".venv-market-research"


def kpsewhich_file(name: str) -> bool:
    if shutil.which("kpsewhich") is None:
        return False
    result = subprocess.run(["kpsewhich", name], text=True, capture_output=True, check=False)
    return result.returncode == 0 and bool(result.stdout.strip())


def python_module_available(name: str, *, python: Path | None = None) -> bool:
    if python is None:
        return importlib.util.find_spec(name) is not None
    result = subprocess.run(
        [str(python), "-c", f"import {name}"],
        text=True,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def venv_python(venv_dir: Path) -> Path:
    return venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def ensure_python_prereqs(venv_dir: Path) -> dict[str, object]:
    missing = [module for module in PYTHON_PREREQS if not python_module_available(module)]
    result: dict[str, object] = {
        "venv_dir": str(venv_dir),
        "python": str(venv_python(venv_dir)),
        "requested": sorted(PYTHON_PREREQS),
        "missing_before": missing,
        "installed": [],
        "errors": [],
    }
    if not missing:
        return result
    try:
        if not venv_python(venv_dir).exists():
            venv.create(venv_dir, with_pip=True)
        packages = [PYTHON_PREREQS[module] for module in missing]
        install = subprocess.run(
            [str(venv_python(venv_dir)), "-m", "pip", "install", *packages],
            text=True,
            capture_output=True,
            check=False,
        )
        if install.returncode == 0:
            result["installed"] = packages
        else:
            result["errors"] = [install.stderr.strip() or install.stdout.strip() or "pip install failed"]
    except Exception as exc:  # noqa: BLE001 - preflight should report failures as data.
        result["errors"] = [str(exc)]
    return result


def collect_checks(*, python: Path | None = None) -> dict[str, bool]:
    return {
        "jsonschema": python_module_available("jsonschema", python=python),
        "pandoc": shutil.which("pandoc") is not None,
        "xelatex": shutil.which("xelatex") is not None,
        "lmodern": kpsewhich_file("lmodern.sty"),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check local market-research tool prerequisites.")
    parser.add_argument(
        "--ensure-python-prereqs",
        action="store_true",
        help="Create a local venv and pip install missing Python prerequisites such as jsonschema.",
    )
    parser.add_argument(
        "--venv-dir",
        default=DEFAULT_VENV_DIR,
        help=f"Local venv directory used with --ensure-python-prereqs. Defaults to {DEFAULT_VENV_DIR}.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    ensure_result = None
    checks = collect_checks()
    if args.ensure_python_prereqs:
        ensure_result = ensure_python_prereqs(Path(args.venv_dir))
        venv_py = venv_python(Path(args.venv_dir))
        if venv_py.exists():
            venv_checks = collect_checks(python=venv_py)
            checks["jsonschema"] = checks["jsonschema"] or venv_checks["jsonschema"]
            ensure_result["checks_with_venv_python"] = venv_checks
    payload = {"checks": checks}
    if ensure_result is not None:
        payload["python_prereq_install"] = ensure_result
        payload["run_with_venv_python"] = f"{venv_python(Path(args.venv_dir))} <script> ..."
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
