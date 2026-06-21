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
