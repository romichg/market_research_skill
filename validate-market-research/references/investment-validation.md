# Investment Validation

Validate the report as if no producer conversation exists.

Check these areas:

- Artifact integrity: markdown, JSON, sources, context, and manifest are present.
- Claim support: every material quantitative claim has a source or is marked unavailable.
- Dates: source date, accessed date, and stale-data caveats are present for fast-changing facts.
- Source quality: primary sources are preferred; secondary sources are labeled.
- Source reproducibility: cited `source_id` values should be present in `sources.json`; cited public documents/pages should be frozen in `source_bundle/` when saveable.
- Internal consistency: markdown and JSON do not contradict each other.
- Facts versus interpretation: major sections keep sourced facts distinct from judgment.
- Data gaps: missing or low-confidence data is disclosed rather than hidden.

ETF-specific checks:

- Expense ratio and fee claims are sourced.
- Benchmark/index name and methodology are supported.
- Holdings, sector, country, and concentration data have as-of dates.
- Performance claims specify period and as-of date.
- Liquidity/trading claims are current or caveated.
- Risks cover concentration, country/currency, sector, methodology, liquidity, and tracking.

Equity/ADR-specific checks:

- Company identity and security type are supported.
- Latest annual and interim filings are used or unavailable filings are disclosed.
- Revenue, earnings, cash flow, balance sheet, and share data are sourced.
- Valuation claims are supported by current or clearly dated inputs.
- Risks include business, financial, regulatory, macro/cyclicality, FX, and ADR-specific issues where applicable.

Severity definitions:

- `critical`: materially misleading, missing core source, wrong security type, fabricated/unsupported major quantitative claim.
- `moderate`: important unsupported claim, stale material data without caveat, missing major risk, weak thesis support.
- `minor`: clarity, formatting, citation polish, or non-blocking improvement.

Issue statuses:

- `open`: fixable with better research, writing, citation, or correction.
- `resolved`: already addressed in the artifact under validation.
- `unresolved_data_unavailable`: public/free data appears unavailable or not accessible in this session.

Validation output should include a "Sources Inspected" section. For each inspected source, distinguish frozen local artifacts from live public pages inspected during validation and include source dates when visible.
