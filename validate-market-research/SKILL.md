---
name: validate-market-research
description: Validate frozen market research bundles for equities, ADRs, and ETFs in a fresh Codex context; inspect cited artifacts and public sources; write validation markdown and JSON without editing the original report. Use when Codex is asked to validate, review, audit, or check an investment research report or a market-research run directory.
---

# Validate Market Research

Use this skill to validate a frozen `market-research` run directory. The validator never edits the producer report.

## Fresh-Context Contract

Use only:

- Files under the provided run directory.
- Sources cited in those files.
- Public sources explicitly inspected in this validation session.

Do not rely on the producer conversation as evidence. Treat the report as claims to test. If the run directory is a deterministic `deterministic_research_collector.py` output bundle, do not rerun successful provider collection; inspect `manifest.json`, `source_manifest.json`, `gaps.json`, `normalized/`, raw cached artifacts, and `research_input_pack.md`.

## Resources

- Run `scripts/validate_market_research.py` first for deterministic artifact discovery and structure checks.
- Read `references/investment-validation.md` before judgment validation.
- Use the validation JSON shape from the producer skill's `schemas/validation-output.schema.json` when available.

## Workflow

1. Inspect the run directory shape. The helper supports legacy `SYMBOL-research.md/json` runs, deterministic `reports/SYMBOL/AS_OF/` bundles, and a symbol parent directory containing dated deterministic bundles. When a parent directory is provided, it selects the latest dated deterministic bundle and writes the scaffold there. It writes a scaffold named `<SYMBOL>-validation-scaffold.md/json`; it is lint input for validation, not the completed validation judgment:

```bash
python3 {baseDir}/scripts/validate_market_research.py /path/to/market-research-runs/SYMBOL
```

2. If the helper reports missing artifacts, stop and tell the user what the producer must regenerate.

3. Read the report markdown, report JSON, `research_context.json`, `sources.json`, and `run_manifest.json` if present.

4. Validate judgment:

- Verify material quantitative claims against cited sources.
- For deterministic bundles, verify normalized values have provider, source URL, raw path, and status provenance.
- Confirm deterministic bundle files align with `market-research/schemas/deterministic-bundle.schema.json`.
- Treat successful deterministic provider outputs as frozen evidence. Validate non-deterministic interpretation, generated prose, missing-data handling, stale-data caveats, and cited-source support.
- Check source dates and stale-data handling.
- Check whether facts and interpretation are separated.
- Check for unsupported valuation, performance, peer, or portfolio-fit claims.
- Check for omitted risks.
- When `sources.json` includes `artifact_sha256` and `artifact_size_bytes`, treat them as frozen-artifact integrity metadata and verify that referenced local artifacts still exist.
- Check ETF fee, holdings, exposure, and index methodology support.
- Check equity/ADR filing, financial, valuation, and risk support.
- Confirm `gaps.json` marks unavailable free-source data clearly instead of letting missing fields become unsupported prose.

5. Write `<SYMBOL>-validation.md` and `<SYMBOL>-validation.json`.

6. Classify every issue:

- `critical`: materially misleading, missing core source, wrong security type, fabricated/unsupported major quantitative claim.
- `moderate`: important unsupported claim, stale material data without caveat, missing major risk, weak thesis support.
- `minor`: clarity, formatting, secondary caveat, or non-blocking improvement.

7. Mark unavailable public-data gaps as `unresolved_data_unavailable`, not `open`.

8. Return validation artifact paths and the count of open critical/moderate issues.

## Output Rule

The validator may create validation files only. It must not modify the producer's research markdown, JSON, source files, or manifest.

Do not overwrite a completed judgment validation with the deterministic scaffold. If rerunning the helper, keep the default `-validation-scaffold` output or pass a separate `--output-prefix`.
