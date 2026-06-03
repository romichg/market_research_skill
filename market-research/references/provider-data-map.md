# Provider Data Map

Use this map to keep deterministic collection, schemas, and report references aligned. Include only free/currently configured endpoint families. Paid or plan-gated endpoints stay out of the schema and must be recorded as gaps if unavailable.

## Normalized Sections

- `identity`: symbol, name, exchange, CIK, SIC/industry, asset type, ADR/foreign filer signals, ETF/fund identifiers.
- `market_snapshot`: latest completed close, OHLCV snapshot, 52-week range, average volume, market cap, valuation snapshot fields when free data returns them.
- `prices_daily`: daily OHLCV and adjusted close rows used for local analytics.
- `technical_signals`: locally computed returns, moving averages, volatility/drawdown-style metrics from `prices_daily`.
- `news`: provider-supplied headlines, source, URL, publication time, entities, language/country, snippets, and sentiment where returned.
- `sec_filings_index`: SEC filing metadata, forms, accession numbers, filing/report dates, primary documents, and relevance labels.
- `sec_filing_sections`: deterministic excerpts or section boundaries from filings when extractable.
- `equity_fundamentals`: SEC XBRL and free provider fundamentals: revenue, margins, net income, EPS, cash flow, balance sheet, dividends, buybacks, ratios, share count, market cap, enterprise value when available.
- `equity_events`: earnings dates/results, dividends, splits, IPO/calendar items, press releases, and other corporate actions available from free configured APIs.
- `equity_insiders`: Form 3/4/5 metadata from SEC and free insider endpoints when available.
- `etf_profile`: fund name, issuer, benchmark, structure, exchange, inception, expense ratios, AUM/NAV if available.
- `etf_holdings`: holdings, country/sector/asset exposure, N-PORT data, top holdings, and concentration when free data returns them.
- `etf_distributions`: dividends, capital gains, SEC/distribution yield if available, tax/distribution facts.
- `etf_performance`: market/NAV returns, tracking proxy metrics, risk statistics, and benchmark comparison inputs when free data supports them.

## Provider Coverage

| Provider | Free/configured endpoint families | Normalized sections |
| --- | --- | --- |
| SEC EDGAR | company tickers, submissions, companyfacts, companyconcept, frames, filing documents, Form N-PORT datasets, investment company series/class data | `identity`, `sec_filings_index`, `sec_filing_sections`, `equity_fundamentals`, `equity_insiders`, `etf_profile`, `etf_holdings` |
| Tiingo | end-of-day prices and daily metadata returned by the configured starter account | `prices_daily`, `market_snapshot`, `technical_signals` |
| EODHD | historical EOD prices returned by the configured free account | `prices_daily`, `market_snapshot`, `technical_signals` |
| Alpha Vantage | adjusted daily prices, overview, ETF profile, news sentiment, income statement, balance sheet, cash flow, earnings | `prices_daily`, `market_snapshot`, `identity`, `news`, `equity_fundamentals`, `equity_events`, `etf_profile`, `etf_holdings`, `etf_performance` |
| Twelve Data | time series, quote, and symbol metadata available to the configured basic account | `prices_daily`, `market_snapshot`, `identity` |
| MarketAux | finance news, similar news, news by UUID, entity metadata/search/types/industries, market stats, trending entities | `news`, `market_snapshot`, `identity`, `equity_events` |
| FMP | profile, quote, historical price, statements, ratios/key metrics, insider trading/statistics, ETF sector/country/asset exposure and disclosures when available to current free account | `identity`, `market_snapshot`, `prices_daily`, `equity_fundamentals`, `equity_events`, `equity_insiders`, `etf_profile`, `etf_holdings`, `etf_performance` |

## Duplicate Data Policy

When multiple providers return the same field, normalize one canonical `DataPoint` using source priority and attach alternates:

```json
{
  "value": 123,
  "provider": "sec",
  "alternates": [
    {"value": 124, "provider": "eodhd", "raw_path": "reports/.../raw/eodhd/file.json"}
  ],
  "attempted_providers": ["sec", "eodhd", "alphavantage"],
  "selection_reason": "primary_source_priority"
}
```

If the preferred source fails after retries, use the next successful provider and keep the failed provider status in `manifest.json` and the attempted source list. If values disagree materially, preserve alternates and add a gap or warning rather than silently blending them.
