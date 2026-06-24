# Skill Token And Helper Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce always-loaded market-research instruction cost first, then deduplicate deterministic-data usage audit helper logic without lowering report quality.

**Architecture:** Phase 1 keeps behavior unchanged by moving detailed researcher command guidance into a conditional reference and shortening `researcher/SKILL.md` to route agents to the right references. Phase 2 makes `validate_market_research.py` call the shared `deterministic_data_usage.py` audit implementation instead of carrying duplicate local functions.

**Tech Stack:** Markdown Agent Skills files, Python 3 standard library, pytest.

---

## Task 1: Instruction Routing And Token Reduction

**Files:**
- Modify: `market-research/researcher/SKILL.md`
- Create: `market-research/researcher/references/researcher-workflow.md`
- Modify: `tests/test_market_research_acceptance.py`

- [ ] Move detailed deterministic/procedural command examples and final artifact workflow from `market-research/researcher/SKILL.md` into `market-research/researcher/references/researcher-workflow.md`.
- [ ] Keep `market-research/researcher/SKILL.md` as a compact required workflow: core rule, resource routing, artifact roots, mandatory quality gates, source discipline, and final output rule.
- [ ] Ensure `researcher/SKILL.md` tells agents to read `references/researcher-workflow.md` for command examples and operational detail.
- [ ] Preserve current report-quality, deterministic-data-usage, source-discipline, PDF best-effort, and paid-data requirements.
- [ ] Add or adjust tests so the researcher skill references the workflow detail file and the detail file contains the quota-safe/offline command guidance.
- [ ] Run `python3 -m pytest tests/test_market_research_acceptance.py tests/test_repository_layout.py -q`.
- [ ] Commit with `git commit -m "reduce researcher instruction load"`.

## Task 2: Deterministic Usage Audit Deduplication

**Files:**
- Modify: `market-research/shared/scripts/validate_market_research.py`
- Modify: `tests/test_validate_market_research.py`

- [ ] Add a focused test proving validation uses the shared deterministic-data usage audit implementation from `deterministic_data_usage.py`.
- [ ] Verify the new test fails before implementation.
- [ ] Replace local duplicate audit helpers in `validate_market_research.py` with calls to `usage_contract.deterministic_data_usage_audit`.
- [ ] Keep deterministic usage disposition comparison through `usage_contract.compare_usage_dispositions`.
- [ ] Remove unused imports/constants/functions made obsolete by the dedupe.
- [ ] Run `python3 -m pytest tests/test_validate_market_research.py tests/test_deterministic_data_usage.py -q`.
- [ ] Run `python3 -m pytest tests -q`.
- [ ] Commit with `git commit -m "deduplicate deterministic usage audit"`.

## Final Verification

- [ ] Run `python3 -m pytest tests`.
- [ ] Check `git status --short`.
- [ ] Review active instruction sizes with `wc -l market-research/researcher/SKILL.md market-research/researcher/references/researcher-workflow.md`.
