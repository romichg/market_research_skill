---
name: market-research-full
description: Research, validate, and supervise market research runs for US-listed equities, ADRs, and ETFs using deterministic provider data, procedural source capture, and frozen-artifact validation.
---

# Market Research Full

Use this single skill for all market research workflows. This is research support, not personalized financial advice.

## Modes

- Producer/researcher: follow `researcher/SKILL.md`.
- Verifier: follow `verifier/SKILL.md`.
- Supervised loop runner: follow `loop-runner/SKILL.md`.

## Canonical Layout

- Deterministic evidence belongs under `data/SYMBOL/YYYY-MM-DD/`.
- Final reports and validations belong under `reports/SYMBOL/YYYY-MM-DD/`.
- Prompts, logs, source workspaces, validation scaffolds, remediation notes, and other transient artifacts belong under `runtime/SYMBOL/YYYY-MM-DD/`.

Do not write new artifacts to the retired run-root name used before this rework. Invoke only `$market-research-full` with the `researcher`, `verifier`, or `loop-runner` mode.
