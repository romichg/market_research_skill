# Twelve Data Endpoint Audit

Official docs checked:
- https://twelvedata.com/docs

Free/configured endpoints to attempt:
- quote: `/quote`; unique latest quote fields and exchange/session context where returned; normalized target is `market_snapshot`.
- profile: `/profile`; unique company/fund profile fields where returned; normalized target is `identity`.

Plan-gated or fallback endpoints:
- prices: `/time_series`; fallback price source only when Tiingo, EODHD, and Alpha Vantage prices are unavailable.

Duplicate endpoints intentionally skipped:
- prices: skipped by default when higher-priority price providers are selected.
