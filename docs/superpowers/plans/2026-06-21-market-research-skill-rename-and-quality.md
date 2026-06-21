# Market Research Skill Rename And Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the market research skill from `market-research-full` to `market-research`, clarify batch-supervisor usage, improve report quality guidance, and add protected-source escalation guidance.

**Architecture:** This is a compatibility-breaking rename with coordinated updates across docs, tests, skill metadata, and loop prompts. The directory layout remains the same inside the skill tree, but the top-level directory, skill metadata names, command examples, and prompt strings change together. Report-quality and protected-source rules live in researcher-facing reference docs and skill instructions, while verifier-only "frozen" terminology remains internal.

**Tech Stack:** Agent Skills Markdown, Python 3 standard library CLI helpers, pytest.

---

### Task 1: Rename Skill Tree And Metadata

**Files:**
- Move: `market-research-full/` to `market-research/`
- Modify: `market-research/SKILL.md`
- Modify: `market-research/researcher/SKILL.md`
- Modify: `market-research/verifier/SKILL.md`
- Modify: `market-research/loop-runner/SKILL.md`
- Modify: `market-research/loop-runner/scripts/research_loop.py`

- [ ] **Step 1: Move the active skill directory**

Run:

```bash
git mv market-research-full market-research
```

Expected: `git status --short` shows a directory rename from `market-research-full` to `market-research`.

- [ ] **Step 2: Update top-level skill metadata and routing**

Edit `market-research/SKILL.md` so it contains:

```markdown
---
name: market-research
description: Research, validate, and supervise market research runs for US-listed equities, ADRs, and ETFs using deterministic provider data, procedural source capture, and evidence-based validation.
---

# Market Research

Use this single, portable Agent Skills-format skill for all market research workflows. This is research support, not personalized financial advice.

## Modes

- Researcher: follow `researcher/SKILL.md`.
- Verifier: follow `verifier/SKILL.md`.
- Batch supervisor: follow `loop-runner/SKILL.md`.

## Canonical Layout

- Deterministic evidence belongs under `data/SYMBOL/YYYY-MM-DD/`.
- Final reports, best-effort PDFs, validation scaffolds, and completed validations belong under `reports/SYMBOL/YYYY-MM-DD/`.
- Prompts, logs, source workspaces, remediation notes, and other transient artifacts belong under `runtime/SYMBOL/YYYY-MM-DD/`.

Do not write new artifacts to the retired run-root name used before this rework. Invoke `$market-research` with the `researcher`, `verifier`, or `batch-supervisor` mode.
```

- [ ] **Step 3: Update sub-skill metadata names**

Change YAML frontmatter names:

```yaml
# market-research/researcher/SKILL.md
name: market-research-researcher
```

```yaml
# market-research/verifier/SKILL.md
name: market-research-verifier
```

```yaml
# market-research/loop-runner/SKILL.md
name: market-research-batch-supervisor
```

Expected: `rg -n "name: market-research-full" market-research` returns no matches.

- [ ] **Step 4: Update loop harness prompt strings**

In `market-research/loop-runner/scripts/research_loop.py`, replace user-facing skill names and script paths:

```python
f"$market-research researcher {symbol}"
"Run the market-research researcher workflow in this fresh Codex context."
f"Use deterministic evidence first: `python3 market-research/shared/scripts/deterministic_research_collector.py fetch {symbol} --data-dir ./data --reports-dir ./reports --as-of YYYY-MM-DD`."
f"Attempt best-effort PDF generation for the final markdown with `bash market-research/shared/scripts/md-to-pdf.sh {report_dir}/{symbol}-research.md`; continue if pandoc or xelatex is unavailable."
f"Write producer skill issues to `{runtime_dir}/{symbol}-market-research-issues.md`."
f"$market-research verifier {run_dir}"
"Run the market-research verifier workflow in this fresh Codex context."
parser = argparse.ArgumentParser(description="Orchestrate market-research researcher and verifier artifacts.")
```

Keep the internal dataclass `frozen=True`; that is Python terminology, not report jargon.

- [ ] **Step 5: Update loop-runner skill instructions**

In `market-research/loop-runner/SKILL.md`, use:

```markdown
# Market Research Batch Supervisor

Use this skill from a supervised Codex session to orchestrate `market-research researcher` and `market-research verifier` child sessions.

- Research child: runs `$market-research researcher SYMBOL`, including best-effort PDF generation after final Markdown.
- Validation child: runs `$market-research verifier RUN_DIR`.

python3 market-research/loop-runner/scripts/research_loop.py run-batch SYMBOL ... --run-root runtime/market-research-loop-YYYYMMDD --as-of YYYY-MM-DD --max-remediation-loops 3

python3 market-research/loop-runner/scripts/research_loop.py summarize RUN_ROOT

python3 market-research/loop-runner/scripts/research_loop.py collect-feedback RUN_ROOT
```

Expected: `rg -n "market-research-full|market-research-full-loop-runner" market-research/loop-runner` returns no matches except none.

### Task 2: Update Tests For Renamed Paths And Prompts

**Files:**
- Modify: `tests/test_repository_layout.py`
- Modify: `tests/test_market_research_acceptance.py`
- Modify: `tests/test_research_loop.py`
- Modify: `tests/test_md_to_pdf.py`
- Modify: `tests/test_research_output_schema.py`
- Modify: `tests/test_validate_market_research.py`
- Modify: `tests/test_procedural_source_helper.py`
- Modify: `tests/test_deterministic_research_collector.py`

- [ ] **Step 1: Update repository layout assertions**

Change `tests/test_repository_layout.py` to:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OLD_ACTIVE_DIRS = ["market-research-full", "validate-market-research", "market-research-loop"]


def test_only_market_research_is_active_skill_tree():
    assert (ROOT / "market-research" / "SKILL.md").exists()
    for name in OLD_ACTIVE_DIRS:
        assert not (ROOT / name).exists(), f"{name} must be moved into market-research"
```

Keep the generated-root ignore test.

Change forbidden references to old active paths while allowing the new `$market-research` invocation:

```python
forbidden = [
    "market-research-full",
    "validate-market-research" + "/scripts/",
    "market-research-loop" + "/scripts/",
    "$" + "market-research-full ",
    "$" + "validate-market-research ",
    "$" + "market-research-loop ",
    "market-research" + "-runs",
]
allowed_prefixes = {"OLD", ".git", ".worktrees"}
allowed_files = {
    Path("docs/plans/20260619_rework_plan.md"),
    Path("docs/superpowers/specs/2026-06-21-market-research-skill-rename-and-quality-design.md"),
    Path("docs/superpowers/plans/2026-06-21-market-research-skill-rename-and-quality.md"),
}
```

- [ ] **Step 2: Update path constants**

Replace path constants in tests:

```python
ROOT / "market-research" / "shared" / "scripts" / "deterministic_research_collector.py"
ROOT / "market-research" / "shared" / "scripts" / "procedural_source_helper.py"
ROOT / "market-research" / "shared" / "scripts" / "validate_market_research.py"
ROOT / "market-research" / "shared" / "scripts" / "md-to-pdf.sh"
ROOT / "market-research" / "shared" / "schemas" / "research-output.schema.json"
ROOT / "market-research" / "loop-runner" / "scripts" / "research_loop.py"
ROOT / "market-research" / "researcher" / "references" / "provider-data-map.md"
```

Expected: `rg -n "market-research-full" tests` only matches allowed historical/spec text if any; active test constants use `market-research`.

- [ ] **Step 3: Update loop prompt expectations**

In `tests/test_research_loop.py`, replace expected prompt fragments:

```python
assert "$market-research verifier reports/EWW/2026-06-01" in validator
assert "Use deterministic evidence first: `python3 market-research/shared/scripts/deterministic_research_collector.py fetch " in producer
assert "Write producer skill issues to `runtime/AAPL/2026-06-16/AAPL-market-research-issues.md`." in producer
assert "$market-research verifier reports/AAPL/2026-06-16" in validator
assert f"Write producer skill issues to `{run_dir}/AAPL-market-research-issues.md`." in producer
assert f"Write producer skill issues to `{expected_runtime_dir / 'AAPL-market-research-issues.md'}`." in producer
assert "$market-research verifier runtime/EWW" in validator
assert f"$market-research verifier {root / 'EWW' / '2026-06-16'}" in validator
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
python3 -m pytest tests/test_repository_layout.py tests/test_research_loop.py tests/test_market_research_acceptance.py
```

Expected: tests pass or fail only on remaining references to the old path/name.

### Task 3: Update README, AGENTS, CONTRIBUTING, And Skill Docs

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `CONTRIBUTING.md`
- Modify: `market-research/researcher/SKILL.md`
- Modify: `market-research/verifier/SKILL.md`
- Modify: `market-research/loop-runner/SKILL.md`

- [ ] **Step 1: Rewrite README around one primary skill**

Update README examples to use:

```markdown
# Market Research Skill

Portable Agent Skills-format workflows for researching, validating, and supervising US-listed equities, ADRs, and ETFs. The skill creates saved source-evidence bundles, cited Markdown research reports, JSON sidecars, validation outputs, and best-effort PDFs when local PDF tooling is available.

- `market-research/`: the installable skill directory.
- `market-research/researcher/`: producer workflow for single-symbol research.
- `market-research/verifier/`: validation workflow for saved research artifacts.
- `market-research/loop-runner/`: batch-supervisor orchestration.
- `market-research/shared/`: reusable scripts, schemas, and helper assets.
```

Install examples:

```bash
ln -s "$(pwd)/market-research" ~/.codex/skills/market-research
ln -s "$(pwd)/market-research" ~/.claude/skills/market-research
```

Invocation examples:

```text
$market-research researcher AAPL
$market-research verifier reports/AAPL/YYYY-MM-DD
$market-research batch-supervisor AAPL MSFT --as-of YYYY-MM-DD --max-remediation-loops 3
```

Direct helper examples:

```bash
python3 market-research/loop-runner/scripts/research_loop.py run-batch AAPL MSFT --run-root runtime/market-research-loop-YYYYMMDD --as-of YYYY-MM-DD --max-remediation-loops 3
python3 market-research/loop-runner/scripts/research_loop.py summarize runtime/market-research-loop-YYYYMMDD
python3 market-research/shared/scripts/deterministic_research_collector.py doctor
python3 market-research/shared/scripts/deterministic_research_collector.py fetch AAPL --as-of YYYY-MM-DD --data-dir ./data --reports-dir ./reports
python3 market-research/shared/scripts/validate_market_research.py --help
bash market-research/shared/scripts/md-to-pdf.sh reports/AAPL/YYYY-MM-DD/AAPL-research.md
```

Add migration note:

```markdown
## Migration From `market-research-full`

The previous active skill directory and invocation name was `market-research-full`. Use `market-research` instead. If you installed the old skill through a symlink, remove the old symlink and create a new one pointing to `market-research/`.
```

- [ ] **Step 2: Update AGENTS and CONTRIBUTING paths**

Replace active tree references with:

```markdown
`market-research/`
`market-research/researcher/`
`market-research/verifier/`
`market-research/loop-runner/`
`market-research/shared/`
```

Replace helper commands with `python3 market-research/...`.

- [ ] **Step 3: Update researcher recommendation and script examples**

In `market-research/researcher/SKILL.md`, replace:

```markdown
recommend running `market-research verifier`
```

and all command examples that begin with `python3 market-research-full/` or `bash market-research-full/` to `market-research/`.

- [ ] **Step 4: Keep verifier internal frozen terminology but update metadata**

In `market-research/verifier/SKILL.md`, update the description to:

```yaml
description: Validate market research evidence bundles for equities, ADRs, and ETFs in a fresh Codex context; inspect cited artifacts and public sources; write validation markdown and JSON without editing the original report.
```

Keep internal validation rules that refer to frozen evidence where they are validation-specific.

- [ ] **Step 5: Run doc reference search**

Run:

```bash
rg -n "market-research-full|\\$market-research-full|loop-runner" README.md AGENTS.md CONTRIBUTING.md market-research
```

Expected: no `market-research-full` matches in active docs/skill files. `loop-runner` may remain as a directory name and internal helper path.

### Task 4: Improve Report Template And Source Access Policy

**Files:**
- Modify: `market-research/researcher/references/report-template.md`
- Modify: `market-research/researcher/references/source-policy.md`
- Modify: `market-research/researcher/SKILL.md`

- [ ] **Step 1: Replace report template with stronger global guidance**

Update `market-research/researcher/references/report-template.md` to include:

```markdown
# Report Template

Use this outline for the human-facing research report. Use `research_input_pack.md`, saved source copies, and recorded procedural sources as the fact base; do not copy unsupported interpretation into the report.

## Report Quality Bar

Every report should read like useful investment research, not an artifact inventory.

- Lead with a clear bottom line.
- Explain what the company, ADR, or fund does in practical terms.
- Discuss business model, demand drivers, financial quality, balance sheet or fund structure, valuation or performance context, catalysts, and risks when applicable and supported by sources.
- Separate facts from interpretation, but make interpretation decision-useful.
- Use sections such as `What Looks Attractive`, `What Worries Me`, and `My Take` when they improve readability.
- If trading data is unavailable, replace mechanical technical analysis with the relevant lifecycle context such as IPO terms, implied valuation, listing timeline, post-listing monitoring items, or explicit absence of market history.
- For ETFs, adapt the same standard to fund objective, index methodology, holdings, exposures, fees, liquidity, tracking/performance context, distributions, portfolio role, risks, and monitoring triggers.

## Full Markdown Report Structure

# SYMBOL Research

As of: YYYY-MM-DD

## Bottom Line

## Key Facts

## Source Base And Data Quality

Describe saved source copies, primary versus secondary sources, source dates, access dates, confidence, and material limitations. Do not use internal jargon such as "frozen sources" in the human-facing report.

## Business Or Fund Profile

## Business Model, Demand Drivers, Or Fund Methodology

## Market Snapshot Or Lifecycle Context

Use `normalized/technical_signals.json` when trading data exists. If no trading history exists, explain why and use the relevant lifecycle context instead.

## Financials, Holdings, And Balance Sheet

## Valuation Or Performance Context

## What Looks Attractive

## What Worries Me

## Catalysts And Monitoring Triggers

## Bull/Base/Bear Decision Variables

## Risks And Invalidation Points

## Explicit Data Gaps

## My Take

## Not Financial Advice
This report is research support and is not personalized financial advice.
```

Keep the JSON sidecar example and update its text to refer to saved evidence rather than frozen sources.

- [ ] **Step 2: Add protected-source policy**

In `market-research/researcher/references/source-policy.md`, add:

```markdown
## Protected Source Access

Protected-source handling applies to any source, not only SEC.

If a material source is blocked by bot protection, CAPTCHA, WAF, JavaScript challenge, suspicious automated-access response, or similar access control:

1. Classify it as a protected-source access issue.
2. Decide whether the source is material to report quality.
3. If material, move promptly to headed-browser human assistance unless an alternative source is clearly equivalent or better quality, current, and authoritative enough for the claim.
4. Ask the human to solve the challenge in the headed browser when required.
5. Continue capture after access is restored and save the source artifact through the normal source registry path.
6. If access cannot be completed, record a workflow extraction/access gap and explain the analytical limitation.

Lower-quality or stale substitutes must not be used merely to avoid headed-browser escalation. Alternatives are acceptable only when they preserve or improve evidence quality.
```

- [ ] **Step 3: Update researcher workflow to point at protected-source policy**

In `market-research/researcher/SKILL.md`, add after source gathering instructions:

```markdown
If a material source is blocked by protected-source technology such as CAPTCHA, WAF, bot challenge, or JavaScript challenge, follow `references/source-policy.md` protected-source access guidance. Treat headed-browser human assistance as a first-class path when it preserves source quality.
```

- [ ] **Step 4: Remove investor-facing frozen wording from researcher docs**

Run:

```bash
rg -n "frozen" market-research/researcher README.md
```

Expected: no investor-facing "frozen sources" phrasing remains. Internal examples such as "Rebuild from saved raw data only" should use "saved" instead of "frozen".

### Task 5: Full Verification And Cleanup

**Files:**
- Potentially modify any active file reported by tests or reference searches.

- [ ] **Step 1: Run full old-name search**

Run:

```bash
rg -n "market-research-full|\\$market-research-full" . --glob '!OLD/**' --glob '!.git/**' --glob '!docs/plans/20260619_rework_plan.md' --glob '!docs/superpowers/specs/2026-06-21-market-research-skill-rename-and-quality-design.md' --glob '!docs/superpowers/plans/2026-06-21-market-research-skill-rename-and-quality.md'
```

Expected: no matches.

- [ ] **Step 2: Run full tests**

Run:

```bash
python3 -m pytest tests
```

Expected: all tests pass.

- [ ] **Step 3: Inspect git status**

Run:

```bash
git status --short
```

Expected: changes include the directory rename, docs, tests, and plan. `DPC-my-example.md` may remain untracked and must not be staged.

- [ ] **Step 4: Commit implementation**

Run:

```bash
git add README.md AGENTS.md CONTRIBUTING.md tests market-research docs/superpowers/plans/2026-06-21-market-research-skill-rename-and-quality.md
git commit -m "rename market research skill and improve guidance"
```

Expected: commit succeeds without staging `DPC-my-example.md`.
