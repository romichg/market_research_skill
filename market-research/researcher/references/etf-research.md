# ETF Research

Use this reference for ETFs, exchange-traded funds, trusts, and fund-like exchange-traded products. Start from the deterministic bundle, then add issuer/SEC procedural artifacts for unavailable fields.

## Deterministic Inputs First

Read `references/provider-data-map.md` and the bundle files under `data/SYMBOL/AS_OF/`:

- `manifest.json`: provider status, failed retries, asset type, cache summary, warnings, and errors.
- `source_manifest.json`: raw provider files, checksums, endpoints, URLs, and fetch status.
- `gaps.json`: unavailable free-source fields and attempted providers.
- `normalized/identity.json`: ticker, fund name where available, exchange, CIK/series/class IDs, issuer/sponsor clues, and fund classification.
- `normalized/market_snapshot.json`: latest completed close, 52-week range, average volume, AUM/NAV/market cap equivalents when providers return them, and duplicate-provider alternates.
- `normalized/prices_daily.json` and `technical_signals.json`: adjusted close history, local returns, moving averages, drawdowns, volatility proxies, and tracking proxy inputs.
- `normalized/sec_filings_index.json` and `sec_filing_sections.json`: prospectus, 497/497K, N-1A, annual/semiannual, N-PORT, N-CEN, and other fund filing metadata/extracts.
- `normalized/etf_profile.json`: issuer, benchmark, objective, structure, active/passive status, inception, exchange, expense ratios, tax/structure facts, securities lending where available.
- `normalized/etf_holdings.json`: SEC N-PORT, free ETF exposure endpoints, top holdings, sector/country/asset-class allocations, and concentration metrics.
- `normalized/etf_distributions.json`: dividends, capital gains, SEC/distribution yield, turnover, and tax/distribution facts when available.
- `normalized/etf_performance.json`: market/NAV returns, tracking proxy metrics, benchmark/category inputs, volatility/beta/drawdown-style metrics.
- `normalized/news.json`: provider-supplied headlines and sentiment.

For duplicate values, use the selected normalized `DataPoint` and review `alternates`, `attempted_providers`, and `selection_reason`. If providers disagree materially, report the discrepancy as a caution instead of averaging values.

If provider technical analysis is missing, compute the technical snapshot locally from `normalized/technical_signals.json` and `normalized/prices_daily.json`; cite both files, describe the formula/date window, and record the work in `technical_analysis` and `calculation_audit`.

## Report Sections

1. **Executive summary facts**: fund name, ticker, issuer/sponsor, benchmark/index, inception date, exchange, expense ratio, AUM, NAV, recent price, premium/discount, holdings count, top-10 concentration, distribution/SEC yield, latest prospectus/summary prospectus, and latest annual/semiannual report dates when available.
2. **Interpretation**: keep separate from facts. Do not issue Buy/Hold/Sell/Avoid recommendations unless the user explicitly asks; default to portfolio role, tradeoffs, monitor variables, and fit considerations.
3. **Market and technical snapshot**: price, NAV, premium/discount, AUM, average volume, bid/ask spread only if free/reproducible, 52-week range, distributions, short interest/options context only if deterministic, and local technical signals.
4. **Sponsor and product identity**: issuer, fund name, benchmark/index, legal structure, tax treatment, active/passive status, replication method, creation/redemption mechanics, and securities lending. Use SEC series/class data and filings as identity support; use issuer artifacts procedurally for current operating facts when APIs are sparse.
5. **Fees, expenses, and tax efficiency**: net/gross expense ratio, waivers, turnover, distribution history, capital gains, SEC yield/distribution yield, and total cost fields when free providers or issuer filings return them.
6. **Strategy and index methodology**: objective, index provider, eligibility, weighting, caps, rebalance/reconstitution cadence, derivatives/leverage/short exposure, methodology changes, and active management discretion when applicable.
7. **Holdings and portfolio composition**: full holdings when deterministic/free, top holdings, top-10 concentration, number of holdings, sector/country/market-cap/asset-class allocation, fixed-income duration/YTW/OAS if available, and theme purity as a clearly labeled heuristic only when holdings support it.
8. **Portfolio companies snapshot**: when holdings are available, include all holdings if the ETF has 25 or fewer holdings; otherwise include the top 25 by weight. For each covered holding, provide company/ticker, portfolio weight, sector or industry, what it does, quick outlook, and quick price/technical context when reliable public/free data is available. Follow with a synthesis paragraph about what the companies imply for concentration, cyclicality, upside drivers, risks, and monitoring.
9. **Performance and risk behavior**: NAV and market returns when available, benchmark/category context, tracking difference/error, volatility, beta, drawdowns, stress-period behavior where history supports it, and tracking proxy versus benchmark symbols when available.
10. **SEC filings review**: prospectus/summary prospectus, SAI, annual/semiannual reports, N-PORT, N-CEN, 497/497K changes, Form 8937 only if deterministically available, and material closure/fee/strategy/risk updates.
11. **Sector, theme, macro, tariff, and regulatory context**: map exposures through holdings. Quantify only with holdings or filing support.
12. **Competitive landscape**: closest alternatives by category, benchmark, fund-name tokens, exposure, expense ratio, AUM, liquidity, methodology, holdings overlap, and performance/tracking metrics when deterministic or procedurally sourced. Do not declare a competitor superior without cited evidence.
13. **Issuer and manager quality**: issuer franchise, fund age, AUM trend if available, manager names/tenure if disclosed, index provider, securities lending, and closure-risk indicators such as low AUM, low volume, young age, or high expense ratio.
14. **Valuation or performance context**: weighted P/E, P/B, dividend yield, market cap, sector/country weights, fixed-income metrics, NAV/market return history, benchmark/category context, and tracking metrics only when holdings and provider fundamentals support them; include coverage percentage.
15. **Catalysts and monitoring triggers**: distribution dates, rebalances, methodology changes, flows/AUM changes when sourced, liquidity changes, premium/discount shifts, and material filing or issuer updates.
16. **Bull/base/bear decision variables**: portfolio role, exposure fit, fee/liquidity tradeoffs, tracking quality, tax considerations, and invalidation trigger candidates.
17. **Risks and invalidation points**: concentration, country, currency, sector, index methodology, liquidity, premium/discount, AP/creation-redemption, cash versus in-kind mechanics, tracking, tax form/treatment, taxable distributions, foreign withholding/tax drag, leverage/path dependency, derivatives, and closure risk.
18. **Explicit data gaps**: copy unresolved deterministic gaps and add procedural-source gaps. Distinguish unavailable free data from collection failures and stale data.

## Source Rules

- Every quantitative claim must cite a normalized file or procedural source artifact.
- Prefer issuer filings/product pages for current operating facts when API data is stale or unavailable.
- Do not describe securities-lending data as unavailable until annual/semiannual reports have been checked.
- If holdings CSV/API capture returns HTML or unusable content, record a workflow extraction gap.
- If a provider fails after retries, use the next successful provider but keep the failure visible via `manifest.json`.
