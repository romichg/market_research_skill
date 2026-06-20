---
name: market-research-full-researcher
description: Research US-listed equities, ADRs, and ETFs from a ticker symbol using public/free sources; create cited markdown and JSON artifacts; use deterministic helper scripts when useful but gracefully fall back to procedural research when helpers fail or are sparse. Use when Codex is asked for investment, equity, stock, ADR, ETF, fund, issuer, holdings, valuation, risk, or market research on a symbol.
---

# Market Research

Use this skill to produce a research bundle for one public equity, ADR, or ETF symbol. This is research support, not personalized financial advice.

## Core Rule

Use helper output as evidence, not authority.

```text
helper succeeds -> use structured context
helper partially succeeds -> use reliable helper output, try targeted procedural gap filling, disclose remaining gaps
helper fails -> research procedurally, disclose helper failure
helper gets bloated/flaky -> split, cap outputs, or demote to optional
```

Do not abandon the report solely because a helper failed unless no credible public source can be accessed and no user-provided files exist.

## Resources

- Prefer `../shared/scripts/deterministic_research_collector.py` for cache-first API gathering, normalization, local technical metrics, source manifests, gaps, and Markdown research input packs.
- Use `../shared/scripts/procedural_source_helper.py` for manual/procedural source registry work: run setup, manual classification, source recording, source-gap recording, context preparation, procedural gap-fill recording, and issuer payload promotion.
- Read `references/provider-data-map.md` when adding, validating, or reasoning about deterministic provider fields, duplicate data, and fallback behavior.
- Read `references/source-policy.md` before source gathering and citation work.
- Read `references/equity-research.md` for equities and ADRs.
- Read `references/etf-research.md` for ETFs.
- Read `references/report-template.md` before writing final artifacts.
- Use `../shared/schemas/research-output.schema.json` for the report sidecar.
- Use `../shared/schemas/validation-output.schema.json` as the shared validation contract.

## Workflow

1. Start with deterministic data collection when provider keys or cached raw files are available:

```bash
python3 {baseDir}/../shared/scripts/deterministic_research_collector.py doctor
python3 {baseDir}/../shared/scripts/deterministic_research_collector.py fetch SYMBOL --asset-type auto --as-of YYYY-MM-DD --data-dir ./data --reports-dir ./reports
```

Use `--providers sec,tiingo,eodhd` to restrict calls, `--provider-endpoints PROVIDER=ENDPOINT[,ENDPOINT]` to avoid duplicate endpoint families, and `--max-provider-calls PROVIDER=N` to stay within free-tier budgets. Provider and endpoint filters apply to both live fetches and cached raw data used during bundle construction, preventing stale cached providers or duplicate cached endpoints from slipping into a quota-preserving run. The collector estimates provider endpoint cost before network calls and skips providers whose estimated cost exceeds the provided or conservative default budget. Successful raw endpoint responses are reused across later `as_of` dates unless `--refresh` is passed, so do not use `--refresh` unless the user specifically needs a fresh provider pull.

Recommended quota-safe starting points:

```bash
# Rebuild from frozen raw data only.
python3 {baseDir}/../shared/scripts/deterministic_research_collector.py fetch SYMBOL --offline --as-of YYYY-MM-DD --data-dir ./data --reports-dir ./reports

# Live refresh using only polite SEC access and one price provider.
python3 {baseDir}/../shared/scripts/deterministic_research_collector.py fetch SYMBOL --providers sec,tiingo --as-of YYYY-MM-DD --data-dir ./data --reports-dir ./reports

# Opt into EODHD fundamentals without duplicating Tiingo price history.
python3 {baseDir}/../shared/scripts/deterministic_research_collector.py fetch SYMBOL --providers sec,tiingo,eodhd --provider-endpoints eodhd=fundamentals --max-provider-calls eodhd=10 --as-of YYYY-MM-DD --data-dir ./data --reports-dir ./reports

# Scrappy full equity pass: one price source plus unique fundamentals/news/events.
python3 {baseDir}/../shared/scripts/deterministic_research_collector.py fetch SYMBOL --providers sec,tiingo,eodhd,alphavantage,marketaux,fmp --provider-endpoints tiingo=prices --provider-endpoints eodhd=fundamentals --provider-endpoints alphavantage=overview --provider-endpoints marketaux=news --provider-endpoints fmp=profile,key_metrics_ttm,ratios_ttm,income_statement,balance_sheet,cash_flow,stock_news,press_releases,dividends,earnings,splits,insider_trading,insider_statistics --max-provider-calls sec=3 --max-provider-calls tiingo=1 --max-provider-calls eodhd=10 --max-provider-calls alphavantage=1 --max-provider-calls marketaux=1 --max-provider-calls fmp=13 --as-of YYYY-MM-DD --data-dir ./data --reports-dir ./reports
```

Use offline mode to rebuild normalized outputs without rerunning successful provider collection:

```bash
python3 {baseDir}/../shared/scripts/deterministic_research_collector.py fetch SYMBOL --offline --as-of YYYY-MM-DD --data-dir ./data --reports-dir ./reports
python3 {baseDir}/../shared/scripts/deterministic_research_collector.py list-cache SYMBOL
```

The deterministic collector writes:

```text
reports/SYMBOL/AS_OF/
  manifest.json
  source_manifest.json
  gaps.json
  raw/
  normalized/
  research_input_pack.md
```

Use this output as the primary factual input. Every normalized value must carry provider, source URL, raw path, and status. Missing data must remain a structured gap with only the attempted providers listed. Do not invent or infer unsupported values. Live API calls use conservative retries/backoff for transient 429/503/network failures and do not retry unauthorized or not-found responses aggressively. Provider authentication failures exit with a clear error; provider rate-limit or endpoint errors are promoted into `manifest.json` warnings and preserved in `source_manifest.json` plus raw `provider_result.error`.

2. If deterministic output is sparse or a procedural source bundle is required, normalize the symbol to uppercase and create the run:

```bash
python3 {baseDir}/../shared/scripts/procedural_source_helper.py init-run SYMBOL --output-root ./runtime
```

Wait for `init-run` to complete before `classify`, `record-source`, or any other dependent helper command. Source registry writes are lock-protected, but run initialization is a required sequential step.

3. Classify the security. If the helper cannot classify from public data, use clear procedural evidence or ask the user to choose `equity`, `adr`, or `etf`; then record it:

```bash
python3 {baseDir}/../shared/scripts/procedural_source_helper.py classify SYMBOL --output-root ./runtime --security-type etf --name "Fund or company name"
```

4. Gather public/free sources. Prefer primary sources. Record each material source:

```bash
python3 {baseDir}/../shared/scripts/procedural_source_helper.py record-source SYMBOL --output-root ./runtime --id source_id --title "Source title" --url "https://example.com/source" --kind issuer_fact_sheet --source-date YYYY-MM-DD --artifact ./downloaded-source.pdf --confidence high
```

Use `--source-date` whenever a document or page has a visible as-of, filing, publication, or effective date. Use `--artifact` for every cited public web page or document you saved locally; the helper copies it into `source_bundle/`, records artifact size and SHA-256 checksum metadata, and rejects obvious extension/content mismatches such as HTML saved as `.csv`.

The helper uses lock-protected registry writes, but source capture is still easier to audit when sources are recorded in small logical groups rather than hidden behind one large shell pipeline.

When a public/free source capture fails or returns unusable content, record the attempted source as a structured gap:

```bash
python3 {baseDir}/../shared/scripts/procedural_source_helper.py record-source-gap SYMBOL --output-root ./runtime --source-id holdings_csv --attempted-url "https://example.com/holdings.csv" --reason "CSV endpoint returned HTML." --replacement-source-id issuer_fact_sheet --severity medium
```

5. Prepare compact context:

```bash
python3 {baseDir}/../shared/scripts/procedural_source_helper.py prepare-research-context SYMBOL --output-root ./runtime
```

For equities, this promotes basic SEC Companyfacts data when `source_bundle/sec_companyfacts.json` is present and a latest annual filing source is recorded. Revenue and income promotion chooses the latest annual fact across equivalent tags rather than trusting the first tag. Still inspect the promoted fiscal year, period end, filing date, and tag before using it in the report. For ETFs, this promotes the classified fund name but most issuer/fact-sheet fields still require targeted extraction or procedural gap fills.

6. Inspect `runtime/SYMBOL/research_context.json`. If material fields are missing, fill only targeted gaps procedurally from public sources. Record fills:

```bash
python3 {baseDir}/../shared/scripts/procedural_source_helper.py record-gap-fill SYMBOL --output-root ./runtime --field expense_ratio --value "0.59%" --source-id issuer_fact_sheet --confidence high --note "Filled from issuer fact sheet."
```

For shell-sensitive values such as dollar amounts, prefer structured input:

```bash
python3 {baseDir}/../shared/scripts/procedural_source_helper.py record-gap-fill SYMBOL --output-root ./runtime --json-file ./gap-fill.json
```

The JSON input may be either one object or an array of objects. Each object may contain `field`, `value`, `source_id`, `confidence`, and `note`. Prefer JSON input for any value containing dollar signs, quotes, percent signs, shell metacharacters, or multiple fields.

7. For BlackRock/iShares ETF payloads already downloaded, extracted from the product page, or user-supplied, promote the useful structured data:

```bash
python3 {baseDir}/../shared/scripts/procedural_source_helper.py extract-blackrock SYMBOL --output-root ./runtime --json-file ./runtime/SYMBOL/source_bundle/blackrock_product_api.json --source-id blackrock_product_api
```

This helper supports both legacy BlackRock API payloads and component-style product-page extracts such as `FundHeaderV3`, `KeyFundFactsV3`, `FeeTableV3`, and `TopHoldingsV3`.

8. Write:

```text
runtime/SYMBOL/
  SYMBOL-research.md
  SYMBOL-research.json
  research_context.json
  research_context.md
  sources.json
  run_manifest.json
  source_bundle/
```

9. Same-session self-check the artifacts for missing citations, stale dates, unsupported claims, and gaps. Label this as a self-check, not independent validation.

10. Tell the user the artifact paths and recommend running `market-research-full verifier` in a fresh Codex context against the run directory.

## Source Discipline

Every material quantitative claim must be cited or marked `Data not available` / `unverified`. Include source date, accessed date, and confidence when possible.

For deterministic bundles, cite the normalized file and raw source path, for example `reports/AAPL/2026-06-01/normalized/market_snapshot.json` and the corresponding `raw/` JSON from `source_manifest.json`.

Every cited `source_id` should appear in `sources.json`; every cited public page or document should have a frozen `local_artifact` in `source_bundle/` when the source can be saved. If a dynamic page cannot be captured cleanly, describe the limitation as a workflow extraction gap rather than public-data unavailability.

Keep facts separate from interpretation in major sections. Do not let procedural gap filling become open-ended browsing; search for named missing fields only.

## Paid Data

Do not require subscriptions or API keys. You may record exploratory notes about data that would have improved quality, but do not recommend purchasing a paid service from a single run.
