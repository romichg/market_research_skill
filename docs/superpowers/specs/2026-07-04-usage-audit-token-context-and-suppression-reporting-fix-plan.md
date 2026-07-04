# Third Follow-Up Review: Usage-Audit Token Context And Suppression-Reporting Fix Plan (2026-07-04)

Scope: verification of the uncommitted working tree on `fix/repo-review-20260703` against
`2026-07-04-budget-cache-trim-and-provider-scope-fix-plan.md` (G1–G6), plus a fresh review of the
changed code and its interplay with the rest of the collector and the usage audit. Test suite
state at review time: `python3 -m pytest tests` → **331 passed**.

## 1. Verification Of The G1–G6 Plan

All six findings are implemented and covered:

- **G1** `endpoints_within_budget` adds a reusable-cached endpoint to `allowed` at zero cost and
  keeps it in the returned set; `price_provider_to_live_fetch`, `cmd_fetch`, and
  `provider_fetch_plan` all share the function, so selection and trim stay mutually consistent.
  Covered by `test_endpoints_within_budget_keeps_cached_endpoint_free_of_charge`,
  `test_fetch_trims_to_cached_plus_affordable_uncached_endpoints`, the updated
  `test_budget_trimmed_endpoint_plan_controls_bundle_outputs` (bundle now normalizes the retained
  cached endpoint), and the plan-fetch case. The G1 premise that cached endpoints in the fetch
  set cost no live call was verified against `fetch_with_cache` (`reuse_endpoint_cache=True` on
  every endpoint) and the post-fetch `after - before > budget` guard (cache reuse adds no files).
- **G2** `parse_provider_endpoints` `die()`s (exit 2) on a filter naming a provider outside the
  run, with the promised message and remedies; plan keys are then a subset of `providers`, so
  `price_provider_to_live_fetch` and `explicit_price_opt_ins` are scoped for free (opt-ins are
  computed after the parse in both `cmd_fetch` and `cmd_plan_fetch`). Three tests cover fetch,
  plan-fetch, and the in-run provider still working.
- **G3** `normalize_market_snapshot` labels `fifty_two_week_high`/`low` with `available_history`
  under 252 sessions, mirroring `technicals_from_prices`; two new tests cover both statuses. The
  interaction with the usage contract was checked: datapoints are only collected when
  `status == "ok"` (`deterministic_data_usage.py:93-95`, same rule in the validator at
  `validate_market_research.py:406-408`), so short-history snapshots drop these fields from
  required dispositions exactly as the L5 technicals relabel already does — consistent, no
  validator breakage.
- **G4** digit-boundary matching implemented in `value_referenced_in_corpus` with the promised
  tests (single-digit non-match, verbatim scalar still matching, humanized billions matching).
  Bare "8" no longer matches inside "1985"/"38.2". **However, the humanized-token half
  reintroduces the over-match at a different point — see J1 below.**
- **G5** `estimated_call_cost` is computed before the budget gate and recorded in both the
  budget-zero and (newly added) budget-skipped metrics branches;
  `test_zero_budget_metrics_entry_records_real_estimated_cost` covers it. A side effect on the
  aggregate metric is J5 below.
- **G6** `read_raw_json` memoizes on `(resolved path, st_mtime_ns)`; `read_raw_latest`,
  `collect_provider_status`, and `copy_raw_files` route through it, and `copy_raw_files` copies
  `provider_result` before rewriting `raw_path`/`status` so the shared payload is not mutated.
  The mtime-invalidation test is present. A mutation audit of every `read_raw_latest` caller came
  up clean: `parse_price_rows` and all `normalize_*` functions build new dicts
  (`sorted(rows, ...)` returns a copy; the in-place sorts at
  `deterministic_research_collector.py:1858-1860` operate on freshly built limitation entries,
  not payloads). Other scripts keep the un-memoized `script_utils.read_json`, as the plan
  required. The optional threading of `statuses` into `build_bundle` was not done — acceptable;
  the memo makes the duplicate `collect_provider_status` cheap.

Verification commands were re-run: full pytest (331 passed), `doctor`, the four-provider
`plan-fetch` smoke, and `run-batch --dry-run` under `runtime/tmp-loop-smoke`; the tree stays
clean afterwards. Residual "codex" strings were re-audited: everything left is genuinely
Codex-specific (the default `codex exec` command template, the labeled README example, the
conditional-on-`codex`-CLI passages, and `research_loop.py:189` which branches on `--agent-cli`).

## 2. New Findings

Severity scale as in the prior reviews. J1, J2, and J3 were confirmed with live reproductions.

### J1 (M). Humanized scaled tokens match bare decimals, re-opening the G4 over-match for large values

`humanized_scaled_tokens()` (`deterministic_data_usage.py:151-169`) emits the scaled one- and
two-decimal renderings as standalone tokens, matched with digit boundaries but **without any
requirement that a magnitude word follows**. It also emits tokens for *every* scale the value
exceeds, not just the natural one. Since `usage_status_from_reasons` grants `narrative_used`
only on a "value" match, this directly inflates the audit's strongest signal.

Confirmed reproduction (via `value_referenced_in_corpus`):

- value `20_000_000_000` matches "revenue grew **20.0**% year over year" and "hired **20**
  engineers" (billion-scale tokens `20.0`/`20`, plus million-scale `20000.0`/`20000`);
- value `8_000_000_000` matches "margins improved **8.0**% while headcount reached **8000**";
- value `5_000_000` matches "a **5.0**% dividend yield".

One-decimal scaled tokens of any value in ~[1M, 100B) with ≤2 significant digits collide with
the percentage space (0.0–99.9) that saturates investor memos — a 5.2B shares-outstanding value
is marked `narrative_used` by any "5.2%" in the text. The `abs(scaled) >= 10` guard only
restricts the *integer* token; the decimal tokens it was meant to keep safe are the ones that
collide. There is also a residual under-match: "$391 billion" (rounded integer, non-exact scale)
still fails against `391035000000` because the integer token requires `scaled == int(scaled)`.

Fix (all in `humanized_scaled_tokens` / `value_referenced_in_corpus`; no external callers):

1. Match humanized tokens only when immediately followed by a scale-appropriate magnitude word:
   build per-scale patterns, e.g. for the 1e9 scale
   `rf"(?<!\d)(?<!\d\.){re.escape(token)}\s*(?:billion|bn|b)\b"` (corpus is already lowercased;
   analogous `trillion|tn|t` and `million|mm|m` for the other scales). "$391.0 billion",
   "391.04bn", "$391.04b" all still match; a bare "20.0%" or "8000" no longer does.
2. With the unit-word requirement in place, add the rounded-integer token
   `str(round(scaled))` for every scale (dropping the `scaled == int(scaled)` and `>= 10`
   conditions), so "$391 billion" and "20 billion" match. Rounding to zero decimals with a
   required unit word is specific enough.
3. Keep verbatim/`%g`/`.2f` tokens exactly as they are (digit-boundary, no unit word) — the F7
   scalar-revenue test must keep passing.

Tests: keep `test_usage_audit_matches_humanized_billion_revenue` green; add negative cases
(20B value vs "grew 20.0% and hired 20 engineers" → `not_referenced`; 8B vs "8.0% margin,
8000 employees" → `not_referenced`) and positive cases ("$391 billion" → `narrative_used`,
"20 billion" for 20B → `narrative_used`, "391.04bn" → `narrative_used`). Re-run the audit tests
plus any acceptance corpus before merging, as the G4 risk note required.

### J2 (L). Budget-zero branch drops a provider's free cached endpoints from the effective plan

In `cmd_fetch`'s budget-zero branch (`deterministic_research_collector.py:2400-2416`),
`effective_endpoint_plan[provider] = {"prices"} if price_suppressed else set()`. G1 established
that reusable-cached endpoints are free (no live call), and the same branch already keeps a
suppressed `prices` entry so cached-price normalization fallback works — but every *other*
cached endpoint of a budget-zero provider is dropped from normalization, despite costing
nothing.

Confirmed reproduction: eodhd with reusable cached `fundamentals`, `--max-provider-calls
eodhd=0`, tiingo configured → `manifest.endpoint_plan.eodhd == ["prices"]` (an endpoint with no
cache behind it) while the cached fundamentals are excluded; `identity.company_name` is absent
from the bundle even though the cache holds it. The kept-`prices`/dropped-`fundamentals` split
within one branch is incoherent, and there is a behavior discontinuity at zero: budget `1` keeps
the cached fundamentals (via the G1-aware trim), budget `0` discards it.

Fix (recommended): in the budget-zero branch, set
`effective_endpoint_plan[provider]` to the provider's reusable-cached endpoints
(`{e for e in endpoints if reusable_cached_raw(cache_root, symbol, provider, e, refresh=args.refresh)}`)
union the suppressed-`prices` carve-out; keep `endpoints: []` and `fetch_attempted: False` in
metrics since nothing is fetched. Alternative, if "budget 0 = exclude the provider's data
entirely" is the intended operator semantic: keep `set()` but drop the `{"prices"}` carve-out
too, and document that `--providers` is the exclusion mechanism while budget 0 also ignores
cache — decide once and record it in `provider-data-map.md`. The recommendation is the first
option: it matches G1's cached-endpoints-are-free principle and the existing prices carve-out.

Tests: budget-zero provider with cached fundamentals → bundle normalizes the cached data and
`endpoint_plan` lists it; metrics entry unchanged (`fetch_attempted: False`, `endpoints: []`).

### J3 (L). `fetch` and `plan-fetch` disagree on `price_fetch_suppressed` when the provider's own cache covers prices

`provider_fetch_plan` guards against misreporting a provider whose own cache covers `prices`
(`price_fetch_suppressed = suppress_prices and "prices" in selected and "prices" not in
cached_endpoints`, `deterministic_research_collector.py:2525-2531`), but `cmd_fetch`'s
`price_suppressed` (`:2387-2393`) has no such guard.

Confirmed reproduction: eodhd holds a reusable cached price series while tiingo (higher
priority, no cache) is selected → `fetch` emits "Skipped live daily-price fetch for eodhd:
tiingo already covers prices" and records `price_fetch_suppressed: true`, while `plan-fetch`
for the identical configuration reports `price_fetch_suppressed: false`. No functional harm
(the cost math is cache-aware either way and `prices` stays in the effective plan), but the two
commands' reporting contradicts each other for the same inputs.

Fix: add the own-cache guard to `cmd_fetch`'s `price_suppressed` — `and not
reusable_cached_raw(cache_root, symbol, provider, "prices", refresh=args.refresh)`. With
suppression off, `prices` stays in `chargeable_endpoints` at zero estimated cost (cache-aware
estimate), `fetch_provider` serves it from cache without a live call, the misleading warning
disappears, and metrics match plan-fetch.

Tests: seed a lower-priority provider's cached prices with a higher-priority provider selected;
assert the fetch metrics entry has `price_fetch_suppressed: false`, no "Skipped live
daily-price fetch" warning for that provider, no live price URL hit for it (monkeypatched
fetch), and parity with the plan-fetch flag.

### J4 (L). `plan-fetch` output has no "no live price fetch" surface, contradicting the maintainer note

The maintainer note (F2 follow-up section) says "`cmd_fetch`/`cmd_plan_fetch` record a 'No live
price fetch this run' warning", but `cmd_plan_fetch` (`deterministic_research_collector.py:2597-2604`)
computes `price_covered_by_cache` and then never uses it: the payload has no warning or
`price_fetch_provider` field at all. An operator dry-running a mis-budgeted configuration sees
only that no provider's `would_fetch_endpoints` contains `prices` — the condition F2 deemed too
implicit for `fetch` is still implicit in the planning tool meant to catch it beforehand.

Fix: add to the plan-fetch payload a top-level `price_fetch_provider` (string or null) and a
`warnings` list carrying the same "No live price fetch this run…" message under the same
condition as `cmd_fetch` (candidates exist, no selection, no cache). Update the maintainer note
if the field names differ from its wording.

Tests: plan-fetch with `tiingo=0`/`eodhd=1` (no cache) → payload warning present and
`price_fetch_provider` null; plan-fetch with an affordable provider → `price_fetch_provider`
set and no warning.

### J5 (L). `provider_call_estimate` aggregate now includes skipped providers' hypothetical costs

G5 records the would-be `estimated_call_cost` in the budget-zero branch, and the new
budget-skipped metrics entry does the same — but `cmd_fetch` sums every entry into
`provider_call_estimate` (`deterministic_research_collector.py:2518`). The aggregate previously
approximated "calls this run may make"; it now also counts providers that fetch nothing (a
budget-zero eodhd adds its full 12 to the total). Per-provider recording is what G5 wanted; the
aggregate inflation is a side effect.

Fix: sum only entries with `fetch_attempted` (`sum(item["estimated_call_cost"] for item in
provider_metrics if item["fetch_attempted"])`), keeping the per-provider entries as recorded.
Test: the G5 zero-budget test additionally asserts the aggregate excludes eodhd's 12.

### Non-issues checked

- Memo aliasing: no `read_raw_latest`/`read_raw_json` caller mutates the shared payload
  (`copy_raw_files` copies `provider_result`; `parse_price_rows`/`normalize_*` build new
  structures; `collect_provider_status` is read-only). Memo growth is bounded per process and
  each CLI invocation is a fresh process; tests reload the module, resetting the memo.
- Bool datapoint values no longer match "true"/"false" prose substrings
  (`value_referenced_in_corpus` rejects bools before the numeric branch) — an improvement, not
  a regression.
- The budget-skipped branch (`not budgeted_endpoints`) cannot strand cached endpoints: with G1,
  the trim returns cached endpoints for free, so the branch is only reachable when the provider
  has no reusable cache at all.
- `explicit_price_opt_ins` runs after `parse_provider_endpoints` in both commands, so the G2
  guard scopes opt-ins before they are read; an opt-in for an endpoint the provider lacks dies
  on the existing unknown-endpoint check.
- The G2 hard error also fires when `--providers` is omitted and defaults to configured
  providers (filtering an unconfigured provider now exits 2); the message names the run
  providers and both remedies, which covers that path.
- `price_provider_to_live_fetch`'s per-candidate cache check, budget skip, and trim fallback
  stay consistent with `cmd_fetch`'s per-provider math because both call the same
  estimate/trim functions on the same inputs (re-verified after G1).

## 3. Fix Plan

### Phase A — usage-audit precision (J1)

1. Rework `humanized_scaled_tokens` to return per-scale `(token, unit_pattern)` pairs and match
   them in `value_referenced_in_corpus` with the unit word required; add the rounded-integer
   token per scale; keep verbatim tokens unchanged.
2. Add the negative and positive tests listed in J1; re-run the full audit suite and the F7
   scalar test.

### Phase B — suppression and budget reporting consistency (J2, J3, J4, J5)

1. Budget-zero branch keeps reusable-cached endpoints in `effective_endpoint_plan` (or the
   documented alternative — decide once); test via the cached-fundamentals bundle.
2. Own-cache guard in `cmd_fetch`'s `price_suppressed`, with the parity test against plan-fetch.
3. `price_fetch_provider` + `warnings` in the plan-fetch payload; align the maintainer note's
   F2 follow-up wording.
4. Restrict `provider_call_estimate` to `fetch_attempted` entries; extend the G5 test.
5. Update `provider-data-map.md` (budget bullet: budget-zero cache retention; plan-fetch
   warning surface) and the 2026-07-03 maintainer note in the same commit.

### Verification (each phase)

```bash
python3 -m pytest tests
python3 market-research/shared/scripts/deterministic_research_collector.py doctor
python3 market-research/shared/scripts/deterministic_research_collector.py plan-fetch AAPL --providers sec,tiingo,eodhd,alphavantage --as-of 2026-07-04 --data-dir ./data --reports-dir ./reports
python3 market-research/batch-supervisor/scripts/research_loop.py run-batch AAPL --run-root runtime/tmp-loop-smoke --dry-run
git status --porcelain  # must stay clean after the smoke commands
```

### Risks

- J1 tightens `narrative_used`: reports that legitimately reference a humanized figure without a
  recognized unit word ("391 billion USD" is fine; "391.0B USD" is fine; a bare "391.0" in a
  table cell is not) will drop to `not_referenced` on the value reason. The field-name/field-path
  reasons still yield `evidence_only_reference`, so the audit degrades gracefully; re-run any
  acceptance corpus and adjust the unit-word list (`t|tn|trn|trillion`, `b|bn|billion`,
  `m|mm|million`) rather than loosening the adjacency requirement.
- J2's recommended option changes what a budget-zero provider contributes to a bundle (cached
  data reappears). If any operator relies on budget 0 to exclude *cached* data, choose the
  documented-exclusion alternative instead; either way note the behavior change in the PR
  description per `AGENTS.md`.
- J3 removes a warning some logs may grep for in the own-cache case; the warning remains for
  genuinely suppressed providers.
- J5 changes an aggregate metric consumers may chart; per-provider entries keep the full detail,
  so the change is a strict improvement in meaning — call it out in the PR description.
