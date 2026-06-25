# Market Research Self-Improvement Ideas

Review scope:

- `runtime/market-research-batch-20260624` / `reports/INFQ/2026-06-24`
- `runtime/market-research-batch-20260625` / `reports/ECH/2026-06-25`
- Current quality docs, researcher/verifier/supervisor instructions, helper scripts, and tests

Both reviewed symbols passed the batch gate in one iteration with no open critical or moderate validation issues. The useful improvement signal is therefore not remediation behavior; it is repeated minor or documented producer friction that should become deterministic checks, helper output, or prompt requirements.

## High-Value Improvements

### 0. Remove internal workflow language from final reports

Evidence:

- `reports/INFQ/2026-06-24/INFQ-research.md` uses terms such as "deterministic market data provider", "deterministic price file", `runtime/...`, `data/...`, and source IDs in the investor-facing report.
- `reports/ECH/2026-06-25/ECH-research.md` uses phrases such as "latest deterministic market close", "deterministic adjusted-price series", "deterministic bundle", and local artifact paths.
- `market-research/shared/scripts/report_language_lint.py` already flags several of these terms, but the current self-improvement plan still proposes new prompt text that would reintroduce phrases such as "deterministic technical data" into report-writing guidance.

Recommended change:

- Define investor-facing vocabulary for main report sections: "latest available close", "available market data", "calculated price signals", "source limitation", and "source evidence set" only where auditability is intended.
- Keep internal terms such as `deterministic`, `bundle`, `artifact`, `normalized`, `raw`, `runtime`, `cache`, `provider`, `source_manifest`, and local file paths out of main report sections before `Data Issues And Discrepancies`.
- Permit internal vocabulary in JSON sidecars, validation artifacts, helper logs, implementation plans, `Sources And Evidence`, and narrowly in `Data Issues And Discrepancies` when the mechanics directly affect investor confidence.

Expected benefit:

- Final reports read less like workflow transcripts and more like investor memos.
- Lints enforce the vocabulary boundary before validation.

### 1. Make SEC identity and filing normalization reliable

Evidence:

- `runtime/market-research-batch-20260624/INFQ/2026-06-24/INFQ-market-research-issues.md` reports that `normalized/sec_filings_index.json` and `normalized/sec_filing_sections.json` were not produced even though SEC submissions and filings existed.
- `reports/INFQ/2026-06-24/INFQ-validation.json` lists `normalized_sec_filings_index_and_sections` as `unresolved_data_unavailable`.
- `market-research/shared/scripts/deterministic_research_collector.py` currently emits the SEC filings index only when `identity.cik` exists, but `normalize_identity()` does not preserve the SEC submissions `cik` field.

Recommended change:

- Preserve CIK in `normalized/identity.json`.
- Emit `sec_filings_index.json` whenever SEC submissions include enough CIK or recent-filing metadata.
- If deterministic section extraction is unavailable, write a structured gap with the affected filing-section artifact name instead of silently omitting expected normalized coverage.

Expected benefit:

- Researchers and validators can distinguish "SEC filings were unavailable" from "section extraction was not implemented."
- Same-day filing checks become easier and less manual for newly public or event-driven issuers.

### 2. Expand SEC companyfacts normalization beyond annual net income

Evidence:

- `runtime/market-research-batch-20260624/INFQ/2026-06-24/INFQ-market-research-issues.md` says raw SEC companyfacts contained revenue, cash, assets, liabilities, operating cash flow, share count, and equity fields, but `normalized/equity_fundamentals.json` surfaced only net income.
- `reports/INFQ/2026-06-24/INFQ-research.md` had to use raw companyfacts and the filed 10-Q directly for Q1 2026 revenue, liquidity, cash flow, and share count.
- `latest_companyfacts_usd_fact()` currently prefers annual 10-K FY facts and does not expose useful interim facts for recently public issuers.

Recommended change:

- Add a reusable companyfacts picker that supports latest annual and latest interim facts by unit.
- Normalize revenue, gross profit or cost of revenue when available, assets, liabilities, cash and restricted cash, operating cash flow, shares outstanding, and equity/book-value fields.
- Preserve tag, unit, period end, filed date, form, fiscal year, and fiscal period in each normalized value.

Expected benefit:

- Deterministic evidence becomes materially more useful for young issuers where annual data is stale or predecessor-style.
- Researchers spend less time manually extracting basic financials from filings.

### 3. Improve ETF classification and ETF-specific routing

Evidence:

- `runtime/market-research-batch-20260625/ECH/2026-06-25/ECH-market-research-issues.md` reports that ECH was classified as `asset_type: equity` even though sponsor materials identify it as the iShares MSCI Chile ETF.
- `reports/ECH/2026-06-25/ECH-validation.json` includes resolved moderate issue `ECH-VAL-001` for the deterministic misclassification.
- `data/ECH/2026-06-25/deterministic_data_usage.json` records `asset_type: equity`, which pushed equity-oriented deterministic usage requirements onto an ETF.

Recommended change:

- Use provider name/category text to infer ETF/fund status before defaulting FMP profiles to `equity`; names containing ETF, iShares, SPDR, Vanguard ETF, fund, trust, or index fund should not be forced to equity without stronger contradictory evidence.
- When classification is ETF/fund, suppress equity-only gap noise such as insider statistics and company statements unless a source explicitly says the vehicle is an operating company.
- Prefer ETF normalized artifacts and ETF usage requirements after a strong ETF classification signal.

Expected benefit:

- ETF reports start in the right workflow without manual procedural classification.
- Provider-limit impact mapping becomes more investor-relevant and less cluttered.

### 4. Add filed-share market-cap reconciliation

Evidence:

- `runtime/market-research-batch-20260624/INFQ/2026-06-24/INFQ-market-research-issues.md` documents a material discrepancy: provider market cap of about $2.45 billion versus about $3.08 billion implied by filed shares and latest close.
- `reports/INFQ/2026-06-24/INFQ-research.md` handled this well as a valuation range, but the helper did not surface the filed-share cross-check.
- Existing `discrepancies_from_snapshot()` only checks alternate provider market-cap values, not filed shares multiplied by latest close.

Recommended change:

- Once normalized shares outstanding and latest close exist, compute `filed_share_implied_market_cap`.
- If it differs materially from provider market cap, add a discrepancy entry with relative difference and investor impact.

Expected benefit:

- Valuation ranges are driven by deterministic evidence instead of relying on the researcher to notice the discrepancy manually.

### 5. Make final report bundles portable without moving runtime into reports

Evidence:

- `reports/INFQ/2026-06-24/INFQ-validation.json` issue `MRV-INFQ-002` says the final report directory did not include local copies of `sources.json`, `research_context.json`, or `run_manifest.json`, so the report bundle was less portable if `reports/INFQ/2026-06-24` was archived alone.
- `reports/ECH/2026-06-25/` does contain `sources.json` and `run_manifest.json`, showing this is feasible without bundling all runtime artifacts.

Recommended change:

- Update batch producer prompts and researcher final-artifact instructions to copy small validation-facing sidecars into `reports/SYMBOL/AS_OF/`: `sources.json`, `run_manifest.json`, and `research_context.json` when present.
- Keep bulky source bundles, prompts, logs, downloads, and transient notes under `runtime/`.

Expected benefit:

- Final report directories become portable investor deliverables while preserving the repo's `reports/`, `runtime/`, and `data/` boundaries.

### 6. Tighten report-quality lints for repeatable minor validation issues

Evidence:

- `reports/ECH/2026-06-25/ECH-validation.json` issue `ECH-VAL-002` says the Markdown technical section omitted interpretation of max drawdown even though JSON included it.
- `reports/ECH/2026-06-25/ECH-validation.json` issue `ECH-VAL-003` says ETF risks omitted authorized-participant/creation-redemption mechanics and securities-lending risk.
- Existing `market-research/shared/scripts/report_language_lint.py` checks only broad technical-analysis terms and main-body provenance hygiene.

Recommended change:

- Extend report language lint to require drawdown discussion in `Market Snapshot And Technical Analysis` when price history exists and deterministic `max_drawdown_available` is present in JSON.
- Add an ETF risk checklist lint that flags missing authorized-participant/creation-redemption, securities lending, premium/discount, tracking, tax/withholding, liquidity, and closure/AUM risk terms when `security_type` is `etf`.

Expected benefit:

- Future ETF reports catch repeatable quality gaps before validation.
- Validator judgment remains necessary, but common omissions become cheap to detect.

### 7. Add ETF portfolio-company snapshots

Evidence:

- `reports/ECH/2026-06-25/ECH-research.md` identifies concentration and names a few top holdings, but it does not give the reader quick company-level context for all 25 holdings.
- For concentrated ETFs, the fund thesis depends on the actual issuers in the basket, not only sector weights and benchmark descriptions.

Recommended change:

- Add a `Portfolio Companies Snapshot` section to ETF reports when holdings are available.
- Use all holdings when the ETF has 25 or fewer holdings; otherwise use the top 25 by portfolio weight.
- Include holding name/ticker, weight, sector or industry, one-sentence business description, quick outlook, and quick price/technical context when reliable public/free data is available.
- Follow the table with a synthesis paragraph explaining what those companies imply for ETF concentration, cyclicality, upside drivers, risk, and monitoring.
- Do not turn ETF reports into full company reports; missing company-level data should be disclosed in investor terms without internal workflow wording.

Expected benefit:

- ETF reports become more useful for understanding what the investor actually owns.
- Concentrated funds like ECH show company-level drivers without requiring separate research bundles for every holding.

## What Not To Change

- Do not make self-improvement automatic. The batch roots followed the intended prompt-only self-improvement workflow.
- Do not push cache mechanics or raw provider details into the main narrative. Existing reports correctly kept most mechanics in `Data Issues And Discrepancies` and `Sources And Evidence`.
- Do not bundle entire runtime trees into `reports/`. Only copy small final-bundle sidecars needed for portability and validation.
