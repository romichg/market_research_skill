# EODHD Endpoint Audit

Official docs checked:
- https://eodhd.com/financial-apis/api-for-historical-data-and-volumes
- https://eodhd.com/lp/fundamental-data-api
- https://eodhd.com/financial-apis/user-api

Free/configured endpoints to attempt:
- fundamentals: `/api/fundamentals/{symbol}.US`; unique company/fund fundamentals, classifications, valuation fields, ETF fields when returned; normalized targets are `identity`, `market_snapshot`, `equity_fundamentals`, and ETF fields.
- news: `/api/news`; unique provider news; normalized target is `news`.
- historical_market_cap: `/api/historical-market-cap/{symbol}.US`; unique historical market-cap context; normalized target is `market_snapshot` or a future `market_cap_history` artifact.

Plan-gated or fallback endpoints:
- prices: `/api/eod/{symbol}.US`; fallback price source only when Tiingo prices are not available.

Duplicate endpoints intentionally skipped:
- prices: skipped by default when Tiingo prices are selected.
