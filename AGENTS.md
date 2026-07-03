# Repository Guidelines

## Project Structure & Module Organization

This repository contains portable Agent Skills-format market research workflows. The active skill tree is consolidated under `market-research/`:

- `market-research/researcher/`: producer skill and research references.
- `market-research/verifier/`: validation skill and validation references.
- `market-research/batch-supervisor/`: supervised batch supervisor skill and orchestration helper.
- `market-research/shared/`: shared scripts, schemas, and agent config.
- `tests/`: pytest coverage for helper scripts and loop behavior.
- `docs/README.md`: active documentation index.
- `docs/architecture.md`: skill boundaries, artifact roots, and evidence roles.
- `docs/quality-bar.md`: durable report-quality, evidence, validation, freshness, and self-improvement standards.
- `docs/operations.md`: repeatable development and operator workflows.
- `docs/maintainer-notes/`: curated handoff notes and durable lessons for future maintainers and agent workers.

Do not keep generated planning artifacts active after their durable conclusions are represented in canonical docs, maintainer notes, or tests.

Skill instructions live in each `SKILL.md`. Reference documents belong under `references/`, schemas under `schemas/`, and executable helpers under `scripts/`. Keep the skill usable by Codex, Claude, OpenClaw, and similar agents by preserving plain Markdown instructions, YAML frontmatter, and repo-relative helper paths.

## Build, Test, and Development Commands

There is no package build step. Run helpers directly with Python:

```bash
python3 market-research/shared/scripts/deterministic_research_collector.py --help
python3 market-research/shared/scripts/procedural_source_helper.py --help
python3 market-research/shared/scripts/validate_market_research.py --help
python3 market-research/batch-supervisor/scripts/research_loop.py --help
bash market-research/shared/scripts/md-to-pdf.sh --help
```

Run the test suite from the repository root:

```bash
python3 -m pytest tests
```

For a focused check, run one file:

```bash
python3 -m pytest tests/test_research_loop.py
```

## Coding Style & Naming Conventions

Use Python 3, four-space indentation, clear function names, and standard-library modules where practical. Keep helper scripts CLI-oriented and deterministic: read inputs from paths or arguments, write JSON/Markdown artifacts explicitly, and return useful exit codes. Prefer `snake_case` for Python names, lowercase hyphenated directory names for skills, and uppercase ticker examples such as `AAPL` or `VTI`.

## Testing Guidelines

Tests use `pytest` and subprocess calls against the real helper scripts. Add tests in `tests/test_<area>.py` with names beginning `test_`. Use `tmp_path` for generated artifacts so tests do not depend on local run directories. Cover both success paths and failure behavior, especially overwrite protection, validation gates, malformed artifacts, and JSON output contracts.

## Commit & Pull Request Guidelines

Recent commits use short, imperative summaries such as `add supervised market research loop skill` or `Refresh market research skill metadata`. Keep commits focused on one logical change. Pull requests should describe the affected skill, list verification commands run, and call out any schema, prompt, or artifact contract changes. Include example command output or sample paths when behavior changes.

## Security & Configuration Tips

Do not commit credentials, private research bundles, or generated run outputs. Use `.env.example` as the active configuration template. When recording external sources, preserve source dates, URLs, checksums, and local artifact paths so later validation can reproduce the evidence trail.
