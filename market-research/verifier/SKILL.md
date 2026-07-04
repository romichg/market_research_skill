---
name: market-research-verifier
description: Validate market research evidence bundles for equities, ADRs, and ETFs in a fresh agent context; inspect cited artifacts and public sources; write validation markdown and JSON without editing the original report.
---

# Validate Market Research

Use this skill to validate a frozen `market-research` run directory. The validator may create validation files only; it must not edit the producer report, JSON, sources, or manifest.

Hard rule: validate the produced report, source registry, deterministic bundle, and cited artifacts. Do not create a competing investment thesis or browse for uncited thesis material. Targeted browsing is allowed only when a cited source is unreachable, ambiguous, or needs source-date confirmation.

## Required Reads

1. Run `market-research/shared/scripts/validate_market_research.py` first.
2. Read `references/verifier-workflow.md` for artifact handling, deterministic scaffold interpretation, issue classification, and output rules.
3. Read `references/investment-validation.md` before judgment validation.
4. Use `market-research/shared/schemas/deterministic-bundle.schema.json` and `market-research/shared/schemas/validation-output.schema.json` for schema contracts.

If JSON Schema tooling is unavailable, use this fallback: run the repository validation helper and perform manual required-field checks against the schemas. Record the limitation in validation JSON under `validation_limitations`.

## Fresh-Context Contract

Use only files under the provided run directory, sources cited in those files, and public sources explicitly inspected in this validation session. Do not rely on the producer conversation as evidence.

For deterministic bundles, inspect frozen evidence: `manifest.json`, `source_manifest.json`, `gaps.json`, `normalized/`, raw cached artifacts, and `research_input_pack.md`. Do not rerun successful provider collection.

## Quality Gates

Validate factual support, source dates, stale-data handling, ticker/name/source-entity alignment, unavailable public-data gaps, omitted risks, and unsupported valuation/performance/peer/portfolio-fit claims.

When reports cite news with "potential", "up to", "framework", or milestone language, verify that the report does not present it as booked revenue unless a filing or company source supports that treatment.

For deterministic bundles, verify normalized values have provider, source URL, raw path, and status provenance. Review `deterministic_data_usage` and `deterministic_data_usage_dispositions`; missing required dispositions are blocking deterministic-lint issues until the report uses the field or explains why it was not usable/material.

Investor usefulness matters: deterministic coverage is not sufficient if the report reads like a source inventory or compliance transcript. The report should have a thesis, prioritize material facts, explain variant view and risks, and avoid citation density that overwhelms the prose.

Investor-facing provenance hygiene matters. Routine data-vendor names, local tool paths, raw paths, source IDs, hashes, cache files, and provider mechanics do not belong in the main body. Main narrative should state the data, range, conflict, and investment implication; details belong in `Data Issues And Discrepancies`, `Sources And Evidence`, appendices, sidecars, or validation artifacts.

Field-level freshness matters. Price, volume, market cap, short interest, forward estimates, recent news, insider transactions, and catalysts should be fresh or clearly described as latest available. Durable filed evidence may use cached artifacts when source dates are preserved.

Business profile depth is a validation dimension. Check whether the report explains what the business does, technology explanation in plain language, who pays, how revenue develops, acquisition contribution, and when procedural research was needed.

Avoid data recital. `Bottom Line` must be an executive summary; `Key Facts` should be at-a-glance; technical analysis must interpret trend, volume, volatility, moving averages, support and resistance, and drawdown; `Valuation` must provide valuation analysis; risk section should not include data-quality risk.

## Output

Write `<SYMBOL>-validation.md` and `<SYMBOL>-validation.json`. If verifier skill issues are found, also write `<SYMBOL>-validator-skill-issues.md/json` matching `market-research/shared/schemas/skill-issue.schema.json`.

Classify every issue as `critical`, `moderate`, or `minor`. Mark unavailable public-data gaps as `unresolved_data_unavailable`, not `open`. Return validation artifact paths and the count of open critical/moderate issues.
