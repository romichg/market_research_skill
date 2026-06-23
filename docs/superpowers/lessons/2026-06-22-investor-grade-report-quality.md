# Investor-Grade Report Quality Lessons

Date: 2026-06-22

## Lessons

- Deterministic evidence should support the report, not become the report. The Markdown should read like an investor memo with thesis, materiality, variant view, risks, and monitoring triggers.
- Keep detailed local artifact paths in `sources.json`, `material_claims`, `deterministic_data_usage`, validation scaffolds, or a consolidated evidence section. Avoid appending path-level `Source:` citations to nearly every paragraph.
- Deterministic coverage is not sufficient for report quality. A report can satisfy field usage requirements and still feel like a compliance transcript if it lacks synthesis and judgment.
- Inline citations are still useful for surprising, contentious, source-sensitive, or highly material claims. The failure mode is citation density, not citation discipline.
- Validation should distinguish narrative use from evidence-only references. Raw paths, field names, and URLs prove auditability, but they do not prove the investor-facing prose used the datapoint well.
- Weak deterministic usage rationales should be surfaced as quality issues. Boilerplate sidecar text can satisfy a schema while hiding whether the datapoint actually mattered.
- Provider gaps should be mapped to affected analysis areas. For example, unavailable short interest affects crowding/squeeze analysis; unavailable forward estimates affects valuation; unavailable insider statistics affects dilution/governance analysis.
- Framework agreements, "up to" values, and milestone-dependent news should be explicitly framed as potential value, firm order, backlog, booked revenue, or non-binding framework as supported by sources.
- The final report is the investor product; runtime artifacts are intermediate work. Preserve the `reports/` versus `runtime/` separation instead of making self-contained report bundles the default improvement.
- Provider/tool internals are usually not investment content. Inline provider names, cache status, deterministic bundle names, local paths, and raw artifact mechanics only when the provenance changes investor interpretation; otherwise keep them in references, appendices, JSON sidecars, or validation artifacts.
- Freshness should be field-specific, not cache-specific. Investors care whether price, market cap, filings, ownership, estimates, short interest, and news are current enough for the decision; they usually do not care whether durable source-dated evidence was read from cache.

## Rerun Watch Items

- Check whether regenerated reports are easier to read after moving detailed citations out of the main flow.
- Check whether validation surfaces minor weak-rationale issues without turning them into noisy blocking failures.
- Check whether early-stage volatile equities promote useful context fields, such as latest volume and book value, into review materiality.
- Check whether filing-section extraction gaps remain disclosed and actionable when direct filing excerpts are absent.
- Check whether the new report states latest-available dates for stale or missing material fields without explaining irrelevant cache mechanics in the main body.
