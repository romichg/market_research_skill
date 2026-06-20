# Equity And ADR Research

Use this reference for common stocks, ADRs, and foreign private issuers. Start from the deterministic bundle, then add procedural evidence only for gaps that the bundle cannot fill.

## Deterministic Inputs First

Read `references/provider-data-map.md` and the bundle files under `data/SYMBOL/AS_OF/`:

- `manifest.json`: provider status, failed retries, asset type, cache summary, warnings, and errors.
- `source_manifest.json`: raw provider files, checksums, endpoints, URLs, and fetch status.
- `gaps.json`: unavailable free-source fields and attempted providers.
- `normalized/identity.json`: symbol, company name, exchange, CIK, SIC/industry, ADR/foreign-filer signals.
- `normalized/market_snapshot.json`: latest completed close, 52-week range, average volume, market cap, valuation snapshot fields, and alternate provider candidates.
- `normalized/prices_daily.json`: OHLCV/adjusted-close rows used for calculations.
- `normalized/technical_signals.json`: local returns, moving averages, volatility/drawdown-style metrics.
- `normalized/sec_filings_index.json` and `sec_filing_sections.json`: SEC filing metadata and deterministic section extracts when available.
- `normalized/equity_fundamentals.json`: SEC XBRL and free-provider fundamentals.
- `normalized/equity_events.json`: earnings, dividends, splits, press releases, corporate actions, and calendars when returned by free providers.
- `normalized/equity_insiders.json`: Form 3/4/5 or free insider endpoint data when available.
- `normalized/news.json`: provider-supplied headlines, entities, snippets, URLs, and sentiment.

For duplicate values, use the selected normalized `DataPoint` and review `alternates`, `attempted_providers`, and `selection_reason`. If providers disagree materially, report the discrepancy as a caution instead of averaging values.

If provider technical analysis is missing, compute the technical snapshot locally from `normalized/technical_signals.json` and `normalized/prices_daily.json`; cite both files, describe the formula/date window, and record the work in `technical_analysis` and `calculation_audit`.

## Report Sections

1. **Executive summary facts**: company name, ticker, exchange, CIK, SIC/industry, headquarters when available, fiscal year end, latest annual/interim filing, latest completed close, market cap, revenue, net income, cash/debt, share count, dividends/buybacks, and next earnings date when deterministically available.
2. **Interpretation**: keep separate from facts. Do not issue Buy/Hold/Sell/Avoid recommendations unless the user explicitly asks; default to decision inputs and monitor variables.
3. **Market and technical snapshot**: use normalized price, volume, 52-week range, market cap, valuation snapshot, local technical signals, news/sentiment, and analyst/estimate data only when returned by configured free APIs. Mark short interest and analyst data as gaps when unavailable.
4. **Company overview**: prefer SEC filings and deterministic filing extracts. Add procedural IR or company website sources only when the deterministic bundle lacks business description, segments, geography, management, or customer/end-market exposure.
5. **Source base**: list deterministic raw providers first, then procedural artifacts. Cite raw paths and source dates.
6. **Financial profile**: use SEC companyfacts/companyconcept first, then free provider statements/ratios as backup. Cover revenue, margins, net income, EPS, cash flow, balance sheet, share count, capital returns, leverage, liquidity, and working-capital trends when available.
7. **SEC filing review**: latest 10-K/20-F/40-F, latest 10-Q/6-K, recent 8-Ks, proxy, Form 4/5, shelves, Form SD, restatements, CEO/CFO changes, and major agreements. Label each filing high/medium/low relevance without overstating thesis impact.
8. **Sector, industry, and moat inputs**: use SIC/industry, provider sectors, peer data if free and deterministic, and filing/business facts. Keep management claims separate from analyst interpretation.
9. **Tariff, regulatory, and macro exposure**: geography revenue, COGS/gross margin trend, FX/rate/commodity risks, policy/regulatory excerpts, and ADR issuer-country risks. Quantify only with source support.
10. **Valuation or performance context**: market cap, enterprise value, P/E, P/S, P/B, EV/EBITDA, dividend yield, buyback yield, FCF yield, and peer multiples only when deterministic or procedurally sourced. Do not invent price targets.
11. **Catalysts and monitoring triggers**: next earnings date, dividend dates, recent material filings, technical levels, support/resistance approximations from local price extrema, product/regulatory/company events, and key monitor list.
12. **Bull/base/bear decision variables**: list the variables that would support, weaken, or invalidate each scenario without turning them into a competing recommendation.
13. **Risks and invalidation points**: business, financial, regulatory, cyclicality, customer/supplier concentration, competition, valuation, FX, geopolitical, litigation, cybersecurity, governance, strategic-partner/platform dependency, and ADR-specific risks. For AI-heavy companies, search filings deterministically for AI/cloud/GPU/model/capex/platform/regulation keywords and surface excerpts.
14. **Explicit data gaps**: copy unresolved deterministic gaps and add procedural-source gaps. Distinguish unavailable free data from collection failures and stale data.

## Source Rules

- Every quantitative claim must cite a normalized file or procedural source artifact.
- Use adjusted-close language for calculated returns and technical metrics.
- Keep fiscal periods, filing dates, source dates, and accessed dates distinct.
- If a provider fails after retries, use the next successful provider but keep the failure visible via `manifest.json`.
- Use completion words such as `closed`, `settled`, or `converted` only when a direct completion source is frozen; otherwise use `announced`, `planned`, or `pending`.
