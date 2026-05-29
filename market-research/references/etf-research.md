# ETF Research

Use this reference for ETFs and exchange-traded funds.

Required sections:

1. Executive summary: fund facts first, then interpretation.
2. Trading and positioning snapshot: price, NAV, premium/discount, AUM, average volume, bid/ask spread, 52-week range, distribution yield, and short interest/options context when free/public and reproducible.
3. Sponsor and product identity: issuer, ticker, fund name, benchmark/index, inception date, exchange, legal structure, tax form/treatment, replication method, and securities lending where available.
4. Fees, expenses, and tax efficiency: net/gross expense ratio, waivers, turnover, distribution history, capital gains history, SEC yield/distribution yield, and total cost of ownership.
5. Strategy and index methodology: objective, active/passive status, index provider, eligibility, weighting, caps, rebalance/reconstitution cadence, derivatives/leverage/short exposure, and methodology changes.
6. Holdings and portfolio composition: top holdings, top-10 concentration, number of holdings, sector, country, market-cap, asset-class, credit/duration/yield metrics for fixed income, and theme purity where relevant.
7. Performance and risk behavior: NAV and market returns, benchmark/category context, tracking difference versus tracking error, volatility/beta/drawdowns when public/free, and stress-period behavior where the fund history supports it.
8. SEC filings review: prospectus/SAI, annual/semiannual reports, N-PORT where useful, 497/497K changes, Form 8937, and any material closure, fee, strategy, or risk updates.
9. Sector, theme, macro, tariff, and regulatory context: map exposures through underlying holdings. Quantify only when source support exists.
10. Competitive landscape: closest alternative ETFs, expense ratio, AUM, spread/liquidity, methodology, holdings overlap, performance/tracking, and whether a competitor is a better vehicle for the exposure.
11. Issuer and manager quality: issuer franchise, fund closure risk, portfolio manager tenure when disclosed, index provider credibility, and securities lending practices.
12. Valuation of underlying exposure: aggregate portfolio multiples, growth/profitability, dividend yield, duration/YTW/OAS for fixed income, and cheap/fair/expensive interpretation versus history or peers only when sourced.
13. Investment decision framework: role in portfolio, Buy/Hold/Sell/Avoid-style view, conviction, explicit bull/base/bear scenarios, key monitor list, and concrete invalidation triggers.
14. Risks: concentration, country, currency, sector, index methodology, liquidity, premium/discount, AP/creation-redemption mechanics, cash versus in-kind creation/redemption, tracking, tax form/treatment, taxable distributions, foreign withholding/tax drag, leverage/path dependency, derivatives, and fund closure risks as applicable.
15. Data gaps: unavailable, stale, or low-confidence ETF data and what public source was attempted.

Source priority:

- Issuer product page.
- Issuer fact sheet.
- Prospectus and summary prospectus.
- SAI when structure or risk details require it.
- Holdings CSV/API/file.
- Index methodology.
- Annual or semiannual reports.
- Public/free market data in this fallback order: issuer quote/product page with frozen artifact, Yahoo chart/download payload, exchange page, other no-login secondary pages, then Stooq only when the downloaded artifact is actual CSV rather than an API-key/captcha instruction page. Label these secondary unless they are issuer/exchange primary data.

BlackRock/iShares handling:

- If a product ID is known or user supplied, try to use official BlackRock/iShares product payloads.
- Run `extract-blackrock` when a product API JSON payload is available.
- If raw issuer payloads contain useful data but `research_context.json` is sparse, enrich context before writing the report.
- For dated fact sheets, prospectuses, annual/semiannual reports, holdings files, and product pages, record `--source-date` and freeze the local artifact with `record-source --artifact`.
- If a holdings CSV endpoint returns HTML or another unexpected payload, do not treat it as holdings data; record the failed capture as a workflow extraction gap if it affects the report.
- If product ID mapping is unavailable, record that as a source gap and use issuer pages/fact sheets procedurally.
- If a dynamic product page or secondary quote/holdings page includes several as-of dates, keep the page-level source date conservative and put each material claim's specific as-of date in the claim and report text. Do not assign one page-level `source_date` to all fast-moving facts when the artifact shows different quote, holdings, spread, yield, or AUM dates.

Before finalizing, run a dedicated ETF structure pass. For every ETF, include a short explicit statement on legal/tax treatment, creation/redemption mechanics, AP/liquidity risk, taxable distributions or foreign withholding where relevant, securities lending if disclosed, and fund closure risk. If a point is immaterial for a plain ETF, say that briefly rather than omitting it.

Peer and macro framing:

- Include peer-fee, peer-liquidity, or lower-cost-alternative claims in the executive summary or decision framework only when peer artifacts are frozen or user-supplied. Otherwise keep peer comparison as a data gap or clearly caveated watch item.
- For commodity, rates, currency, and macro-sensitive ETFs/trusts, keep macro variables framed as scenario drivers unless current macro, flows, rates, dollar, inventory, or central-bank-demand data is frozen.
- Do not describe securities-lending data as unavailable until annual/semiannual reports have been checked for dated securities-lending tables. If only dated lending figures are available, cite them as dated and avoid implying current lending exposure.

For ETF EDGAR data, treat SEC fund ticker and series mappings as useful but not sufficient by themselves. Prefer issuer sources for current operating facts unless SEC filings are clearly identified.

Do not require paid subscriptions or API keys. Peer rankings, options flow, full holdings downloads, risk metrics, and category percentile data are valuable only when public/free and reproducible. If unavailable, mark them `Data not available` or `unverified`.
