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

For every cited source, record it in `sources.json`. When a public page, PDF, CSV, JSON payload, or other source artifact is saved locally, freeze it under `source_bundle/` through `record-source --artifact` so validation can reproduce the cited source base. If a downloaded artifact's extension and content disagree, inspect it before citing it.

Use stable, exact source IDs. Before finalizing, compare every markdown bracket/source reference and every JSON `source_id` against `sources.json` and `run_manifest.json.source_gaps`. Do not add suffixes such as " gap" to source IDs in citations; explain gap status in prose instead.

Staleness rules:

- Fast-changing market data such as price, NAV, AUM, holdings, yield, and performance should be treated as stale if older than 90 days unless the report explicitly explains why it is still useful.
- Annual filing data can remain useful but must carry the filing period/date.
- ETF holdings and exposure data should include an as-of date.
- Distinguish artifact capture/access date from the underlying filing date, fact period, quote date, holdings date, or as-of date. SEC Companyfacts API captures may have today's access date while the fact itself has an older fiscal period and filed date.
- If a calculated market metric uses adjusted close, label it as adjusted close. If the report says "close" without qualification, calculate from raw close or cite a source that labels it that way.

Helper failure handling:

- Use reliable helper output.
- Try targeted procedural gap filling for missing material fields.
- Disclose remaining gaps in markdown, JSON, and `run_manifest.json`.
- Do not invent precision to cover missing data.
- If public data is visible but the workflow did not capture it, call it a workflow extraction gap rather than unavailable public data and record it with `record-source-gap` when using the helper.
- Do not cite unfrozen volatile live-page fields as current facts unless the exact page, payload, screenshot-equivalent text, or extracted artifact was frozen. Update the frozen artifact, label the field stale, or remove the volatile number from investment framing.
