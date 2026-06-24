# Docs And Instruction Consolidation Design

Date: 2026-06-24

## Goal

Consolidate the repository documentation and agent-facing instructions so the active tree is small, current, and easy to load without losing historical planning context. This pass is limited to documentation, instruction files, and tests that encode documentation expectations. It does not change market-research workflow behavior, helper-script behavior, schemas, provider logic, or report validation rules.

## Current Problems

The active `docs/` tree mixes durable guidance with completed implementation plans, generated self-improvement prompts, generated JSON outputs, and historical rework notes. Several plan files duplicate lessons that are already implemented in the skill and tests. The largest active file, `docs/plans/20260619_rework_plan.md`, is historical and still references old skill names that should not guide future work.

`AGENTS.md` and `README.md` are mostly current, but they both carry operational guidance without a single canonical docs map. Tests also assert dated lesson files directly, which makes lesson consolidation harder unless the tests are updated with the new canonical documentation contract.

## Recommended Approach

Use a canonical-docs pass:

- Move stale and generated planning artifacts out of active `docs/` into `OLD/docs-archive/`, preserving their original relative paths for future recovery.
- Replace scattered lessons and plans with a compact active documentation set.
- Keep `README.md` user-facing and concise.
- Keep `AGENTS.md` as the short contributor and agent contract.
- Update tests so they assert the consolidated active docs rather than specific dated lesson artifacts.

This keeps history available while reducing token load and future maintenance drift.

## Active Documentation Structure

After this pass, active `docs/` should contain:

- `docs/README.md`: documentation index, active-vs-archive policy, and links to the canonical docs.
- `docs/architecture.md`: repository layout, skill-mode boundaries, canonical artifact roots, and source/evidence artifact roles.
- `docs/quality-bar.md`: consolidated lessons for investor-grade reports, evidence discipline, deterministic-data usage, field-level freshness, validation expectations, provider/provenance handling, and self-improvement boundaries.
- `docs/operations.md`: common commands, test workflow, preflight checks, batch-supervisor usage, self-improvement prompt workflow, and generated-artifact handling.
- `docs/plans/`: only current, approved implementation plans.
- `docs/superpowers/specs/`: current design specs that are still useful for process history.

Historical plans, generated prompt outputs, completed implementation plans, and dated scratch JSON should not remain in active `docs/`.

## Archive Policy

Move obsolete active docs into `OLD/docs-archive/` with their original paths preserved. For example:

- `docs/plans/20260619_rework_plan.md` becomes `OLD/docs-archive/docs/plans/20260619_rework_plan.md`.
- completed or generated files under `docs/superpowers/plans/` become `OLD/docs-archive/docs/superpowers/plans/...`.
- stale specs under `docs/superpowers/specs/` may be archived after their durable conclusions are represented in the new canonical docs.

Do not delete historical material in this pass. Do not extend `OLD/` material except to preserve the archive.

## README Design

`README.md` remains the user-facing entry point:

- Summarize what the skill does.
- Describe requirements, install, configuration, single research, verification, supervised batch, and troubleshooting.
- Point readers to `docs/operations.md` for detailed operator workflows.
- Point readers to `docs/quality-bar.md` for report-quality and validation standards.
- Avoid duplicating detailed internal policy that belongs in canonical docs.

## AGENTS Design

`AGENTS.md` should stay short and directive:

- Repository structure and active docs entry points.
- Build/test/helper commands.
- Coding and naming conventions.
- Testing expectations.
- Commit/PR expectations.
- Security/configuration rules.
- Archive and generated-artifact rules.

It should tell agents where to look instead of embedding every policy detail.

## Quality-Bar Consolidation

`docs/quality-bar.md` should synthesize the durable lessons currently spread across dated lesson and self-improvement files:

- The final report is the investor product; runtime artifacts are intermediate work.
- Deterministic evidence supports the report but must not become the report.
- Investor-facing prose should prioritize thesis, materiality, variant view, valuation context, catalysts, risks, and monitoring triggers.
- Detailed local paths, hashes, provider mechanics, and source IDs belong in sidecars, evidence sections, appendices, or validation artifacts unless they change investor interpretation.
- Freshness is field-specific, not cache-specific.
- Required and review deterministic datapoints must be used or explicitly dispositioned.
- Weak boilerplate deterministic-usage rationales are quality issues.
- Provider gaps must map to affected analysis areas.
- Self-improvement remains prompt-only and operator-triggered.

The existing test assertions that read dated lesson files should move to this consolidated file.

## Operations Consolidation

`docs/operations.md` should collect repeatable workflows:

- Preflight command.
- Helper `--help` commands.
- Pytest commands.
- Single-symbol researcher/verifier flow.
- Batch-supervisor flow.
- Self-improvement prompt generation flow.
- PDF tooling expectations.
- Generated artifact policy for `data/`, `reports/`, and `runtime/`.

Operational details should not be repeated in every historical plan.

## Test Design

Update documentation-related tests to enforce the new contract:

- Active docs do not reference retired skill paths except archived material under `OLD/`.
- The consolidated quality-bar doc contains the durable investor-product and freshness lessons.
- The docs index points to active canonical docs.
- Historical/generated planning files are absent from active `docs/`.
- Archive files remain under `OLD/docs-archive/` when moved.

Keep behavior tests for helpers and skill contracts unchanged unless path assertions must follow the documentation moves.

## Migration Steps

1. Create the new canonical active docs.
2. Move obsolete and generated plan artifacts into `OLD/docs-archive/`, preserving their relative paths.
3. Update `README.md` and `AGENTS.md` to point at canonical docs.
4. Update tests that currently assert dated lesson or plan files.
5. Run the documentation/layout-related tests first, then the full pytest suite if time allows.

## Non-Goals

- No helper-script refactor.
- No market-research workflow behavior changes.
- No schema contract changes.
- No provider changes.
- No report-template or verifier-quality behavior changes beyond documentation references.
- No deletion of historical planning artifacts.

## Risks

Moving docs can break tests that intentionally allow old-path references only in specific active files. The implementation should update those tests alongside the doc moves.

Archiving too aggressively can hide useful rationale. Each archived plan should either be clearly historical or have its durable conclusions represented in `docs/quality-bar.md`, `docs/architecture.md`, or `docs/operations.md`.

Keeping too many generated files active defeats the purpose of consolidation. Active docs should be documents humans and agents are expected to read before future work.
