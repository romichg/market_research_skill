# Investment Validation

Validate the report as if no producer conversation exists.

Check these areas:

- Artifact integrity: markdown, JSON, sources, context, and manifest are present.
- Claim support: every material quantitative claim has a source or is marked unavailable.
- Dates: source date, accessed date, and stale-data caveats are present for fast-changing facts.
- Source quality: primary sources are preferred; secondary sources are labeled.
- Source reproducibility: cited `source_id` values should be present in `sources.json`; cited public documents/pages should be frozen in `source_bundle/` when saveable.
- Entity alignment: cited sources must refer to the same issuer, fund, share class, listing, and ticker context as the report. Scrutinize ticker collisions, similarly named companies, ADR/local-listing differences, pending IPO symbols, renamed issuers, and news-provider results that mention a different company. If a source is about the wrong entity, mark the supported claim as unsupported even if the ticker text matches.
- Internal consistency: markdown and JSON do not contradict each other.
- Facts versus interpretation: major sections keep sourced facts distinct from judgment.
- Data gaps: missing or low-confidence data is disclosed rather than hidden.
- Decision usefulness: the report should give a trader concrete monitored metrics, catalysts, bull/base/bear framing, and invalidation triggers without overstating precision.

ETF-specific checks:

- Expense ratio and fee claims are sourced.
- Benchmark/index name and methodology are supported.
- Holdings, sector, country, and concentration data have as-of dates.
- Performance claims specify period and as-of date.
- Liquidity/trading claims are current or caveated.
- Tracking difference and tracking error are not conflated.
- Competitor ETF comparisons use obvious alternatives when public/free data exists, or clearly disclose why peer data is unavailable.
- Structural/tax claims cover legal wrapper, tax form/treatment, securities lending, AP/creation-redemption, premium/discount, and closure risks where material.
- Leveraged, inverse, volatility-linked, futures-based, covered-call, buffered, or derivative-heavy ETPs include prominent path-dependency, decay, cap/participation, counterparty, K-1/60-40, or other wrapper-specific warnings.
- Risks cover concentration, country/currency, sector, methodology, liquidity, tracking, tax, structure, and macro/regulatory exposure.

Equity/ADR-specific checks:

- Company identity and security type are supported.
- For pending IPOs and newly listed securities, confirm SEC filing entity, issuer legal name, expected exchange/ticker, and any secondary news item all point to the same company before accepting IPO terms, listing timing, or recent-event claims.
- Latest annual and interim filings are used or unavailable filings are disclosed.
- Revenue, earnings, cash flow, balance sheet, and share data are sourced.
- Valuation claims are supported by current or clearly dated inputs.
- Market snapshot claims such as price, 52-week range, market cap, volume, moving averages, short interest, analyst/consensus context, and options-positioning context are dated, sourced, and marked secondary/unverified when not primary.
- SEC filing review covers risk factors, MD&A, recent 8-Ks, proxy/governance, and insider activity where material and publicly available.
- Valuation work reconciles with the executive summary and bull/base/bear framework; scenario probabilities should sum to 100% when used.
- Risks include business, financial, valuation, regulatory, macro/cyclicality, FX, governance, litigation, cybersecurity, customer/supplier concentration, and ADR-specific issues where applicable.

Severity definitions:

- `critical`: materially misleading, missing core source, wrong security type, fabricated/unsupported major quantitative claim.
- `moderate`: important unsupported claim, stale material data without caveat, missing major risk, weak thesis support.
- `minor`: clarity, formatting, citation polish, or non-blocking improvement.

Missing sections from the expanded research references should be severity-rated by investor impact. Absence of a material risk, unsupported valuation/recommendation, wrong security structure, or fabricated market/financial data is critical or moderate. Unavailable public/free data that is clearly disclosed is not a blocking issue.

Issue statuses:

- `open`: fixable with better research, writing, citation, or correction.
- `resolved`: already addressed in the artifact under validation.
- `unresolved_data_unavailable`: public/free data appears unavailable or not accessible in this session.

Validation output should include a "Sources Inspected" section. For each inspected source, distinguish frozen local artifacts from live public pages inspected during validation and include source dates when visible.
