#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

test -f SKILL.md
test -f pyproject.toml

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

if [ ! -x .venv/bin/python ]; then
  echo "Missing .venv. Run: python -m venv .venv && source .venv/bin/activate && pip install -e '.[dev]'" >&2
  exit 1
fi

if ! .venv/bin/python -m cool_financial_research.openclaw_helper --help >/dev/null 2>&1; then
  echo "OpenClaw helper is not installed. Run: source .venv/bin/activate && pip install -e '.[dev]'" >&2
  exit 1
fi

if ! .venv/bin/python -m cool_financial_research.openclaw_helper prompt equity research >/dev/null 2>&1; then
  echo "OpenClaw helper prompt loading failed. Reinstall with: source .venv/bin/activate && pip install -e '.[dev]'" >&2
  exit 1
fi

echo "OpenClaw skill check passed."
