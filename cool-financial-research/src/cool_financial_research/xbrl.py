"""Thin importable wrappers for SEC companyfacts/XBRL extraction."""
from __future__ import annotations

from .openclaw_helper import cmd_extract_xbrl_metrics, latest_fact_by_tag

__all__ = ["cmd_extract_xbrl_metrics", "latest_fact_by_tag"]
