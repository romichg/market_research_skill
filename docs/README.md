# Market Research Skill Docs

This directory contains active documentation for the market-research skill repository. Active docs should be short, current, and useful for future work. Durable lessons belong in canonical docs, maintainer notes, or tests; generated scratch artifacts should be deleted rather than preserved indefinitely.

## Active Docs

- `docs/architecture.md`: skill layout, mode boundaries, canonical artifact roots, and evidence roles.
- `docs/quality-bar.md`: investor-grade report standards, evidence discipline, deterministic-data usage, freshness, validation expectations, and self-improvement lessons.
- `docs/operations.md`: development commands, preflight checks, research and validation workflows, batch supervision, self-improvement prompt generation, and generated-artifact handling.
- `docs/maintainer-notes/`: curated handoff notes and implementation lessons that are useful to future maintainers but too run-specific for canonical docs.

There are currently no active implementation plans or design specs. New human-reviewed plans/specs may live under `docs/superpowers/` while actively guiding work, then should be deleted once implemented and summarized in canonical docs, maintainer notes, or tests. Generated self-improvement prompt outputs under `docs/superpowers/plans/self-improvement/` are local-only.

## Generated Material Policy

Do not keep completed/generated plans active just because they may be useful someday. Extract durable conclusions into the active docs above and remove stale generated material before publishing.

Do not depend on generated `data/`, `reports/`, or `runtime/` outputs in committed tests or docs.
