# Market Research Skill

Portable Agent Skills-format workflows for researching, validating, and supervising US-listed equities, ADRs, and ETFs. The skill creates saved source-evidence bundles, cited Markdown research reports, JSON sidecars, validation outputs, and best-effort PDFs when local PDF tooling is available.

This is research support, not personalized financial advice.

## What Is Included

- `market-research/`: the installable skill directory.
- `market-research/researcher/`: producer workflow for single-symbol research.
- `market-research/verifier/`: validation workflow for saved research artifacts.
- `market-research/batch-supervisor/`: batch-supervisor orchestration helper.
- `market-research/shared/`: reusable scripts, schemas, and helper assets.
- `tests/`: pytest coverage for helper behavior and loop contracts.

The skill follows the Agent Skills convention: a directory containing `SKILL.md` with YAML frontmatter and Markdown instructions, plus optional `scripts/`, `references/`, and `schemas/` support files. See the Agent Skills spec at <https://agentskills.io/specification>.

## Documentation

Active project documentation lives under `docs/`:

- `docs/architecture.md` explains skill boundaries, artifact roots, and evidence roles.
- `docs/quality-bar.md` captures the report-quality, evidence, freshness, validation, and self-improvement standards.
- `docs/operations.md` collects development commands and operator workflows.
- `docs/maintainer-notes/` preserves curated handoff notes and lessons for future maintainers and agent workers.

## Requirements

- Python 3.11 or newer recommended.
- `pytest` for development tests.
- Optional provider API keys for richer deterministic data.
- Optional PDF tools:
  - `pandoc`
  - `xelatex`
  - Noto Sans or another compatible system font
- Optional headed-browser tools for protected-source access:
  - Chromium
  - Playwright for Python

PDF generation is best-effort. If `pandoc` or `xelatex` is missing, the skill reports that and keeps the Markdown/JSON report valid.

Optional environment preflight:

```bash
python3 market-research/shared/scripts/preflight_environment.py
```

This reports optional `jsonschema`, `pandoc`, `xelatex`, and LaTeX package availability such as `lmodern`. Missing PDF tooling is non-fatal.

To install missing Python prerequisites into a local venv instead of the system Python:

```bash
python3 market-research/shared/scripts/preflight_environment.py --ensure-python-prereqs
.venv-market-research/bin/python market-research/shared/scripts/preflight_environment.py
```

The helper uses `.venv-market-research/` by default and reports the venv Python path. If network or `pip` is unavailable, it reports the install failure and leaves the normal fallback validation path available.

### Optional PDF Tooling

Debian/Ubuntu:

```bash
sudo apt update
sudo apt install -y pandoc texlive-xetex fonts-noto
```

Fedora:

```bash
sudo dnf install -y pandoc texlive-xetex google-noto-sans-fonts
```

macOS with Homebrew:

```bash
brew install pandoc
brew install --cask mactex-no-gui
```

### Optional Headed Browser Tooling

Use this when protected-source handling needs a browser session for CAPTCHA, JavaScript challenges, or manual source capture.

```bash
python3 -m pip install playwright
python3 -m playwright install chromium
```

If the system already has Chromium installed, Playwright can still be useful for reproducible headed capture and screenshots.

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

## Configure

Start from the active template:

```bash
cp .env.example .env
```

Add only the provider keys you want to use. SEC fair-access systems may block unclassified automated tools, so keep `SEC_USER_AGENT` descriptive and include a project name plus contact email:

```dotenv
SEC_USER_AGENT=market-research-skill/1.0 your-email@example.com
HTTP_USER_AGENT=
```

Avoid browser-like values such as `Mozilla/5.0 ... Chrome/...` for SEC API calls. If `SEC_USER_AGENT` is empty or browser-like, SEC calls use the built-in descriptive `DEFAULT_SEC_USER_AGENT`. `HTTP_USER_AGENT` is separate: it is used for generic HTTP provider calls such as MarketAux and defaults to a browser-like value when unset.

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
python3 market-research/batch-supervisor/scripts/research_loop.py run-batch AAPL MSFT \
  --run-root runtime/market-research-batch-YYYYMMDD \
  --as-of YYYY-MM-DD \
  --max-remediation-loops 3
```

Direct `run-batch` uses local `codex exec` only when the `codex` CLI is available. If the supervising environment is OpenClaw, Claude Code, or another agent runtime without a local `codex` binary, use that agent's native fresh-child/subagent mechanism with the generated producer, verifier, and remediation prompts, or pass explicit command templates.

Artifact roots default to `data/`, `reports/`, and `runtime/`. CLI arguments are authoritative; supported environment fallbacks are `RESEARCH_DATA_DIR`, `RESEARCH_REPORTS_DIR`, `RESEARCH_RUNTIME_DIR`, and `RESEARCH_CACHE_DIR`. `RESEARCH_CACHE_DIR` controls deterministic raw/cache reuse; batch artifact roots should still be passed explicitly when reproducibility matters.

Summarize an existing loop run:

```bash
python3 market-research/batch-supervisor/scripts/research_loop.py summarize runtime/market-research-batch-YYYYMMDD
```

Create a prompt-only self-improvement review over one or more completed batch roots:

```text
$market-research batch-supervisor self-improve runtime/market-research-batch-20260620 runtime/market-research-batch-20260621
```

The batch-supervisor self-improve mode writes a central prompt under `docs/superpowers/plans/self-improvement/TIMESTAMP/` by default so durable improvement prompts, ideas, plans, and JSON survive `runtime/` cleanup. Run that prompt inside your agent session when you want to consolidate lessons and plan skill improvements.

The underlying helper can also be run directly from the repository root for debugging or custom output roots:

```bash
python3 market-research/batch-supervisor/scripts/research_loop.py self-improve \
  runtime/market-research-batch-20260620 \
  runtime/market-research-batch-20260621
```

## Useful Helper Commands

```bash
python3 market-research/shared/scripts/deterministic_research_collector.py doctor
python3 market-research/shared/scripts/deterministic_research_collector.py fetch AAPL --as-of YYYY-MM-DD --data-dir ./data --reports-dir ./reports
python3 market-research/shared/scripts/validate_market_research.py --help
bash market-research/shared/scripts/md-to-pdf.sh reports/AAPL/YYYY-MM-DD/AAPL-research.md
```

For the full command list, preflight workflow, and batch/self-improvement operations, see `docs/operations.md`.

Deterministic bundles include `deterministic_data_usage.json`. Research reports should use or explicitly disposition required/review datapoints in the report JSON `deterministic_data_usage` array.

## Troubleshooting

- Missing provider data: run `doctor`, check `.env`, then use cached/offline rebuilds where possible.
- PDF missing: install `pandoc` and a TeX distribution containing `xelatex`; rerun `md-to-pdf.sh`.
- Validation failures: inspect the validation Markdown/JSON first, then fix only cited blocking issues.
- Rate limits or provider errors: use provider filters, endpoint filters, and call budgets before refreshing live data. For SEC `HTTP 403`, check whether the saved raw artifact body says `Request Rate Threshold Exceeded`; if the selected SEC user-agent is browser-like or lacks contact information, fix `SEC_USER_AGENT` before retrying.
- Protected source access: if a material source is blocked by bot protection, CAPTCHA, WAF, or a JavaScript challenge, use headed-browser human assistance instead of accepting a stale or lower-quality substitute.
