# Follow-Up Review: Findings And Fix Plan (2026-07-04)

Scope: verification of branch `fix/repo-review-20260703` against
`2026-07-03-repo-review-findings-and-fix-plan.md`, plus a fresh review of the changed code and
the rest of the repo. Test suite state at review time: `python3 -m pytest tests` → **312 passed**.

## 1. Verification Of The 2026-07-03 Plan

All fourteen findings (H1–H3, M1–M7, L1–L5) are implemented and covered by tests:

- **H1** `normalize_identity()` now sets `identity["cik"]` from SEC submissions with a
  `company_tickers` fallback; `build_bundle()` emits `normalized/sec_filings_index.json`
  end-to-end (`test_build_bundle_emits_sec_filings_index_from_submissions`).
- **H2** implemented as the recommended option, at the fetch layer rather than the plan layer:
  `price_provider_to_live_fetch()` selects one live price provider; `cmd_fetch`/`plan-fetch`
  suppress the rest and record `price_fetch_suppressed`. `provider-data-map.md` and the
  maintainer note `docs/maintainer-notes/20260703-price-fetch-suppression-and-plan-normalize-split.md`
  document the plan-vs-fetch-vs-normalize split. Code, doc, and tests agree. (New edge cases in
  this logic are findings F1–F3 below.)
- **H3** `truncate_prices_at_as_of()` runs in `build_bundle()` before snapshot/technicals, with
  both the dropped-rows warning and `price_history_ends_before_as_of` manifest warning; rows are
  sorted before truncation so the string comparisons are safe.
- **M1** `read_http_error_body()` caches the body on the exception; classification survives the
  no-retry path (`test_sec_403_error_body_is_read_once_and_preserved`).
- **M2** `raise_for_auth_failures()` now embeds an exact `--offline --providers ...` recovery
  command built from providers with usable cache.
- **M3** `looks_rate_limited()` scans stderr plus the stdout tail only, and
  `run_shell_command` additionally requires a non-zero exit.
- **M4** lint patterns are word-boundary/context-scoped regexes; `saved` dropped; benign investor
  prose fixture test added. (`body` at `report_language_lint.py:103` is still live — used by the
  vendor-name check.)
- **M5** companyfacts DataPoints are scalar with sibling `tag`/`fiscal_year`/`period_end`/
  `filed_date`/`form` keys; schema updated.
- **M6** `write_env_example()` writes only on content change; `doctor` leaves the tree clean
  (verified by running it).
- **M7** EWW/Germany special case removed; ticker evidence is authoritative, name heuristic dropped.
- **L1–L5** frontmatter is agent-neutral, `{baseDir}` is fully gone (repo-root-relative paths
  everywhere), README brew command split, retired-run-root sentence replaced, `.replace` no-op
  removed, short-history technicals labeled `available_history`, helpers consolidated into
  `script_utils.py` with the `sys.path` guard added, and the sibling-roots assumption documented
  in `docs/architecture.md`.

Verification commands from the plan were re-run: full pytest, `doctor`, and the batch dry-run
smoke all pass.

Two tests promised by Phase 1 were not added (tracked as F7):

- SEC 403 classification **with** retries (descriptive UA path); only the no-retry path is tested.
- An end-to-end usage-audit test that a scalar companyfacts revenue value in a report corpus is
  recognized as `narrative_used` — the stated rationale for M5.

## 2. New Findings

Severity scale as in the prior review.

### F1 (M). Budget trimming runs before price suppression, so a never-fetched `prices` endpoint consumes budget

In `cmd_fetch` (`deterministic_research_collector.py:2312-2334`), `estimated_provider_call_cost`
and `endpoints_within_budget` are computed on the endpoint set that still includes `prices`, and
only afterwards is the suppressed `prices` endpoint discarded from `fetch_endpoints`.
`ENDPOINT_BUDGET_PRIORITY` puts `prices` **first** for `alphavantage` and `twelve_data`, so for a
suppressed provider the budget trimmer preferentially keeps the one endpoint that will never be
fetched.

Concrete failure: providers `tiingo,alphavantage`, no cache, `--max-provider-calls
alphavantage=1`. Tiingo is the selected price provider. Alpha Vantage's estimated cost exceeds 1,
`endpoints_within_budget` keeps `{prices}` (first in priority), suppression then discards it —
Alpha Vantage fetches **nothing**, although its budget of 1 could have fetched `overview`. A
provider can also be skipped outright ("estimated call cost exceeds budget") based on cost it
would never incur. `provider_fetch_plan` (plan-fetch) has the same skew: `estimated_call_cost`
and `limited_by_budget` include the suppressed price call, and the budget trim happens before
`would_fetch.discard("prices")`.

Fix: for a provider whose prices are suppressed, remove `prices` from the endpoint set **before**
cost estimation and budget trimming (in both `cmd_fetch` and `provider_fetch_plan`), while still
recording `price_fetch_suppressed` and keeping `prices` in `effective_endpoint_plan` for
normalization. Tests: suppressed provider with budget 1 fetches its highest-priority
non-price endpoint; plan-fetch `estimated_call_cost`/`limited_by_budget` exclude suppressed
prices.

### F2 (M). Selected price provider can drop out after selection, leaving no live price fetch and misleading warnings

`price_fetch_provider` is chosen once, before the per-provider loop (line 2289). If that
provider is then skipped by budget (`budget <= 0`, or trimmed to an endpoint set without
`prices`), no other provider fetches prices — every other price provider was already suppressed
with the warning "`<selected>` already covers prices", which is now false. Combined with the
documented trade-off (no cross-provider fallback on a failed live fetch), a mis-budgeted run
silently produces a bundle with no price series.

Fix: after computing each provider's budgeted endpoints, re-evaluate the selection — if the
selected provider will not actually fetch `prices`, promote the next planned price provider
(or at minimum replace the suppression warnings with an accurate
"no live price fetch this run" warning). Test: `tiingo` budget 0 with `eodhd` configured →
either eodhd fetches prices or the manifest warns that no provider fetched prices.

### F3 (L). Explicit `--provider-endpoints PROVIDER=prices` is silently suppressed

`parse_provider_endpoints` replaces only the named provider's endpoint set; higher-priority
providers keep their default plan (including `prices`). So
`--provider-endpoints eodhd=prices` with Tiingo configured still selects Tiingo and suppresses
the explicitly requested EODHD price call. `provider-data-map.md` promises lower-priority price
series are fetched when a higher-priority provider is "explicitly excluded via
`--providers`/`--provider-endpoints`" — exclusion works, but explicit *inclusion* of a
lower-priority price endpoint does not opt in.

Fix (pick one, keep doc in sync): treat an explicit `PROVIDER=...prices...` filter as opting that
provider into live price fetching alongside/instead of the default selection; or emit a distinct
warning that the explicit request was suppressed and how to honor it (exclude prices from the
higher-priority provider's endpoint filter).

### F4 (L). `.gitignore` regression: documented smoke command now dirties the tree

Commit `1e35b1f` removed `tmp-loop-smoke/` from `.gitignore`, but the prior plan's verification
section (and operator habit) still uses
`research_loop.py run-batch AAPL --run-root tmp-loop-smoke --dry-run`, which creates
`tmp-loop-smoke/` at the repo root as untracked noise. Restore the ignore entry, or change the
documented smoke command to a path under an already-ignored root (e.g. `runtime/tmp-loop-smoke`).

### F5 (L). Helper consolidation (L4) is incomplete

`script_utils.py` now owns `die`/`utc_now`/`nested_get`/`latest_companyfacts_usd_fact`, but three
scripts still define local copies instead of importing them:

- `validate_market_research.py:19-26` — `utc_now`, `die`
- `producer_self_check.py:20` — `utc_now`
- `research_loop.py:93` — `die`

Replace with `script_utils` imports (research_loop already inserts `shared/scripts` on
`sys.path`).

### F6 (L). `provider_metrics` entries have inconsistent shape

`price_fetch_suppressed` appears only in the fetched-provider branch of `cmd_fetch`; the
budget-zero, budget-skipped, and offline branches omit the key. Consumers must `.get()` it.
Add the key (value `False`) to the other branches for a uniform metrics schema.

### F7 (L). Tests promised by the prior plan are missing

- SEC 403 rate-threshold classification when retries are attempted (descriptive UA →
  `should_retry` True, retries exhausted): assert the final saved raw artifact still carries
  `rate_limited` and the body snippet.
- Usage-audit end-to-end: a report corpus containing the scalar companyfacts revenue value is
  recognized (`datapoint_reference_reasons` → `"value"`, `usage_status` → `narrative_used`),
  which was the motivating consequence of M5.

### F8 (L). Residual "Codex" wording outside frontmatter

L1 covered the three `SKILL.md` descriptions, but agent-specific wording remains in
agent-neutral surfaces:

- `research_loop.py:46` — generated prompt heading "## Child Codex Command Issues" (emitted
  regardless of `--agent-cli`).
- `research_loop.py:532` — self-improvement prompt "…in this Codex session."
- `procedural_source_helper.py:743` — argparse description "…for the Codex market-research skill."
- `docs/operations.md:118`, `supervisor-workflow.md:72`, `README.md:200` — "run in/inside Codex"
  where "your agent session" is meant.

`market-research/batch-supervisor/agents/openai.yaml` and the README's labeled "Codex example"
are legitimately Codex-specific and should stay. `research_loop.py:194` already branches on
`--agent-cli`; reuse that mechanism or use neutral wording for the unconditional strings.

### F9 (L). Auth-failure recovery command does not carry custom cache/runtime dirs

The recovery command built in `cmd_fetch` (lines 2370-2376) includes `--data-dir`/`--reports-dir`
but not `--cache-dir`/`--runtime-dir`. With a custom `--cache-dir` outside the data root, the
suggested offline rerun would look in the wrong cache. Paths are also unquoted (breaks on
spaces). Propagate the flags the user passed and quote with `shlex.quote`.

### Non-issues checked

- `body` in `lint_report_language` is not dead code (used by the vendor-name scan).
- Price rows are sorted before `truncate_prices_at_as_of`, so string-date comparison and the
  `prices[-1]["date"] < as_of` staleness check are sound.
- `identity["cik"]` provenance-dict shape is handled at the `emit_sec_filings_index` call site
  (`.get("cik", {}).get("value")` with an isinstance guard).
- `docs/superpowers/specs/` is allowlisted in `test_repository_layout.py`, so this document does
  not break the layout test.
- Suppression keeps `prices` in `effective_endpoint_plan`, so cached-price normalization
  fallback works as the maintainer note describes.

## 3. Fix Plan

### Phase A — price-suppression correctness (F1, F2, F3)

1. In `cmd_fetch`, compute per-provider suppression first, derive `fetch_endpoints`
   (= planned endpoints minus suppressed prices), and run `estimated_provider_call_cost` /
   `endpoints_within_budget` on `fetch_endpoints`. Keep `effective_endpoint_plan` as
   planned endpoints (prices retained for normalization). Mirror the same ordering in
   `provider_fetch_plan`.
2. After budget gating, verify the selected price provider still fetches `prices`; otherwise
   promote the next planned price provider or emit an accurate "no live price fetch this run"
   warning (replacing the per-provider "already covers prices" text for that run).
3. Decide and implement the explicit-endpoint policy for F3; update `provider-data-map.md`
   and the maintainer note in the same commit.

Tests: budgeted suppressed provider fetches non-price endpoints (F1); plan-fetch cost excludes
suppressed prices (F1); budget-zero selected provider promotes or warns accurately (F2);
explicit `eodhd=prices` behavior matches the documented policy (F3).

### Phase B — hygiene and consistency (F4, F5, F6, F9)

1. Restore `tmp-loop-smoke/` to `.gitignore` (or repoint the documented smoke command).
2. Import `die`/`utc_now` from `script_utils` in `validate_market_research.py`,
   `producer_self_check.py`, `research_loop.py`; delete local copies.
3. Add `price_fetch_suppressed: False` to the non-fetch `provider_metrics` branches.
4. Extend the recovery command with the user's `--cache-dir`/`--runtime-dir` when set and
   quote all paths.

### Phase C — test debt and wording (F7, F8)

1. Add the two missing Phase-1 tests (SEC 403 with retries; usage-audit scalar revenue match).
2. Neutralize the unconditional "Codex" strings listed in F8, leaving genuinely Codex-specific
   files untouched.

### Verification (each phase)

```bash
python3 -m pytest tests
python3 market-research/shared/scripts/deterministic_research_collector.py doctor
python3 market-research/shared/scripts/deterministic_research_collector.py plan-fetch AAPL --providers sec,tiingo,eodhd,alphavantage --as-of 2026-07-04 --data-dir ./data --reports-dir ./reports
python3 market-research/batch-supervisor/scripts/research_loop.py run-batch AAPL --run-root runtime/tmp-loop-smoke --dry-run
git status --porcelain  # must stay clean after the smoke commands
```

### Risks

- Phase A reorders budget math that `test_provider_plan_quality.py` and metrics consumers
  observe; update assertions in the same commit and note the behavior change in the PR
  description per `AGENTS.md`.
- F2's promotion option re-adds a live price call in narrow cases; if quota conservatism is
  preferred, choose the warning-only option and document it in the maintainer note.
