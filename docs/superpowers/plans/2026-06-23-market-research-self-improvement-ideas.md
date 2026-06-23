# Market Research Self-Improvement Ideas

Review date: 2026-06-23

Run reviewed: `runtime/market-research-batch-20260623`

## Executive Summary

The QUBT batch passed with no open critical or moderate validation issues, and the report has the raw ingredients of a useful investor memo. The biggest improvement opportunity is report quality: make the final product sharper, less tool-aware, more explicit about what matters to an investor, and more disciplined about source/provider caveats.

The separation between `reports/` and `runtime/` is useful and should be preserved. `reports/` should remain the final product; `runtime/` should remain the workspace for intermediate evidence, prompts, logs, and source artifacts. The improvement target is not to copy runtime into reports by default. It is to make the report reference evidence cleanly, keep audit details out of the main narrative, and ensure validation can follow those references when needed.

The highest-value fixes are:

- Reduce investor-facing provider and skill-internal references in the main report. Provider names matter when source discrepancies or data-quality limits change the investment conclusion; otherwise provenance belongs in an appendix or evidence section.
- Add a freshness policy for time-sensitive fields. Cache mechanics should stay in audit artifacts; the report should disclose source dates or "latest available" status only when freshness affects investment interpretation.
- Add explicit market-cap discrepancy severity and provider-limit impact summaries to deterministic outputs, so reports can map data quality limits to affected analysis areas without hand-built prose.
- Strengthen the report template toward buy-side memo quality: thesis, variant view, what has to go right, what can break, valuation sanity check, catalysts, monitoring triggers, and clear caveats.
- Teach `validate_market_research.py` to resolve `procedural_runtime.sources_file`, deterministic source artifacts, and canonical deterministic bundle sources without requiring runtime evidence to be copied into reports.
- Aggregate weak deterministic-data-usage rationale findings into concise audit warnings instead of emitting dozens of separate minor issues.
- Add helper support for SEC submissions wrapper inspection and normalized SEC filing indexes/section extracts so researchers can extract investor-relevant filing facts with less manual work.

## Evidence From The Run

- Supervisor summary: `runtime/market-research-batch-20260623/research-loop-summary.json`
- Research memo: `reports/QUBT/2026-06-23/QUBT-research.md`
- Research sidecar: `reports/QUBT/2026-06-23/QUBT-research.json`
- Validation: `reports/QUBT/2026-06-23/QUBT-validation.md`
- Validation scaffold: `reports/QUBT/2026-06-23/QUBT-validation-scaffold.md`
- Producer skill issues: `runtime/market-research-batch-20260623/QUBT/2026-06-23/QUBT-market-research-issues.md`
- Validator skill issues: `reports/QUBT/2026-06-23/QUBT-validator-skill-issues.md`
- Deterministic bundle: `data/QUBT/2026-06-23/`

## What Worked

- The final research memo passed validation with zero open critical or moderate issues.
- The report framed QUBT as a high-upside, high-variance commercialization option and did not overstate the Planck Dynamics framework as booked revenue.
- Data gaps were mapped to investor relevance: missing short interest limited squeeze/crowding analysis; missing forward estimates limited forward valuation; missing insider statistics limited dilution/governance analysis.
- The report used deterministic data without becoming a path-heavy audit trail. It had thesis, valuation tension, risks, catalysts, monitoring triggers, bull/base/bear variables, and a clear "My Take" section.
- The validator checked source hashes for frozen SEC filings and the Planck press release, and correctly downgraded the two remaining issues to minor.

## Improvement Ideas

### 1. Move Provider And Skill-Internal References Out Of The Main Investor Narrative

Evidence: `reports/QUBT/2026-06-23/QUBT-research.md` includes main-body references to `Alpha Vantage`, `FMP`, `Tiingo`, `Twelve Data`, `EODHD`, `MarketAux`, `deterministic bundle`, `runtime source registry`, `raw/sec`, `normalized`, `source_manifest.json`, and `sources.json`.

As an investor, provider names are useful only when they affect confidence or interpretation:

- Material discrepancy: the market-cap conflict between Alpha Vantage and FMP is relevant because it changes sales-multiple framing.
- Data gap: missing short interest, forward estimates, and insider statistics are relevant because they limit crowding, forward valuation, and governance analysis.
- Primary-source confidence: SEC filings and company press releases are relevant because they are authoritative source types.

Most other provider labels are not useful in-line. The investor does not care that the close came from Tiingo or the volume came from Twelve Data unless the figure is stale, disputed, or methodologically unusual. The main report should say "latest available market data" or "provider data showed a discrepancy" and keep provider names in an appendix or JSON sidecar.

Recommended report structure:

- Main body: investment thesis, facts, valuation, risks, catalysts, monitoring triggers, and only material source-quality caveats.
- "Data Quality And Source Notes" near the end: concise bullets for material data limitations and discrepancies.
- Appendix or sidecar: provider names, local artifact paths, source IDs, raw paths, hashes, deterministic bundle paths, and skill/runtime internals.

### 2. Add Field-Level Freshness Policy

Evidence: `data/QUBT/2026-06-23/manifest.json` shows a fresh `as_of` bundle created at `2026-06-23T01:33:41.463861+00:00` with `offline: false`, while `source_manifest.json` shows all 35 endpoint records have `cache_raw_path` entries. The older `data/QUBT/2026-06-22/` bundle was not cited in the report, but the 2026-06-23 run used the shared cache layer.

The useful investor-facing question is not whether a datapoint came from cache. The useful question is whether the datapoint is fresh enough for its role in the analysis.

Recommended policy:

- Fresh/latest-available required: price, volume, market cap, short interest, forward estimates, recent news, insider transactions, and any event-driven datapoint used as a catalyst.
- Cached durable evidence acceptable: SEC filings, company press releases, historical statements, company identity, filed share counts, and older risk-factor text, as long as source dates are preserved.
- Report disclosure required only when freshness affects interpretation: stale market data, unavailable current short interest, unavailable forward estimates, no fresh insider data, or a catalyst/event date that could have changed.
- Cache mechanics belong in references, validation artifacts, manifests, or JSON sidecars. The main report should use investor-readable phrasing such as "latest available market data as of DATE" or "no current short-interest source was available."

The validator should check that freshness-sensitive fields have source dates or latest-available dates and are not misleadingly described as current when they are stale.

### 3. Strengthen Buy-Side Memo Quality

Evidence: `reports/QUBT/2026-06-23/QUBT-research.md` has useful sections, but still spends too much attention on provider mechanics and not enough on investor decision structure.

The report should be optimized for an experienced investor who wants to know:

- What is the thesis in one paragraph?
- What is the market likely pricing in?
- What is the variant view or controversy?
- What evidence would make the thesis work?
- What would invalidate it?
- What valuation sanity check matters now?
- What are the next 3-5 monitoring events?

This does not require a recommendation rating. It does require more disciplined synthesis and fewer audit mechanics in the main body.

### 4. Resolve Source IDs Across Runtime And Deterministic Evidence

Evidence: `reports/QUBT/2026-06-23/QUBT-validation-scaffold.md` flagged six moderate missing `source_id` issues, while `reports/QUBT/2026-06-23/QUBT-validation.md` confirmed the frozen artifacts existed and were inspected.

`validate_market_research.py` currently checks only `run_dir/sources.json` and a top-level `sources_file` field. The QUBT report stores procedural information under `procedural_runtime`, and deterministic claims cite IDs such as `deterministic_sec_companyfacts` that should resolve to `data/QUBT/2026-06-23/source_manifest.json` or deterministic normalized artifacts.

This is a validator navigation problem, not an argument for copying runtime evidence into reports. The validator should follow the report's explicit runtime and deterministic pointers while preserving the `reports/` and `runtime/` separation.

The validator should load sources from:

- `run_dir/sources.json`
- `report["sources_file"]`
- `report["procedural_runtime"]["sources_file"]`
- deterministic bundle `source_manifest.json`
- deterministic `material_claims[*].source_artifact` paths when present

### 5. Aggregate Weak Usage Rationale Noise

Evidence: `reports/QUBT/2026-06-23/QUBT-validation-scaffold.md` emitted 39 weak-rationale minor issues. The completed validation reduced this to one useful minor issue, `QUBT-VAL-002`.

The scaffold should still preserve field-level detail in JSON, but the Markdown and top-level issue list should use one aggregate minor warning per materiality bucket:

- `deterministic-usage-weak-required-summary`
- `deterministic-usage-weak-review-summary`

Each aggregate issue should include a count and a short sample list. Full field detail can remain under `deterministic_data_usage_dispositions`.

### 6. Improve SEC Filing Index And Section Extraction

Evidence: `runtime/market-research-batch-20260623/QUBT/2026-06-23/QUBT-market-research-issues.md` says the deterministic bundle had SEC submissions but lacked `normalized/sec_filings_index.json` and filing-section extracts.

The deterministic collector should emit a normalized SEC filing index from raw SEC submissions, including accession number, form type, filing date, report date, primary document URL, and local raw path. For common forms like 10-K, 10-Q, DEF 14A, 8-K, and 13D/A, add best-effort section extraction status fields. If extraction is unavailable, record a structured gap with attempted source and reason.

### 7. Document And Helperize Wrapped Provider Payloads

Evidence: the producer issue file notes that SEC submissions are wrapped under a top-level `data` key, which is reasonable for provenance but error-prone for ad hoc inspection.

Add a small inspection helper or documented function to unwrap provider payloads for common raw formats. This should avoid each researcher child rediscovering wrapper shape manually.

### 8. Promote Deterministic Fundamentals Into Procedural Context

Evidence: `procedural_source_helper.py prepare-research-context` marked QUBT context sparse despite deterministic SEC companyfacts and normalized fundamentals being available.

When procedural context is sparse, the helper should import selected deterministic facts from `normalized/identity.json`, `market_snapshot.json`, `equity_fundamentals.json`, `technical_signals.json`, and `gaps.json`. This gives the researcher a coherent base context without weakening source discipline.

### 9. Add Discrepancy Severity For Valuation-Sensitive Fields

Evidence: QUBT market capitalization differed materially between Alpha Vantage and FMP. The report disclosed this well, but the producer had to write the severity assessment manually.

Add deterministic discrepancy metadata for valuation-sensitive fields such as market capitalization, shares outstanding, revenue, book value, and target price. The output should distinguish minor provider variance from material discrepancies that must be disclosed.

### 10. Add Provider-Limit Impact Summaries

Evidence: the QUBT report manually mapped provider issues to affected analysis areas, including short interest, forward estimates, insider statistics, and statement coverage.

The deterministic collector already preserves endpoint status. Add a derived `analysis_limitations` summary that maps endpoint failures to analysis effects. This should remain factual, not infer unsupported investment conclusions.

### 11. Clarify Runtime-Root Validation Behavior

Evidence: the producer issue file reports `validate_market_research.py` rejected the supervised runtime root even though the final report was under the canonical reports layout.

Do not allow final reports under runtime, but add a supervised-run mode or better error guidance: when given `runtime/market-research-batch-.../SYMBOL/YYYY-MM-DD`, detect `run_manifest.json` and point to the canonical `reports/SYMBOL/YYYY-MM-DD` artifact path if it exists.

### 12. Make Environment Dependency Gaps Actionable

Evidence: PDF generation failed because LaTeX was missing `lmodern.sty`, and the producer could not run schema validation because `jsonschema` was absent.

Add a dependency preflight helper that reports optional and required tooling status:

- required: Python standard library scripts
- optional but expected: `jsonschema`
- optional PDF path: `pandoc`, `xelatex`, LaTeX packages including `lmodern`

The helper should write an operator-facing note and never turn optional PDF tooling absence into a research failure.
