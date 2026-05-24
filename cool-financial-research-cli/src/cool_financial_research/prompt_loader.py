from __future__ import annotations

from importlib import resources

PROMPT_NAMES = {
    ("equity", "research"): "equity-research.md",
    ("equity", "validation"): "equity-validation.md",
    ("equity", "fix"): "equity-research-fix-validation.md",
    ("adr", "research"): "equity-research.md",
    ("adr", "validation"): "equity-validation.md",
    ("adr", "fix"): "equity-research-fix-validation.md",
    ("etf", "research"): "etf-research.md",
    ("etf", "validation"): "etf-validation.md",
    ("etf", "fix"): "etf-research-fix-validation.md",
}


def load_prompt(security_type: str, stage: str) -> str:
    filename = PROMPT_NAMES[(security_type, stage)]
    return resources.files("cool_financial_research.prompts").joinpath(filename).read_text(encoding="utf-8")


def runtime_contract() -> str:
    return """

# Runtime Output Contract Added by cool-financial-research

You must return a single JSON object conforming to the provided JSON schema.
The `markdown_report` field must contain the full human-readable markdown output for this stage.
The `structured_data` field must contain machine-readable summaries of the same content.

Do not omit any required section from the original prompt. If reliable data is unavailable, write
"Data not available" or "unverified" rather than guessing. Preserve the requested FACTS vs.
INTERPRETATION distinction. Do not provide personalized financial advice; frame the output as
research only.
"""
