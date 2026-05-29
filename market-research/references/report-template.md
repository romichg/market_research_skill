# Report Template

Markdown report structure:

```markdown
# SYMBOL Research

As of: YYYY-MM-DD

## Executive Summary

### Facts

### Interpretation

## Source Base

## Business Or Fund Profile

## Market Snapshot And Positioning

## Financials Or Portfolio Exposures

## Filings, Governance, And Structure

## Sector, Macro, And Competitive Context

## Valuation Or Performance Context

## Catalysts And Decision Framework

## Risks

## Data Gaps And Confidence

## Not Financial Advice
This report is research support and is not personalized financial advice.
```

Minimal JSON sidecar:

```json
{
  "symbol": "AAPL",
  "security_type": "equity",
  "as_of_date": "2026-05-29",
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
  "data_gaps": []
}
```
