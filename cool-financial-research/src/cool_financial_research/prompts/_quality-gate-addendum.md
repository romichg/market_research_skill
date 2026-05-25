# Quality Gate Addendum — Applies to All Cool Financial Research Agents

This addendum is binding and overrides weaker language elsewhere in the prompt.

## Source hierarchy

Prefer sources in this order:

1. **Primary official sources**: SEC EDGAR filings and XBRL, issuer investor-relations pages, ETF prospectuses/SAI, N-CSR/N-CSRS/N-PORT/497 filings, issuer fact sheets and holdings files, index methodology documents, official exchange data, FINRA short-interest data, and regulator data.
2. **Licensed/paid institutional data** if explicitly available to OpenClaw through the user's local tools or exports: Bloomberg, FactSet, S&P Capital IQ / Market Intelligence, LSEG/Refinitiv, Morningstar Direct, Visible Alpha, OptionMetrics, Cboe DataShop, ORTEX, S&P Global Securities Finance, etc.
3. **Secondary public aggregators** only when primary data is unavailable or not reasonably accessible. Mark these as lower confidence and explain why a primary source was not used.

Do not treat an unsourced aggregator number as verified.

## Quantitative claim discipline

Every material quantitative claim in markdown must also appear in the JSON sidecar under `quantitative_claims` with:

- `claim_text`
- `value` where applicable
- `as_of_date`
- `source_id`
- `source_date`
- `accessed_date`
- `confidence`: `high`, `medium`, `low`, or `unverified`
- `verification_status`: `verified_primary`, `verified_secondary`, `unverified`, or `not_available`
- `stale`: boolean
- `staleness_reason` when stale or fast-changing

If a material number cannot be verified, write **`unverified`** in markdown and set `verification_status: "unverified"` in JSON. If data is genuinely unavailable, write **`Data not available`** and set `verification_status: "not_available"`.

## Freshness rules

Always include source dates and access dates. Flag stale or fast-changing data instead of inventing precision.

Treat these as fast-changing and require an explicit `as_of_date`:

- Equity/ETF price, NAV, market cap, AUM, bid/ask spread, premium/discount, volume, technical indicators, options flow, analyst ratings/targets, short interest, borrow cost, ETF holdings, ETF distributions, consensus estimates.

Default freshness thresholds:

- Price/NAV/technicals/options/premium-discount/spread/volume: stale if older than 7 calendar days.
- Analyst ratings/targets, short interest, AUM, ETF holdings/fact sheets, consensus estimates: stale if older than 30 calendar days unless the source is the latest official release schedule.
- SEC filings, annual reports, prospectuses, index methodologies, and audited financials: flag if older than 90 days, but do not call them invalid if they are the latest official document.

## FACTS vs. INTERPRETATION

Every major report section must separate:

- **FACTS:** sourced observations and verified data.
- **INTERPRETATION:** the analyst's reasoning, implications, and judgment.

Never present a model output, extrapolation, or valuation conclusion as a fact.

## Validation and fix discipline

Validation issue counts must exactly match the issue list by severity. Each issue must have a stable `id`, severity, section, status, required fix, evidence/source, and source confidence.

Each fix pass must address every open Critical or Moderate issue from the immediately prior validation. Each issue must be marked in the fix JSON as either:

- `fixed`, with a concise explanation and source evidence; or
- `unresolved_data_unavailable`, with a concise explanation of the missing primary data and where it is carried forward.

Unresolved Critical/Moderate issues must be carried into:

- the final report Section 15,
- the final JSON `unresolved_issues`, and
- `run_manifest.json`.

## Auditability

Preserve all intermediate files. Do not overwrite validation or fix files. The final report should be consumption-ready, but the output directory must retain the full audit trail.

## Data-gap and paid-service usefulness logging

Every validation agent must identify which unavailable or low-confidence data most limited the quality of the report. Add these to JSON as `data_gaps` using the categories from the validation schema. Do **not** recommend a paid service merely because data would be nice to have; recommend it only when it would materially improve a Critical/Moderate issue, a repeated low-confidence claim, or a fast-changing section that cannot be verified from free primary sources.

For each data gap, include:

- affected section(s),
- severity,
- why free/primary public sources were insufficient,
- potential retail-accessible paid services that could reduce the gap,
- expected quality lift: `high`, `medium`, or `low`,
- related validation issue ids.

Each run should then call the deterministic helper `assess-data-gaps` on the latest validation JSON so the cumulative provider-value ledger is updated. The ledger is directional until at least 20 completed research runs. After 20 runs, use the cumulative evidence to identify the one or two retail services with the best recurring quality lift per dollar. Never claim that the skill has purchased, accessed, or verified against a paid service unless the user explicitly provided licensed local exports.

## Deterministic local-data preference

When local source bundles, XBRL extracts, ETF holdings summaries, chart images, or provider exports are present in the run directory, treat them as higher-priority context than unsourced web snippets. Cite the local source bundle file name and its upstream source. If a chart is generated, it must be generated only from verified local CSV/JSON inputs and must disclose its source file.
