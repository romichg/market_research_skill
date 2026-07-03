# Researcher Workflow Commands

Use this reference for operational command detail. The main researcher skill contains the required quality gates; this file keeps command examples and helper mechanics out of the always-loaded instruction path.

## Deterministic Collection

Start with deterministic data collection when provider keys or cached raw files are available:

```bash
python3 {baseDir}/../shared/scripts/deterministic_research_collector.py doctor
python3 {baseDir}/../shared/scripts/deterministic_research_collector.py fetch SYMBOL --asset-type auto --as-of YYYY-MM-DD --data-dir ./data --reports-dir ./reports
```

Before a live or broad fetch, use `plan-fetch` to estimate cache reuse, endpoint call cost, and budget trimming without network calls or bundle writes:

```bash
python3 {baseDir}/../shared/scripts/deterministic_research_collector.py plan-fetch SYMBOL --providers sec,tiingo,eodhd --as-of YYYY-MM-DD --data-dir ./data --reports-dir ./reports
```

Do not restrict providers by default. Let the collector use every configured provider unless the user requests a narrower run, a provider budget/access issue requires narrowing, or a focused remediation pass is being run after a broader attempt. If you use `--providers`, `--provider-endpoints`, or `--max-provider-calls`, state in the report which deterministic providers or endpoint families were skipped and why.

Use `--providers sec,tiingo,eodhd` only for targeted or quota-preserving reruns, `--provider-endpoints PROVIDER=ENDPOINT[,ENDPOINT]` to restrict endpoint families, and `--max-provider-calls PROVIDER=N` to stay within free-tier budgets. Provider and endpoint filters apply to both live fetches and cached raw data used during bundle construction. Successful raw endpoint responses are reused across later `as_of` dates unless `--refresh` is passed, so do not use `--refresh` unless the user specifically needs a fresh provider pull.

## Quota-Safe Starting Points

Rebuild from saved raw data only:

```bash
python3 {baseDir}/../shared/scripts/deterministic_research_collector.py fetch SYMBOL --offline --as-of YYYY-MM-DD --data-dir ./data --reports-dir ./reports
```

Targeted rerun using only polite SEC access and one price provider:

```bash
python3 {baseDir}/../shared/scripts/deterministic_research_collector.py fetch SYMBOL --providers sec,tiingo --as-of YYYY-MM-DD --data-dir ./data --reports-dir ./reports
```

Opt into EODHD fundamentals without duplicating Tiingo price history:

```bash
python3 {baseDir}/../shared/scripts/deterministic_research_collector.py fetch SYMBOL --providers sec,tiingo,eodhd --provider-endpoints eodhd=fundamentals --max-provider-calls eodhd=10 --as-of YYYY-MM-DD --data-dir ./data --reports-dir ./reports
```

Scrappy full equity pass with one price source plus unique fundamentals/news/events:

```bash
python3 {baseDir}/../shared/scripts/deterministic_research_collector.py fetch SYMBOL --providers sec,tiingo,eodhd,alphavantage,marketaux,fmp --provider-endpoints tiingo=prices --provider-endpoints eodhd=fundamentals --provider-endpoints alphavantage=overview --provider-endpoints marketaux=news --provider-endpoints fmp=profile,key_metrics_ttm,ratios_ttm,income_statement,balance_sheet,cash_flow,stock_news,press_releases,dividends,earnings,splits,insider_trading,insider_statistics --max-provider-calls sec=3 --max-provider-calls tiingo=1 --max-provider-calls eodhd=10 --max-provider-calls alphavantage=1 --max-provider-calls marketaux=1 --max-provider-calls fmp=13 --as-of YYYY-MM-DD --data-dir ./data --reports-dir ./reports
```

Use offline mode to rebuild normalized outputs without rerunning successful provider collection:

```bash
python3 {baseDir}/../shared/scripts/deterministic_research_collector.py fetch SYMBOL --offline --as-of YYYY-MM-DD --data-dir ./data --reports-dir ./reports
python3 {baseDir}/../shared/scripts/deterministic_research_collector.py list-cache SYMBOL
```

If a deterministic fetch aborts because one provider is `unauthorized`, `rate_limited`, or `plan_gated`, rerun a restricted/offline bundle with only providers and endpoints that have usable cache or a low-risk live path:

```bash
python3 {baseDir}/../shared/scripts/deterministic_research_collector.py fetch SYMBOL --offline --providers tiingo,alphavantage,marketaux,fmp --as-of YYYY-MM-DD --data-dir ./data --reports-dir ./reports
python3 {baseDir}/../shared/scripts/deterministic_research_collector.py fetch SYMBOL --offline --providers eodhd,marketaux --provider-endpoints eodhd=news --provider-endpoints marketaux=news --as-of YYYY-MM-DD --data-dir ./data --reports-dir ./reports
```

For pending IPOs or symbols with no trading history, always attempt a targeted news/events pass when any configured news provider is available. Use `normalized/news.json` as evidence only after checking relevance, because ticker collisions can return unrelated issuers.

## Deterministic Bundle Contents

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

Use this output as the primary factual input. Live API calls use conservative retries/backoff for transient 429/503/network failures and do not retry unauthorized or not-found responses aggressively. Provider authentication failures exit with a clear error; provider rate-limit or endpoint errors are promoted into `manifest.json` warnings and preserved in `source_manifest.json` plus raw `provider_result.error`.

When provider technical output is absent or incomplete, compute technical analysis locally from `data/SYMBOL/AS_OF/normalized/technical_signals.json` and `data/SYMBOL/AS_OF/normalized/prices_daily.json`. Use adjusted-close language for returns, moving averages, drawdowns, volatility, and support/resistance approximations, and record calculation inputs in the report JSON `technical_analysis` and `calculation_audit` fields.

## Procedural Source Workspace

Create the procedural run only when deterministic output is sparse or a procedural source bundle is required:

```bash
python3 {baseDir}/../shared/scripts/procedural_source_helper.py init-run SYMBOL --output-root ./runtime --as-of YYYY-MM-DD
```

Pass `--as-of YYYY-MM-DD` to place procedural runtime artifacts under `runtime/SYMBOL/YYYY-MM-DD/`; without `--as-of`, explicit `--output-root` calls keep the legacy `output_root/SYMBOL` layout.

Mutating procedural helper commands such as `classify`, `record-source`, `record-source-gap`, and `record-gap-fill` auto-create the dated runtime directory and manifest when needed. `init-run` remains the recommended first step because it makes the run directory explicit before source capture.

Classify the security when needed:

```bash
python3 {baseDir}/../shared/scripts/procedural_source_helper.py classify SYMBOL --output-root ./runtime --as-of YYYY-MM-DD --security-type etf --name "Fund or company name"
```

Record material sources:

```bash
python3 {baseDir}/../shared/scripts/procedural_source_helper.py record-source SYMBOL --output-root ./runtime --as-of YYYY-MM-DD --id source_id --title "Source title" --url "https://example.com/source" --kind issuer_fact_sheet --source-date YYYY-MM-DD --artifact ./downloaded-source.pdf --confidence high
```

Use `--source-date` whenever a document or page has a visible as-of, filing, publication, or effective date. Use `--artifact` for every cited public web page or document you saved locally; the helper copies it into `source_bundle/`, records artifact size and SHA-256 checksum metadata, and rejects obvious extension/content mismatches such as HTML saved as `.csv`.

Record public/free source capture failures as structured gaps:

```bash
python3 {baseDir}/../shared/scripts/procedural_source_helper.py record-source-gap SYMBOL --output-root ./runtime --as-of YYYY-MM-DD --source-id holdings_csv --attempted-url "https://example.com/holdings.csv" --reason "CSV endpoint returned HTML." --replacement-source-id issuer_fact_sheet --severity medium
```

Prepare compact context:

```bash
python3 {baseDir}/../shared/scripts/procedural_source_helper.py prepare-research-context SYMBOL --output-root ./runtime --as-of YYYY-MM-DD
```

For shell-sensitive gap-fill values such as dollar amounts, prefer structured input:

```bash
python3 {baseDir}/../shared/scripts/procedural_source_helper.py record-gap-fill SYMBOL --output-root ./runtime --as-of YYYY-MM-DD --json-file ./gap-fill.json
```

For BlackRock/iShares ETF payloads already downloaded, extracted from the product page, or user-supplied, promote useful structured data:

```bash
python3 {baseDir}/../shared/scripts/procedural_source_helper.py extract-blackrock SYMBOL --output-root ./runtime --as-of YYYY-MM-DD --json-file ./runtime/SYMBOL/YYYY-MM-DD/source_bundle/blackrock_product_api.json --source-id blackrock_product_api
```

The BlackRock/iShares extractor validates the payload identity against the requested ticker before promoting data. If a product ID resolves to the wrong fund, record a source gap instead of using the payload.

When capturing BlackRock/iShares API payloads manually, save the complete response before previewing it. Avoid commands such as `tee payload.json | head`, which can terminate the pipe early and leave a truncated saved artifact. Inspect the saved file after capture with `jq`, `python3 -m json.tool`, or another non-truncating reader.

## Final Artifacts

Working/procedural artifacts belong under runtime:

```text
runtime/SYMBOL/YYYY-MM-DD/
  research_context.json
  research_context.md
  sources.json
  run_manifest.json
  source_bundle/
```

Final report artifacts belong under reports:

```text
reports/SYMBOL/YYYY-MM-DD/
  SYMBOL-research.md
  SYMBOL-research.json
  SYMBOL-research.pdf
```

Attempt best-effort PDF generation after the final Markdown report is written:

```bash
bash {baseDir}/../shared/scripts/md-to-pdf.sh ./reports/SYMBOL/YYYY-MM-DD/SYMBOL-research.md
```

If `pandoc`, `xelatex`, or LaTeX packages such as `lmodern.sty` are unavailable, report the helper message and continue with Markdown and JSON artifacts. Do not treat missing PDF tooling as a research failure.

Before handing the final report to a verifier, run the producer self-check:

```bash
python3 {baseDir}/../shared/scripts/producer_self_check.py ./reports/SYMBOL/YYYY-MM-DD --data-dir ./data/SYMBOL/YYYY-MM-DD --runtime-dir ./runtime/SYMBOL/YYYY-MM-DD --fix-safe
```

Fix open critical or moderate self-check findings before requesting validation. Minor self-check findings may remain when they are not thesis-blocking, but record them in runtime issue notes. The self-check writes `producer-self-check.md` and `producer-self-check.json` under runtime; do not add a Self-Check section to the investor report.
