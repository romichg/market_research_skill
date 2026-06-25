# Full Skill And Helper Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce skill token load, expose runtime/provider-call metrics, remove repeated script plumbing, and add guardrails that preserve market-research quality.

**Architecture:** Keep `SKILL.md` files as short routing and quality-gate entrypoints, moving procedure into references loaded only when needed. Add opt-in JSON metrics through a shared helper so scripts can report elapsed time and provider/cache behavior without changing default output contracts. Extract shared Python utilities only where duplicate behavior is already tested.

**Tech Stack:** Python 3 standard library, pytest subprocess tests, portable Agent Skills markdown.

---

### Task 1: Compact Verifier And Supervisor Entrypoints

**Files:**
- Modify: `market-research/verifier/SKILL.md`
- Create: `market-research/verifier/references/verifier-workflow.md`
- Modify: `market-research/batch-supervisor/SKILL.md`
- Create: `market-research/batch-supervisor/references/supervisor-workflow.md`
- Modify: `tests/test_market_research_acceptance.py`
- Modify: `tests/test_repository_layout.py`

- [ ] **Step 1: Write failing routing tests**

Add tests requiring the verifier and supervisor entrypoints to point to workflow references while preserving critical quality trigger phrases:

```python
def test_verifier_skill_routes_operational_detail_to_workflow_reference():
    skill = (ROOT / "market-research" / "verifier" / "SKILL.md").read_text(encoding="utf-8").lower()
    workflow = ROOT / "market-research" / "verifier" / "references" / "verifier-workflow.md"
    assert "references/verifier-workflow.md" in skill
    assert workflow.exists()
    text = workflow.read_text(encoding="utf-8").lower()
    assert "deterministic_data_usage" in text
    assert "routine data-vendor names" in text
    assert "open critical/moderate" in text


def test_supervisor_skill_routes_operational_detail_to_workflow_reference():
    skill = (ROOT / "market-research" / "batch-supervisor" / "SKILL.md").read_text(encoding="utf-8").lower()
    workflow = ROOT / "market-research" / "batch-supervisor" / "references" / "supervisor-workflow.md"
    assert "references/supervisor-workflow.md" in skill
    assert workflow.exists()
    text = workflow.read_text(encoding="utf-8").lower()
    assert "research_loop.py run-batch" in text
    assert "self-improvement is not automatic" in text
    assert "field-level freshness" in text
```

Update `tests/test_repository_layout.py` so this plan remains an intentional active doc.

- [ ] **Step 2: Run focused tests and verify red**

Run:

```bash
python3 -m pytest tests/test_market_research_acceptance.py::test_verifier_skill_routes_operational_detail_to_workflow_reference tests/test_market_research_acceptance.py::test_supervisor_skill_routes_operational_detail_to_workflow_reference -q
```

Expected: both new tests fail because the reference files and routing text do not exist yet.

- [ ] **Step 3: Move procedural detail into references**

Replace the verbose verifier/supervisor entrypoints with concise routing docs. Preserve quality gates in the entrypoint; put commands, artifact shapes, failure handling, and self-improvement details in the new reference files.

- [ ] **Step 4: Verify and commit**

Run:

```bash
python3 -m pytest tests/test_market_research_acceptance.py tests/test_repository_layout.py -q
python3 -m pytest tests
git add market-research/verifier/SKILL.md market-research/verifier/references/verifier-workflow.md market-research/batch-supervisor/SKILL.md market-research/batch-supervisor/references/supervisor-workflow.md tests/test_market_research_acceptance.py tests/test_repository_layout.py docs/superpowers/plans/2026-06-24-full-skill-and-helper-optimization.md
git commit -m "compact verifier and supervisor instructions"
```

### Task 2: Add Opt-In Helper Metrics

**Files:**
- Create: `market-research/shared/scripts/script_metrics.py`
- Modify: `market-research/shared/scripts/deterministic_research_collector.py`
- Modify: `market-research/shared/scripts/procedural_source_helper.py`
- Modify: `market-research/batch-supervisor/scripts/research_loop.py`
- Add/modify tests in existing helper test files.

- [ ] **Step 1: Write failing metrics tests**

Add subprocess tests proving `--metrics-json PATH` writes a sidecar with `script`, `command`, `elapsed_seconds`, and relevant counters while stdout remains valid JSON.

- [ ] **Step 2: Verify red**

Run focused tests for the new metrics cases. Expected: parser rejects `--metrics-json` or no metrics file is written.

- [ ] **Step 3: Implement shared metrics helper**

Create a small `script_metrics.py` with a monotonic timer and `write_metrics(path, payload)`. Wire it into collector, procedural helper, and research loop without changing default stdout.

- [ ] **Step 4: Verify and commit**

Run focused helper tests and the full suite, then commit:

```bash
git commit -m "add opt-in helper metrics"
```

### Task 3: Extract Shared Script Utilities

**Files:**
- Create or extend: `market-research/shared/scripts/script_utils.py`
- Modify: `deterministic_research_collector.py`, `procedural_source_helper.py`, `validate_market_research.py`, and `research_loop.py` where safe.
- Add tests that statically prevent reintroduced duplicate primitives.

- [ ] **Step 1: Write failing duplicate-guard tests**

Test that scripts import common `read_json`, `write_json`, `normalize_symbol`, and checksum helpers where applicable instead of local copies.

- [ ] **Step 2: Verify red**

Run the duplicate-guard tests. Expected: local duplicate definitions still exist.

- [ ] **Step 3: Extract conservative utilities**

Move only identical or near-identical primitives with stable behavior: JSON read/write, symbol validation, as-of validation, checksum, and process-safe atomic JSON writes. Keep domain-specific logic in place.

- [ ] **Step 4: Verify and commit**

Run all affected helper tests plus the full suite, then commit:

```bash
git commit -m "share helper script primitives"
```

### Task 4: Add Cache And Preflight Guardrails

**Files:**
- Modify: `deterministic_research_collector.py`
- Modify: `preflight_environment.py` if useful
- Modify: docs or workflow references only if commands change.
- Add tests for cache/provider call estimates.

- [ ] **Step 1: Write failing guardrail tests**

Add tests for a command that reports estimated provider calls/cache hits before a fetch, and for metrics that distinguish cache hits from newly fetched files.

- [ ] **Step 2: Verify red**

Run focused collector tests. Expected: no preflight payload or cache counters exist.

- [ ] **Step 3: Implement minimal preflight**

Expose a `plan-fetch` or equivalent mode that uses existing endpoint-estimation functions and configured providers to report planned calls without network or bundle writes.

- [ ] **Step 4: Verify and commit**

Run focused collector tests and the full suite, then commit:

```bash
git commit -m "add provider call preflight"
```

### Task 5: Final Optimization Review

**Files:**
- No predetermined files.

- [ ] **Step 1: Measure final state**

Run:

```bash
wc -l market-research/*/SKILL.md market-research/SKILL.md
python3 -m pytest tests
```

- [ ] **Step 2: Inspect remaining hotspots**

Use `rg` and `wc` to look for large entrypoints, duplicate helper definitions, and repeated guidance. Only make another commit if there is a clear quality-preserving simplification.

- [ ] **Step 3: Finish branch**

Use `superpowers:verification-before-completion`, then merge locally to `main`, rerun `python3 -m pytest tests`, clean the worktree, and report commits and verification.
