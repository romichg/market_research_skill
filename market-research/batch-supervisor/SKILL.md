---
name: market-research-batch-supervisor
description: Use when running supervised market research batches that need fresh Codex contexts for research, validation, remediation, or later skill-improvement feedback collection.
---

# Market Research Batch Supervisor

Use this skill from a supervised Codex session to orchestrate `market-research researcher` and `market-research verifier` child sessions. The batch supervisor owns subprocess execution, pass/fail gating, remediation retries, logs, summaries, and skill-improvement feedback collection.

Core rule: keep research, validation, remediation, and skill improvement separate.

- Research child: runs `$market-research researcher SYMBOL`, including best-effort PDF generation after final Markdown.
- Validation child: runs `$market-research verifier RUN_DIR`.
- Remediation child: fixes only open critical/moderate validation issues in the research bundle.
- Self-improvement: explicit prompt-only review over completed batch roots; self-improvement is not automatic.
- Supervisor: watches the run, inspects failures, and preserves improvement feedback for later consolidation.

## Required Read

Read `references/supervisor-workflow.md` for commands, artifact layout, custom command templates, failure handling, and feedback collection.

## Run Gate

Final pass gate: no open `critical` or `moderate` validation issues. Open `minor` findings are allowed but must be reported.

Treat the finished investor report as the product: preserve `reports/` for polished deliverables, `runtime/` for intermediate work, and `data/` for deterministic evidence. Prefer field-level freshness guidance over cache-mechanics disclosure; only surface cache/provider mechanics in the main report when stale, missing, or conflicting data changes investor interpretation.

## Output Contract

Each run root contains `research-loop-summary.json`, `loop-skill-issues.md`, `operator-notes.md`, iteration logs, canonical deterministic bundles under `data/SYMBOL/YYYY-MM-DD/`, final reports and validations under `reports/SYMBOL/YYYY-MM-DD/`, and transient prompts/logs/issues under `runtime/SYMBOL/YYYY-MM-DD/` or the configured runtime run root.

Use `operator-notes.md` for future user-requested changes that should not be implemented automatically, such as browser/captcha handoff, alternate report formats, or new data providers.
