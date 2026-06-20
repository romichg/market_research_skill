# Market Research Full Rework Plan

## Summary

- Consolidate the repo into one canonical skill: `market-research-full/`, with `researcher/`, `verifier/`, `loop-runner/`, and `shared/` subdirectories.
- Expand deterministic collection by auditing all six external providers: Tiingo, EODHD, Alpha Vantage, Twelve Data, MarketAux, and FMP. Keep SEC as a primary public-source provider.
- Make final reports substantially richer: deterministic facts first, then procedural source review, technical analysis, valuation/performance context, risks, catalysts, and investment-decision framing.
- Make verifier validate the produced report and calculations only; it must not run parallel research except targeted source checks needed to validate cited claims.
- Save this plan during implementation as `docs/plans/20260619_rework_plan.md` so a fresh context can pick it up.

## Key Changes

### Repository Layout

- Move canonical skill content to:
  - `market-research-full/SKILL.md`
  - `market-research-full/researcher/`
  - `market-research-full/verifier/`
  - `market-research-full/loop-runner/`
  - `market-research-full/shared/{schemas,references,provider-docs,scripts}`
- Update tests and docs to use only `market-research-full`.
- Remove or archive old canonical skill dirs: `market-research/`, `validate-market-research/`, `market-research-loop/`.
- Standardize outputs:
  - `data/<SYMBOL>/<YYYY-MM-DD>/...` for deterministic raw/normalized bundles and provider cache.
  - `reports/<SYMBOL>/<YYYY-MM-DD>/...` for final markdown/json reports and validation outputs.
  - `runtime/<SYMBOL>/<YYYY-MM-DD>/...` for loop prompts, logs, temp source bundles, scaffolds, remediation notes, and transient artifacts.
- Update env defaults to `RESEARCH_DATA_DIR=./data`, `RESEARCH_REPORTS_DIR=./reports`, `RESEARCH_RUNTIME_DIR=./runtime`.

### Deterministic Provider Expansion

- Read and summarize official docs for all six external providers, storing concise endpoint maps under `market-research-full/shared/provider-docs/`.
- Expand the deterministic collector to fetch all unique free/configured data before procedural research:
  - Tiingo: primary daily EOD prices and metadata.
  - EODHD: fundamentals, company news, historical market cap if available, EOD prices only as fallback/alternate.
  - Alpha Vantage: overview, income statement, balance sheet, cash flow, earnings, ETF/profile/news endpoints where available and not duplicated.
  - Twelve Data: price/quote/symbol/profile only when it adds unique fields or as price fallback.
  - MarketAux: news, entity metadata, sentiment, relevance, source, tags.
  - FMP: profile plus any working/free statement, ratios, key metrics, events, news, insider, ETF endpoints; plan-gated endpoints logged clearly.
- Preserve quota efficiency through endpoint-level planning, cache-first reuse, provider-specific budgets, and no duplicate price-history calls unless primary price source fails.
- Use an anonymous browser-like deterministic fetch `User-Agent`, e.g. a current Chrome or Firefox desktop UA, for non-SEC providers. Keep SEC on the configured compliant `SEC_USER_AGENT`.
- Fix `.env-starter` parsing so provider `API Token:` values may be on the same line or the following line.

### Researcher Behavior

- Update researcher instructions so every final report must use:
  - deterministic bundle files,
  - normalized technical signals,
  - locally computed technical analysis from prices when deterministic technical output is missing,
  - provider news/events,
  - procedural source capture for gaps that matter to an investment decision.
- Add mandatory report sections for equities and ETFs:
  - source base and data quality,
  - business/fund profile,
  - market and technical snapshot,
  - financials or holdings/exposures,
  - valuation or performance context,
  - catalysts and monitoring triggers,
  - bull/base/bear decision variables,
  - risks and invalidation points,
  - explicit data gaps.
- Update research JSON schema to include structured sections for `technical_analysis`, `valuation_or_performance`, `decision_factors`, `risks`, `catalysts`, `source_coverage`, and `calculation_audit`.

### Verifier Behavior

- Update verifier instructions to validate the produced research, not create a separate competing report.
- Verifier checks:
  - every material claim has cited evidence,
  - procedural calculations are reproducible from cited/deterministic data,
  - conclusions follow from sources without overreach,
  - risks and gaps are not hidden,
  - report JSON and markdown agree,
  - deterministic raw/normalized artifacts have provenance.
- Allow targeted source inspection only to validate cited sources or frozen artifacts. Do not browse for new thesis material unless a cited source is unreachable or ambiguous.

## Test Plan

- Unit tests:
  - New path resolution for `data/`, `reports/`, and `runtime`.
  - `.env-starter` multiline token parsing.
  - Browser-like UA is sent for non-SEC providers; SEC still uses configured SEC-compliant UA.
  - Provider endpoint plans include unique endpoints and skip duplicate price history.
  - Provider status distinguishes `ok`, `unauthorized`, `rate_limited`, `plan_gated`, and `error`.
  - Research JSON schema requires the new analytical sections.
  - Verifier rejects unsupported calculations/conclusions without adding new research.
- Migration tests:
  - Old path references are absent from active docs/tests, except intentional archived notes.
  - Loop dry-run writes prompts/log targets under `runtime/<SYMBOL>/<DATE>/`.
  - Deterministic bundle writes under `data/<SYMBOL>/<DATE>/`.
  - Final report writes under `reports/<SYMBOL>/<DATE>/`.
- Live validation:
  - Run deterministic smoke tests for all configured providers on one equity and one ETF.
  - Run full loop on at least two equities and two ETFs during iteration.
  - Final acceptance run produces one polished equity report and one polished ETF report with zero open critical/moderate verifier issues.
- Final verification command:
  - `python3 -m pytest tests`

## Assumptions

- Treat "six data providers" as the six external APIs: Tiingo, EODHD, Alpha Vantage, Twelve Data, MarketAux, and FMP; SEC remains a required public-source provider.
- Do not preserve old skill-directory names as active skills. The canonical active skill will be `market-research-full`.
- Existing generated outputs may remain on disk during development, but active code and docs will write only to the new `data/`, `reports/`, and `runtime/` layout.
- Provider endpoints that are plan-gated or quota-exhausted will be attempted only when budget allows, logged explicitly, and excluded from normalized facts unless successful.
