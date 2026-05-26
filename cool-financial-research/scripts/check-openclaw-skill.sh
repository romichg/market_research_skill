#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

test -f SKILL.md
test -f pyproject.toml

if grep -q 'cool-financial-research-dev' pyproject.toml README.md SKILL.md; then
  echo "OpenClaw-only package must not expose cool-financial-research-dev" >&2
  exit 1
fi

if [ -f src/cool_financial_research/cli.py ]; then
  echo "OpenClaw-only package must not include src/cool_financial_research/cli.py" >&2
  exit 1
fi

if ! grep -q '^name: cool-financial-research$' SKILL.md; then
  echo "SKILL.md is missing the expected OpenClaw skill name" >&2
  exit 1
fi

if awk '
  tolower($0) ~ /openai_api_key/ && tolower($0) ~ /requir/ &&
    tolower($0) !~ /(do|does|must) not requir/ { found=1 }
  END { exit found ? 0 : 1 }
' SKILL.md; then
  echo "OpenClaw path must not require OPENAI_API_KEY" >&2
  exit 1
fi

PYTHON_BIN="${PYTHON:-python3}"
if [ -z "${PYTHON:-}" ] &&
  [ -x .venv/bin/python ] &&
  .venv/bin/python -m cool_financial_research.openclaw_helper --help >/dev/null 2>&1; then
  PYTHON_BIN=".venv/bin/python"
fi

if ! "$PYTHON_BIN" -m cool_financial_research.openclaw_helper --help >/dev/null 2>&1; then
  echo "OpenClaw helper is not installed. Run: python3 -m pip install -e '.[dev]'" >&2
  exit 1
fi

if ! "$PYTHON_BIN" -m cool_financial_research.openclaw_helper prompts equity >/dev/null 2>&1; then
  echo "OpenClaw helper prompt loading failed. Reinstall with: python3 -m pip install -e '.[dev]'" >&2
  exit 1
fi

echo "OpenClaw skill check passed."
