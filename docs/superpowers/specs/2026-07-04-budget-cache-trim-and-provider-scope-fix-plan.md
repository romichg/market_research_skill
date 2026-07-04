# Second Follow-Up Review: Budget/Cache Trim, Provider Scope, And Output-Quality Fix Plan (2026-07-04)

Scope: verification of the uncommitted working tree on `fix/repo-review-20260703` against
`2026-07-04-followup-review-fix-plan.md`, plus a fresh review of the collector's budget/price
logic, normalization output quality, and the usage-audit matching. Test suite state at review
time: `python3 -m pytest tests` → **319 passed**.

## 1. Verification Of The 2026-07-04 Plan

All nine findings (F1–F9) are implemented and covered:

- **Phase A (F1, F2, F3)** — `cmd_fetch`/`provider_fetch_plan` exclude a suppressed provider's
  `prices` endpoint from cost estimation and budget trimming before the trim runs;
  `price_provider_to_live_fetch()` takes a `budgets` dict and promotes the next configured price
  provider when a candidate cannot afford `prices`, with a "No live price fetch this run" warning
  when nobody can; `explicit_price_opt_ins()` honors `--provider-endpoints PROVIDER=...prices...`
  as an opt-in. `provider-data-map.md` and the maintainer note document the new behavior in the
  same change. Four new tests cover all three findings.
- **Phase B (F4, F5, F6, F9)** — `tmp-loop-smoke/` restored to `.gitignore`; `die`/`utc_now`
  imported from `script_utils` in `validate_market_research.py`, `producer_self_check.py`, and
  `research_loop.py` with local copies deleted; `price_fetch_suppressed` present in every
  `provider_metrics` branch (a metrics entry was also added to the previously silent
  budget-skipped branch); the recovery command carries `--cache-dir`/`--runtime-dir` when the
  user passed them and quotes all parts with `shlex.quote`.
- **Phase C (F7, F8)** — both promised tests added
  (`test_sec_403_with_descriptive_user_agent_retries_and_preserves_final_classification`,
  `test_usage_audit_recognizes_scalar_companyfacts_revenue_value`); the unconditional "Codex"
  strings in `research_loop.py`, `procedural_source_helper.py`, `docs/operations.md`,
  `supervisor-workflow.md`, and `README.md` are neutralized while `agents/openai.yaml` and the
  labeled README Codex example correctly remain.

Verification commands from the plan were re-run: full pytest (319 passed), `doctor`, the
`plan-fetch` smoke, and the `run-batch --dry-run` smoke under `runtime/tmp-loop-smoke`; the
working tree stays clean afterwards.

Interplay checks that came up clean: the F2 selection function and the F1 trim in `cmd_fetch`
use the same `estimated_provider_call_cost`/`endpoints_within_budget` calls on the same inputs,
so a provider selected to fetch prices cannot subsequently lose `prices` to the trim; a provider
whose *own* cache covers prices is not misreported as suppressed in `provider_fetch_plan`
(cached-endpoints guard); suppressed providers keep `prices` in `effective_endpoint_plan` so
cached-price normalization fallback still works, including in the budget-zero and budget-skipped
branches.

## 2. New Findings

Severity scale as in the prior reviews. G1 and G2 were confirmed with live reproductions.

### G1 (M). `endpoints_within_budget` charges cached endpoints against the budget

`endpoints_within_budget()` (`deterministic_research_collector.py:951-964`) accepts `cache_root`
and `refresh` but never uses them: the greedy trim charges every selected endpoint's full cost,
including endpoints whose reusable cache means no live call will be made. This is the same class
of bug as F1 (budget spent on a call that will never happen), but for cached endpoints instead
of suppressed prices — and F1's fix made the *estimate* cache-aware while leaving the *trim*
cache-blind, so the two now disagree.

Confirmed reproduction: alphavantage with a reusable cached `overview` (cost 10), suppressed
prices, budget 10. Cache-aware estimated cost is 18 (> 10), so the trim runs; the trim charges
the cached `overview` its full 10 and returns `{overview}` — the provider "fetches" only an
endpoint that is served from cache, making **zero** live calls, when budget 10 could have fetched
`income_statement` + `cash_flow` (or four cost-1 endpoints). Any provider with an expensive
cached endpoint early in `ENDPOINT_BUDGET_PRIORITY` wastes its whole budget this way.

Fix: in the trim loop, add a reusable-cached endpoint to `allowed` without charging its cost
(`if reusable_cached_raw(...): allowed.add(endpoint); continue`). Cached endpoints must stay in
the returned set — `fetch_provider` reuses their cache without a network call and
`effective_endpoint_plan` needs them for normalization — they just must not consume budget.
This uses the already-passed `cache_root`/`refresh` parameters, and keeps
`price_provider_to_live_fetch` consistent automatically since it calls the same function.

Tests: cached `overview` + `alphavantage=10` budget + suppressed prices → trimmed set contains
`overview` **and** the highest-priority uncached endpoints totalling ≤ 10
(`income_statement`, `cash_flow`); the "Limited …" warning path in `cmd_fetch` fetches those
endpoints (assert via the `fetch_provider` monkeypatch pattern used by the F1 test); a
plan-fetch case asserting `would_fetch_endpoints` excludes the cached endpoint but includes the
newly affordable ones.

### G2 (M). An endpoint filter naming a provider outside the run poisons price-provider selection

`parse_provider_endpoints()` (`deterministic_research_collector.py:919-931`) starts from
`default_endpoint_plan(providers)` but then sets `plan[provider] = requested` for **any**
provider named in a `--provider-endpoints` filter, silently adding providers that are not in the
run's `--providers` list. `price_provider_to_live_fetch()` iterates `PRICE_PROVIDER_PRIORITY`
against `endpoint_plan` without intersecting with `providers`, so the phantom provider can win
selection.

Confirmed reproduction: `plan-fetch AAPL --providers eodhd --provider-endpoints tiingo=prices`
(no cache) → tiingo is selected as the price fetch provider, eodhd reports
`price_fetch_suppressed: true` with `would_fetch_endpoints` lacking `prices` — but tiingo is
not in the run and never fetches. The run gets no live price series and no accurate warning.
`cmd_fetch` has the identical skew. The F3 opt-in mechanic makes `--provider-endpoints ...prices`
a documented workflow, so this misuse is now likelier to occur.

Fix: make `parse_provider_endpoints` `die()` when a filter names a provider not in the run's
provider list (mirroring the existing `die()` for unknown endpoints), e.g.
`Unknown provider in endpoint filter: tiingo (run providers: eodhd). Add it to --providers or
drop the filter.` After that guard, `endpoint_plan` keys are a subset of `providers` by
construction, so `price_provider_to_live_fetch` and `explicit_price_opt_ins` are automatically
scoped without extra intersection logic.

Tests: the reproduction above exits 2 with the clear message (both `fetch` and `plan-fetch`);
`--providers eodhd,tiingo --provider-endpoints tiingo=prices` keeps working.

### G3 (L). `market_snapshot` 52-week high/low lack the `available_history` label

L5 (prior plan) added `available_history` status to the 52-week fields in
`technicals_from_prices()` when fewer than 252 sessions exist, but
`normalize_market_snapshot()` (`deterministic_research_collector.py:1363-1364`) computes
`fifty_two_week_high`/`fifty_two_week_low` from the same `closes[-252:]` slice with an
unconditional `status="ok"`. A short-history symbol (recent IPO) publishes a
`market_snapshot.fifty_two_week_high` that implies a full 52-week range — and these fields are
`REQUIRED_FIELD_PATHS` in the usage contract, so the mislabel flows into report requirements.

Fix: mirror the technicals logic — `status="ok" if len(closes) >= 252 else "available_history"`
on both snapshot points. Test: extend the existing short-history fixture test to assert the
snapshot status alongside the technicals status.

### G4 (L). Usage-audit value matching over-matches short tokens and under-matches humanized numbers

`datapoint_reference_reasons()` / `value_tokens()` (`deterministic_data_usage.py:271-291`) use
plain substring containment against the lowercased report corpus:

- **Over-match:** a datapoint value like `8` (e.g. `analyst_rating_hold`) produces token `"8"`,
  which matches any digit 8 anywhere in the corpus — such datapoints are effectively always
  `narrative_used`, weakening the audit's teeth exactly where dispositions matter.
- **Under-match:** a companyfacts revenue of `391035000000` is only matched verbatim; a report
  that (correctly, per the memo style) writes "$391.0 billion" is scored `not_referenced` on the
  `value` reason.

Fix (two independent parts, both in `value_tokens`/`datapoint_reference_reasons`):

1. Match numeric tokens with digit-boundary regex instead of substring
   (`(?<![\d.])TOKEN(?![\d.])` on the escaped token), so `"8"` does not match inside `"1985"`
   or `"38.2"`. Keep non-numeric values on substring matching.
2. For `abs(value) >= 1_000_000`, add conservative humanized tokens: the value scaled to
   millions/billions/trillions rendered as `f"{scaled:.1f}"` and `f"{scaled:.2f}"` (and the
   integer form when exact), each matched with the same digit-boundary regex. `391035000000`
   then yields `391.0`ᵇ tokens that match "391.0 billion" / "$391.04b" phrasing without
   matching bare coincidental numbers, since the scaled decimal is specific.

This changes audit outcomes, so recalibrate expectations: run the audit tests and the acceptance
corpus; the F7 scalar-revenue test must still pass (verbatim value still matches). Add tests:
single-digit value in a corpus without that figure → `not_referenced`; revenue value with only
"391.0 billion" in the corpus → `narrative_used`.

### G5 (L). Budget-zero metrics entry reports `estimated_call_cost: 0`

In `cmd_fetch`, the budget-zero branch (`deterministic_research_collector.py:2354-2370`) records
`estimated_call_cost: 0` while the budget-skipped branch records the real estimate. Move the
`estimated_provider_call_cost` computation above the `budget <= 0` check and record it in that
branch too, so metrics consumers see what the provider would have cost regardless of which gate
skipped it.

### G6 (L). Repeated JSON parsing of large raw payloads per run

A fetch run parses each raw cache file many times: `collect_provider_status` runs once in
`cmd_fetch` and again inside `build_bundle` for the manifest; `copy_raw_files` re-reads
everything to copy it; each `normalize_*` function calls `read_raw_latest` on the same files
(SEC `companyfacts` — routinely several MB — is parsed by `normalize_identity`,
`normalize_equity_fundamentals`, `collect_provider_status` ×2, and `copy_raw_files` in a single
run). Functionally correct, but measurable seconds per bundle and pure waste.

Fix (keep it minimal): a module-level memo in the collector keyed by
`(resolved path, st_mtime_ns)` wrapped around the raw-payload reads
(`read_raw_latest`/`collect_provider_status`/`copy_raw_files`), returning the parsed payload.
No invalidation logic beyond the mtime key; writes go through `write_json` (atomic replace →
new mtime). Do **not** cache in `script_utils.read_json` itself — other scripts (validator,
loop) have different freshness expectations. Optionally, pass `cmd_fetch`'s computed `statuses`
into `build_bundle` to drop the duplicate `collect_provider_status` call, keeping the internal
call as the fallback for other entry points.

Tests: existing suite must pass unchanged (the memo must be transparent); one test that a
refreshed fetch (new file content, new mtime) is re-read.

## 3. Fix Plan

### Phase A — budget/scope correctness (G1, G2)

1. Make `endpoints_within_budget` cache-aware: reusable-cached endpoints join `allowed` at zero
   cost. Verify `price_provider_to_live_fetch` and `cmd_fetch`/`provider_fetch_plan` stay
   mutually consistent (they share the function — assert via the F1/F2 tests).
2. `parse_provider_endpoints`: `die()` on a filter naming a provider outside the run's provider
   list, with a message naming the provider, the run providers, and both remedies.
3. Update `provider-data-map.md` (budget bullet) and the 2026-07-03 maintainer note follow-up
   section in the same commit.

### Phase B — output quality (G3, G4)

1. `available_history` status on `market_snapshot.fifty_two_week_high`/`low` under 252 sessions.
2. Digit-boundary matching plus humanized-number tokens in the usage audit, with the
   recalibration tests described in G4.

### Phase C — polish and performance (G5, G6)

1. Record the real `estimated_call_cost` in the budget-zero metrics branch.
2. Mtime-keyed raw-payload memo in the collector; optionally thread `statuses` from `cmd_fetch`
   into `build_bundle`.

### Verification (each phase)

```bash
python3 -m pytest tests
python3 market-research/shared/scripts/deterministic_research_collector.py doctor
python3 market-research/shared/scripts/deterministic_research_collector.py plan-fetch AAPL --providers sec,tiingo,eodhd,alphavantage --as-of 2026-07-04 --data-dir ./data --reports-dir ./reports
python3 market-research/batch-supervisor/scripts/research_loop.py run-batch AAPL --run-root runtime/tmp-loop-smoke --dry-run
git status --porcelain  # must stay clean after the smoke commands
```

### Risks

- G1 changes which endpoints survive a trim, so `test_provider_plan_quality.py` and any metrics
  consumers observing `endpoints`/`would_fetch_endpoints` may need assertion updates in the same
  commit; note the behavior change in the PR description per `AGENTS.md`.
- G2 turns previously-silent misconfiguration into a hard error; if any documented workflow
  legitimately filters a non-run provider (none found in `docs/` or `references/`), prefer a
  warning-plus-ignore instead — decide once and document it.
- G4's humanized tokens loosen `narrative_used`; keep the scaled-decimal precision requirement
  (no bare integer-millions token below 10M) so a coincidental "391" in unrelated text cannot
  match, and re-run the acceptance corpus before merging.
- G6 is optional; skip it if the memo complicates test isolation (tests reload the module per
  test via `load_module()`, which naturally resets the memo).
