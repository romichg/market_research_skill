# Report Template

Use this outline for the human-facing research report. Use `research_input_pack.md` from the deterministic bundle as the fact base; do not copy unsupported interpretation into the report.

Deterministic input pack structure:

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

Full Markdown report structure:

```markdown
# SYMBOL Research

As of: YYYY-MM-DD

## Executive Summary

### Facts

### Interpretation

## Source Base And Data Quality

List deterministic bundle files, provider sources, source dates, raw paths, and unavailable-source gaps.

## Business Or Fund Profile

## Market And Technical Snapshot

Use `normalized/technical_signals.json` when available. If provider technical output is missing, compute local technical context from `normalized/technical_signals.json` and `normalized/prices_daily.json`, label it as locally calculated, and record the inputs in `calculation_audit`.

## Financials Or Holdings And Exposures

## Valuation Or Performance Context

## Catalysts And Monitoring Triggers

## Bull/Base/Bear Decision Variables

## Risks And Invalidation Points

## Explicit Data Gaps

## Not Financial Advice
This report is research support and is not personalized financial advice.
```

Minimal JSON sidecar:

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
