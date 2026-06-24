---
name: market-research-researcher
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
- Use `../shared/scripts/md-to-pdf.sh` after the final Markdown report is written. PDF generation is best-effort: continue if `pandoc` or `xelatex` is unavailable.
- Read `references/provider-data-map.md` when adding, validating, or reasoning about deterministic provider fields, duplicate data, and fallback behavior.
- Read `references/source-policy.md` before source gathering and citation work.
- Read `references/equity-research.md` for equities and ADRs.
- Read `references/etf-research.md` for ETFs.
- Read `references/report-template.md` before writing final artifacts.
- Use `../shared/schemas/research-output.schema.json` for the report sidecar.
- Use `../shared/schemas/validation-output.schema.json` as the shared validation contract.

## Workflow

Use separate roots for generated artifacts:

- `data/SYMBOL/AS_OF/`: deterministic raw, normalized, manifest, gaps, and research input pack artifacts.
- `reports/SYMBOL/AS_OF/`: polished research markdown, JSON sidecar, and validation-facing report artifacts.
- `runtime/SYMBOL/AS_OF/`: procedural helper manifests, source bundles, prompts, notes, and other run-time working files.

1. Start with deterministic data collection when provider keys or cached raw files are available:

```bash
python3 {baseDir}/../shared/scripts/deterministic_research_collector.py doctor
python3 {baseDir}/../shared/scripts/deterministic_research_collector.py fetch SYMBOL --asset-type auto --as-of YYYY-MM-DD --data-dir ./data --reports-dir ./reports
```

Do not restrict providers by default. Let the collector use every configured provider unless the user requests a narrower run, a provider budget/access issue requires narrowing, or a focused remediation pass is being run after a broader attempt. If you use `--providers`, `--provider-endpoints`, or `--max-provider-calls`, state in the report which deterministic providers or endpoint families were skipped and why.

Use `--providers sec,tiingo,eodhd` only for targeted or quota-preserving reruns, `--provider-endpoints PROVIDER=ENDPOINT[,ENDPOINT]` to restrict endpoint families, and `--max-provider-calls PROVIDER=N` to stay within free-tier budgets. Provider and endpoint filters apply to both live fetches and cached raw data used during bundle construction, preventing stale cached providers or duplicate cached endpoints from slipping into a quota-preserving run. The collector estimates provider endpoint cost before network calls and skips providers whose estimated cost exceeds the provided or conservative default budget. Successful raw endpoint responses are reused across later `as_of` dates unless `--refresh` is passed, so do not use `--refresh` unless the user specifically needs a fresh provider pull.

Recommended quota-safe starting points:

```bash
# Rebuild from saved raw data only.
python3 {baseDir}/../shared/scripts/deterministic_research_collector.py fetch SYMBOL --offline --as-of YYYY-MM-DD --data-dir ./data --reports-dir ./reports

# Targeted rerun using only polite SEC access and one price provider.
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

If a deterministic fetch aborts because one provider is `unauthorized`, `rate_limited`, or `plan_gated`, do not stop deterministic work immediately. Rerun a restricted/offline bundle with only providers and endpoints that have usable cache or a low-risk live path. Examples:

```bash
python3 {baseDir}/../shared/scripts/deterministic_research_collector.py fetch SYMBOL --offline --providers tiingo,alphavantage,marketaux,fmp --as-of YYYY-MM-DD --data-dir ./data --reports-dir ./reports
python3 {baseDir}/../shared/scripts/deterministic_research_collector.py fetch SYMBOL --offline --providers eodhd,marketaux --provider-endpoints eodhd=news --provider-endpoints marketaux=news --as-of YYYY-MM-DD --data-dir ./data --reports-dir ./reports
```

For pending IPOs or symbols with no trading history, always attempt a targeted news/events pass when any configured news provider is available. Use the resulting `normalized/news.json` as evidence only after checking relevance, because ticker collisions can return unrelated issuers.

The deterministic collector writes:

```text
data/SYMBOL/AS_OF/
  manifest.json
  source_manifest.json
  gaps.json
  deterministic_data_usage.json
  raw/
  normalized/
  research_input_pack.md
```

Use this output as the primary factual input. Every normalized value must carry provider, source URL, raw path, and status. Missing data must remain a structured gap with only the attempted providers listed. Do not invent or infer unsupported values. Live API calls use conservative retries/backoff for transient 429/503/network failures and do not retry unauthorized or not-found responses aggressively. Provider authentication failures exit with a clear error; provider rate-limit or endpoint errors are promoted into `manifest.json` warnings and preserved in `source_manifest.json` plus raw `provider_result.error`.

Before drafting the final report, inspect `data/SYMBOL/AS_OF/deterministic_data_usage.json`. For every datapoint marked `materiality: required`, use it in the report or add a field-level `deterministic_data_usage` JSON disposition explaining why it was not used. For every datapoint marked `materiality: review`, use it when it affects the investor thesis, risk profile, valuation/performance context, lifecycle context, or source-quality discussion; otherwise add a disposition explaining why it was not material, duplicated by a better source, stale/wrong-entity, or unusable. Do not let required or review deterministic fields disappear silently.

For every required deterministic datapoint, the report JSON `deterministic_data_usage` entry must include a field-specific `rationale` that names the field or value and explains the investor relevance, duplication by better evidence, or reason for omission. Generic rationales such as "used for valuation context" are insufficient for required datapoints.

When provider technical output is absent or incomplete, compute technical analysis locally from `data/SYMBOL/AS_OF/normalized/technical_signals.json` and `data/SYMBOL/AS_OF/normalized/prices_daily.json`. Use adjusted-close language for returns, moving averages, drawdowns, volatility, and support/resistance approximations, and record the calculation inputs in the report JSON `technical_analysis` and `calculation_audit` fields.

2. If deterministic output is sparse or a procedural source bundle is required, normalize the symbol to uppercase and create the run:

```bash
python3 {baseDir}/../shared/scripts/procedural_source_helper.py init-run SYMBOL --output-root ./runtime --as-of YYYY-MM-DD
```

Pass `--as-of YYYY-MM-DD` to place procedural runtime artifacts under `runtime/SYMBOL/YYYY-MM-DD/`; without `--as-of`, explicit `--output-root` calls keep the legacy `output_root/SYMBOL` layout.

Wait for `init-run` to complete before `classify`, `record-source`, or any other dependent helper command. Source registry writes are lock-protected, but run initialization is a required sequential step.

3. Classify the security. If the helper cannot classify from public data, use clear procedural evidence or ask the user to choose `equity`, `adr`, or `etf`; then record it:

```bash
python3 {baseDir}/../shared/scripts/procedural_source_helper.py classify SYMBOL --output-root ./runtime --as-of YYYY-MM-DD --security-type etf --name "Fund or company name"
```

4. Gather public/free sources. Prefer primary sources. Record each material source:

```bash
python3 {baseDir}/../shared/scripts/procedural_source_helper.py record-source SYMBOL --output-root ./runtime --as-of YYYY-MM-DD --id source_id --title "Source title" --url "https://example.com/source" --kind issuer_fact_sheet --source-date YYYY-MM-DD --artifact ./downloaded-source.pdf --confidence high
```

Use `--source-date` whenever a document or page has a visible as-of, filing, publication, or effective date. Use `--artifact` for every cited public web page or document you saved locally; the helper copies it into `source_bundle/`, records artifact size and SHA-256 checksum metadata, and rejects obvious extension/content mismatches such as HTML saved as `.csv`.

The helper uses lock-protected registry writes, but source capture is still easier to audit when sources are recorded in small logical groups rather than hidden behind one large shell pipeline.

When a public/free source capture fails or returns unusable content, record the attempted source as a structured gap:

```bash
python3 {baseDir}/../shared/scripts/procedural_source_helper.py record-source-gap SYMBOL --output-root ./runtime --as-of YYYY-MM-DD --source-id holdings_csv --attempted-url "https://example.com/holdings.csv" --reason "CSV endpoint returned HTML." --replacement-source-id issuer_fact_sheet --severity medium
```

If a material source is blocked by protected-source technology such as CAPTCHA, WAF, bot challenge, suspicious automated-access response, or JavaScript challenge, follow `references/source-policy.md` protected-source access guidance. Treat headed-browser human assistance as a first-class path when it preserves source quality.

5. Prepare compact context:

```bash
python3 {baseDir}/../shared/scripts/procedural_source_helper.py prepare-research-context SYMBOL --output-root ./runtime --as-of YYYY-MM-DD
```

For equities, this promotes basic SEC Companyfacts data when `source_bundle/sec_companyfacts.json` is present and a latest annual filing source is recorded. Revenue and income promotion chooses the latest annual fact across equivalent tags rather than trusting the first tag. Still inspect the promoted fiscal year, period end, filing date, and tag before using it in the report. For ETFs, this promotes the classified fund name but most issuer/fact-sheet fields still require targeted extraction or procedural gap fills.

6. Inspect `runtime/SYMBOL/YYYY-MM-DD/research_context.json`. If material fields are missing, fill only targeted gaps procedurally from public sources. Record fills:

```bash
python3 {baseDir}/../shared/scripts/procedural_source_helper.py record-gap-fill SYMBOL --output-root ./runtime --as-of YYYY-MM-DD --field expense_ratio --value "0.59%" --source-id issuer_fact_sheet --confidence high --note "Filled from issuer fact sheet."
```

For shell-sensitive values such as dollar amounts, prefer structured input:

```bash
python3 {baseDir}/../shared/scripts/procedural_source_helper.py record-gap-fill SYMBOL --output-root ./runtime --as-of YYYY-MM-DD --json-file ./gap-fill.json
```

The JSON input may be either one object or an array of objects. Each object may contain `field`, `value`, `source_id`, `confidence`, and `note`. Prefer JSON input for any value containing dollar signs, quotes, percent signs, shell metacharacters, or multiple fields.

7. For BlackRock/iShares ETF payloads already downloaded, extracted from the product page, or user-supplied, promote the useful structured data:

```bash
python3 {baseDir}/../shared/scripts/procedural_source_helper.py extract-blackrock SYMBOL --output-root ./runtime --as-of YYYY-MM-DD --json-file ./runtime/SYMBOL/YYYY-MM-DD/source_bundle/blackrock_product_api.json --source-id blackrock_product_api
```

This helper supports both legacy BlackRock API payloads and component-style product-page extracts such as `FundHeaderV3`, `KeyFundFactsV3`, `FeeTableV3`, and `TopHoldingsV3`.

Use targeted procedural research when the deterministic bundle does not explain the business well enough for an investor. For operating companies, fill business-profile gaps on: what the product does, technology explanation in plain language, who pays, revenue model, customer or government/commercial exposure, acquisition contribution, current commercial traction, valuation context, current technical setup, and practical demand drivers. Do not stop at filing labels or provider profiles when they leave the business unclear. The final report is judged on investor usefulness and analysis, not on whether a fact arrived through deterministic or procedural collection.

For event-driven issuer news dated on or after the as-of date, perform a same-day SEC freshness check against the issuer filings page or SEC company browse results, especially for 8-K, 10-Q, 10-K, S-3, S-1, 13D/G, and proxy filings. If deterministic SEC submissions lag, capture the filing procedurally, cite the filing date, and disclose the deterministic omission in `Data Issues And Discrepancies`.

8. Write working/procedural artifacts under runtime and final report artifacts under reports:

```text
runtime/SYMBOL/YYYY-MM-DD/
  research_context.json
  research_context.md
  sources.json
  run_manifest.json
  source_bundle/

reports/SYMBOL/YYYY-MM-DD/
  SYMBOL-research.md
  SYMBOL-research.json
  SYMBOL-research.pdf  # Best-effort when pandoc and xelatex are available.
```

The final Markdown report must include these sections:

- `## Bottom Line`
- `## Key Facts`
- `## Business Profile`
- `## Business Model And Demand Drivers`
- `## Market Snapshot And Technical Analysis`
- `## Financials And Balance Sheet`
- `## Valuation`
- `## What Looks Attractive`
- `## What Worries Me`
- `## Catalysts And Monitoring Triggers`
- `## Bull/Base/Bear Decision Variables`
- `## Risks And Invalidation Points`
- `## My Take`
- `## Data Issues And Discrepancies`
- `## Sources And Evidence`

The JSON sidecar must satisfy `../shared/schemas/research-output.schema.json`, including `technical_analysis`, `valuation_or_performance`, `decision_factors`, `risks`, `catalysts`, `source_coverage`, and `calculation_audit`.

When a deterministic bundle exists, the JSON sidecar should also include `deterministic_bundle` and field-level `deterministic_data_usage` entries for all required/review datapoints that were used or intentionally omitted.

9. Same-session self-check the artifacts for missing citations, stale dates, unsupported claims, and gaps. Label this as a self-check, not independent validation.

10. Attempt best-effort PDF generation for the final Markdown report:

```bash
bash {baseDir}/../shared/scripts/md-to-pdf.sh ./reports/SYMBOL/YYYY-MM-DD/SYMBOL-research.md
```

If `pandoc`, `xelatex`, or LaTeX packages such as `lmodern.sty` are unavailable, report the helper message and continue with the Markdown and JSON artifacts. Do not treat missing PDF tooling as a research failure.

11. Tell the user the artifact paths, including the PDF path if generated, and recommend running `market-research verifier` in a fresh agent context against the run directory.

## Source Discipline

Every material quantitative claim must be cited or marked `Data not available` / `unverified`. Include source date, accessed date, and confidence when possible.

For deterministic bundles, cite the normalized file and raw source path, for example `data/AAPL/2026-06-01/normalized/market_snapshot.json` and the corresponding `raw/` JSON from `source_manifest.json`.

The Markdown report must read like investor-grade research, not a validation transcript. Use deterministic data aggressively, but do not make deterministic coverage the organizing principle of the prose. Lead with thesis, variant view, what matters, what can go wrong, what would change the view, and what to monitor. Keep detailed local artifact paths in the JSON sidecar or a consolidated evidence section unless an inline citation is necessary for a contentious, surprising, or source-sensitive claim.

When provider endpoints are rate-limited, plan-gated, protected, unavailable, or otherwise incomplete, include provider-limit impact mapping in the report JSON and, when material, in the data-quality discussion. Map each limitation to its affected analysis area. Examples: unavailable short interest affects crowding/squeeze analysis; unavailable forward estimates affects valuation; unavailable insider statistics affects dilution/governance analysis; unavailable filing sections affects direct risk-factor and MD&A validation.

Every cited `source_id` should appear in `sources.json`; every cited public page or document should have a saved `local_artifact` in `source_bundle/` when the source can be saved. If a dynamic page cannot be captured cleanly, describe the limitation as a workflow extraction gap rather than public-data unavailability.

Keep facts separate from interpretation in major sections. Do not let procedural gap filling become open-ended browsing; search for named missing fields only.

## Paid Data

Do not require subscriptions or API keys. You may record exploratory notes about data that would have improved quality, but do not recommend purchasing a paid service from a single run.
