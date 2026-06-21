# Report Template

Use this outline for the human-facing research report. Use `research_input_pack.md`, saved source copies, deterministic bundle files, and recorded procedural sources as the fact base; do not copy unsupported interpretation into the report.

## Report Quality Bar

Every report should read like useful investment research, not an artifact inventory.

- Lead with a clear bottom line.
- Explain what the company, ADR, or fund does in practical terms.
- Discuss business model, demand drivers, financial quality, balance sheet or fund structure, valuation or performance context, catalysts, and risks when applicable and supported by sources.
- Separate facts from interpretation, but make interpretation decision-useful.
- Use sections such as `What Looks Attractive`, `What Worries Me`, and `My Take` when they improve readability.
- If trading data is unavailable, replace mechanical technical analysis with relevant lifecycle context such as IPO terms, implied valuation, listing timeline, post-listing monitoring items, or explicit absence of market history.
- For ETFs, adapt the same standard to fund objective, index methodology, holdings, exposures, fees, liquidity, tracking/performance context, distributions, portfolio role, risks, and monitoring triggers.

## Deterministic Input Pack Structure

```markdown
# SYMBOL Deterministic Research Input Pack

As of: YYYY-MM-DD

## Executive Summary Facts

## Source Base

## Market Snapshot

## Technical Signals

## Fundamentals Or Fund Profile

## SEC Filings And Disclosures

## News And Events

## Data Gaps And Cautions

## Not Financial Advice
This package is deterministic research support and is not personalized financial advice.
```

## Full Markdown Report Structure

```markdown
# SYMBOL Research

As of: YYYY-MM-DD

## Bottom Line

State the practical investment-research conclusion in one or two tight paragraphs. Include the main opportunity, the main offsetting risk, and the core monitoring question.

## Key Facts

List the most material sourced facts. Keep this short enough that it supports the analysis rather than replacing it.

## Source Base And Data Quality

Describe saved source copies, deterministic bundle files, primary versus secondary sources, source dates, access dates, confidence, and material limitations. Do not expose internal validation jargon in the human-facing report.

## Business Or Fund Profile

Explain what the company, ADR, or fund is and what economic exposure it provides.

## Business Model, Demand Drivers, Or Fund Methodology

For companies and ADRs, cover revenue model, customers, end-market demand, competitive position, and operating constraints. For ETFs, cover index methodology, selection rules, weighting, rebalance cadence, and what drives returns.

## Market Snapshot Or Lifecycle Context

Use `normalized/technical_signals.json` when trading data exists. If provider technical output is missing, compute local technical context from `normalized/technical_signals.json` and `normalized/prices_daily.json`, label it as locally calculated, and record the inputs in `calculation_audit`.

If no trading history exists, explain why and use the relevant lifecycle context instead: IPO terms, implied valuation, listing timeline, post-listing monitoring items, liquidity expectations, or explicit absence of market history.

## Financials, Holdings, And Balance Sheet

For companies and ADRs, cover revenue growth, margins, earnings quality, cash flow, leverage, liquidity, and use of proceeds when applicable. For ETFs, cover holdings, sector/geography/factor exposures, concentration, distributions, fees, AUM, and liquidity.

## Valuation Or Performance Context

Discuss valuation multiples, peer or market framing, IPO implied valuation, total return, tracking, drawdowns, or other performance context supported by sources.

## What Looks Attractive

Explain the strongest evidence-backed positives.

## What Worries Me

Explain the most important risks, weak points, missing data, or quality concerns.

## Catalysts And Monitoring Triggers

Identify near-term and medium-term events or metrics that would change the view.

## Bull/Base/Bear Decision Variables

Frame the decision around variables that can be monitored, not unsupported price targets.

## Risks And Invalidation Points

List risks and what evidence would invalidate the current interpretation.

## Explicit Data Gaps

State missing or inaccessible data, attempted sources, whether the gap is public-data unavailable or workflow/source-access limited, and how it affects the analysis.

## My Take

Give a concise, evidence-backed interpretation. Avoid personalized advice.

## Not Financial Advice
This report is research support and is not personalized financial advice.
```

## Minimal JSON Sidecar

```json
{
  "symbol": "AAPL",
  "security_type": "equity",
  "as_of_date": "2026-05-29",
  "deterministic_bundle": {
    "bundle_dir": "data/AAPL/2026-05-29",
    "manifest": "data/AAPL/2026-05-29/manifest.json",
    "source_manifest": "data/AAPL/2026-05-29/source_manifest.json",
    "gaps": "data/AAPL/2026-05-29/gaps.json",
    "research_input_pack": "data/AAPL/2026-05-29/research_input_pack.md"
  },
  "material_claims": [
    {
      "claim": "Example sourced quantitative claim.",
      "source_id": "latest_10k",
      "source_date": "2025-09-27",
      "accessed_date": "2026-05-29",
      "confidence": "high",
      "verification_status": "verified"
    }
  ],
  "data_gaps": [],
  "technical_analysis": {
    "summary": "Locally calculated or provider-returned technical context.",
    "inputs": ["data/AAPL/2026-05-29/normalized/technical_signals.json", "data/AAPL/2026-05-29/normalized/prices_daily.json"]
  },
  "valuation_or_performance": {},
  "decision_factors": {},
  "risks": [],
  "catalysts": [],
  "source_coverage": {},
  "calculation_audit": [
    {
      "calculation": "Example return or moving-average calculation.",
      "input_artifacts": ["data/AAPL/2026-05-29/normalized/prices_daily.json"],
      "method": "Describe formula and date window."
    }
  ]
}
```
