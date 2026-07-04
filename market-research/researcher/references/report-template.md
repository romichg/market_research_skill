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

Use investor-facing language in the main report. Avoid workflow terms such as deterministic, bundle, artifact, normalized, raw, runtime, cache, provider, and local file paths before `Data Issues And Discrepancies`. Prefer phrases such as latest available close, available market data, calculated price signals, source limitation, and source evidence set.

Use inline citations sparingly:

- Use them for highly material numbers, controversial claims, direct filing language, or places where source quality itself matters.
- Avoid appending `Source:` to every paragraph when the paragraph is ordinary synthesis from already captured evidence.
- Prefer one consolidated `Sources And Evidence` section that maps major claim groups to local artifacts.

Do not name routine data vendors in the main investment narrative. State the data, range, conflict, and investment implication there; put vendor attribution, source IDs, local paths, raw paths, hashes, deterministic bundle names, runtime directories, cache paths, and skill/tool internals in `Data Issues And Discrepancies`, `Sources And Evidence`, validation artifacts, runtime artifacts, or JSON sidecars. Primary source types such as SEC filings, 10-Qs, 10-Ks, proxy statements, and company releases may be named in the main body because they describe source authority rather than data-vendor plumbing.

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

Write this as an executive summary, not a compressed thesis. Use 3-5 substantial paragraphs. Introduce the company/security, what it does, current market value or valuation range, the core upside argument, the main risks, and the most important monitoring questions. Introduce the market value or valuation range before discussing whether it is justified; do not make the Bottom Line a compressed one-paragraph thesis.

## Key Facts

Use a compact Markdown table. Do not cite local paths, helper internals, deterministic artifacts, raw files, routine data-vendor names, or source registries in this table.

| Item | Latest / Current | Why It Matters |
| --- | --- | --- |
| Security | US-listed equity / ADR / ETF | Defines what the investor owns. |
| Market value | $X-Y billion or unavailable | Anchors valuation discussion. |
| Revenue base | $X for period/date | Shows scale. |
| Liquidity | Cash/investments/debt | Shows runway and financing risk. |
| Profitability | Gross margin / operating loss / cash burn | Shows business quality. |
| Technical setup | Price, trend, support/resistance | Shows trading context. |
| Near-term monitors | Events and dates | Shows what can change the view. |

## Business Profile

Explain what the company or fund is in plain language. For operating companies, explain what the product does, how the technology works in investor-readable terms, who pays, customers, end markets, acquisitions, acquisition contribution, and practical economic exposure. Do not write "not an ETF or ADR"; write what the security is. If the business uses specialized technology, explain specialized technology instead of assuming the reader already understands terms such as photonic components, quantum security, or reservoir computing.

## Business Model And Demand Drivers

Explain how the company makes or expects to make money, who pays, what products or services are sold, what demand drivers matter, and what operating constraints could limit adoption. Avoid vague phrases like "appears" or "business model is forming" unless the uncertainty is explicitly explained.

## Market Snapshot And Technical Analysis

Present market data in a table, then analyze it. Include price, market value/range, volume/liquidity, 52-week range, moving averages, volatility, relative strength, drawdown, support and resistance levels, and trend interpretation when price history exists.

Translate the setup into investor-useful action context. State what the technical picture implies for entry timing, sizing, confirmation, invalidation, or monitoring. Do not merely list indicators.

If no trading history exists, explain why and use the relevant lifecycle context instead: IPO terms, implied valuation, listing timeline, post-listing monitoring items, liquidity expectations, or explicit absence of market history.

## Financials And Balance Sheet

Use a table plus analysis. For companies and ADRs, cover revenue, gross margin, operating expense, net income/loss, operating cash flow, cash/investments, debt/liabilities, working capital, share count/dilution, and acquisition contribution when available. For ETFs, cover holdings, sector/geography/factor exposures, concentration, distributions, fees, AUM, and liquidity. Avoid citation clutter in the main prose.

## Portfolio Companies Snapshot

Use this section for ETFs when holdings are available. If the ETF has 25 or fewer holdings, cover all holdings; otherwise cover the top 25 by portfolio weight. Keep each row compact: company/ticker, weight, sector or industry, what it does, quick outlook, and quick price/technical context when reliable public/free data is available. Follow with a synthesis paragraph about what the companies imply for concentration, cyclicality, upside drivers, risks, and monitoring. Do not write full single-company reports for each holding.

## Valuation

Choose a valuation basis or range and analyze it. If market capitalization or share count conflicts across sources, state the range in this section without vendor attribution, then explain vendor/source attribution in `Data Issues And Discrepancies`. Discuss revenue multiples, book value, cash-adjusted value, peer/context limits, and what revenue or margin improvement would be needed to make the valuation less speculative.

For ETFs, include peer or competitor ETF context when reproducible public/free evidence is available. If no reliable peer data was captured, disclose that limitation in `Data Issues And Discrepancies` and avoid unsupported superiority claims.

## What Looks Attractive

Explain the strongest evidence-backed positives.

## What Worries Me

Explain the most important risks, weak points, missing data, or quality concerns. For equities and ADRs, explicitly consider material weaknesses, litigation, dilution or warrant overhang, financing needs, lock-ups/resale pressure, governance, customer concentration, and liquidity/runway when filings discuss them.

## Catalysts And Monitoring Triggers

Identify near-term and medium-term events or metrics that would change the view.

## Bull/Base/Bear Decision Variables

Use a table or clearly separated bullets. Each case should state what must happen operationally, financially, and in market perception. Frame the decision around variables that can be monitored, not unsupported price targets.

## Risks And Invalidation Points

Focus on company, security, market, financial, governance, execution, liquidity, dilution, customer, product, and regulatory risks. Do not include research/data-quality risk here; put those in `Data Issues And Discrepancies`.

For ETFs, explicitly address authorized participant and creation/redemption mechanics, securities lending, premium/discount, tracking, tax or withholding drag, liquidity, closure/AUM, concentration, country, currency, sector, and index-methodology risks when material. If securities lending or creation/redemption detail is not found in the available sources, state that limitation in investor terms rather than omitting the topic.

For equities and ADRs, explicitly treat the following risk checklist with one of `addressed`, `not material`, or `not found in filed sources`: commercialization/execution, liquidity/runway, dilution/share issuance, customer concentration, supplier concentration/manufacturing dependence, cybersecurity/data integrity, litigation/legal proceedings, internal controls, related-party/governance, regulatory/export-control, and valuation/multiple compression. The Markdown should summarize only material risks; the JSON sidecar can preserve checklist dispositions.

## My Take

Give a fuller evidence-backed interpretation. Explain what would make the security interesting, what would keep it out of a portfolio, and what evidence would change the view. Avoid personalized advice.

## Data Issues And Discrepancies

Merge source-base, data-quality, missing-field, stale-field, and vendor-discrepancy discussion here. Use investor-readable explanations first. Routine data-vendor names, local paths, manifests, gaps files, source registries, and other validation-facing details may be named here when they explain a discrepancy, missing field, or confidence limit.

## Sources And Evidence

Map major claim groups to source documents and local artifacts for auditability. This is where local paths, source IDs, source registries, manifests, and validation-facing provenance belong.

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
