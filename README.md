# Market Research Skill

Portable Agent Skills-format workflows for researching, validating, and supervising US-listed equities, ADRs, and ETFs. The skill creates frozen evidence bundles, cited Markdown research reports, JSON sidecars, validation outputs, and best-effort PDFs when local PDF tooling is available.

This is research support, not personalized financial advice.

## What Is Included

- `market-research-full/`: the installable skill directory.
- `market-research-full/researcher/`: producer workflow for single-symbol research.
- `market-research-full/verifier/`: validation workflow for frozen research artifacts.
- `market-research-full/loop-runner/`: supervised batch orchestration.
- `market-research-full/shared/`: reusable scripts, schemas, and helper assets.
- `tests/`: pytest coverage for helper behavior and loop contracts.

The skill follows the Agent Skills convention: a directory containing `SKILL.md` with YAML frontmatter and Markdown instructions, plus optional `scripts/`, `references/`, and `schemas/` support files. See the Agent Skills spec at <https://agentskills.io/specification>.

## Requirements

- Python 3.11 or newer recommended.
- `pytest` for development tests.
- Optional provider API keys for richer deterministic data.
- Optional PDF tools:
  - `pandoc`
  - `xelatex`
  - Noto Sans or another compatible system font

PDF generation is best-effort. If `pandoc` or `xelatex` is missing, the skill reports that and keeps the Markdown/JSON report valid.

## Install

Install by copying or symlinking the `market-research-full/` directory into your agent's skills directory.

Codex example:

```bash
mkdir -p ~/.codex/skills
ln -s "$(pwd)/market-research-full" ~/.codex/skills/market-research-full
```

Claude Code example:

```bash
mkdir -p ~/.claude/skills
ln -s "$(pwd)/market-research-full" ~/.claude/skills/market-research-full
```

Other agents such as OpenClaw should work if they support the same `SKILL.md` directory contract. Use the agent's configured skills directory and point it at `market-research-full/`.

## Configure

Start from the active template:

```bash
cp .env.example .env
```

Add only the provider keys you want to use. Deterministic HTTP calls default to a browser-like user agent; set `HTTP_USER_AGENT` only if you want a custom override. `SEC_USER_AGENT` is still tolerated as a legacy override, but new installs should use `HTTP_USER_AGENT`.

Generated `data/`, `reports/`, `runtime/`, `.env`, and private research bundles should stay out of commits.

## Run A Single Research Job

Ask your agent to use the skill:

```text
$market-research-full researcher AAPL
```

The researcher writes canonical artifacts under:

```text
data/AAPL/YYYY-MM-DD/
reports/AAPL/YYYY-MM-DD/
runtime/AAPL/YYYY-MM-DD/
```

Expected final report artifacts:

```text
reports/AAPL/YYYY-MM-DD/AAPL-research.md
reports/AAPL/YYYY-MM-DD/AAPL-research.json
reports/AAPL/YYYY-MM-DD/AAPL-research.pdf  # if PDF tooling is available
```

## Validate A Report

Run validation in a fresh agent context:

```text
$market-research-full verifier reports/AAPL/YYYY-MM-DD
```

The verifier checks citations, source coverage, stale dates, unsupported claims, JSON schema shape, and blocking issues.

## Run A Supervised Batch

From the repository root:

```bash
python3 market-research-full/loop-runner/scripts/research_loop.py run-batch AAPL MSFT \
  --run-root runtime/market-research-loop-YYYYMMDD \
  --as-of YYYY-MM-DD \
  --max-remediation-loops 3
```

Summarize an existing loop run:

```bash
python3 market-research-full/loop-runner/scripts/research_loop.py summarize runtime/market-research-loop-YYYYMMDD
```

## Useful Helper Commands

```bash
python3 market-research-full/shared/scripts/deterministic_research_collector.py doctor
python3 market-research-full/shared/scripts/deterministic_research_collector.py fetch AAPL --as-of YYYY-MM-DD --data-dir ./data --reports-dir ./reports
python3 market-research-full/shared/scripts/validate_market_research.py --help
bash market-research-full/shared/scripts/md-to-pdf.sh reports/AAPL/YYYY-MM-DD/AAPL-research.md
```

## Troubleshooting

- Missing provider data: run `doctor`, check `.env`, then use cached/offline rebuilds where possible.
- PDF missing: install `pandoc` and a TeX distribution containing `xelatex`; rerun `md-to-pdf.sh`.
- Validation failures: inspect the validation Markdown/JSON first, then fix only cited blocking issues.
- Rate limits or provider errors: use provider filters, endpoint filters, and call budgets before refreshing live data.
