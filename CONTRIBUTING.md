# Contributing

This repo is an Agent Skills-format project. Preserve portability first: keep the installable skill as plain `SKILL.md` Markdown with YAML frontmatter, repo-relative references, and standard Python/Bash helpers.

## Development Rules

- Keep active work under `market-research/`, `tests/`, and root documentation.
- Do not extend `OLD/` unless restoring historical context.
- Do not commit credentials, `.env`, private research bundles, or generated `data/`, `reports/`, or `runtime/` outputs.
- Use `.env.example` as the active configuration template.
- Keep provider helpers deterministic: explicit inputs, explicit output paths, JSON/Markdown artifacts, useful exit codes.
- Keep PDF generation best-effort. Missing `pandoc` or `xelatex` must not fail a research run.

## Testing

Run the full suite:

```bash
python3 -m pytest tests
```

Focused checks:

```bash
python3 -m pytest tests/test_deterministic_research_collector.py
python3 -m pytest tests/test_research_loop.py
python3 -m pytest tests/test_md_to_pdf.py
python3 -m pytest tests/test_validate_market_research.py
```

Check helper CLIs:

```bash
python3 market-research/shared/scripts/deterministic_research_collector.py --help
python3 market-research/shared/scripts/procedural_source_helper.py --help
python3 market-research/shared/scripts/validate_market_research.py --help
python3 market-research/batch-supervisor/scripts/research_loop.py --help
bash market-research/shared/scripts/md-to-pdf.sh --help
```

## How To Update The Skill

1. Start with the user-facing behavior contract.
2. Add or update tests before changing implementation code.
3. Update helper scripts or schemas.
4. Update `SKILL.md` instructions and references so future agents use the new behavior.
5. Update `README.md` or this file when install, run, test, artifact, or dependency behavior changes.
6. Run focused tests, then the full suite.

When editing skill instructions, keep frontmatter descriptions short and trigger-focused. Do not put long workflow summaries in frontmatter. Put detailed behavior in the Markdown body or references.

## Debugging Checklist

- Reproduce with the narrowest command first.
- Inspect generated manifests before editing reports.
- For deterministic data issues, check `data/SYMBOL/AS_OF/source_manifest.json`, `manifest.json`, `gaps.json`, and raw provider payloads.
- For procedural source issues, check `runtime/SYMBOL/AS_OF/sources.json` and `source_bundle/`.
- For loop issues, check `research-loop-summary.json`, child prompt files, and `iteration-*/*.log`.
- For PDF issues, run `bash market-research/shared/scripts/md-to-pdf.sh REPORT.md` directly and inspect stderr.

## Artifact Contracts

Single-symbol research should produce:

```text
data/SYMBOL/YYYY-MM-DD/
reports/SYMBOL/YYYY-MM-DD/SYMBOL-research.md
reports/SYMBOL/YYYY-MM-DD/SYMBOL-research.json
reports/SYMBOL/YYYY-MM-DD/SYMBOL-research.pdf  # optional, best-effort
runtime/SYMBOL/YYYY-MM-DD/
```

Validation should produce:

```text
reports/SYMBOL/YYYY-MM-DD/SYMBOL-validation.md
reports/SYMBOL/YYYY-MM-DD/SYMBOL-validation.json
```

Loop runs should keep prompts, logs, and issue files under `runtime/` and polished artifacts under `reports/`.
