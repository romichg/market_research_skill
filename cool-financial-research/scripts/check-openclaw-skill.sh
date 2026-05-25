#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

test -f SKILL.md
test -f pyproject.toml

if ! grep -q '^name: cool-financial-research$' SKILL.md; then
  echo "SKILL.md is missing the expected OpenClaw skill name" >&2
  exit 1
fi

if grep -q 'OPENAI_API_KEY.*Required' SKILL.md README.md; then
  echo "OpenClaw path must not require OPENAI_API_KEY" >&2
  exit 1
fi

if [ ! -x .venv/bin/python ]; then
  echo "Missing .venv. Run: python -m venv .venv && source .venv/bin/activate && pip install -e '.[dev]'" >&2
  exit 1
fi

.venv/bin/python -m cool_financial_research.openclaw_helper --help >/dev/null
.venv/bin/python -m cool_financial_research.openclaw_helper prompt equity research >/dev/null

echo "OpenClaw skill check passed."
