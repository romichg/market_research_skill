# FMP Endpoint Audit

Official docs checked:
- https://site.financialmodelingprep.com/developer/docs
- https://site.financialmodelingprep.com/developer/docs/stable/profile-symbol
- https://site.financialmodelingprep.com/developer/docs/stable/key-metrics
- https://site.financialmodelingprep.com/developer/docs/stable/metrics-ratios
- https://site.financialmodelingprep.com/developer/docs/stable/income-statement

Free/configured endpoints to attempt:
- profile: `/stable/profile`; normalized targets are `identity` and `market_snapshot`.
- key_metrics_ttm: `/stable/key-metrics-ttm`; normalized targets are `market_snapshot` and `equity_fundamentals`.
- ratios_ttm: `/stable/ratios-ttm`; normalized target is `equity_fundamentals`.
- income_statement: `/stable/income-statement`; normalized target is `equity_fundamentals`.
- balance_sheet: `/stable/balance-sheet-statement`; normalized target is `equity_fundamentals`.
- cash_flow: `/stable/cash-flow-statement`; normalized target is `equity_fundamentals`.
- stock_news: `/stable/news/stock`; normalized target is `news`.
- press_releases: `/stable/news/press-releases`; normalized target is `news`.
- dividends: `/stable/dividends`; normalized target is `equity_events`.
- earnings: `/stable/earnings`; normalized target is `equity_events`.
- splits: `/stable/splits`; normalized target is `equity_events`.
- insider_trading: `/stable/insider-trading`; normalized target is `equity_insiders`.
- insider_statistics: `/stable/insider-trading/statistics`; normalized target is `equity_insiders`.
- etf_holdings: `/stable/etf/holdings`; normalized target is `etf_holdings`.

Plan-gated or fallback endpoints:
- bulk endpoints: not default because single-symbol research does not need them and plan limits vary.

Duplicate endpoints intentionally skipped:
- historical prices: skipped because Tiingo is the primary price source.
