#!/usr/bin/env python3
"""Compatibility wrapper for the packaged OpenClaw helper.

The implementation lives in src/cool_financial_research/openclaw_helper.py so it
can be imported, tested, and packaged. This wrapper keeps the v0.5 command path
stable for SKILL.md and existing OpenClaw instructions.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cool_financial_research.openclaw_helper import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
