# Market Research Self-Improvement Ideas

Review date: 2026-06-23

Run reviewed: `runtime/market-research-batch-20260623`

Additional human feedback incorporated: the QUBT report still read too much like an internal evidence audit and not enough like investor research. The next improvement pass should optimize the finished report, not merely polish provenance handling.

## Executive Summary

The prior self-improvement plan was too narrow. It correctly identified provenance leakage, but the deeper issue is report product quality: the report must add analysis, explain the business, organize numbers for consumption, and keep internal mechanics out of the investor narrative.

The report should use deterministic and procedural research as inputs, not as visible organizing principles. Investors do not care whether a fact came from a deterministic bundle, a procedural source helper, a manifest, or a normalized JSON file. They care what the company does, what the valuation implies, what can go right, what can break, what evidence would change the view, and what data limitations affect confidence.

## Core Product Requirements

1. `Bottom Line` should be an executive summary. It should not be a tight one-paragraph thesis that loses fidelity. It must introduce market value or valuation range before discussing whether valuation is justified.
2. `Key Facts` should be a table or at-a-glance presentation. It should not cite `normalized/*.json`, `manifest.json`, deterministic artifacts, source registries, or routine provider names.
3. `Source Base And Data Quality` and `Explicit Data Gaps` should become one bottom-of-report section, `Data Issues And Discrepancies`.
4. Provider names belong in the main body only when provider identity itself changes interpretation. Otherwise, provider details belong in `Data Issues And Discrepancies` or `Sources And Evidence`.
5. `Business Profile` should say what the security is directly, such as "QUBT is a US-listed equity." It should not contain awkward negative classification language like "not an ETF or ADR."
6. Business and technology explanations must be plain-language and useful. If the company sells photonic components, quantum security, reservoir computing, or similar specialized products, the report must explain what those mean and how they can become revenue.
7. Business model and demand drivers need actual research and interpretation. Vague phrases like "appears" or "business model is forming" should be replaced by specific uncertainty and evidence.
8. Market snapshot should be a snapshot, not a paragraph of numbers. It should include a table and actual technical analysis: trend, support/resistance, moving averages, volume/liquidity, volatility, and drawdown where price history exists.
9. Financial and valuation sections should organize data in tables and analyze scale, margin quality, cash burn, liquidity, dilution, valuation range, and what the market is pricing in.
10. Risks should be company/security risks. Data quality and research limitations belong in `Data Issues And Discrepancies`.
11. `What Looks Attractive`, `What Worries Me`, `Bull/Base/Bear`, and `My Take` are directionally good sections, but should be deeper and more decision-useful.

## Evidence From QUBT

- `reports/QUBT/2026-06-23/QUBT-research.md` includes main-body references to deterministic artifacts, local paths, provider mechanics, and saved filings.
- `reports/QUBT/2026-06-23/QUBT-validation.json` records open minor issue `QUBT-VAL-001` for local paths and process wording in investor-facing sections.
- The QUBT `Bottom Line` introduces whether market value is justified before stating the market value/range.
- `Key Facts` contains internal artifact references that duplicate the audit trail already available in `Sources And Evidence`.
- `Business Profile` spends wording on classification and provenance rather than explaining the business in enough practical detail.
- `Market Snapshot` presents many numbers but does not deliver enough technical analysis.
- `Financials` and `Valuation` are useful but citation-heavy and less consumable than tables plus analysis would be.

## Recommended Implementation Theme

Treat the final Markdown as the product. Add tests and lints that reward investor usefulness:

- section order and section naming;
- executive-summary depth;
- table-based key facts and market/financial snapshots;
- absence of internal provenance in main-body sections;
- plain-language business and technology explanation;
- actual technical and valuation analysis;
- data issues moved to a bottom section;
- sources and local paths confined to evidence sections and sidecars.

The corresponding implementation plan is `runtime/self-improvement/20260623-174952-554854/self-improvement-plan.md`.
