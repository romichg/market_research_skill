# Market Research Skill

Portable Agent Skills-format workflows for researching, validating, and supervising US-listed equities, ADRs, and ETFs. The skill creates saved source-evidence bundles, cited Markdown research reports, JSON sidecars, validation outputs, and best-effort PDFs when local PDF tooling is available.

This is research support, not personalized financial advice.

## What Is Included

- `market-research/`: the installable skill directory.
- `market-research/researcher/`: producer workflow for single-symbol research.
- `market-research/verifier/`: validation workflow for saved research artifacts.
- `market-research/loop-runner/`: batch-supervisor orchestration helper.
- `market-research/shared/`: reusable scripts, schemas, and helper assets.
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

Install by copying or symlinking the `market-research/` directory into your agent's skills directory.

Codex example:

```bash
mkdir -p ~/.codex/skills
ln -s "$(pwd)/market-research" ~/.codex/skills/market-research
```

Claude Code example:

```bash
mkdir -p ~/.claude/skills
ln -s "$(pwd)/market-research" ~/.claude/skills/market-research
```

Other agents such as OpenClaw should work if they support the same `SKILL.md` directory contract. Use the agent's configured skills directory and point it at `market-research/`.

## Migration From `market-research-full`

The previous active skill directory and invocation name was `market-research-full`. Use `market-research` instead. If you installed the old skill through a symlink, remove the old symlink and create a new one pointing to `market-research/`.

## Configure

Start from the active template:

```bash
cp .env.example .env
```

Add only the provider keys you want to use. Deterministic HTTP calls default to a browser-like user agent; set `HTTP_USER_AGENT` only if you want a custom override. `SEC_USER_AGENT` is still tolerated as a legacy override, but new installs should use `HTTP_USER_AGENT`.

Generated `data/`, `reports/`, `runtime/`, `.env`, and private research bundles should stay out of commits.

## Run A Single Research Job

Ask your agent to use the primary skill in researcher mode:

```text
$market-research researcher AAPL
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
$market-research verifier reports/AAPL/YYYY-MM-DD
```

The verifier checks citations, source coverage, stale dates, unsupported claims, JSON schema shape, and blocking issues.

## Run A Supervised Batch

Ask your agent to use batch-supervisor mode:

```text
$market-research batch-supervisor AAPL MSFT --as-of YYYY-MM-DD --max-remediation-loops 3
```

The batch supervisor launches fresh researcher and verifier child contexts, applies the no-open-critical/moderate validation gate, retries remediation within the configured loop budget, and writes summaries plus issue files.

The underlying helper can also be run directly from the repository root for debugging, dry runs, or custom command templates:

```bash
python3 market-research/loop-runner/scripts/research_loop.py run-batch AAPL MSFT \
  --run-root runtime/market-research-loop-YYYYMMDD \
  --as-of YYYY-MM-DD \
  --max-remediation-loops 3
```

Summarize an existing loop run:

```bash
python3 market-research/loop-runner/scripts/research_loop.py summarize runtime/market-research-loop-YYYYMMDD
```

## Useful Helper Commands

```bash
python3 market-research/shared/scripts/deterministic_research_collector.py doctor
python3 market-research/shared/scripts/deterministic_research_collector.py fetch AAPL --as-of YYYY-MM-DD --data-dir ./data --reports-dir ./reports
python3 market-research/shared/scripts/validate_market_research.py --help
bash market-research/shared/scripts/md-to-pdf.sh reports/AAPL/YYYY-MM-DD/AAPL-research.md
```

## Troubleshooting

- Missing provider data: run `doctor`, check `.env`, then use cached/offline rebuilds where possible.
- PDF missing: install `pandoc` and a TeX distribution containing `xelatex`; rerun `md-to-pdf.sh`.
- Validation failures: inspect the validation Markdown/JSON first, then fix only cited blocking issues.
- Rate limits or provider errors: use provider filters, endpoint filters, and call budgets before refreshing live data.
- Protected source access: if a material source is blocked by bot protection, CAPTCHA, WAF, or a JavaScript challenge, use headed-browser human assistance instead of accepting a stale or lower-quality substitute.
