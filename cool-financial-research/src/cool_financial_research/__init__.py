"""OpenClaw-only deterministic helpers for Cool Financial Research.

This package intentionally performs no LLM calls and exposes no standalone
research CLI. OpenClaw remains the agent harness; the importable modules and
``scripts/cfr_helper.py`` provide deterministic support for classification,
artifact validation, source bundling, PDF fallbacks, charts, and the
provider-value ledger.
"""

__version__ = "0.7.0"
