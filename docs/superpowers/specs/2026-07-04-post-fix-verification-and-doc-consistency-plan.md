# Fourth Review: Post-Fix Verification And Doc-Consistency Plan (2026-07-04)

Scope: verification of commits `43f8afb` (spec/self-improvement ignore-policy change) and
`9dce495` ("fix repo review follow-ups", J1–J5) on `fix/repo-review-20260703` against
`2026-07-04-usage-audit-token-context-and-suppression-reporting-fix-plan.md`, plus a fresh pass
over the changed code. Test suite state at review time: `python3 -m pytest tests` → **340
passed**. Tree clean; `doctor`, the four-provider `plan-fetch`, and `run-batch --dry-run` under
`runtime/tmp-loop-smoke` all pass without dirtying the tree.

## 1. Verification Of The J1–J5 Plan

All five findings are implemented, tested, and were re-verified against the original
reproductions:

- **J1** `humanized_scaled_tokens` now returns `(token, unit_pattern)` pairs
  (`HUMANIZED_SCALE_UNITS`: `trillion|tn|trn|t`, `billion|bn|b`, `million|mm|m`) and
  `value_referenced_in_corpus` requires the scale-appropriate unit word adjacent to the token;
  the rounded-integer token was added per scale (dropping the old `>= 10`/exact-integer
  conditions), so "$391 billion" now matches. Verbatim tokens are untouched. A 14-case probe
  confirmed every previously reported false positive is gone (a 20B value no longer matches
  "20.0%", "20 engineers", "20 basis points", or "on 20 May"; an 8B value no longer matches
  "8.0%"/"8000"; a 5M value no longer matches "5.0%") while "$391.0 billion", "$391 billion",
  "$391.04B", "20bn", "$1.5 billion", and the verbatim scalar all still match. Scale-paired
  units also prevent cross-scale confusion ("20 million" does not satisfy a 20B value). Four
  new tests cover the negative and positive cases; the original humanized and scalar tests
  still pass.
- **J2** the budget-zero branch keeps `reusable_cached_endpoints(...)` in
  `effective_endpoint_plan` (union with the suppressed-`prices` carve-out); the original
  reproduction now yields `endpoint_plan.eodhd == ["fundamentals", "prices"]` and the cached
  company name in the bundle. Metrics stay `fetch_attempted: False`, `endpoints: []`. The
  budget-skipped branch was correctly left alone (unreachable with cached endpoints under G1).
- **J3** `cmd_fetch`'s `price_suppressed` gained the own-cache guard
  (`and not reusable_cached_raw(..., "prices", ...)`); the misleading "already covers prices"
  warning is gone for own-cache providers and the new test asserts metrics parity with
  `provider_fetch_plan` for the same configuration. The guard is correctly inert under
  `--refresh` (a live fetch would then really be suppressed).
- **J4** `cmd_plan_fetch` exposes top-level `price_fetch_provider` and `warnings`, sharing
  `no_live_price_fetch_warning()` with `cmd_fetch`; both new tests pass and the live smoke
  shows `price_fetch_provider: tiingo, warnings: []`. New payload keys are additive; no
  consumer parses the plan-fetch payload strictly.
- **J5** `provider_call_estimate` in fetch metrics sums only `fetch_attempted` entries; the
  zero-budget test asserts the aggregate excludes the skipped provider's hypothetical cost.

The `provider-data-map.md` budget/price bullets and the maintainer note's third-pass section
document all five changes accurately.

**Policy change (43f8afb + docs)**: `tmp-loop-smoke/` and
`docs/superpowers/plans/self-improvement/` were deliberately removed from `.gitignore`, with
README/docs README/operations.md rewritten from "ignored local-only" to "may be committed on
active work branches", and `test_repository_layout.py` updated to *enforce* the new policy
(asserts the path is not ignored and the docs carry the new wording). Internally consistent.
The current smoke commands all use `runtime/tmp-loop-smoke` (already ignored), so dropping the
root-level ignore entry is safe; only the historical `2026-07-03` spec's verification block
still shows the bare `tmp-loop-smoke` path, which is acceptable in a point-in-time record.

## 2. New Findings

### K1 (L). `docs/README.md` still claims there are no active plans or specs

`docs/README.md:12` opens with "There are currently no active implementation plans or design
specs" — immediately before the sentence describing how such specs "may be committed on active
work branches". On this branch, four specs are committed under `docs/superpowers/specs/` and
are actively guiding work, so the claim is false exactly where the new policy makes it
possible. The sentence predates the policy change and was left behind when the paragraph was
rewritten in `9dce495`.

Fix: drop the sentence (or rephrase to point at the specs directory), e.g. replace
"There are currently no active implementation plans or design specs. New human-reviewed
plans/specs and generated self-improvement prompt outputs …" with
"Human-reviewed plans/specs and generated self-improvement prompt outputs under
`docs/superpowers/` may be committed on active work branches while they guide or document the
work, then should be deleted once implemented and summarized in canonical docs, maintainer
notes, or tests." No code change; `test_self_improvement_plan_history_policy_is_documented`
keeps passing since the "may be committed on active work branches" phrase is retained.

### Observations (no action planned)

- `plan-fetch`'s `provider_call_estimate` still sums every provider's unconstrained,
  cache-aware estimate (including budget-zero providers whose `would_fetch_endpoints` is
  empty), while fetch's aggregate is now attempted-only after J5. These have always measured
  slightly different things ("cost if unconstrained" vs "cost of attempted fetches"), and the
  per-provider fields carry the detail; not worth a schema change unless a consumer starts
  comparing the two aggregates directly.
- The humanized matcher intentionally does not handle comma-grouped humanized forms
  ("20,000 million") or truncated (rather than rounded) decimals ("391.03 billion" for
  391.035B). Both fail toward the safe side (`evidence_only_reference` at worst) and are rare
  phrasings; the field-name/field-path reasons still register such datapoints as referenced.

## 3. Fix Plan

Single phase: apply the K1 one-sentence rewrite to `docs/README.md`.

### Verification

```bash
python3 -m pytest tests/test_repository_layout.py -q
python3 -m pytest tests -q
git status --porcelain  # must stay clean
```

### Risks

None material — documentation-only; the layout-policy test pins the phrases that must survive
the rewrite.
