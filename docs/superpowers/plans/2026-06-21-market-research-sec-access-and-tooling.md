# Market Research SEC Access And Tooling Notes

Date: 2026-06-21

## Outcome

This change set tightened market-research helper behavior after the DPC run exposed ambiguous SEC access handling, sparse procedural fallback, and verifier/report-path confusion.

## Decisions

- `SEC_USER_AGENT` is SEC-only.
- Empty or browser-like `SEC_USER_AGENT` values fall back to `DEFAULT_SEC_USER_AGENT`.
- `HTTP_USER_AGENT` is for general HTTP providers such as MarketAux.
- Empty `HTTP_USER_AGENT` falls back to a browser-like default.
- SEC `HTTP 403` responses are not automatically authentication failures. Raw error bodies and headers must be preserved and inspected.
- SEC `Request Rate Threshold Exceeded` responses are classified as rate-limited/fair-access failures.
- SEC fair-access `HTTP 403` responses are retried only when the active SEC user-agent is already descriptive.
- Researchers should use endpoint/provider-restricted deterministic rebuilds and procedural recent-news passes when full deterministic bundles are sparse or provider calls fail.
- Verifiers should scrutinize ticker, issuer, and evidence alignment, especially for name collisions, pending IPOs, and thin-source symbols.
- Report validation should follow the report JSON `sources_file` pointer instead of relying on a single assumed report/runtime layout.

## Verification

- `python3 -m pytest tests` passed with 150 tests.
- A live SEC company-tickers smoke fetch for `AAPL` completed with provider status `ok`.
- Stale references to the old combined user-agent helper were removed.
