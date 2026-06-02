# Deterministic Market Research Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a cache-first deterministic data collector to the existing `market-research` skill without creating a separate project.

**Architecture:** Keep KISS: one new focused CLI helper, `market-research/scripts/research_data.py`, plus small validator enhancements. The new helper loads `.env-starter`/`.env`, redacts secrets, fetches official/public API data into raw cache, normalizes source-backed fields, computes local analytics from daily prices, writes an output bundle, and supports offline rebuilds from cache.

**Tech Stack:** Python standard library first; optional live HTTP through `urllib.request`; pytest with mocked local fixtures for tests.

---

### Task 1: Environment, Redaction, and Cache Primitives

**Files:**
- Create: `market-research/scripts/research_data.py`
- Create: `tests/test_research_data.py`
- Modify: `.gitignore`
- Create: `.env.example`

- [ ] Write failing tests for `.env-starter` parsing, secret redaction, provider detection, and stable cache key generation.
- [ ] Run: `python -m pytest tests/test_research_data.py -v`; expected failure from missing module/functions.
- [ ] Implement `load_env_files`, `redact`, `configured_providers`, `cache_key`, raw JSON read/write, and `.env.example` generation.
- [ ] Run: `python -m pytest tests/test_research_data.py -v`; expected pass.
- [ ] Commit: `git add .gitignore .env.example market-research/scripts/research_data.py tests/test_research_data.py && git commit -m "add deterministic research data env and cache core"`.

### Task 2: Offline Bundle Normalization and Analytics

**Files:**
- Modify: `market-research/scripts/research_data.py`
- Modify: `tests/test_research_data.py`

- [ ] Write failing tests for offline rebuild from cached identity, fundamentals, and daily price JSON fixtures.
- [ ] Include assertions for provenance on normalized values, gaps for unavailable fields, technical metrics, and no secrets in output files.
- [ ] Run focused pytest and verify expected failures.
- [ ] Implement bundle paths under `data/output/{SYMBOL}/{AS_OF}/`, normalized JSON, daily price JSON, technical metrics, source manifest, gaps, manifest, and `research_input_pack.md`.
- [ ] Run focused pytest and full existing pytest.
- [ ] Commit: `git add market-research/scripts/research_data.py tests/test_research_data.py && git commit -m "add deterministic offline research bundle builder"`.

### Task 3: Live Provider Fetching With Budgets

**Files:**
- Modify: `market-research/scripts/research_data.py`
- Modify: `tests/test_research_data.py`

- [ ] Write failing tests for provider URL construction and `--max-provider-calls PROVIDER=N` enforcement.
- [ ] Implement conservative fetchers for SEC company tickers/submissions/companyfacts, Tiingo daily prices, EODHD fundamentals and EOD prices, Alpha Vantage overview/time series, Twelve Data time series, and MarketAux news.
- [ ] Cache raw responses before normalization, redact tokens from manifests, and support `fetch --providers`, `--offline`, and `--refresh`.
- [ ] Run focused pytest and full existing pytest.
- [ ] Commit: `git add market-research/scripts/research_data.py tests/test_research_data.py && git commit -m "add live deterministic provider fetches"`.

### Task 4: Validator Enhancement

**Files:**
- Modify: `validate-market-research/scripts/validate_market_research.py`
- Modify: `tests/test_validate_market_research.py`

- [ ] Write failing tests where validator discovers `research_input_pack.md`, `manifest.json`, `source_manifest.json`, `gaps.json`, and normalized deterministic files.
- [ ] Assert validator flags normalized data points without provenance and missing raw paths, and does not require/refetch provider data.
- [ ] Implement deterministic output bundle validation while retaining old report validation support.
- [ ] Run validator tests and full pytest.
- [ ] Commit: `git add validate-market-research/scripts/validate_market_research.py tests/test_validate_market_research.py && git commit -m "validate deterministic research data bundles"`.

### Task 5: Skill Docs, Live Smoke Runs, and Final Verification

**Files:**
- Modify: `market-research/SKILL.md`
- Modify: `validate-market-research/SKILL.md`
- Modify: `AGENTS.md` if needed

- [ ] Update skill docs with `research_data.py doctor`, `fetch`, offline rebuild, and validation expectations.
- [ ] Run `python -m pytest tests`.
- [ ] Run `python market-research/scripts/research_data.py doctor`.
- [ ] Run limited live fetches for `AAPL`, `TSM`, `SPY`, `VTI`, and `VUG` with conservative provider budgets.
- [ ] Run offline rebuild for at least one symbol.
- [ ] Run validator against at least one deterministic bundle.
- [ ] Commit docs and any final fixes.
