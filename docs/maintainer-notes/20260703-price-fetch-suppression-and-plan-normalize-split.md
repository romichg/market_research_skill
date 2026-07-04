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

## Follow-Up (2026-07-04): Budget-Aware Selection And Explicit Opt-In

A follow-up review found the selection above was budget-*unaware* in three ways; all three are now fixed in `deterministic_research_collector.py`:

- **Suppressed cost leakage (F1).** `cmd_fetch` and `provider_fetch_plan` (`plan-fetch`) used to run `estimated_provider_call_cost`/`endpoints_within_budget` on the endpoint set that still included the suppressed provider's `prices` endpoint. Because `ENDPOINT_BUDGET_PRIORITY` lists `prices` *first* for `alphavantage` and `twelve_data`, a suppressed provider's budget trimmer could spend the whole budget on a `prices` call that was about to be discarded, starving it of budget for endpoints it could have actually fetched. Fix: `prices` is now excluded from a suppressed provider's chargeable endpoint set *before* cost estimation and budget trimming, not after.
- **Selection can silently fail (F2).** `price_provider_to_live_fetch` used to pick the highest-priority provider without cache, without checking whether that provider's own budget could actually cover a `prices` call. If it couldn't, every other price provider was still suppressed with an "X already covers prices" warning that was no longer true, and the run got no price series with no indication why. Fix: `price_provider_to_live_fetch` now takes an optional `budgets` dict and, when a candidate can't afford `prices`, moves on to the next configured price provider. If none can afford it and none has cache, `cmd_fetch`/`cmd_plan_fetch` record a "No live price fetch this run" warning instead of a misleading per-provider message.
- **Explicit inclusion was ignored (F3).** `--provider-endpoints eodhd=prices` (or any explicit filter naming `prices`) used to be silently overridden by a higher-priority provider's default suppression. Fix: `explicit_price_opt_ins()` reads the raw `--provider-endpoints` filters and treats naming `prices` for a provider as an opt-in — that provider is never suppressed, so it fetches prices *alongside* whichever provider the default priority selection picks.

These are budget/selection fixes only; the plan-vs-fetch-vs-normalize split and the trade-off above are unchanged.

## Follow-Up (2026-07-04, second pass): Cache-Aware Trim And Provider Scope

A second review found two more budget/scope corners, both now fixed in `deterministic_research_collector.py`:

- **Trim charged cached endpoints (G1).** F1 made the cost *estimate* cache-aware but left `endpoints_within_budget` cache-*blind*: the greedy trim charged every selected endpoint its full cost, including endpoints whose reusable cache means no live call happens. An expensive cached endpoint early in `ENDPOINT_BUDGET_PRIORITY` (e.g. `alphavantage` `overview`, cost 10) could then consume the whole budget on a call that never fires, fetching nothing live. Fix: the trim now adds a reusable-cached endpoint to the allowed set at *zero* cost (using the already-passed `cache_root`/`refresh`), so cached endpoints stay in the plan for normalization while the budget goes to the highest-priority uncached endpoints. `price_provider_to_live_fetch` shares the same function, so it stays consistent automatically.
- **Out-of-run provider in an endpoint filter (G2).** `parse_provider_endpoints` started from `default_endpoint_plan(providers)` but then set `plan[provider] = requested` for *any* provider named in a `--provider-endpoints` filter, silently adding providers outside the run's `--providers` list. `price_provider_to_live_fetch` iterates `PRICE_PROVIDER_PRIORITY` against the plan, so the phantom provider could win price-fetch selection while never actually fetching. The F3 opt-in workflow made `--provider-endpoints ...prices` a documented use, raising the odds of this misuse. Fix: `parse_provider_endpoints` now `die()`s (exit 2) when a filter names a provider not in the run, mirroring the existing unknown-endpoint guard; after that guard the plan keys are a subset of `providers` by construction, so selection and opt-in scoping need no extra intersection logic.

Also in this pass: the `market_snapshot` 52-week high/low now carry the same `available_history` status as the technicals when fewer than 252 sessions exist (G3); the usage audit matches numeric values with digit boundaries and adds conservative humanized million/billion/trillion tokens so a bare "8" no longer matches inside "1985" and a "$391.0 billion" memo phrasing matches a `391035000000` revenue (G4); and raw payloads are parsed once per `(path, mtime)` via a module-level memo to avoid re-parsing multi-megabyte SEC companyfacts several times per run (G6).

## Follow-Up (2026-07-04, third pass): Usage-Audit Context And Reporting Consistency

A third review tightened the edges left by the second pass:

- **Humanized value context (J1).** Humanized million/billion/trillion value matches now require an adjacent magnitude word or compact suffix (`million`/`m`, `billion`/`bn`/`b`, `trillion`/`tn`/`trn`/`t`). This keeps "$391 billion" and "$391.04bn" valid value references while preventing bare "20.0%" or "8000 employees" from satisfying a large-dollar datapoint.
- **Budget-zero cached endpoints (J2).** `--max-provider-calls PROVIDER=0` still blocks live calls, but reusable cached endpoints for that provider stay in the effective endpoint plan because they cost no calls and can safely support normalization.
- **Own-cache suppression reporting (J3).** A lower-priority provider whose own reusable cache already covers `prices` is no longer reported as `price_fetch_suppressed`; that matches `plan-fetch` and avoids a misleading "already covers prices" warning.
- **Plan-fetch price warning (J4).** `plan-fetch` now exposes `price_fetch_provider` and top-level `warnings`, including the same "No live price fetch this run" warning as `fetch` when all configured price providers are either unaffordable or uncached.
- **Aggregate call estimate (J5).** Per-provider metrics still record the cost a skipped provider would have incurred, but the aggregate `provider_call_estimate` now sums only providers that attempted a fetch.
