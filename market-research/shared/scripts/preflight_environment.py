#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess


def kpsewhich_file(name: str) -> bool:
    if shutil.which("kpsewhich") is None:
        return False
    result = subprocess.run(["kpsewhich", name], text=True, capture_output=True, check=False)
    return result.returncode == 0 and bool(result.stdout.strip())


def main() -> None:
    checks = {
        "jsonschema": importlib.util.find_spec("jsonschema") is not None,
        "pandoc": shutil.which("pandoc") is not None,
        "xelatex": shutil.which("xelatex") is not None,
        "lmodern": kpsewhich_file("lmodern.sty"),
    }
    print(json.dumps({"checks": checks}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
