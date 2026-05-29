# ETF Research

Use this reference for ETFs and exchange-traded funds.

Required sections:

1. Executive summary: fund facts first, then interpretation.
2. Sponsor and product identity: issuer, ticker, fund name, benchmark/index, inception date, exchange, structure when available.
3. Fees and expenses: net/gross expense ratio, waivers if applicable, source date.
4. Index methodology: what the index owns, weighting rules, reconstitution/rebalancing, eligibility rules.
5. Holdings and concentration: top holdings, top-10 weight, number of holdings, country/sector/asset exposure.
6. Performance: only with clear as-of dates and benchmark context.
7. Liquidity and trading: AUM, bid/ask spread, volume, premium/discount if public and current.
8. Risks: concentration, country, currency, sector, index methodology, liquidity, tracking, tax/structure.
9. Data gaps: unavailable, stale, or low-confidence ETF data.

Source priority:

- Issuer product page.
- Issuer fact sheet.
- Prospectus and summary prospectus.
- SAI when structure or risk details require it.
- Holdings CSV/API/file.
- Index methodology.
- Annual or semiannual reports.

BlackRock/iShares handling:

- If a product ID is known or user supplied, try to use official BlackRock/iShares product payloads.
- Run `extract-blackrock` when a product API JSON payload is available.
- If raw issuer payloads contain useful data but `research_context.json` is sparse, enrich context before writing the report.
- For dated fact sheets, prospectuses, annual/semiannual reports, holdings files, and product pages, record `--source-date` and freeze the local artifact with `record-source --artifact`.
- If a holdings CSV endpoint returns HTML or another unexpected payload, do not treat it as holdings data; record the failed capture as a workflow extraction gap if it affects the report.
- If product ID mapping is unavailable, record that as a source gap and use issuer pages/fact sheets procedurally.

For ETF EDGAR data, treat SEC fund ticker and series mappings as useful but not sufficient by themselves. Prefer issuer sources for current operating facts unless SEC filings are clearly identified.
