# Source Policy

Prefer primary sources:

- SEC filings, companyfacts, and issuer investor-relations pages for equities and ADRs.
- ETF sponsor product pages, fact sheets, prospectuses, SAI, holdings files, annual/semiannual reports, and index methodology documents for ETFs.
- Official exchange, regulator, and issuer documents before aggregators.

Use secondary sources only when primary data is unavailable or to add context. Label secondary-source claims with lower confidence.

Required metadata for material claims:

- `source_id`
- source URL or local source path
- source date when visible
- accessed date
- confidence: `high`, `medium`, `low`, or `unverified`
- verification status: `verified`, `unverified`, or `data_not_available`

Staleness rules:

- Fast-changing market data such as price, NAV, AUM, holdings, yield, and performance should be treated as stale if older than 90 days unless the report explicitly explains why it is still useful.
- Annual filing data can remain useful but must carry the filing period/date.
- ETF holdings and exposure data should include an as-of date.

Helper failure handling:

- Use reliable helper output.
- Try targeted procedural gap filling for missing material fields.
- Disclose remaining gaps in markdown, JSON, and `run_manifest.json`.
- Do not invent precision to cover missing data.
