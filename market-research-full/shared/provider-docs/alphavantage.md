# Alpha Vantage Endpoint Audit

Official docs checked:
- https://www.alphavantage.co/documentation/

Free/configured endpoints to attempt:
- overview: `OVERVIEW`; unique overview, valuation, dividend, and classification fields; normalized targets are `identity`, `market_snapshot`, and `equity_fundamentals`.
- income_statement: `INCOME_STATEMENT`; normalized target is `equity_fundamentals`.
- balance_sheet: `BALANCE_SHEET`; normalized target is `equity_fundamentals`.
- cash_flow: `CASH_FLOW`; normalized target is `equity_fundamentals`.
- earnings: `EARNINGS`; normalized target is `equity_events`.
- etf_profile: `ETF_PROFILE`; normalized target is ETF profile/holdings fields when returned.
- news_sentiment: `NEWS_SENTIMENT`; normalized target is `news`.

Plan-gated or fallback endpoints:
- prices: `TIME_SERIES_DAILY_ADJUSTED`; fallback price source only when Tiingo and EODHD prices are unavailable.

Duplicate endpoints intentionally skipped:
- prices: skipped by default when Tiingo prices are selected.
