# Repository Review: Findings And Fix Plan (2026-07-03)

Reviewer scope: full repo — skill intent, prompt files (`SKILL.md` + references), helper scripts,
deterministic fetch behavior, batch orchestration, tests, and docs. Test suite state at review
time: `python3 -m pytest tests` → **300 passed**.

## 1. Intent Of The Skill (as understood)

A portable Agent Skills-format package (`market-research/`) for researching US-listed equities,
ADRs, and ETFs with three modes routed by the top-level `SKILL.md`:

- **researcher** — produces one evidence-backed bundle per symbol: deterministic provider data
  first (`deterministic_research_collector.py`, cache-first, budget-aware, provenance-preserving),
  targeted procedural capture second (`procedural_source_helper.py`), then an investor-grade
  Markdown report + JSON sidecar + best-effort PDF under `reports/SYMBOL/AS_OF/`.
- **verifier** — fresh-context validation of frozen artifacts: deterministic lint scaffold via
  `validate_market_research.py`, then judgment validation; never edits producer output.
- **batch-supervisor** — `research_loop.py` orchestrates producer → self-check → verifier →
  remediation child sessions with a no-open-critical/moderate gate, plus prompt-only
  self-improvement packaging.

Cross-cutting invariants: three artifact roots (`data/` deterministic evidence, `reports/` final
deliverables, `runtime/` transient work), field-level provenance on every normalized value,
deterministic-data-usage dispositions as a producer contract, and "investor memo, not audit
trail" report language enforced by `report_language_lint.py`.

The design is coherent and the invariants are well-enforced by tests. The findings below are
gaps between the documented contract and what the code actually does, plus robustness and
consistency issues.

## 2. Findings

Severity: **H** = behavior contradicts the documented contract or silently loses evidence;
**M** = robustness/correctness edge or quota waste; **L** = polish, consistency, docs.

### H1. `sec_filings_index.json` is never emitted (dead wiring)

`deterministic_research_collector.py:1897` gates emission on `identity["cik"]`, but
`normalize_identity()` (lines 961–1053) never sets a `cik` key, so
`emit_sec_filings_index()` is dead code in real runs. The function itself is unit-tested
directly (`tests/test_deterministic_research_collector.py:2069`), which hides the wiring bug.

Impact: the deterministic bundle schema, `provider-data-map.md`, and the verifier workflow all
advertise `normalized/sec_filings_index.json`; researcher workflow step 6 (same-day SEC
freshness checks) loses its deterministic filing index; validators see a permanently absent
artifact.

Fix: populate `identity["cik"]` in `normalize_identity()` — from the SEC submissions payload
(`data["cik"]`) with `cik_from_cached_tickers()` as fallback — with normal provenance. Add an
end-to-end test that a bundle built from cached SEC submissions contains
`normalized/sec_filings_index.json`.

### H2. Default endpoint plan live-fetches daily prices from all four price providers

`default_endpoint_plan()` (`deterministic_research_collector.py:833`) adds `"prices"` for every
provider in `PRICE_PROVIDER_PRIORITY` present, and `cmd_fetch` fetches everything in the plan.
With all providers configured, a fresh run pulls duplicate daily price history from Tiingo,
EODHD, Alpha Vantage, and Twelve Data, then `normalize_prices()` uses only the first
successful one.

This contradicts `provider-data-map.md` ("EODHD fundamentals/news … **without EOD prices**,
Alpha Vantage … **without adjusted daily prices**, Twelve Data quote/profile **without time
series**; Twelve Data prices are a **fallback** when no higher-priority configured price
provider is selected") and wastes scarce quota (EODHD free ≈ 20 calls/day, Alpha Vantage ≈ 25).
Note `tests/test_provider_plan_quality.py:17` currently asserts the all-providers behavior, so
this is a deliberate decision point, not an accidental one — but code and doc disagree either way.

Fix (recommended): keep fallback prices *plan-eligible for normalization from cache*, but
live-fetch prices only from the highest-priority configured provider that lacks a reusable
cached response. Alternatively, update `provider-data-map.md` to describe the
fetch-everything behavior. Whichever direction, code, doc, and test must agree.

### H3. Bundle `as_of` is not enforced on normalized prices (look-ahead leak)

Raw price cache is reused across `as_of` dates by design, but `normalize_prices()` /
`technicals_from_prices()` never truncate rows at the requested `as_of`. Rebuilding a bundle
for a past `as_of` from a newer cache silently includes future price rows in
`prices_daily.json`, SMAs, returns, and 52-week ranges — breaking the reproducibility story
("as of" no longer means as-of).

Fix: filter `rows` to `date <= as_of` in `build_bundle()` before snapshot/technical
computation, and record in the manifest when cached rows end before `as_of` (stale) so the
researcher can disclose it.

### M1. SEC 403 error body is consumed twice → misclassification

`should_retry()` (`deterministic_research_collector.py:635`) calls `exc.read(4096)` for SEC
403s. When the request is not retried and the exception propagates, `fetch_with_cache()`
(line 677) calls `exc.read(4096)` again on the already-drained `HTTPError`, getting an empty
body. Result: a "Request Rate Threshold Exceeded" 403 with a browser-like UA is stored as
generic `unauthorized`/`HTTP 403` with no title and no `error_body_snippet`, defeating the
troubleshooting path documented in the README.

Fix: read the body once (e.g., cache it on the exception or restructure so classification
happens in one place) and pass the classified status/body through.

### M2. `fetch` aborts the whole bundle on any provider auth failure

`raise_for_auth_failures()` runs after all providers were fetched and `die()`s before
`build_bundle()`. One bad key throws away an otherwise complete multi-provider collection run
(the raw cache survives, but no bundle/manifest is written, and the operator must know to
rerun `--offline`). The workflow docs treat this as expected, but it is a sharp edge.

Fix (design decision): still build the bundle with a prominent manifest error and exit
non-zero, or at least include the exact `--offline` recovery command in the error message.

### M3. Producer-status "rate_limited" detection can false-positive

`looks_rate_limited()` (`research_loop.py:64`) substring-scans child stdout/stderr. Market
research children legitimately print phrases like "rate limit" when describing provider
budgets, so a failed producer can be mislabeled `producer_rate_limited`. Only affects failure
labeling, but the label drives operator triage.

Fix: restrict the scan to stderr and/or the tail of output, or require the child exit code to
be non-zero plus a signature match near known CLI error formats.

### M4. Report-language lint patterns are too broad

`FORBIDDEN_MAIN_BODY_PATTERNS` in `report_language_lint.py` includes bare substrings
`"saved"`, `"provider"`, `"artifact"`, `"normalized"`, `"data/"`. Ordinary investor prose —
"healthcare provider", "saved costs", "normalized earnings" — triggers findings. Severity is
minor (non-blocking) but this trains agents to either ignore lint or contort wording.

Fix: use word-boundary regexes and narrow the domain terms (e.g., `provider` only when
adjacent to data/API/vendor context; drop `saved`; `normalized` only as `normalized/` path or
"normalized artifact").

### M5. SEC companyfacts values are dict-valued DataPoints

`normalize_equity_fundamentals()` stores the whole fact dict (`{tag, value, fy, period_end,
filed, form}`) as the DataPoint `value` for `revenue`/`net_income`. Every other DataPoint value
is scalar. Consequences: the deterministic-usage audit's `value_tokens()` can never match the
report corpus (these required fields are effectively always "not referenced" by value), and
consumers must special-case the shape.

Fix: store the scalar `val` as `value`; carry `tag`/`fy`/`period_end`/`filed`/`form` as sibling
keys on the provenance point. Update the bundle schema and tests accordingly.

### M6. `doctor` silently rewrites `.env.example`

`cmd_doctor()` calls `write_env_example()` unconditionally — a diagnostic command mutating a
tracked repo file is surprising and can produce noise in `git status` (or clobber intentional
template edits).

Fix: write only when content differs, or move regeneration behind an explicit flag
(`doctor --write-env-example`).

### M7. Hardcoded EWW/Germany special case in identity validation

`validate_blackrock_product_identity()` (`procedural_source_helper.py:695`) contains
`if expected == "EWW" and any("germany" in name...)`. This is a fossilized single-incident
patch; it does nothing for the identical failure with any other ticker.

Fix: generalize — when the payload exposes a ticker, the ticker check already covers it; for
name-only payloads, compare a country/index keyword derived from the requested fund (or drop
the name heuristic and require ticker evidence, recording a source gap otherwise).

### L1. Portability wording: "Codex" baked into prompt frontmatter

The repo claims portability (Codex, Claude Code, OpenClaw), but researcher `SKILL.md`
description says "Use when **Codex** is asked …", verifier description says "in a fresh
**Codex** context", and batch-supervisor says "fresh **Codex** contexts". Frontmatter
descriptions drive skill triggering in some agents; agent-specific naming weakens matching
elsewhere.

Fix: agent-neutral wording ("Use when the agent is asked…", "in a fresh agent context").

### L2. `{baseDir}` placeholder is used but never defined

`researcher-workflow.md` and `verifier-workflow.md` use `{baseDir}/../shared/scripts/...` in
commands; nothing in the repo defines `{baseDir}` and the Agent Skills spec linked in the
README does not guarantee substitution. Meanwhile the batch-supervisor prompts use repo-root
relative paths (`market-research/shared/scripts/...`), and researcher `SKILL.md` uses
`../shared/scripts/...`. Three conventions for the same paths.

Fix: standardize on repo-root-relative paths (matching the generated prompts), or add one
line defining how `{baseDir}` is to be interpreted by agents that do not substitute it.

### L3. Doc/template nits

- `report-template.md` JSON example uses `"report_section": "Market Snapshot Or Lifecycle
  Context"` — not a heading in the template ("Market Snapshot And Technical Analysis").
- README macOS install: `brew install pandoc --cask mactex-no-gui` is one malformed command;
  should be `brew install pandoc` and `brew install --cask mactex-no-gui`.
- `market-research/SKILL.md`: "Do not write new artifacts to the retired run-root name used
  before this rework" never names the retired root — unactionable for a fresh agent; name it
  or delete the sentence.
- `validate_market_research.py:356` `.replace("_", "_")` is a no-op.
- 52-week high/low and `average_volume_90` are computed and labeled even when fewer than
  252/90 rows exist; label as "available-history" or mark `insufficient_data` below threshold.
- `technicals_from_prices()` inner `point(name, value, …)` ignores `name` — drop the arg.

### L4. Code duplication across helpers

`latest_companyfacts_usd_fact()` + `nested_get()` are duplicated verbatim in
`deterministic_research_collector.py` and `procedural_source_helper.py`; `die()`/`utc_now()`
are re-defined in most scripts despite `script_utils`. Also `procedural_source_helper.py` is
the only script that imports siblings without the `sys.path.insert` guard (works when run as a
script; breaks module import from another cwd).

Fix: consolidate into `script_utils.py`; add the path guard for consistency.

### L5. Repo-root inference by fixed depth

`validate_market_research.py` (`sibling_report_json_for_data_bundle`,
`default_output_prefix`) and `source_registry_reconcile.py` derive the repo root as
`path.parent.parent.parent`. Canonical-layout enforcement makes this mostly safe, but it
silently misbehaves when `RESEARCH_DATA_DIR`/`RESEARCH_REPORTS_DIR` point at non-sibling
locations. At minimum document that data/reports/runtime must be siblings; better, resolve
against the configured roots when available.

### Non-issues verified during review

- Secrets hygiene: raw cache URLs store token-free `source_url`; `redact()` is applied to
  manifests and CLI output; `assert_no_secrets_in_tree()` guards the bundle; `.env` is
  gitignored and untracked.
- Scaffold/validation overwrite protection, canonical-path gating, and the batch pass gate
  behave as documented and are well-tested.
- `md-to-pdf.sh` degrades gracefully with structured status JSON, as documented.
- Cache key/glob namespaces per provider endpoint do not collide.

## 3. Fix Plan

### Phase 1 — contract restorations (H1, H3, M1, M5)

1. `normalize_identity()`: add `cik` provenance point (SEC submissions payload first,
   `cik_from_cached_tickers()` fallback). Keep `emit_sec_filings_index()` call sites unchanged.
2. `build_bundle()`: truncate price rows at `as_of` before snapshot/technicals; add manifest
   warning `price_history_ends_before_as_of` when cache is short.
3. Restructure SEC 403 handling so the HTTPError body is read exactly once; preserve
   `error_body_snippet` and rate-limit-title classification in the saved raw artifact.
4. Flatten companyfacts DataPoint values to scalars with sibling metadata keys; update
   `deterministic-bundle.schema.json`.

Tests to add: end-to-end `sec_filings_index.json` emission from cached submissions; bundle
rebuild at earlier `as_of` excludes newer cached rows; simulated SEC 403 with
rate-threshold HTML body classifies `rate_limited` both with and without retries; usage audit
recognizes companyfacts revenue value in a report corpus.

### Phase 2 — quota and orchestration behavior (H2, M2, M3)

1. Decide the price-fallback policy (recommended: live-fetch prices from the top configured
   priority provider only; others normalize-from-cache). Update
   `default_endpoint_plan()`/`cmd_fetch`, `provider-data-map.md`, and
   `tests/test_provider_plan_quality.py` together so all three agree.
2. Auth failure path: either build-then-fail or embed the exact `--offline` recovery command
   in the `die()` message.
3. Tighten `looks_rate_limited()` (stderr/tail scoping + non-zero exit requirement).

### Phase 3 — lint precision and helper hygiene (M4, M6, M7, L4)

1. Convert `FORBIDDEN_MAIN_BODY_PATTERNS` to word-boundary regexes; drop/narrow `saved`,
   `provider`, `normalized`. Add fixture-based tests with benign investor prose that must not
   trigger findings.
2. `doctor`: write `.env.example` only on content change (or behind a flag).
3. Generalize/remove the EWW special case in BlackRock identity validation.
4. Move `latest_companyfacts_usd_fact`, `nested_get`, `die`, `utc_now` into `script_utils.py`;
   add the `sys.path` guard to `procedural_source_helper.py`.

### Phase 4 — prompt and doc consistency (L1, L2, L3, L5)

1. Agent-neutral frontmatter descriptions in the three mode `SKILL.md` files.
2. Standardize script paths across `SKILL.md` files and references (repo-root relative,
   matching the prompts `research_loop.py` generates); remove or define `{baseDir}`.
3. Fix README brew command; name or delete the "retired run-root" sentence; fix the
   `report_section` example; remove the `.replace("_", "_")` no-op; label short-history
   technicals honestly.
4. Document the sibling-roots assumption for `data/`/`reports/`/`runtime/` in
   `docs/architecture.md` (or resolve from configured roots).

### Verification (each phase)

```bash
python3 -m pytest tests
python3 market-research/shared/scripts/deterministic_research_collector.py doctor
python3 market-research/shared/scripts/deterministic_research_collector.py fetch AAPL --offline --as-of 2026-07-03 --data-dir ./data --reports-dir ./reports  # with fixture cache
python3 market-research/batch-supervisor/scripts/research_loop.py run-batch AAPL --run-root tmp-loop-smoke --dry-run
```

### Risks

- Phase 1 item 4 (scalar companyfacts values) and Phase 2 item 1 (price plan) change artifact
  shape/behavior that existing tests assert; update tests in the same commit and note the
  contract change in the PR description per `AGENTS.md`.
- Lint-pattern tightening may un-flag reports that previously failed; re-run lint against any
  retained sample reports before relying on new thresholds.
