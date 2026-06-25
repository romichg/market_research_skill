# Market Research Skill Docs

This directory contains active documentation for the market-research skill repository. Active docs should be short, current, and useful for future work. Historical implementation plans, generated self-improvement outputs, and stale specs can be kept locally under ignored `archives/`.

## Active Docs

- `docs/architecture.md`: skill layout, mode boundaries, canonical artifact roots, and evidence roles.
- `docs/quality-bar.md`: investor-grade report standards, evidence discipline, deterministic-data usage, freshness, validation expectations, and self-improvement lessons.
- `docs/operations.md`: development commands, preflight checks, research and validation workflows, batch supervision, self-improvement prompt generation, and generated-artifact handling.

There are currently no active implementation plans or design specs. New plans/specs may live under `docs/superpowers/` while actively guiding work, then should be archived once implemented and summarized in canonical docs or tests.

## Archive Policy

Do not keep completed/generated plans active just because they may be useful someday. Move them to local ignored `archives/` and preserve enough path context to recover the reason for the work later.

Do not extend archived files unless restoring legacy context. Put durable conclusions in the active docs above. Local archives should not be pushed to GitHub.
