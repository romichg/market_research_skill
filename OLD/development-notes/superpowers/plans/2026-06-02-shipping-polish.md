# Shipping Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Polish the market research skill for wider use by adding retry/backoff, moving runtime output to `reports/`, updating loop/validation contracts, expanding deterministic schemas, and archiving old development artifacts.

**Architecture:** Keep the three existing skills (`market-research`, `validate-market-research`, `market-research-loop`). Treat `research_data.py` as the deterministic producer, validator as deterministic bundle lint plus judgment scaffold, and loop as the orchestrator for deterministic report directories.

**Tech Stack:** Python standard library, pytest, JSON Schema files as repository contracts.

---

### Task 1: Retry And Output Defaults

**Files:**
- Modify: `market-research/scripts/research_data.py`
- Modify: `tests/test_research_data.py`
- Modify: `.env.example`
- Modify: `.gitignore`

- [ ] Add failing tests for retrying 429/503/URLError with exponential backoff and for default output under `reports/`.
- [ ] Implement conservative retry/backoff with provider defaults and no secret leakage.
- [ ] Change default report output to `reports/` while keeping cache configurable.
- [ ] Run focused tests and full pytest.

### Task 2: Loop And Validator Contracts

**Files:**
- Modify: `market-research-loop/scripts/research_loop.py`
- Modify: `tests/test_research_loop.py`
- Modify: `validate-market-research/scripts/validate_market_research.py`
- Modify: `tests/test_validate_market_research.py`

- [ ] Add failing tests for deterministic bundle artifact detection and validation summaries.
- [ ] Update loop prompts to produce and validate deterministic report bundles under `reports/`.
- [ ] Ensure validator checks deterministic schema-facing fields without refetching providers.
- [ ] Run focused tests and full pytest.

### Task 3: Schema And Reporting Polish

**Files:**
- Modify: `market-research/schemas/research-output.schema.json`
- Create: `market-research/schemas/deterministic-bundle.schema.json`
- Modify: `market-research/references/report-template.md`
- Modify: `market-research/SKILL.md`
- Modify: `validate-market-research/SKILL.md`
- Modify: `market-research-loop/SKILL.md`

- [ ] Expand schemas for deterministic provenance, manifests, source manifests, gaps, normalized identity, market snapshot, prices, technicals, news, filings, fundamentals, and ETF placeholders.
- [ ] Update report outline to be facts-first and deterministic-output compatible.
- [ ] Update skill docs to describe shipping workflow, output names, validation, and loop operation.
- [ ] Run tests and schema sanity checks.

### Task 4: Archive Development Artifacts And Verify

**Files:**
- Move: `docs/superpowers/**` to `OLD/development-notes/superpowers/`
- Leave ignored/untracked runtime artifacts out of git.

- [ ] Move tracked development plans/specs under `OLD/development-notes/`.
- [ ] Confirm no tracked `experiments/`, `data/`, `.env`, `.env-starter`, or live report outputs.
- [ ] Run `python3 -m pytest tests`.
- [ ] Run `python3 market-research/scripts/research_data.py doctor --no-network`.
- [ ] Run a deterministic offline smoke bundle and validator if cached data exists.
