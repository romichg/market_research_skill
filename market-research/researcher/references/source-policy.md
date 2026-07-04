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

For every cited source, record it in `sources.json`. When a public page, PDF, CSV, JSON payload, or other source artifact is saved locally, save it under `source_bundle/` through `record-source --artifact` so validation can reproduce the cited source base. If a downloaded artifact's extension and content disagree, inspect it before citing it.

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
- Do not cite volatile live-page fields as current facts unless the exact page, payload, screenshot-equivalent text, or extracted artifact was saved. Update the saved artifact, label the field stale, or remove the volatile number from investment framing.

## SEC Fair-Access Failures

When SEC returns `HTTP 403`, inspect the raw provider artifact before calling it authentication failure.

- If the saved body title or snippet says `Request Rate Threshold Exceeded`, classify it as an SEC fair-access/rate-threshold issue.
- If `SEC_USER_AGENT` is browser-like or lacks a project/contact hint, treat the first remediation as user-agent correction, not blind retry.
- If the SEC user-agent is descriptive and the body still says rate threshold, use conservative backoff/retry or switch to saved SEC filing URLs discovered through search.
- If equivalent SEC filing URLs are available and can be saved directly, headed-browser escalation is not required. If a material SEC page remains inaccessible and no equivalent primary source is available, ask for headed-browser human assistance.

## SEC Filing Search Reliability

`browse-edgar` company search (`https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company=...`) can return a valid but empty Atom feed even for well-known issuers; do not treat that as proof SEC search is unavailable. EDGAR full-text search (`https://efts.sec.gov/LATEST/search-index`) is sensitive to query shape: use a non-empty `forms` parameter and `%20`-encoded spaces (not `+`), since some parameter combinations return `{"message": "Internal server error"}`. Once a CIK is known, `https://data.sec.gov/submissions/CIK{10-digit-CIK}.json` is a reliable fallback for a filer's filing history. For a multi-series registrant (e.g. an ETF family filing one N-CSR or 497K per batch across many funds), downloading and inspecting a batch filing to isolate the fund-specific pages/schedule of investments is expected; do not conclude a fund-specific filing does not exist without checking that filing type in that registrant's submissions history.

## Protected Source Access

Protected-source handling applies to any source, not only SEC.

If a material source is blocked by bot protection, CAPTCHA, WAF, JavaScript challenge, suspicious automated-access response, or similar access control:

1. Classify it as a protected-source access issue.
2. Decide whether the source is material to report quality.
3. If material, move promptly to headed-browser human assistance unless an alternative source is clearly equivalent or better quality, current, and authoritative enough for the claim.
4. Ask the human to solve the challenge in the headed browser when required.
5. Continue capture after access is restored and save the source artifact through the normal source registry path.
6. If access cannot be completed, record a workflow extraction/access gap and explain the analytical limitation.

Lower-quality or stale substitutes must not be used merely to avoid headed-browser escalation. Alternatives are acceptable only when they preserve or improve evidence quality.
