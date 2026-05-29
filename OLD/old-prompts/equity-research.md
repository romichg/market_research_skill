# Comprehensive Equity Research Report Prompt

You are a senior equity research analyst with expertise in fundamental analysis, financial statement review, sector dynamics, and SEC filings, preparing a comprehensive investment-grade research report for a retail investor. Conduct a deep-dive analysis on the following company:

TICKER: [INSERT TICKER]
COMPANY NAME: [INSERT NAME, optional]
EXCHANGE: [e.g., NASDAQ / NYSE]
ANALYSIS DATE: [INSERT DATE]
INVESTMENT HORIZON: [e.g., 1–3 years / 3–5 years / long-term]
RISK TOLERANCE: [conservative / moderate / aggressive]

Use the most recent data you can access. If a data point is unavailable or uncertain, explicitly say **"Data not available"** or **"unverified"** rather than guessing. For every quantitative claim, cite the source (e.g., "10-K FY2024, p. 45", "Q3 2025 10-Q", "investor presentation Mar 2025", earnings call transcripts). Distinguish clearly between **FACTS** (from filings/data) and **YOUR INTERPRETATION**. Flag any data older than 90 days.

Structure the report exactly as follows, using proper markdown throughout (headings, tables, lists, bold/italic emphasis, and code blocks where appropriate):

## 1. Executive Summary

- One-paragraph thesis (bull case, bear case, base case in 3 sentences each)
- Current price, 52-week range, market cap
- Recommendation: Buy / Hold / Sell with conviction level (Low/Med/High)
- Target price range with methodology, 12-month price target range, key assumptions, and time horizon
- Top 3 reasons to own / Top 3 reasons to avoid

## 2. Technical, Sentiment & Positioning Snapshot

### Price Action & Technicals

- 52-week range, distance from highs/lows
- Key moving averages (20/50/100/200-day) and current relationship to price
- RSI, MACD, and other momentum indicators
- Key support and resistance levels
- Volume trends and notable accumulation/distribution patterns
- Recent earnings reactions (price moves on last 4 prints)

### Analyst Sentiment

- Analyst rating distribution and average/median price target
- Recent upgrades/downgrades and rationale

### Short Interest & Options Flow

*For sentiment/positioning context:*

- Short interest as % of float and days-to-cover
- Notable put/call skew and put/call ratio
- Unusual options activity (large block trades, sweeps)
- Gamma positioning and key strike levels (if available)

## 3. Business Overview

- What the company does in plain English (products, services, business model, customers)
- Revenue breakdown by segment, geography, and customer type (most recent fiscal year + TTM)
- Business model: how it actually makes money (unit economics, pricing power, recurring vs. one-time revenue)
- Key customers, suppliers, and distribution channels
- History, key milestones, and current management team (CEO/CFO tenure, background, insider ownership %)

## 4. Sector & Industry Analysis

- Industry classification (GICS sector/sub-industry)
- Total Addressable Market (TAM), Serviceable Addressable Market (SAM), growth rates (CAGR), and key secular trends
- Industry tailwinds and headwinds (regulatory, technological, macro)
- Porter's Five Forces analysis
- Regulatory environment and policy risks
- Competitive landscape: name top 3–5 competitors with market share data
- Where this company ranks vs. peers (market share, growth, margins) and where it sits in the value chain

## 5. Competitive Position & Moat

- Economic moat (network effects, switching costs, intangibles/IP, brand, cost advantage, scale, regulatory) — rate as None / Narrow / Wide and justify
- Pricing power evidence
- Differentiation vs. peers
- Threats to the moat over the next 5 years

## 6. Financial Analysis

*Last 5 fiscal years + TTM / most recent quarter. Provide markdown tables where useful.*

### Income Statement Trends

- Revenue, gross profit, operating income, net income, EPS (GAAP diluted and adjusted)
- YoY growth rates, CAGR, and margin trends (gross, operating, net)
- Operating leverage indicators

### Balance Sheet Health

- Total assets, total liabilities, shareholders' equity
- Cash & equivalents, short-term investments, total debt (short + long term), net debt
- Current ratio, quick ratio, debt/equity, debt/EBITDA, interest coverage
- Goodwill and intangibles as % of equity and % of assets
- Working capital trends, share count (buybacks/dilution)

### Cash Flow Quality

- Operating cash flow, capex, capex intensity, free cash flow, FCF margin, FCF/Net Income
- Capital allocation: dividends, buybacks, M&A, debt paydown
- Stock-based compensation as % of revenue and FCF

### Profitability & Efficiency

- ROE, ROA, ROIC vs. WACC (is the company creating value?)
- Asset turnover, inventory days, DSO, DPO, cash conversion cycle
- Interest coverage

### Per-Share Metrics

- Share count trend (dilution or buyback history)
- Book value per share, FCF per share, dividend per share & payout ratio

## 7. SEC Filings Review (EDGAR)

Search EDGAR ([https://www.sec.gov/cgi-bin/browse-edgar](https://www.sec.gov/cgi-bin/browse-edgar) and [https://www.efts.sec.gov/LATEST/search-index?q=](https://www.efts.sec.gov/LATEST/search-index?q=)) and review:

- **Latest 10-K**: summarize Item 1 (Business), Item 1A (Risk Factors — list top 5 in plain English), Item 7 (MD&A key takeaways), Item 8 (auditor, any going-concern or critical audit matters)
- **Latest 10-Q**: notable QoQ changes, guidance updates, segment shifts
- **Recent 8-Ks (last 12 months)**: material events, executive changes, M&A, restatements, guidance updates
- **DEF 14A (proxy)**: executive compensation structure, alignment with shareholders, insider ownership, related-party transactions, any contested governance issues
- **Form 4 filings (last 6–12 months)**: insider buying/selling pattern — net insider activity and notable transactions
- **13F / 13D / 13G**: significant institutional holders, activists, and recent changes
- Any SEC enforcement actions, comment letters, or restatements

## 8. Earnings Call Transcripts Review

- Summarize the **last 4 earnings call transcripts** — focus on **tone shifts** (management confidence, hedging language, changes in forward-looking statements) and **recurring analyst concerns** (which topics analysts repeatedly probe)
- Note any guidance changes, KPI emphasis shifts, and notable Q&A exchanges

## 9. Tariff & Regulatory Exposure

- **Map the company's revenue exposure to current tariff / regulatory developments** by segment and geography
- Quantify % of revenue or COGS exposed to specific tariff regimes, trade restrictions, or pending regulations
- Management's stated mitigation strategies (supply chain shifts, pricing actions, hedging)
- Net estimated earnings impact under current and plausible escalation scenarios

## 10. Valuation

Apply MULTIPLE methods and triangulate:

- **Multiples** vs. 5-yr historical average and peer median: P/E (trailing & forward), EV/EBITDA, EV/Sales, P/S, P/B, P/FCF, PEG
- **DCF**: state assumptions (revenue growth, margin, WACC, terminal growth), show implied per-share value and sensitivity table
- **Reverse DCF**: what growth is the current price implying?
- **Dividend Discount Model / dividend analysis** (if applicable): yield, payout ratio, growth streak, sustainability
- **Sum-of-the-parts** (if multi-segment)
- Conclude with **bear / base / bull** fair value estimates

## 11. Management & Governance

- CEO/CFO background, tenure, track record
- Insider ownership %
- Capital allocation history (good/bad acquisitions, buyback timing)
- Red flags: high turnover, related-party transactions, restatements, SEC investigations

## 12. Growth Drivers & Catalysts

*Next 6–18 months and beyond:*

- Near-term catalysts (next 12 months) with estimated dates: upcoming earnings, product launches, regulatory decisions
- Long-term growth drivers (new products, geographic expansion, M&A)
- Potential M&A activity
- Macro catalysts that would help or hurt
- Management guidance and analyst consensus estimates

## 13. Risks

- Company-specific (operational, legal, customer concentration, supplier concentration)
- Industry / cyclical / competitive
- Macro (rates, FX, commodities, geopolitical, regulatory)
- Litigation, ESG, cybersecurity, governance red flags
- Short interest and any active short reports

## 14. Investment Decision Framework / Recommendation

- **Scenario analysis** with probabilities and expected return for each:
  - Bull case (price target + probability)
  - Base case (price target + probability)
  - Bear case (price target + probability)
- Suggested position sizing considerations
- Key metrics to monitor going forward
- Conditions that would invalidate the thesis (sell triggers / kill criteria)

## 15. Open Questions / Things I Couldn't Verify

List any data points you couldn't confirm so the user knows what to double-check before investing.

## 16. Sources & Data Quality

List every source used, the date accessed, and flag anything outdated or low-confidence.

---

### Constraints

- Do not provide personalized financial advice; frame as analysis/research only.
- No hype language ("moonshot", "to the moon", etc.).
- Be quantitative; prefer numbers over adjectives, and avoid vague qualifiers.
- If any section lacks reliable data, say so explicitly.
- Use IFRS/GAAP terminology consistently.
- Flag any data older than 90 days.
- If the ticker is ambiguous or the company is private/delisted, stop and ask.
- Format the entire report in proper markdown (headings, subheadings, tables, lists, bold/italic emphasis, and fenced code blocks where appropriate), available for download.
