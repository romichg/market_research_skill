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

By default this writes under `docs/superpowers/plans/self-improvement/TIMESTAMP/`. Review the generated prompt manually, run it in Codex when appropriate, and later archive completed/generated outputs under local ignored `OLD/docs-archive/` after durable conclusions are captured in active docs or skill files.

## Generated Artifacts

Do not commit generated `data/`, `reports/`, `runtime/`, local `OLD/` archives, private research bundles, credentials, or `.env`. Commit only durable skill instructions, helper code, tests, schemas, provider docs, and active documentation.
