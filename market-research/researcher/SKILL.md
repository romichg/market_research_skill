---
name: market-research-researcher
description: Research US-listed equities, ADRs, and ETFs from a ticker symbol using public/free sources; create cited markdown and JSON artifacts; use deterministic helper scripts when useful but gracefully fall back to procedural research when helpers fail or are sparse. Use when the agent is asked for investment, equity, stock, ADR, ETF, fund, issuer, holdings, valuation, risk, or market research on a symbol.
---

# Market Research Researcher

Use this skill to produce one evidence-backed research bundle for a public equity, ADR, or ETF symbol. This is research support, not personalized financial advice.

## Core Rule

Use helper output as evidence, not authority.

```text
helper succeeds -> use structured context
helper partially succeeds -> use reliable helper output, fill targeted gaps, disclose remaining limits
helper fails -> research procedurally, disclose helper failure
helper gets bloated/flaky -> split, cap outputs, or demote to optional
```

Do not abandon the report solely because a helper failed unless no credible public source can be accessed and no user-provided files exist.

## Required References

- Read `references/source-policy.md` before source gathering and citation work.
- Read `references/equity-research.md` for equities and ADRs.
- Read `references/etf-research.md` for ETFs.
- Read `references/report-template.md` before writing final artifacts.
- Read `references/researcher-workflow.md` for command examples, deterministic fetch options, procedural helper commands, artifact layout details, and PDF generation.
- Read `references/provider-data-map.md` when adding, validating, or reasoning about deterministic provider fields, duplicate data, endpoint budgets, or fallback behavior.

## Artifact Roots

- `data/SYMBOL/AS_OF/`: deterministic raw, normalized, manifest, gaps, deterministic-data-usage requirements, and research input pack.
- `runtime/SYMBOL/AS_OF/`: procedural helper manifests, source bundles, prompts, notes, and run-time working files.
- `reports/SYMBOL/AS_OF/`: polished research Markdown, JSON sidecar, best-effort PDF, and validation-facing report artifacts.

Keep final investor deliverables under `reports/`; keep intermediate work under `runtime/`; keep deterministic evidence under `data/`.

## Workflow Summary

1. Start with `market-research/shared/scripts/deterministic_research_collector.py fetch SYMBOL --asset-type auto --as-of YYYY-MM-DD --data-dir ./data --reports-dir ./reports` when provider keys or cached raw files are available. Use `doctor`, `--offline`, provider filters, endpoint filters, and `--max-provider-calls` as described in `references/researcher-workflow.md`.
2. Inspect the deterministic bundle before drafting. Every normalized value must carry provider, source URL, raw path, and status. Missing data must remain a structured gap with only attempted providers listed.
3. Inspect `data/SYMBOL/AS_OF/deterministic_data_usage.json`. Required and review datapoints must be used in the report or explicitly dispositioned in the report JSON. Required datapoint rationales must be field-specific and explain investor relevance, duplication by better evidence, or reason for omission.
4. Use `market-research/shared/scripts/procedural_source_helper.py` only for classification, source recording, source gaps, compact context preparation, targeted gap fills, and supported issuer payload promotion. Do not let procedural gap filling become open-ended browsing; search for named missing fields only.
5. Use targeted procedural research when the deterministic bundle does not explain the business well enough for an investor. For operating companies, fill business-profile gaps on what the product does, business model, technology explanation in plain language, who pays, revenue model, customer or government/commercial exposure, acquisition contribution, current commercial traction, valuation context, current technical setup, and practical demand drivers.
6. For event-driven issuer news dated on or after the as-of date, perform a same-day SEC freshness check against the issuer filings page or SEC company browse results, especially for 8-K, 10-Q, 10-K, S-3, S-1, 13D/G, and proxy filings. If deterministic SEC submissions lag, capture the filing procedurally, cite the filing date, and disclose the deterministic omission in `Data Issues And Discrepancies`.
7. Write final artifacts under `reports/SYMBOL/AS_OF/`: `SYMBOL-research.md`, `SYMBOL-research.json`, and best-effort `SYMBOL-research.pdf` when local PDF tooling is available.
8. Same-session self-check the artifacts for missing citations, stale dates, unsupported claims, deterministic-usage gaps, and source/entity alignment. Label this as a self-check, not independent validation.

## Report Contract

The Markdown report must follow `references/report-template.md` and read like investor-grade research, not a validation transcript or artifact inventory. Lead with thesis, variant view, what matters, what can go wrong, what would change the view, and what to monitor.

The JSON sidecar must satisfy `market-research/shared/schemas/research-output.schema.json`, including `technical_analysis`, `valuation_or_performance`, `decision_factors`, `risks`, `catalysts`, `source_coverage`, and `calculation_audit`. When a deterministic bundle exists, include `deterministic_bundle` and field-level `deterministic_data_usage` entries for all required/review datapoints that were used or intentionally omitted.

When provider endpoints are rate-limited, plan-gated, protected, unavailable, or otherwise incomplete, include provider-limit impact mapping in the report JSON and, when material, in the data-quality discussion. Map each limitation to its affected analysis area. Examples: unavailable short interest affects crowding/squeeze analysis; unavailable forward estimates affects valuation; unavailable insider statistics affects dilution/governance analysis; unavailable filing sections affects direct risk-factor and MD&A validation.

## Source Discipline

Every material quantitative claim must be cited or marked `Data not available` / `unverified`. Include source date, accessed date, and confidence when possible.

For deterministic bundles, cite the normalized file and raw source path, for example `data/AAPL/2026-06-01/normalized/market_snapshot.json` and the corresponding `raw/` JSON from `source_manifest.json`.

Every cited `source_id` should appear in `sources.json`; every cited public page or document should have a saved `local_artifact` in `source_bundle/` when the source can be saved. If a dynamic page cannot be captured cleanly, describe the limitation as a workflow extraction gap rather than public-data unavailability.

Keep detailed local artifact paths in the JSON sidecar or a consolidated evidence section unless an inline citation is necessary for a contentious, surprising, or source-sensitive claim. Keep facts separate from interpretation in major sections.

## Final Response

Tell the user the artifact paths, including the PDF path if generated, and recommend running `market-research verifier` in a fresh agent context against the report directory.

Do not require subscriptions or API keys. You may record exploratory notes about data that would have improved quality, but do not recommend purchasing a paid service from a single run.
