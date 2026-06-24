---
name: market-research-verifier
description: Validate market research evidence bundles for equities, ADRs, and ETFs in a fresh Codex context; inspect cited artifacts and public sources; write validation markdown and JSON without editing the original report.
---

# Validate Market Research

Use this skill to validate a frozen `market-research` run directory. The validator never edits the producer report.

Hard rule: The verifier validates the produced report, source registry, deterministic bundle, and cited artifacts. It must not create a competing investment thesis or browse for uncited thesis material. Targeted browsing is allowed only when a cited source is unreachable, ambiguous, or needs source-date confirmation.

## Fresh-Context Contract

Use only:

- Files under the provided run directory.
- Sources cited in those files.
- Public sources explicitly inspected in this validation session.

Do not rely on the producer conversation as evidence. Treat the report as claims to test. If the run directory is a deterministic `deterministic_research_collector.py` output bundle, do not rerun successful provider collection; inspect `manifest.json`, `source_manifest.json`, `gaps.json`, `normalized/`, raw cached artifacts, and `research_input_pack.md`.

## Resources

- Run `../shared/scripts/validate_market_research.py` first for deterministic artifact discovery and structure checks.
- Read `references/investment-validation.md` before judgment validation.
- Use `../shared/schemas/deterministic-bundle.schema.json` for deterministic bundle checks.
- Use `../shared/schemas/validation-output.schema.json` for the validation JSON contract.

If a JSON Schema validator is unavailable, use this fallback: run the repository validation helper and perform manual required-field checks against the schema files. Record this limitation in validation JSON under `validation_limitations`; do not imply full Draft 2020-12 schema validation passed.

## Workflow

1. Inspect the run directory shape. The helper supports final report directories under `reports/SYMBOL/AS_OF/`, deterministic `data/SYMBOL/AS_OF/` bundles, and a `data/SYMBOL/` parent directory containing dated deterministic bundles. Deterministic bundles outside `data/SYMBOL/AS_OF/` are not valid inputs. When a deterministic data bundle is provided, write the scaffold under `reports/SYMBOL/AS_OF/`. It writes a scaffold named `<SYMBOL>-validation-scaffold.md/json`; it is lint input for validation, not the completed validation judgment:

```bash
python3 {baseDir}/../shared/scripts/validate_market_research.py data/SYMBOL/AS_OF --output-prefix reports/SYMBOL/AS_OF/SYMBOL-validation-scaffold
```

The scaffold includes `deterministic_data_usage`, a heuristic audit of normalized `status: ok` datapoints and whether the report text/JSON appears to reference each field, value, raw path, or source URL. It also includes `deterministic_data_usage_dispositions`, which compares the report JSON against `deterministic_data_usage.json` requirements. Missing required dispositions are blocking deterministic-lint issues until the report either uses the field or explains why it was not usable/material. Treat other `not_referenced` datapoints as review leads, not automatic failures: the verifier should decide whether the datapoint was material, stale, wrong-entity, duplicated by a better source, or genuinely omitted.

2. If the helper reports missing artifacts, stop and tell the user what the producer must regenerate.

3. Read the report markdown, report JSON, `research_context.json`, `sources.json`, and `run_manifest.json` if present.

4. Validate judgment:

- Verify material quantitative claims against cited sources.
- For deterministic bundles, verify normalized values have provider, source URL, raw path, and status provenance.
- Confirm deterministic bundle files align with `../shared/schemas/deterministic-bundle.schema.json`.
- Treat successful deterministic provider outputs as frozen evidence. Validate non-deterministic interpretation, generated prose, missing-data handling, stale-data caveats, and cited-source support.
- Review the scaffold `deterministic_data_usage` and `deterministic_data_usage_dispositions` sections. Confirm required/review deterministic datapoints were used or field-level dispositions are defensible before deciding the producer passed data-usage validation.
- For every required deterministic datapoint, the report JSON `deterministic_data_usage` entry must include a field-specific `rationale` that names the field or value and explains the investor relevance, duplication by better evidence, or reason for omission. Generic rationales such as "used for valuation context" are insufficient for required datapoints.
- Check source dates and stale-data handling.
- Check whether facts and interpretation are separated.
- Check investor usefulness. Deterministic coverage is not sufficient if the report reads like a source inventory or compliance transcript. The report should have a clear thesis, prioritize material facts, explain variant view and risks, and keep citations from overwhelming the prose. Treat excessive path-level citation density as a minor quality issue; treat missing thesis or purely mechanical deterministic recitation as moderate.
- Assess investor-facing provenance hygiene. Routine data-vendor names and local tool paths do not belong in the main investment narrative. The main body should state the data, range, conflict, and investment implication; vendor attribution and mechanics belong in `Data Issues And Discrepancies`, `Sources And Evidence`, appendices, sidecars, or validation artifacts. Flag main-body references to deterministic bundles, runtime directories, raw paths, source IDs, hashes, cache files, routine vendor names, or provider mechanics.
- Assess field-level freshness. Time-sensitive fields such as price, volume, market cap, short interest, forward estimates, recent news, insider transactions, and event-driven catalysts should be fresh or explicitly described as latest available. Durable filed evidence may use cached artifacts when source dates are preserved. Main report disclosure should focus on stale or unavailable material data, not cache mechanics.
- Check for unsupported valuation, performance, peer, or portfolio-fit claims.
- Check for omitted risks.
- Check ticker/name/source-entity alignment. News and secondary data providers can return similarly named but unrelated issuers for the same ticker text, ADR/local-listing collisions, predecessor entities, or pending IPO symbols. Treat any claim supported only by a mismatched issuer/source entity as unsupported.
- When `sources.json` includes `artifact_sha256` and `artifact_size_bytes`, treat them as frozen-artifact integrity metadata and verify that referenced local artifacts still exist.
- Check ETF fee, holdings, exposure, and index methodology support.
- Check equity/ADR filing, financial, valuation, and risk support.
- For equities and ADRs, check whether the report addresses or dispositions cybersecurity/data-integrity risk and litigation/legal-proceeding status from filed materials. Missing treatment is at least minor; make it moderate when the omitted risk is material to the thesis or when filings contain active proceedings that affect valuation or solvency.
- If filing-section extracts are absent for an equity, check whether the report discloses that limitation. Treat disclosed absence as a minor evidence-depth issue; treat undisclosed absence as moderate when the report discusses filing-specific risks, MD&A, litigation, liquidity, or going-concern claims.
- Confirm `gaps.json` marks unavailable free-source data clearly instead of letting missing fields become unsupported prose.
- Confirm material provider limits are mapped to affected analysis areas, not only listed. Examples include short-interest gaps affecting crowding/squeeze analysis, forward-estimate gaps affecting valuation, insider-statistics gaps affecting dilution/governance analysis, and filing-section gaps affecting direct risk-factor or MD&A validation.
- When reports cite news with "potential", "up to", "framework", or milestone language, verify that the report does not present it as booked revenue unless a filing or company source supports that treatment.

## Investor Analysis Quality Checks

Flag report-quality issues when a report merely produces a data recital instead of analyzing it. In particular:

- `Bottom Line` must be an executive summary and must introduce market value or valuation range before discussing whether valuation is justified.
- `Key Facts` should be a table or equivalent at-a-glance presentation, without internal paths or provider mechanics.
- Business profile depth is a validation dimension. A report that accurately cites filings but does not explain what the business does, technology explanation in plain language, who pays, how revenue is expected to develop, acquisition contribution, or when procedural research was needed should receive a report-quality issue even if deterministic coverage is complete.
- `Market Snapshot And Technical Analysis` must interpret the numbers. When price history exists, expect discussion of trend, volume, volatility, moving averages, support and resistance, and drawdown.
- `Financials And Balance Sheet` should organize numbers in a consumable way and explain scale, liquidity, cash burn, margin quality, and dilution.
- `Valuation` must provide valuation analysis of a selected value or range instead of narrating provider conflicts. Vendor attribution belongs in `Data Issues And Discrepancies`.
- Risk section should not include data-quality risk; `Risks And Invalidation Points` should focus on company/security risks, and data-quality risk belongs in `Data Issues And Discrepancies`.

5. Write `<SYMBOL>-validation.md` and `<SYMBOL>-validation.json`.

When validator skill issues are found, write `<SYMBOL>-validator-skill-issues.md` for human reading and `<SYMBOL>-validator-skill-issues.json` matching `../shared/schemas/skill-issue.schema.json` for aggregation.

If schema tooling is missing, include a validation JSON limitation such as: `"Python jsonschema was unavailable; manual required-field checks were performed."`

6. Classify every issue:

- `critical`: materially misleading, missing core source, wrong security type, fabricated/unsupported major quantitative claim.
- `moderate`: important unsupported claim, stale material data without caveat, missing major risk, weak thesis support.
- `minor`: clarity, formatting, secondary caveat, or non-blocking improvement.

7. Mark unavailable public-data gaps as `unresolved_data_unavailable`, not `open`.

8. Return validation artifact paths and the count of open critical/moderate issues.

## Output Rule

The validator may create validation files only. It must not modify the producer's research markdown, JSON, source files, or manifest.

Do not overwrite a completed judgment validation with the deterministic scaffold. If rerunning the helper, keep the default `-validation-scaffold` output or pass a separate `--output-prefix`.
