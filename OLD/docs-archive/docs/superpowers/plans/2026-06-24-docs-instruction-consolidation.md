# Docs And Instruction Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate active docs and agent-facing instructions into a compact canonical documentation set while moving historical/generated plans to `OLD/docs-archive/`.

**Architecture:** Active docs become an index plus three canonical references: architecture, quality bar, and operations. Historical and generated planning artifacts are preserved under `OLD/docs-archive/` with original relative paths. Documentation tests enforce the active-vs-archive contract and updated lesson locations.

**Tech Stack:** Markdown, Python 3.11+, pytest, pathlib, git file moves.

---

## File Structure

- Create: `docs/README.md`
  - Active documentation index and archive policy.
- Create: `docs/architecture.md`
  - Durable repo layout, skill-mode boundaries, artifact roots, and evidence roles.
- Create: `docs/quality-bar.md`
  - Consolidated investor report, deterministic evidence, validation, freshness, provider-limit, and self-improvement lessons.
- Create: `docs/operations.md`
  - Common helper commands, tests, preflight, single-run, batch-run, self-improvement, and artifact handling workflows.
- Modify: `README.md`
  - Keep it user-facing and point to canonical docs instead of carrying all operator detail inline.
- Modify: `AGENTS.md`
  - Keep it short and point agents to canonical docs.
- Modify: `tests/test_repository_layout.py`
  - Assert active docs contract and archive policy.
- Modify: `tests/test_market_research_acceptance.py`
  - Move dated lesson-file assertions to `docs/quality-bar.md`.
- Move to archive:
  - `docs/plans/20260619_rework_plan.md`
  - completed/generated files currently under `docs/superpowers/plans/`, except this active implementation plan until the work is complete.
  - stale historical spec `docs/superpowers/specs/2026-06-21-market-research-skill-rename-and-quality-design.md` after its durable conclusions are represented in canonical docs.

### Task 1: Add Documentation Contract Tests

**Files:**
- Modify: `tests/test_repository_layout.py`
- Modify: `tests/test_market_research_acceptance.py`

- [ ] **Step 1: Update repository-layout tests for canonical docs**

In `tests/test_repository_layout.py`, add these tests after `test_active_files_do_not_reference_old_skill_paths`:

```python
def test_active_docs_use_canonical_consolidated_structure():
    required_docs = [
        Path("docs/README.md"),
        Path("docs/architecture.md"),
        Path("docs/quality-bar.md"),
        Path("docs/operations.md"),
    ]
    for rel in required_docs:
        assert (ROOT / rel).exists(), f"{rel} should be an active canonical doc"

    index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    for rel in required_docs[1:]:
        assert str(rel) in index
    assert "OLD/docs-archive/" in index


def test_historical_generated_docs_are_archived_outside_active_docs():
    archived = [
        Path("OLD/docs-archive/docs/plans/20260619_rework_plan.md"),
        Path("OLD/docs-archive/docs/superpowers/plans/2026-06-23-market-research-self-improvement.json"),
        Path("OLD/docs-archive/docs/superpowers/specs/2026-06-21-market-research-skill-rename-and-quality-design.md"),
    ]
    for rel in archived:
        assert (ROOT / rel).exists(), f"{rel} should be preserved in the archive"

    forbidden_active = [
        Path("docs/plans/20260619_rework_plan.md"),
        Path("docs/superpowers/plans/2026-06-23-market-research-self-improvement.json"),
        Path("docs/superpowers/specs/2026-06-21-market-research-skill-rename-and-quality-design.md"),
    ]
    for rel in forbidden_active:
        assert not (ROOT / rel).exists(), f"{rel} should not remain active"
```

- [ ] **Step 2: Narrow old-path allowlist to archived docs and current spec/plan**

In `tests/test_repository_layout.py`, replace the `allowed_files` block inside `test_active_files_do_not_reference_old_skill_paths` with:

```python
    allowed_files = {
        Path("docs/superpowers/specs/2026-06-24-docs-instruction-consolidation-design.md"),
        Path("docs/superpowers/plans/2026-06-24-docs-instruction-consolidation.md"),
    }
```

Keep `allowed_prefixes = {"OLD", ".git", ".worktrees"}` unchanged so archived historical content may preserve old references.

- [ ] **Step 3: Update lesson assertions to consolidated quality-bar doc**

In `tests/test_market_research_acceptance.py`, replace `test_self_improvement_lessons_prioritize_investor_product_over_runtime_packaging` with:

```python
def test_quality_bar_prioritizes_investor_product_over_runtime_packaging():
    quality_bar = (ROOT / "docs" / "quality-bar.md").read_text(encoding="utf-8").lower()
    supervisor = (ROOT / "market-research" / "batch-supervisor" / "SKILL.md").read_text(encoding="utf-8").lower()

    assert "final report is the investor product" in quality_bar
    assert "field-specific, not cache-specific" in quality_bar
    assert "finished investor experience before artifact ergonomics" in quality_bar
    assert "reports/` is for polished final deliverables" in quality_bar
    assert "field-level freshness guidance over cache-mechanics disclosure" in supervisor
```

- [ ] **Step 4: Run focused tests and verify expected failures**

Run:

```bash
python3 -m pytest tests/test_repository_layout.py tests/test_market_research_acceptance.py::test_quality_bar_prioritizes_investor_product_over_runtime_packaging -q
```

Expected: FAIL because the canonical docs do not exist yet and archive moves have not happened.

- [ ] **Step 5: Commit the failing tests**

Run:

```bash
git add tests/test_repository_layout.py tests/test_market_research_acceptance.py
git commit -m "test docs consolidation contract"
```

### Task 2: Create Canonical Active Docs

**Files:**
- Create: `docs/README.md`
- Create: `docs/architecture.md`
- Create: `docs/quality-bar.md`
- Create: `docs/operations.md`

- [ ] **Step 1: Create `docs/README.md`**

Create `docs/README.md` with:

```markdown
# Market Research Skill Docs

This directory contains active documentation for the market-research skill repository. Active docs should be short, current, and useful for future work. Historical implementation plans, generated self-improvement outputs, and stale specs belong under `OLD/docs-archive/` with their original relative paths preserved.

## Active Docs

- `docs/architecture.md`: skill layout, mode boundaries, canonical artifact roots, and evidence roles.
- `docs/quality-bar.md`: investor-grade report standards, evidence discipline, deterministic-data usage, freshness, validation expectations, and self-improvement lessons.
- `docs/operations.md`: development commands, preflight checks, research and validation workflows, batch supervision, self-improvement prompt generation, and generated-artifact handling.
- `docs/superpowers/specs/`: current approved design specs.
- `docs/superpowers/plans/`: current approved implementation plans.

## Archive Policy

Do not keep completed/generated plans active just because they may be useful someday. Move them to `OLD/docs-archive/` and preserve their original path below that directory. For example, `docs/plans/example.md` becomes `OLD/docs-archive/docs/plans/example.md`.

Do not extend archived files unless restoring legacy context. Put durable conclusions in the active docs above.
```

- [ ] **Step 2: Create `docs/architecture.md`**

Create `docs/architecture.md` with:

```markdown
# Market Research Architecture

The active skill tree lives under `market-research/` and follows the Agent Skills directory contract: Markdown `SKILL.md` instructions, optional `references/`, executable `scripts/`, schemas, and agent config files.

## Skill Modes

- `market-research/researcher/`: produces a single-symbol research bundle for US-listed equities, ADRs, and ETFs.
- `market-research/verifier/`: validates frozen report artifacts and evidence without editing producer output.
- `market-research/batch-supervisor/`: orchestrates fresh researcher, verifier, remediation, and self-improvement prompt sessions.
- `market-research/shared/`: shared scripts, schemas, provider docs, and agent config.

The top-level `market-research/SKILL.md` routes users to the mode-specific skill files. Keep mode-specific guidance in the smallest relevant file or reference so agents do not load unnecessary policy.

## Artifact Roots

- `data/SYMBOL/YYYY-MM-DD/`: deterministic evidence, raw provider cache copies, normalized values, manifests, gaps, and deterministic-data-usage requirements.
- `reports/SYMBOL/YYYY-MM-DD/`: polished research Markdown, JSON sidecar, best-effort PDF, validation scaffold, completed validation, and validator issue files.
- `runtime/SYMBOL/YYYY-MM-DD/`: procedural source workspaces, prompts, logs, run manifests, notes, source bundles, remediation notes, and transient working files.

Generated `data/`, `reports/`, and `runtime/` outputs are not committed.

## Evidence Roles

Deterministic helper output is evidence, not authority. Researchers should use it aggressively, but final reports must synthesize material facts into an investor-readable memo. Procedural source bundles fill targeted gaps and preserve source dates, URLs, local artifact metadata, and confidence notes.

Validators inspect frozen artifacts, cited sources, deterministic bundles, source registries, schemas, and report claims. They do not create competing investment theses or rewrite producer reports.

## Historical Material

Historical plans and generated self-improvement artifacts live under `OLD/docs-archive/`. They can explain why a decision was made, but active docs and skill files define current behavior.
```

- [ ] **Step 3: Create `docs/quality-bar.md`**

Create `docs/quality-bar.md` with:

```markdown
# Market Research Quality Bar

This repository optimizes for investor-useful research supported by reproducible evidence. The final report is the investor product; runtime artifacts are intermediate work.

## Investor Report Standard

The report should read like an investor memo, not a deterministic-data recital or validation transcript. Lead with thesis, materiality, variant view, valuation context, catalysts, risks, invalidation points, and monitoring triggers. For ETFs, adapt the same standard to fund objective, index methodology, holdings, exposures, fees, liquidity, tracking/performance context, distribution profile, portfolio role, risks, and monitoring triggers.

Deterministic evidence should support the report, not become the report. A report can satisfy field-usage requirements and still fail quality if it lacks synthesis and judgment.

## Evidence And Provenance

Every material quantitative claim needs citation support or an explicit unavailable/unverified caveat. Inline citations are useful for surprising, contentious, source-sensitive, or highly material claims. Excessive path-level citation density is the failure mode, not citation discipline.

Detailed local paths, hashes, provider mechanics, cache files, source IDs, and raw artifact details belong in JSON sidecars, source registries, evidence sections, appendices, or validation artifacts unless they change investor interpretation. Routine provider names are usually not investment content.

## Deterministic Data Usage

Treat `deterministic_data_usage.json` as the researcher-stage contract for usable deterministic data. Required and review datapoints must be used in the final report or explicitly dispositioned in the report JSON.

Rationales must be field-specific. Boilerplate such as "used for valuation context" can satisfy a schema while hiding whether the datapoint actually mattered. Weak boilerplate rationales are quality issues.

Validator referenced/not-referenced audits are useful review leads, but explicit field-level dispositions are the stronger enforcement path.

## Freshness

Freshness is field-specific, not cache-specific. Investors care whether price, volume, market cap, filings, ownership, estimates, short interest, and news are current enough for the decision; they usually do not care whether durable source-dated evidence came from cache.

Use fresh or latest-available data for time-sensitive fields. Durable filed evidence, historical statements, company identity, older risk-factor text, and dated press releases may use cached/source-dated artifacts when the source date is preserved.

Main-report disclosure should focus on missing, stale, or conflicting data that changes interpretation. Prefer field-level freshness guidance over cache-mechanics disclosure.

## Provider Limits And Discrepancies

Provider gaps must map to affected analysis areas. Examples: unavailable short interest affects crowding/squeeze analysis; unavailable forward estimates affects valuation; unavailable insider statistics affects dilution/governance analysis; unavailable filing sections affects direct risk-factor and MD&A validation.

Material discrepancies should be described in investor-readable terms: the data, the range or conflict, and why it matters. Provider names and mechanics belong near the end or in sidecars unless the provider identity changes confidence.

Framework agreements, "up to" values, milestones, potential contract value, backlog, and booked revenue must be framed according to what the cited source supports.

## Validation Quality

Validation should test source support, stale dates, unsupported claims, omitted risks, ticker/name/source-entity alignment, deterministic provenance, schema shape, and investor usefulness. Deterministic coverage alone is not enough.

Reports should keep company/security risks in `Risks And Invalidation Points`. Research limits, stale fields, data discrepancies, and source-quality issues belong in `Data Issues And Discrepancies`.

## Self-Improvement

Self-improvement is prompt-only and operator-triggered. Do not launch surprise subprocesses after a successful research loop.

Use completed batch roots to compare recurring missing-data, omitted-risk, report-quality, and validator-specificity patterns before changing the skill. Judge the finished investor experience before artifact ergonomics. `reports/` is for polished final deliverables, `runtime/` is for prompts/logs/intermediate notes, and `data/` is for deterministic evidence.
```

- [ ] **Step 4: Create `docs/operations.md`**

Create `docs/operations.md` with:

````markdown
# Market Research Operations

Run commands from the repository root.

## Development Checks

```bash
python3 market-research/shared/scripts/deterministic_research_collector.py --help
python3 market-research/shared/scripts/procedural_source_helper.py --help
python3 market-research/shared/scripts/validate_market_research.py --help
python3 market-research/batch-supervisor/scripts/research_loop.py --help
bash market-research/shared/scripts/md-to-pdf.sh --help
python3 market-research/shared/scripts/preflight_environment.py
python3 -m pytest tests
```

For focused checks:

```bash
python3 -m pytest tests/test_repository_layout.py
python3 -m pytest tests/test_research_loop.py
```

## Single Research Run

Ask the agent to run:

```text
$market-research researcher AAPL
```

Expected final artifacts:

```text
data/AAPL/YYYY-MM-DD/
runtime/AAPL/YYYY-MM-DD/
reports/AAPL/YYYY-MM-DD/AAPL-research.md
reports/AAPL/YYYY-MM-DD/AAPL-research.json
reports/AAPL/YYYY-MM-DD/AAPL-research.pdf
```

PDF generation is best-effort. Missing `pandoc`, `xelatex`, or LaTeX packages should not fail the research job when Markdown and JSON artifacts are valid.

## Validation

Run validation in a fresh agent context:

```text
$market-research verifier reports/AAPL/YYYY-MM-DD
```

The verifier writes validation Markdown and JSON under the report directory and must not edit producer artifacts.

## Supervised Batch

Use the batch supervisor for fresh child researcher and verifier sessions:

```text
$market-research batch-supervisor AAPL MSFT --as-of YYYY-MM-DD --max-remediation-loops 3
```

For direct helper debugging:

```bash
python3 market-research/batch-supervisor/scripts/research_loop.py run-batch AAPL MSFT \
  --run-root runtime/market-research-batch-YYYYMMDD \
  --as-of YYYY-MM-DD \
  --max-remediation-loops 3
```

Summarize a completed or running batch:

```bash
python3 market-research/batch-supervisor/scripts/research_loop.py summarize runtime/market-research-batch-YYYYMMDD
```

The final pass gate is no open critical or moderate validation issues.

## Self-Improvement Prompt

Self-improvement is explicit and prompt-only:

```text
$market-research batch-supervisor self-improve runtime/market-research-batch-YYYYMMDD
```

Direct helper form:

```bash
python3 market-research/batch-supervisor/scripts/research_loop.py self-improve \
  runtime/market-research-batch-YYYYMMDD
```

By default this writes under `docs/superpowers/plans/self-improvement/TIMESTAMP/`. Review the generated prompt manually, run it in Codex when appropriate, and later archive completed/generated outputs under `OLD/docs-archive/` after durable conclusions are captured in active docs or skill files.

## Generated Artifacts

Do not commit generated `data/`, `reports/`, `runtime/`, private research bundles, credentials, or `.env`. Commit only durable skill instructions, helper code, tests, schemas, provider docs, and active documentation.
````

- [ ] **Step 5: Run focused tests**

Run:

```bash
python3 -m pytest tests/test_repository_layout.py tests/test_market_research_acceptance.py::test_quality_bar_prioritizes_investor_product_over_runtime_packaging -q
```

Expected: still FAIL until archive moves are complete, but no failure should mention missing canonical doc files or missing consolidated lesson text.

- [ ] **Step 6: Commit canonical docs**

Run:

```bash
git add docs/README.md docs/architecture.md docs/quality-bar.md docs/operations.md
git commit -m "add canonical market research docs"
```

### Task 3: Archive Historical And Generated Docs

**Files:**
- Move: `docs/plans/20260619_rework_plan.md`
- Move: `docs/superpowers/plans/*` except `docs/superpowers/plans/2026-06-24-docs-instruction-consolidation.md`
- Move: `docs/superpowers/specs/2026-06-21-market-research-skill-rename-and-quality-design.md`

- [ ] **Step 1: Create archive directories**

Run:

```bash
mkdir -p OLD/docs-archive/docs/plans OLD/docs-archive/docs/superpowers/plans OLD/docs-archive/docs/superpowers/specs
```

- [ ] **Step 2: Move historical rework plan**

Run:

```bash
git mv docs/plans/20260619_rework_plan.md OLD/docs-archive/docs/plans/20260619_rework_plan.md
```

- [ ] **Step 3: Move generated/completed Superpowers plan artifacts**

Run these `git mv` commands:

```bash
git mv docs/superpowers/plans/2026-06-21-market-research-quality-remediation.md OLD/docs-archive/docs/superpowers/plans/2026-06-21-market-research-quality-remediation.md
git mv docs/superpowers/plans/2026-06-21-market-research-sec-access-and-tooling.md OLD/docs-archive/docs/superpowers/plans/2026-06-21-market-research-sec-access-and-tooling.md
git mv docs/superpowers/plans/2026-06-21-market-research-skill-rename-and-quality.md OLD/docs-archive/docs/superpowers/plans/2026-06-21-market-research-skill-rename-and-quality.md
git mv docs/superpowers/plans/2026-06-22-market-research-investor-grade-report-quality.md OLD/docs-archive/docs/superpowers/plans/2026-06-22-market-research-investor-grade-report-quality.md
git mv docs/superpowers/plans/2026-06-23-market-research-investor-focused-report-ideas.md OLD/docs-archive/docs/superpowers/plans/2026-06-23-market-research-investor-focused-report-ideas.md
git mv docs/superpowers/plans/2026-06-23-market-research-investor-focused-report-implementation.md OLD/docs-archive/docs/superpowers/plans/2026-06-23-market-research-investor-focused-report-implementation.md
git mv docs/superpowers/plans/2026-06-23-market-research-investor-focused-report-self-improvement.json OLD/docs-archive/docs/superpowers/plans/2026-06-23-market-research-investor-focused-report-self-improvement.json
git mv docs/superpowers/plans/2026-06-23-market-research-investor-grade-report-quality-plan.md OLD/docs-archive/docs/superpowers/plans/2026-06-23-market-research-investor-grade-report-quality-plan.md
git mv docs/superpowers/plans/2026-06-23-market-research-self-improvement-ideas.md OLD/docs-archive/docs/superpowers/plans/2026-06-23-market-research-self-improvement-ideas.md
git mv docs/superpowers/plans/2026-06-23-market-research-self-improvement.json OLD/docs-archive/docs/superpowers/plans/2026-06-23-market-research-self-improvement.json
git mv docs/superpowers/plans/2026-06-23-qubt-batch-self-improvement-ideas.md OLD/docs-archive/docs/superpowers/plans/2026-06-23-qubt-batch-self-improvement-ideas.md
git mv docs/superpowers/plans/2026-06-23-qubt-batch-self-improvement-plan.md OLD/docs-archive/docs/superpowers/plans/2026-06-23-qubt-batch-self-improvement-plan.md
git mv docs/superpowers/plans/2026-06-23-qubt-batch-self-improvement-prompt.md OLD/docs-archive/docs/superpowers/plans/2026-06-23-qubt-batch-self-improvement-prompt.md
git mv docs/superpowers/plans/2026-06-23-qubt-batch-self-improvement.json OLD/docs-archive/docs/superpowers/plans/2026-06-23-qubt-batch-self-improvement.json
```

Leave `docs/superpowers/plans/2026-06-24-docs-instruction-consolidation.md` active until this implementation is complete.

- [ ] **Step 4: Move stale historical spec**

Run:

```bash
git mv docs/superpowers/specs/2026-06-21-market-research-skill-rename-and-quality-design.md OLD/docs-archive/docs/superpowers/specs/2026-06-21-market-research-skill-rename-and-quality-design.md
```

Leave `docs/superpowers/specs/2026-06-24-docs-instruction-consolidation-design.md` active.

- [ ] **Step 5: Inspect active docs tree**

Run:

```bash
find docs -maxdepth 4 -type f -print | sort
```

Expected output should include only:

```text
docs/README.md
docs/architecture.md
docs/operations.md
docs/quality-bar.md
docs/superpowers/plans/2026-06-24-docs-instruction-consolidation.md
docs/superpowers/specs/2026-06-24-docs-instruction-consolidation-design.md
```

- [ ] **Step 6: Run focused tests**

Run:

```bash
python3 -m pytest tests/test_repository_layout.py tests/test_market_research_acceptance.py::test_quality_bar_prioritizes_investor_product_over_runtime_packaging -q
```

Expected: PASS.

- [ ] **Step 7: Commit archive moves**

Run:

```bash
git add docs OLD
git commit -m "archive historical docs"
```

### Task 4: Update README And AGENTS Pointers

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: Add canonical docs pointer to `README.md`**

In `README.md`, add this section after `## What Is Included`:

```markdown
## Documentation

Active project documentation lives under `docs/`:

- `docs/architecture.md` explains skill boundaries, artifact roots, and evidence roles.
- `docs/quality-bar.md` captures the report-quality, evidence, freshness, validation, and self-improvement standards.
- `docs/operations.md` collects development commands and operator workflows.

Historical plans and generated self-improvement artifacts are archived under `OLD/docs-archive/`.
```

- [ ] **Step 2: Trim duplicate operations detail in `README.md` only if it remains accurate**

Read the `README.md` sections `Useful Helper Commands` and `Troubleshooting`. Keep user-facing quick-start content intact. If a paragraph duplicates `docs/operations.md` in a way that can drift, replace it with one sentence:

```markdown
For the full command list, preflight workflow, and batch/self-improvement operations, see `docs/operations.md`.
```

Do not remove install, configure, single research, validation, or supervised batch examples from `README.md`.

- [ ] **Step 3: Add active-docs contract to `AGENTS.md`**

In `AGENTS.md`, update the `Project Structure & Module Organization` docs bullets to include:

```markdown
- `docs/README.md`: active documentation index and archive policy.
- `docs/architecture.md`: skill boundaries, artifact roots, and evidence roles.
- `docs/quality-bar.md`: durable report-quality, evidence, validation, freshness, and self-improvement standards.
- `docs/operations.md`: repeatable development and operator workflows.
```

Also add this paragraph after the existing `OLD/` bullet:

```markdown
Historical plans, generated self-improvement outputs, and stale specs belong under `OLD/docs-archive/` with their original relative paths preserved. Do not keep generated planning artifacts active after their durable conclusions are represented in canonical docs.
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
python3 -m pytest tests/test_repository_layout.py tests/test_market_research_acceptance.py::test_quality_bar_prioritizes_investor_product_over_runtime_packaging -q
```

Expected: PASS.

- [ ] **Step 5: Commit README and AGENTS changes**

Run:

```bash
git add README.md AGENTS.md
git commit -m "point instructions to canonical docs"
```

### Task 5: Final Verification

**Files:**
- Verify all changed files.

- [ ] **Step 1: Check active docs for retired skill references**

Run:

```bash
rg -n "market-research-full|validate-market-research|market-research-loop|market-research-runs" docs README.md AGENTS.md market-research tests
```

Expected: no matches except inside `docs/superpowers/specs/2026-06-24-docs-instruction-consolidation-design.md` or `docs/superpowers/plans/2026-06-24-docs-instruction-consolidation.md` while the plan remains active.

- [ ] **Step 2: Run documentation/layout tests**

Run:

```bash
python3 -m pytest tests/test_repository_layout.py tests/test_market_research_acceptance.py::test_quality_bar_prioritizes_investor_product_over_runtime_packaging -q
```

Expected: PASS.

- [ ] **Step 3: Run full test suite**

Run:

```bash
python3 -m pytest tests
```

Expected: PASS.

- [ ] **Step 4: Review git status**

Run:

```bash
git status --short
```

Expected: clean worktree.

- [ ] **Step 5: Report outcome**

Tell the user:

```text
Docs consolidation is complete. Active docs are now docs/README.md, docs/architecture.md, docs/quality-bar.md, docs/operations.md, plus the current Superpowers spec/plan. Historical generated docs were moved to OLD/docs-archive/. Verification: python3 -m pytest tests.
```
