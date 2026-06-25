# Market Research Quality Bar

This repository optimizes for investor-useful research supported by reproducible evidence. The final report is the investor product; runtime artifacts are intermediate work.

## Investor Report Standard

The report should read like an investor memo, not a deterministic-data recital or validation transcript. Lead with thesis, materiality, variant view, valuation context, catalysts, risks, invalidation points, and monitoring triggers. For ETFs, adapt the same standard to fund objective, index methodology, holdings, exposures, fees, liquidity, tracking/performance context, distribution profile, portfolio role, risks, and monitoring triggers.

Deterministic evidence should support the report, not become the report. A report can satisfy field-usage requirements and still fail quality if it lacks synthesis and judgment.

## Evidence And Provenance

Every material quantitative claim needs citation support or an explicit unavailable/unverified caveat. Inline citations are useful for surprising, contentious, source-sensitive, or highly material claims. Excessive path-level citation density is the failure mode, not citation discipline.

Detailed local paths, hashes, provider mechanics, cache files, source IDs, and raw artifact details belong in JSON sidecars, source registries, evidence sections, appendices, or validation artifacts unless they change investor interpretation. Routine provider names are usually not investment content.

## Deterministic Data Usage

Treat `deterministic_data_usage.json` as the researcher-stage contract for usable deterministic data. Required and review datapoints must be used in the final report or explicitly dispositioned in the report JSON.

Rationales must be field-specific. Boilerplate such as "used for valuation context" can satisfy a schema while hiding whether the datapoint actually mattered. Weak boilerplate rationales are quality issues.

Validator referenced/not-referenced audits are useful review leads, but explicit field-level dispositions are the stronger enforcement path.

### Known ETF Collector Gap

ETF identity and holdings can be sparse or wrong in deterministic output when generic profile providers classify the ticker like an operating company or ETF endpoints are plan-gated. Until the collector normalizes ETF profile, holdings, distributions, performance, and source gaps more reliably, researcher runs must cross-check issuer/SEC evidence, correct the security type in the final report and JSON sidecar, and record the deterministic mismatch as a data-quality issue rather than letting it shape the investor narrative.

## Freshness

Freshness is field-specific, not cache-specific. Investors care whether price, volume, market cap, filings, ownership, estimates, short interest, and news are current enough for the decision; they usually do not care whether durable source-dated evidence came from cache.

Use fresh or latest-available data for time-sensitive fields. Durable filed evidence, historical statements, company identity, older risk-factor text, and dated press releases may use cached/source-dated artifacts when the source date is preserved.

Main-report disclosure should focus on missing, stale, or conflicting data that changes interpretation. Prefer field-level freshness guidance over cache-mechanics disclosure.

## Provider Limits And Discrepancies

Provider gaps must map to affected analysis areas. Examples: unavailable short interest affects crowding/squeeze analysis; unavailable forward estimates affects valuation; unavailable insider statistics affects dilution/governance analysis; unavailable filing sections affects direct risk-factor and MD&A validation.

Material discrepancies should be described in investor-readable terms: the data, the range or conflict, and why it matters. Provider names and mechanics belong near the end or in sidecars unless the provider identity changes confidence.

Framework agreements, "up to" values, milestones, potential contract value, backlog, and booked revenue must be framed according to what the cited source supports.

## Validation Quality

Validation should test source support, stale dates, unsupported claims, omitted risks, ticker/name/source-entity alignment, deterministic provenance, schema shape, and investor usefulness. Deterministic coverage alone is not enough.

Reports should keep company/security risks in `Risks And Invalidation Points`. Research limits, stale fields, data discrepancies, and source-quality issues belong in `Data Issues And Discrepancies`.

## Self-Improvement

Self-improvement is prompt-only and operator-triggered. Do not launch surprise subprocesses after a successful research loop.

Use completed batch roots to compare recurring missing-data, omitted-risk, report-quality, and validator-specificity patterns before changing the skill. Judge the finished investor experience before artifact ergonomics. `reports/` is for polished final deliverables, `runtime/` is for prompts/logs/intermediate notes, and `data/` is for deterministic evidence.
