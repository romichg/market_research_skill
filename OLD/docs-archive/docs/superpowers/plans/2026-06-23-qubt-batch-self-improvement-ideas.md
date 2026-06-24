# Market Research Self-Improvement Ideas

Review date: 2026-06-24

Run reviewed: `runtime/market-research-batch-20260623`

## Executive Summary

The QUBT batch passed the blocking validation gate, but it is a useful regression sample because the remaining defects are product-quality and workflow-contract issues rather than basic evidence failures. The final report is materially supported, yet it still leaks routine provenance language into the investor-facing narrative, leaves report-JSON deterministic usage rationales weak, omits a few filed-risk checklist items, and exposes validation/tooling gaps around JSON Schema and validator skill issue sidecars.

The next improvement pass should not rewrite the production skills in this review step. It should prepare a focused implementation that converts the QUBT minor issues into tests and helper checks, then tightens researcher/verifier instructions so future reports remediate these issues before the batch can be considered clean.

## Evidence From The Run

- `runtime/market-research-batch-20260623/research-loop-summary.json` and `python3 market-research/batch-supervisor/scripts/research_loop.py summarize runtime/market-research-batch-20260623` show QUBT passed with no unresolved blocking issues.
- `reports/QUBT/2026-06-23/QUBT-validation.md` reports `0` open critical issues, `0` open moderate issues, and `3` open minor issues.
- `reports/QUBT/2026-06-23/QUBT-validation.md` issue `QUBT-VAL-001` flags main-body phrases such as "latest deterministic adjusted close", "primary normalized market capitalization", routine provider names, and local-calculation language.
- `python3 market-research/shared/scripts/report_language_lint.py reports/QUBT/2026-06-23/QUBT-research.md --json` returns four minor findings: two `deterministic` findings and two `vendor-name-main-body` findings.
- `reports/QUBT/2026-06-23/QUBT-validation-scaffold.json` reports no missing required/review dispositions, but `deterministic_data_usage_dispositions.summary` shows `weak_required: 20` and `weak_review: 16`.
- `reports/QUBT/2026-06-23/QUBT-validation.md` issue `QUBT-VAL-003` says the risk section does not separately summarize cybersecurity/data-integrity risk or current litigation/legal-proceeding status.
- `reports/QUBT/2026-06-23/QUBT-validator-skill-issues.md` records `VSKILL-001`: the verifier expects JSON Schema checks but this environment did not have `jsonschema` installed.
- `reports/QUBT/2026-06-23/QUBT-validator-skill-issues.md` records `VSKILL-002`: validator skill issue sidecars have no schema or required format.
- `runtime/market-research-batch-20260623/QUBT/2026-06-23/QUBT-market-research-issues.md` says same-day SEC filings can be missed by deterministic SEC submissions snapshots and that provider profile text may be stale versus current filings/releases.
- `runtime/market-research-batch-20260623/QUBT/2026-06-23/iteration-01/producer.log` records PDF generation failure because local LaTeX lacked `lmodern.sty`.

## Improvement Ideas

1. Make investor-facing provenance hygiene a producer-side quality gate, not only a validator note. The linter already catches the QUBT report's main-body `deterministic` and routine vendor-name leakage. Add tests around the exact QUBT failure shape and wire the linter into researcher final verification guidance before handoff to the validator.

2. Tighten the deterministic usage sidecar contract. The report JSON uses `disposition`, not `status`, and the scaffold can count weak rationales but still lets the run pass. Keep weak rationales non-blocking by default, but require field-specific rationales for all required datapoints and make the scaffold expose concise actionable examples that producers can remediate.

3. Add an equity risk checklist that the researcher must explicitly address or disposition. QUBT covered major execution, manufacturing, dilution, governance, and valuation risks, but omitted cybersecurity/data-integrity and current litigation/legal-proceeding status as distinct risks. The template should require an `addressed`, `not_material`, or `not_found_in_filed_sources` treatment for key filed-risk categories.

4. Provide an operational JSON Schema validation helper. The verifier skill should not depend on an undeclared local `jsonschema` module. Add either a standard-library fallback for lightweight required-field checks plus documented limitations, or a project dependency and tests that fail clearly when unavailable.

5. Define a validator skill issue sidecar contract. The markdown sidecar was useful, but its format is ad hoc. Add a small JSON schema or markdown structure with `id`, `severity`, `status`, `description`, `suggested_owner`, and `evidence_path` so batch-level feedback collection can aggregate it.

6. Add same-day SEC freshness handling for event-driven equities. The QUBT producer had to capture a same-day June 23, 2026 8-K procedurally because the deterministic SEC submissions snapshot lagged. The researcher should be instructed to query issuer SEC filings pages or SEC company browse pages for same-day events when there is same-day issuer news or acquisition language.

7. Improve PDF preflight and reporting. PDF generation is best effort, but repeated LaTeX missing-package failures should produce a concise operator note or dependency hint instead of a large log-only failure.

## Priority

Highest priority is items 1-3 because they directly affect the final investor report product. Items 4-5 improve validator reproducibility and feedback aggregation. Items 6-7 are operational hardening that should be implemented after the report-quality gate is reliable.

