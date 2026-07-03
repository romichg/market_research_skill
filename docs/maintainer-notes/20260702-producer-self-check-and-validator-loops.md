# Producer Self-Check And Validator Loop Lessons

Date: 2026-07-02

## Context

A supervised batch run showed that several validator findings were mechanical enough to catch before the first verifier handoff. Some producer-validator loops reached multiple remediation passes even though the root causes could be shifted into producer-owned self-checks.

## Durable Lessons

- Keep expanding `market-research/shared/scripts/producer_self_check.py` rather than relying on validator remediation loops for mechanical report defects.
- ETF holdings rows with business, sector, outlook, or price/technical context need supporting company/context sources. If that support is missing, the producer should either capture it before validation or clearly disclose that the portfolio snapshot has thin context.
- Source portability matters. Final report directories should prefer report-local `source_bundle/` paths in source registries, report JSON, copied context JSON, run manifests, and parseable bundle JSON when matching copied artifacts exist.
- Validator findings that repeat across symbols are usually candidates for deterministic lint, source-registry reconciliation, or report-language lint rather than more prompt prose.

## Follow-Up Candidates

- Add an arithmetic audit for derived JSON values such as `shares * latest_close`.
- Improve deterministic data-usage rationale generation so sidecars use field-specific, report-section-specific wording.
- Add an ETF peer/alternative comparison self-check for funds where the thesis depends on product structure or niche exposure.
- Keep reducing workflow/provenance wording in investor-facing sections while preserving reproducibility in sources and data-quality sections.
