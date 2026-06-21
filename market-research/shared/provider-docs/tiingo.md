# Tiingo Endpoint Audit

Official docs checked:
- https://www.tiingo.com/documentation/end-of-day
- https://www.tiingo.com/documentation/fundamentals

Free/configured endpoints to attempt:
- metadata: symbol metadata from `/tiingo/daily/{symbol}`; unique fields include exchange/name where returned; raw evidence only in this iteration.
- prices: daily adjusted EOD history from `/tiingo/daily/{symbol}/prices`; primary price source for `prices_daily`, `market_snapshot`, and `technical_signals`.

Plan-gated or fallback endpoints:
- fundamentals: document endpoint availability and do not make it default until a configured key is confirmed to return free data; record `plan_gated` or `unauthorized` when provider payload says so.

Duplicate endpoints intentionally skipped:
- alternative daily prices from EODHD, Alpha Vantage, and Twelve Data are skipped unless Tiingo prices are missing or filtered out by endpoint settings.
