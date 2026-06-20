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
| Tiingo | daily metadata and end-of-day prices returned by the configured starter account | `identity`, `prices_daily`, `market_snapshot`, `technical_signals` |
| EODHD | fundamentals, news, historical market cap, and historical EOD prices returned by the configured account | `identity`, `market_snapshot`, `prices_daily`, `technical_signals`, `equity_fundamentals`, `news` |
| Alpha Vantage | overview, income statement, balance sheet, cash flow, earnings, ETF profile, news sentiment, and adjusted daily prices | `prices_daily`, `market_snapshot`, `identity`, `equity_fundamentals`, `equity_events`, `news`, `etf_profile`, `etf_holdings` |
| Twelve Data | quote and profile plus time series available to the configured basic account; time series is a price fallback when higher-priority price providers are unavailable | `identity`, `prices_daily`, `market_snapshot` |
| MarketAux | finance news, similar news, news by UUID, entity metadata/search/types/industries, market stats, trending entities | `news`, `market_snapshot`, `identity`, `equity_events` |
| FMP | profile, key metrics TTM, ratios TTM, income statement, balance sheet, cash flow, stock news, press releases, dividends, earnings, splits, insider trading/statistics, and ETF holdings when available to current free account | `identity`, `market_snapshot`, `news`, `equity_fundamentals`, `equity_events`, `equity_insiders`, `etf_holdings` |

## Rate-Limit-Aware Fetch Policy

The deterministic collector must be cache-first:

- Reuse successful raw endpoint cache files for later `as_of` dates unless `--refresh` is passed.
- Apply `--providers` to both live fetching and cached-data normalization. A run restricted to `sec,tiingo` must not silently include older Alpha Vantage, EODHD, Twelve Data, MarketAux, or FMP cache files.
- Estimate provider cost before network calls. If the estimated cost is above `--max-provider-calls PROVIDER=N` or the default conservative budget, skip the provider and write a manifest warning.
- Use endpoint-level planning to avoid duplicated daily price history. The default deterministic plan fetches Tiingo metadata and prices when Tiingo is configured, EODHD fundamentals/news/historical market cap without EOD prices, Alpha Vantage overview/statements/events/news sentiment without adjusted daily prices, Twelve Data quote/profile without time series, MarketAux news, and FMP unique equity/ETF endpoints. Twelve Data prices are a fallback when no higher-priority configured price provider is selected.
- Treat provider authentication failure as fatal with a clear error. Treat provider rate limits and endpoint errors as non-fatal bundle warnings when other selected evidence remains usable.
- Use `--offline` for reruns, validation prep, report regeneration, and post-run inspection whenever raw files already exist.
- Prefer SEC and one price provider for first-pass bundles. Add scarce providers only for named gaps.

Conservative endpoint cost estimates used by the collector:

| Provider | Endpoint family | Estimated cost |
| --- | --- | ---: |
| SEC EDGAR | company tickers, submissions, companyfacts | 1 each |
| Tiingo | daily metadata, daily prices | 1 each |
| EODHD | fundamentals, news, historical market cap, EOD prices | 10 + 1 + 1 + 1 |
| Alpha Vantage | overview, income statement, balance sheet, cash flow, earnings, ETF profile, news sentiment, adjusted daily prices | 10 + 5 + 5 + 5 + 1 + 1 + 1 + 1 |
| Twelve Data | quote, profile, daily time series | 1 each |
| MarketAux | news | 1 |
| FMP | profile, key metrics TTM, ratios TTM, stock news, press releases, dividends, earnings, splits, insider trading, insider statistics, ETF holdings | 1 each |
| FMP | income statement, balance sheet, cash flow | 5 each |

Official limit notes checked June 2026:

- SEC fair access guidance says automated access should stay at no more than 10 requests per second and should download only what is needed: https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data
- Twelve Data Basic lists 8 API credits per minute and 800 per day, with endpoint-specific data weights: https://twelvedata.com/pricing
- EODHD free plan documentation describes 20 calls per day; EODHD API-limits documentation says fundamentals consume 10 calls and EOD prices consume 1 call: https://eodhd.com/financial-apis/quick-start-with-our-financial-data-apis and https://eodhd.com/financial-apis/api-limits
- MarketAux free pricing lists 100 requests daily and 3 articles per news request: https://www.marketaux.com/pricing
- Financial Modeling Prep pricing lists 250 calls per day for the free Basic plan: https://site.financialmodelingprep.com/developer/docs/pricing
- Financial Modeling Prep documentation lists stable profile, key metrics, ratios, statements, events, insider, press-release, and stock-news endpoints under the current developer docs: https://site.financialmodelingprep.com/developer/docs
- Tiingo documentation describes hourly and daily request limits by account: https://www.tiingo.com/documentation/

## Duplicate Data Policy

When multiple providers return the same field, normalize one canonical `DataPoint` using source priority and attach alternates:

```json
{
  "value": 123,
  "provider": "sec",
  "alternates": [
    {"value": 124, "provider": "eodhd", "raw_path": "data/.../raw/eodhd/file.json"}
  ],
  "attempted_providers": ["sec", "eodhd", "alphavantage"],
  "selection_reason": "primary_source_priority"
}
```

If the preferred source fails after retries, use the next successful provider and keep the failed provider status in `manifest.json` and the attempted source list. If values disagree materially, preserve alternates and add a gap or warning rather than silently blending them.
