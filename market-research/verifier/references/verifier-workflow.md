# Verifier Workflow

## Scaffold First

The helper supports final report directories under `reports/SYMBOL/AS_OF/`, deterministic `data/SYMBOL/AS_OF/` bundles, and a `data/SYMBOL/` parent directory containing dated deterministic bundles. Deterministic bundles outside `data/SYMBOL/AS_OF/` are invalid inputs.

When a deterministic data bundle is provided, write the scaffold under `reports/SYMBOL/AS_OF/`. It is lint input, not the completed judgment validation:

```bash
python3 market-research/shared/scripts/validate_market_research.py data/SYMBOL/AS_OF --output-prefix reports/SYMBOL/AS_OF/SYMBOL-validation-scaffold
```

The scaffold includes `deterministic_data_usage`, a heuristic audit of normalized `status: ok` datapoints and whether report text/JSON appears to reference each field, value, raw path, or source URL. It also includes `deterministic_data_usage_dispositions`, comparing report JSON against `deterministic_data_usage.json` requirements.

Missing required dispositions are blocking deterministic-lint issues until the report either uses the field or explains why it was not usable/material. Other `not_referenced` datapoints are review leads, not automatic failures: decide whether each datapoint was material, stale, wrong-entity, duplicated by better evidence, or genuinely omitted.

Do not overwrite a completed judgment validation with the deterministic scaffold. If rerunning the helper, keep the default `-validation-scaffold` output or pass a separate `--output-prefix`.

## Evidence Review

1. If the helper reports missing artifacts, stop and tell the user what the producer must regenerate.
2. Read report markdown, report JSON, `research_context.json`, `sources.json`, and `run_manifest.json` if present.
3. Verify material quantitative claims against cited sources.
4. For deterministic bundles, verify normalized values have provider, source URL, raw path, and status provenance.
5. Confirm successful deterministic provider outputs are treated as frozen evidence. Validate interpretation, missing-data handling, stale-data caveats, and cited-source support.
6. For every required deterministic datapoint, report JSON `deterministic_data_usage` must include a field-specific `rationale` naming the field or value and explaining investor relevance, duplication by better evidence, or reason for omission. Generic rationales such as "used for valuation context" are insufficient.
7. Check whether facts and interpretation are separated.

## Investor Quality Review

Flag report-quality issues when a report merely produces a data recital instead of analyzing it.

- `Bottom Line` must be an executive summary and must introduce market value or valuation range before discussing whether valuation is justified.
- `Key Facts` should be a table or equivalent at-a-glance presentation without internal paths or provider mechanics.
- Business profile depth includes what the business does, technology explanation in plain language, who pays, how revenue is expected to develop, acquisition contribution, and whether procedural research was needed.
- `Market Snapshot And Technical Analysis` must interpret trend, volume, volatility, moving averages, support and resistance, and drawdown.
- `Financials And Balance Sheet` should explain scale, liquidity, cash burn, margin quality, and dilution.
- `Valuation` must analyze a selected value or range instead of narrating provider conflicts.
- Risk section should not include data-quality risk; data-quality risk belongs in `Data Issues And Discrepancies`.
- ETF reports should include `Portfolio Companies Snapshot` when holdings are available. If there are 25 or fewer holdings, the report should cover all holdings; otherwise it should cover the top 25 by weight. The section should give compact company, weight, sector/industry, business, outlook, and price/technical context when available, followed by synthesis.

Routine data-vendor names and local tool/provider mechanics should not appear in the main body unless stale, missing, or conflicting data changes investor interpretation.

Producer self-check artifacts under runtime are useful for understanding what the producer already linted, but they are not investor-facing report sections and do not replace verifier judgment.

## Common Evidence Traps

- Wrong issuer, ADR/local-listing collisions, predecessor entities, pending IPO symbols, or similarly named companies.
- News with "potential", "up to", "framework", or milestone language presented as booked revenue without filing or company-source support.
- Missing or stale short interest, forward estimates, insider statistics, filing sections, or event-driven catalysts without mapped analysis impact.
- Cybersecurity/data-integrity risk or litigation/legal-proceeding status omitted from filed-material review.
- Filing-section extracts absent without disclosure when the report discusses risk factors, MD&A, litigation, liquidity, or going-concern claims.

## Issue Classification

- `critical`: materially misleading, missing core source, wrong security type, fabricated/unsupported major quantitative claim.
- `moderate`: important unsupported claim, stale material data without caveat, missing major risk, weak thesis support.
- `minor`: clarity, formatting, secondary caveat, or non-blocking improvement.

Final pass requires no open critical/moderate issues. Return validation artifact paths and the count of open critical/moderate issues.
