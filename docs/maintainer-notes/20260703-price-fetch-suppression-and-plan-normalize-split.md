# Price-Fetch Suppression And The Plan-vs-Normalize Split

Date: 2026-07-03

## Context

A repo review (see the phase commits on `fix/repo-review-20260703`) found the default endpoint plan live-fetched daily prices from every configured price provider (Tiingo, EODHD, Alpha Vantage, Twelve Data), while `normalize_prices` only ever used the first successful one by `PRICE_PROVIDER_PRIORITY`. That duplicated scarce free-tier quota (EODHD ~20 calls/day, Alpha Vantage ~25) and contradicted `provider-data-map.md`, which documents prices as a fallback for lower-priority providers.

## What Changed (H2)

Daily prices are now fetched from only one provider per run: the highest-priority configured price provider that lacks a reusable cached price response (`price_provider_to_live_fetch` in `deterministic_research_collector.py`). If the top-priority provider already has usable cached prices, no provider live-fetches prices at all. Suppressed price calls are recorded as a manifest warning and as `price_fetch_suppressed` in the fetch metrics and `plan-fetch` output. `provider-data-map.md` was updated to describe this.

## The Load-Bearing Distinction: Plan vs. Fetch vs. Normalize

Keep three concepts separate; conflating them reintroduces the bug or breaks fallback:

- **Endpoint plan** (`default_endpoint_plan`): prices stay plan-eligible for *every* configured price provider. This is what `build_bundle`/`normalize_prices` consult, so cache-based price fallback still works when a higher-priority provider is missing or unparseable.
- **Live fetch** (`cmd_fetch`): suppresses the redundant live price *call* for all but the selected provider. This is where quota is saved.
- **Normalize**: unchanged — still walks `PRICE_PROVIDER_PRIORITY` and uses the first provider with cached, parseable rows.

Because suppression happens at fetch time (not plan time), `tests/test_provider_plan_quality.py::test_default_endpoint_plan_includes_all_configured_price_fallbacks` still correctly asserts `"prices"` is in the plan for tiingo/eodhd/alphavantage/twelve_data. **Do not "fix" that test by stripping prices from the plan** — doing so would also disable cache-based normalization fallback for short or failed top-priority pulls. The fetch-suppression behavior is covered separately by `test_price_live_fetch_*` and `test_fetch_suppresses_duplicate_live_price_calls` in the same file.

## Trade-Off To Remember

If the selected provider's live fetch fails at runtime and no lower-priority provider has cached prices, that run gets no price series (older code might have, since it pulled all four). Mitigation: rerun with explicit `--providers`/`--provider-endpoints`, or `--refresh`. If this proves too fragil in practice, the localized revert is to have `cmd_fetch` fall through to the next price provider on an empty/failed top-priority pull rather than suppressing unconditionally.
