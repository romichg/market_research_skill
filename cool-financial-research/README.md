# cool-financial-research

Local OpenClaw skill for US-listed stock, ADR, and ETF research with a research → validation → revision feedback loop.

OpenClaw provides the model connection and reasoning. The Python package provides deterministic helpers for ticker classification, prompt loading, schema validation, artifact writing, and manifest generation.

## Local OpenClaw Setup

```bash
cd cool-financial-research
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
scripts/check-openclaw-skill.sh
```

Expose this folder to OpenClaw as a local skill by copying or symlinking it into the active OpenClaw workspace `skills/` directory, or by adding its parent directory to OpenClaw's configured extra skill directories.

This OpenClaw skill path does not require `OPENAI_API_KEY`; it uses the model connection already configured in OpenClaw.

## Workflow

The skill workflow supports these stages:

1. Classify the input symbol as `equity`, `adr`, or `etf` using EDGAR by default.
2. Run the correct initial research agent.
3. Save `<SYMBOL>-first_run.md` and `<SYMBOL>-first_run.json`.
4. Run a forensic validation agent using the first agent's output as input.
5. Save `<SYMBOL>-validation1.md` and `<SYMBOL>-validation1.json`.
6. If the validation contains open Critical or Moderate issues, run a fix/revision agent.
7. Save `<SYMBOL>-validation-fix1.md` and `<SYMBOL>-validation-fix1.json`.
8. Repeat validation/fix until no open Critical or Moderate issues remain, remaining issues are explicitly unresolved because data is unavailable, or the max iteration cap is reached.
9. Save final markdown, JSON, manifest, and PDF if the optional PDF stack is installed.

## OpenClaw Helpers

The packaged helpers are intended for deterministic local work around OpenClaw's model calls:

```bash
python -m cool_financial_research.openclaw_helper --help
python -m cool_financial_research.openclaw_helper prompt equity research
```

Use `scripts/check-openclaw-skill.sh` after setup to verify the expected skill metadata, local package install, and prompt loading path.

## Legacy Direct CLI Mode

The direct CLI mode is retained for running the original local multi-agent workflow outside OpenClaw. It uses the package's own provider configuration and environment variables.

```bash
cd cool-financial-research
python -m venv .venv
source .venv/bin/activate
pip install -e '.[pdf,dev]'
cp .env.example .env
# edit .env and set provider credentials such as OPENAI_API_KEY
```

If WeasyPrint system dependencies are not available, omit `[pdf]` and run with `--no-pdf`.

### Legacy Usage

```bash
cool-financial-research run AAPL
cool-financial-research run SPY --type auto
cool-financial-research run BABA --security-type adr
cool-financial-research run AAPL --max-iterations 5 --pdf
cool-financial-research classify AAPL
```

Outputs are written to:

```text
./cool-financial-research/
  AAPL/
    AAPL-first_run.md
    AAPL-first_run.json
    AAPL-validation1.md
    AAPL-validation1.json
    AAPL-validation-fix1.md
    AAPL-validation-fix1.json
    ...
    AAPL-final.md
    AAPL-final.json
    AAPL-final.pdf
    run_manifest.json
```

## Defaults

Model IDs are configurable through environment variables. The default model map is:

```text
CFR_ORCHESTRATOR_MODEL=gpt-5.5
CFR_RESEARCH_MODEL=gpt-5.5-pro
CFR_VALIDATION_MODEL=gpt-5.5-pro
CFR_FIX_MODEL=gpt-5.5-pro
CFR_JSON_REPAIR_MODEL=gpt-5.5
```

The code intentionally keeps these model names in config rather than scattering them through the codebase.

## Classification

The default classifier uses:

- SEC ticker/exchange mapping
- SEC submissions metadata
- filing-form heuristics:
  - ETF/fund forms: `N-1A`, `485BPOS`, `N-CSR`, `NPORT-P`, `N-CEN`, `497`, `497K`
  - ADR/foreign issuer forms: `F-6`, `20-F`, `6-K`
  - operating company forms: `10-K`, `10-Q`, `8-K`, `DEF 14A`

If classification cannot be performed, the workflow fails rather than guessing.

A paid-provider classifier extension point is included in `providers/paid.py`.

## Validation loop stopping rules

The loop stops when one of the following is true:

- no Critical or Moderate issues remain;
- all remaining Critical or Moderate issues are explicitly marked `unresolved_data_unavailable`;
- the configured maximum iteration count is reached, default `5`.

## Strict JSON

Every agent is asked to return a strict JSON envelope containing:

- `markdown_report`: full markdown for human consumption;
- `structured_data`: machine-readable sections, facts, interpretations, claims, sources, issues, and open questions.

The markdown remains the canonical human report. The JSON is optimized for downstream automation, search, audits, and regression tests.

## Prompt files

The original prompts are included under:

```text
src/cool_financial_research/prompts/
  equity-research.md
  equity-validation.md
  equity-research-fix-validation.md
  etf-research.md
  etf-validation.md
  etf-research-fix-validation.md
```

A runtime output contract is appended in code so the source prompts remain intact.

## PDF and charts

Final PDF generation renders the final markdown. Chart generation is intentionally conservative: the default hook creates charts only when chart-ready reliable data has been added by a data adapter. This avoids fabricating or visually implying unsupported data.

## Development

```bash
pytest
ruff check .
mypy src
```

## Notes

This tool produces research, not personalized financial advice. Users should independently verify live prices, NAV/premium-discount, SEC filings, issuer data, and any stale or unresolved inputs before acting.
