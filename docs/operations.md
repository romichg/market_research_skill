# Market Research Operations

Run commands from the repository root.

## Development Checks

```bash
python3 market-research/shared/scripts/deterministic_research_collector.py --help
python3 market-research/shared/scripts/procedural_source_helper.py --help
python3 market-research/shared/scripts/validate_market_research.py --help
python3 market-research/batch-supervisor/scripts/research_loop.py --help
bash market-research/shared/scripts/md-to-pdf.sh --help
python3 market-research/shared/scripts/preflight_environment.py
python3 -m pytest tests
```

For focused checks:

```bash
python3 -m pytest tests/test_repository_layout.py
python3 -m pytest tests/test_research_loop.py
```

## Single Research Run

Ask the agent to run:

```text
$market-research researcher AAPL
```

Expected final artifacts:

```text
data/AAPL/YYYY-MM-DD/
runtime/AAPL/YYYY-MM-DD/
reports/AAPL/YYYY-MM-DD/AAPL-research.md
reports/AAPL/YYYY-MM-DD/AAPL-research.json
reports/AAPL/YYYY-MM-DD/AAPL-research.pdf
```

PDF generation is best-effort. Missing `pandoc`, `xelatex`, or LaTeX packages should not fail the research job when Markdown and JSON artifacts are valid.

## Validation

Run validation in a fresh agent context:

```text
$market-research verifier reports/AAPL/YYYY-MM-DD
```

The verifier writes validation Markdown and JSON under the report directory and must not edit producer artifacts.

## Supervised Batch

Use the batch supervisor for fresh child researcher and verifier sessions:

```text
$market-research batch-supervisor AAPL MSFT --as-of YYYY-MM-DD --max-remediation-loops 3
```

For direct helper debugging:

```bash
python3 market-research/batch-supervisor/scripts/research_loop.py run-batch AAPL MSFT \
  --run-root runtime/market-research-batch-YYYYMMDD \
  --as-of YYYY-MM-DD \
  --max-remediation-loops 3
```

Summarize a completed or running batch:

```bash
python3 market-research/batch-supervisor/scripts/research_loop.py summarize runtime/market-research-batch-YYYYMMDD
```

The final pass gate is no open critical or moderate validation issues.

The batch harness runs a producer self-check before verifier launch for completed report bundles. To run the same check manually:

```bash
python3 market-research/shared/scripts/producer_self_check.py reports/SYMBOL/YYYY-MM-DD \
  --data-dir data/SYMBOL/YYYY-MM-DD \
  --runtime-dir runtime/SYMBOL/YYYY-MM-DD \
  --fix-safe
```

If manual post-loop remediation changes a final validation result, refresh the persisted summary:

```bash
python3 market-research/batch-supervisor/scripts/research_loop.py refresh-summary runtime/market-research-batch-YYYYMMDD
```

## Self-Improvement Prompt

Self-improvement is explicit and prompt-only:

```text
$market-research batch-supervisor self-improve runtime/market-research-batch-YYYYMMDD
```

Direct helper form:

```bash
python3 market-research/batch-supervisor/scripts/research_loop.py self-improve \
  runtime/market-research-batch-YYYYMMDD
```

Before writing the prompt, the helper refreshes `skill-improvement-feedback.md` and `.json` under each runtime batch root. That runtime package consolidates loop notes, operator notes, report-side skill issue files, and inline report comments such as `<@researcher: ...>`, so self-improvement review does not depend on scanning final report directories directly.

By default the prompt itself writes under the ignored local-only path `docs/superpowers/plans/self-improvement/TIMESTAMP/`. Review the generated prompt manually, run it in Codex when appropriate, then capture durable conclusions in active docs, maintainer notes, skill files, or tests before deleting completed generated outputs.

## Generated Artifacts

Do not commit generated `data/`, `reports/`, `runtime/`, private research bundles, credentials, or `.env`. Commit only durable skill instructions, helper code, tests, schemas, provider docs, maintainer notes, and active documentation.
