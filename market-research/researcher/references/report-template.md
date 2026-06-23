# Report Template

Use this outline for the human-facing research report. Use `research_input_pack.md`, saved source copies, deterministic bundle files, and recorded procedural sources as the fact base; do not copy unsupported interpretation into the report.

## Report Quality Bar

Every report should read like useful investor-grade investment research, not an artifact inventory.

- Lead with a clear bottom line.
- Explain what the company, ADR, or fund does in practical terms.
- Discuss business model, demand drivers, financial quality, balance sheet or fund structure, valuation or performance context, catalysts, and risks when applicable and supported by sources.
- Separate facts from interpretation, but make interpretation decision-useful.
- Use sections such as `What Looks Attractive`, `What Worries Me`, and `My Take` when they improve readability.
- If trading data is unavailable, replace mechanical technical analysis with relevant lifecycle context such as IPO terms, implied valuation, listing timeline, post-listing monitoring items, or explicit absence of market history.
- For ETFs, adapt the same standard to fund objective, index methodology, holdings, exposures, fees, liquidity, tracking/performance context, distributions, portfolio role, risks, and monitoring triggers.

## Reader Experience And Evidence Placement

Write the main Markdown as an investor memo. Do not turn the report into an audit trail. Local artifact paths are important for validation, but they should usually live in `sources.json`, `material_claims`, `deterministic_data_usage`, or a consolidated evidence section rather than after every paragraph.

Use inline citations sparingly:

- Use them for highly material numbers, controversial claims, direct filing language, or places where source quality itself matters.
- Avoid appending `Source:` to every paragraph when the paragraph is ordinary synthesis from already captured evidence.
- Prefer one consolidated `Sources And Evidence` section that maps major claim groups to local artifacts.

Provider names, source IDs, local paths, raw paths, hashes, deterministic bundle names, runtime directories, cache paths, and skill/tool internals belong in an appendix, validation artifact, runtime artifact, or JSON sidecar unless they affect investment interpretation. In the main investor narrative, name providers only when provider identity changes the conclusion, such as a material discrepancy, stale source, missing data category, or source-quality caveat. Use investor-readable phrases such as "latest available market data", "SEC filings", or "company press release" when provider identity is not material.

Field-level freshness matters more than cache mechanics. Time-sensitive fields should be fresh or explicitly described as latest available: price, volume, market cap, short interest, forward estimates, recent news, insider transactions, and event-driven catalysts. Durable filed evidence may use cached artifacts when source dates are preserved: SEC filings, company releases, historical financial statements, company identity, and risk-factor text. Main report disclosure should focus on stale or unavailable material data, not cache mechanics; cache mechanics belong in references, validation artifacts, manifests, or JSON sidecars.

## News And Contract Value Framing

For framework agreements, letters of intent, milestone-dependent values, or "up to" contract announcements, state whether the amount is booked revenue, backlog, a firm order, a non-binding framework, or potential value dependent on milestones. Do not let potential program value read like recognized revenue.

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

State whether usable deterministic data was fully reviewed. If material normalized datapoints were omitted, briefly say why: stale, low-confidence, wrong entity/listing, duplicate of a better source, or not material to the decision.

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

Explain the most important risks, weak points, missing data, or quality concerns. For equities and ADRs, explicitly consider material weaknesses, litigation, dilution or warrant overhang, financing needs, lock-ups/resale pressure, governance, customer concentration, and liquidity/runway when filings discuss them.

## Catalysts And Monitoring Triggers

Identify near-term and medium-term events or metrics that would change the view.

## Bull/Base/Bear Decision Variables

Frame the decision around variables that can be monitored, not unsupported price targets.

## Risks And Invalidation Points

List risks and what evidence would invalidate the current interpretation. Do not collapse filing-specific material disclosures into a generic risk list when they are central to the investment case.

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
  "source_coverage": {
    "provider_limit_impact": [
      {
        "provider_or_gap": "FMP insider statistics plan-gated",
        "affected_analysis_area": "Dilution and governance monitoring",
        "report_handling": "Used SEC filing index evidence; did not quantify insider activity."
      }
    ]
  },
  "calculation_audit": [
    {
      "calculation": "Example return or moving-average calculation.",
      "input_artifacts": ["data/AAPL/2026-05-29/normalized/prices_daily.json"],
      "method": "Describe formula and date window."
    }
  ],
  "deterministic_data_usage": [
    {
      "field_path": "market_snapshot.latest_close",
      "materiality": "required",
      "disposition": "used",
      "rationale": "Latest close anchors market snapshot and valuation context.",
      "report_section": "Market Snapshot Or Lifecycle Context",
      "source_artifact": "data/AAPL/2026-05-29/normalized/market_snapshot.json"
    },
    {
      "field_path": "market_snapshot.beta",
      "materiality": "review",
      "disposition": "intentionally_omitted_not_material",
      "rationale": "Beta was not used because the report's thesis centered on issuer fundamentals and recent price action."
    }
  ]
}
```
