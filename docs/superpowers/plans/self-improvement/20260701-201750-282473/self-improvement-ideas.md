# Market Research Self-Improvement Ideas

Review target: `runtime/market-research-batch-20260701`

As-of date: 2026-07-01

## Executive Assessment

The batch passed the supervisor gate for all three symbols: `QTUM`, `QTUP`, and `WQTM` have no open critical or moderate validation issues in `runtime/market-research-batch-20260701/research-loop-summary.json`. The reports are materially usable ETF memos, with executive summaries, key facts, portfolio-company snapshots, valuation/performance framing, risk sections, data-quality sections, and source/evidence sections.

The recurring defects are workflow and artifact-quality issues rather than thesis failures:

- ETF classification and ETF-specific normalization are still weak in the deterministic collector.
- Final source registries can miss deterministic source IDs, preserve runtime-local paths, or drift between runtime and report copies.
- Validator and lint checks do not yet catch weak deterministic-usage rationales or final-package portability issues consistently.
- PDF generation status is ambiguous when local TeX tooling fails.
- Dependent procedural helper commands can be parallelized accidentally before `init-run` creates the run directory.

## Findings And Ideas

### 1. Fix ETF classification precedence in deterministic collection

Evidence:

- `runtime/market-research-batch-20260701/QTUM/2026-07-01/QTUM-market-research-issues.md` says `identity.asset_type` was `equity` even though raw profile evidence had `isEtf: true`, the name was "Defiance Quantum ETF", and issuer documents identify QTUM as an ETF.
- `runtime/market-research-batch-20260701/QTUP/2026-07-01/QTUP-market-research-issues.md` says QTUP was classified as `unknown` even though quote/name and issuer pages identified it as an ETF.
- `runtime/market-research-batch-20260701/WQTM/2026-07-01/WQTM-market-research-issues.md` says WQTM was `unknown` despite issuer evidence clearly identifying it as an ETF.
- `market-research/shared/scripts/deterministic_research_collector.py` currently lets early SEC/EOD/FMP decisions prevent later ETF-specific evidence from overriding `asset_type`.

Improvement:

Create an evidence-ranked asset-type resolver. Explicit ETF signals such as FMP `isEtf`, Alpha Vantage `ETF_PROFILE`, Twelve Data type text, EOD fund category, or fund-name tokens should override generic SEC `equity` unless ADR evidence is stronger. Preserve alternates and the reason for the selected type in `normalized/identity.json`.

### 2. Normalize available ETF profile and holdings data instead of leaving raw-only evidence

Evidence:

- QTUM had Alpha Vantage ETF profile raw evidence, including holdings, but no `normalized/etf_profile.json` or `normalized/etf_holdings.json`.
- QTUP and WQTM needed procedural issuer pages for NAV, holdings, AUM, expense, and ETF identity because deterministic output lacked ETF-specific normalized sections.
- `docs/quality-bar.md` already documents this as a known ETF collector gap.

Improvement:

Add `normalize_etf_profile()` and broaden `normalize_etf_holdings()` so Alpha Vantage ETF profile and any existing free provider ETF holdings are emitted when asset type is ETF/fund. Emit unavailable ETF files with structured gaps only when no usable ETF payload exists.

### 3. Add final report source-registry reconciliation

Evidence:

- `runtime/market-research-batch-20260701/loop-skill-issues.md` records `source-registry-remediation-sync`.
- `reports/QTUM/2026-07-01/QTUM-market-research-skill-issues.md`, `reports/QTUP/2026-07-01/QTUP-market-research-skill-issues.md`, and `reports/WQTM/2026-07-01/WQTM-market-research-skill-issues.md` all point to missing or fragile source-registry entries for deterministic source IDs.
- `reports/QTUM/2026-07-01/QTUM-validation.md` still has minor issue `QTUM-VAL-002` because `det_prices_daily` and `det_news` appear in Sources And Evidence but not in `sources.json`.

Improvement:

Add a shared source-registry reconciliation helper that extracts source IDs from Markdown and JSON, verifies that each ID exists in final `reports/SYMBOL/AS_OF/sources.json`, and registers deterministic source IDs from `data/SYMBOL/AS_OF/source_manifest.json` plus normalized artifacts. Use it in researcher finalization, remediation prompts, and validation scaffolds.

### 4. Rewrite runtime-local artifacts to report-local paths in final packages

Evidence:

- `reports/QTUP/2026-07-01/QTUP-validation.md` minor issue `QTUP-V-001` says final `sources.json` points at absolute/runtime paths even though equivalent frozen copies exist under `reports/QTUP/2026-07-01/source_bundle/`.
- `reports/QTUP/2026-07-01/QTUP-research.md` lines 191-194 list runtime `source_bundle` paths in the final evidence table.
- `market-research/batch-supervisor/scripts/research_loop.py` copies `sources.json` from runtime to report in `sync_runtime_sources_to_report()` without rewriting copied artifact paths.

Improvement:

During runtime-to-report sync, copy source artifacts first and rewrite `local_artifact` paths to `reports/SYMBOL/AS_OF/source_bundle/...` when the copied report-local file exists and the checksum matches. Add lint to flag runtime paths in final `Sources And Evidence` when a report-local copy is available.

### 5. Flag boilerplate deterministic-usage rationales

Evidence:

- `reports/WQTM/2026-07-01/WQTM-research.json` repeats rationales like `market_snapshot.fifty_two_week_high was used to anchor WQTM market, liquidity, performance, or technical context for investors`.
- `market-research/verifier/references/verifier-workflow.md` says generic rationales are insufficient, but the final validation still passed with only unrelated minor issues.

Improvement:

Extend `deterministic_data_usage.py` or `validate_market_research.py` to flag repeated boilerplate rationales across required/review datapoints. This should be at least a minor finding, and moderate when the field is required and the rationale does not name the value or investor relevance.

### 6. Improve PDF helper machine-readable status

Evidence:

- `runtime/market-research-batch-20260701/QTUM/2026-07-01/QTUM-market-research-issues.md` says `md-to-pdf.sh` printed a pandoc/xelatex failure and "PDF not generated" but exited status 0.

Improvement:

Keep missing optional PDF tooling non-blocking, but make the helper emit a small JSON status or clear stdout token such as `{"generated": false, "reason": "latex_package_missing"}`. The batch supervisor can then record PDF status without inferring from exit code.

### 7. Make validator CLI mode harder to misuse

Evidence:

- QTUM remediation notes show `validate_market_research.py` was confusing when run against `data/QTUM/2026-07-01` with explicit final report paths.
- `reports/QTUM/2026-07-01/QTUM-market-research-skill-issues.md` records `validator-helper-input-ergonomics`.

Improvement:

When `--report-md` or `--report-json` is supplied and `run_dir` is a deterministic data bundle, print a direct hint to pass `reports/SYMBOL/AS_OF` for final-report validation, or accept the data bundle path while deriving canonical report output paths from the explicit report files.

### 8. Prevent parallelization of dependent procedural helper commands

Evidence:

- `runtime/market-research-batch-20260701/WQTM/2026-07-01/WQTM-market-research-issues.md` says `classify` failed when run in parallel with `init-run` because the run directory did not exist.

Improvement:

Document and test that `init-run` is a dependency for helper commands that mutate a run manifest. Optionally make `classify`, `record-source`, and `record-source-gap` auto-create the dated run directory when missing, using the same layout as `init-run`.

## What Not To Change Yet

- Do not weaken the pass gate. The current no-open-critical/moderate rule worked.
- Do not move runtime artifacts into final reports wholesale. The issue is final-package provenance resolution, not preserving every intermediate file in `reports/`.
- Do not force main-body disclosure of provider/cache mechanics. In this batch, those details were mostly kept in `Data Issues And Discrepancies` or `Sources And Evidence`, which matches `docs/quality-bar.md`.
