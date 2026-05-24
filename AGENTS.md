# Repository Guidelines

## Project Structure & Module Organization

This repository contains one Python CLI project in `cool-financial-research/`. Source code lives under `cool-financial-research/src/cool_financial_research/`. The main CLI entry point is `cli.py`, orchestration logic is in `orchestrator.py`, typed contracts are in `schemas.py`, and provider integrations are under `providers/`. Agent implementations live in `agents/`, prompt templates in `prompts/`, and tests in `cool-financial-research/tests/`.

Generated research output is written at runtime to `cool-financial-research/cool-financial-research/` and should not be treated as source.

## Build, Test, and Development Commands

Run commands from `cool-financial-research/`.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[pdf,dev]'
```

Installs the package in editable mode with PDF and developer dependencies. If WeasyPrint system dependencies are unavailable, use `pip install -e '.[dev]'`.

```bash
pytest
ruff check .
mypy src
cool-financial-research classify AAPL
cool-financial-research run AAPL --no-pdf
```

`pytest` runs the test suite, `ruff` checks linting, `mypy` runs static type checks, and the CLI commands exercise classification and a local research run.

## Coding Style & Naming Conventions

Use Python 3.10+ and keep modules under the existing `src/` layout. Follow Ruff defaults with the configured `line-length = 100`. Use 4-space indentation, `snake_case` for functions and modules, `PascalCase` for classes and Pydantic models, and explicit type hints for public functions and shared data structures. Keep model and prompt names centralized in configuration or prompt files rather than scattering literals through the code.

## Testing Guidelines

Tests use `pytest` and should live in `tests/` with names like `test_loop_stop.py`. Name test functions by behavior, for example `test_stops_when_no_blocking_issues`. Add focused tests for orchestration stopping rules, schema changes, provider behavior, and CLI edge cases. Run `pytest`, `ruff check .`, and `mypy src` before submitting changes.

## Commit & Pull Request Guidelines

No git history is available in this checkout, so use concise imperative commit messages such as `Add EDGAR classifier fallback` or `Fix validation loop stop rule`. Pull requests should include a short summary, test results, configuration or environment changes, and sample CLI output when behavior changes. Link related issues and include screenshots or generated report snippets only when they clarify user-visible output.

## Security & Configuration Tips

Copy `.env.example` to `.env` for local settings and keep API keys out of commits. Verify live market data, SEC filings, and unresolved validation issues before relying on generated reports; this project produces research, not personalized financial advice.
