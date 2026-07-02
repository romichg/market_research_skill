# Market Research ETF And Source Registry Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make ETF deterministic bundles and final report source packages reliable enough that future ETF batches do not need manual source-registry remediation.

**Architecture:** Add narrowly scoped shared helpers around existing scripts instead of changing artifact roots. The deterministic collector will own ETF classification and normalized ETF outputs; the report/source reconciliation helper will own final source ID resolution and path portability; validation/lint will enforce the new contracts.

**Tech Stack:** Python 3 standard library, existing CLI helper scripts, pytest subprocess tests, Markdown skill references.

---

## Evidence Base

- Batch summary: `runtime/market-research-batch-20260701/research-loop-summary.json`
- Loop issue: `runtime/market-research-batch-20260701/loop-skill-issues.md`
- ETF classification and source issues:
  - `runtime/market-research-batch-20260701/QTUM/2026-07-01/QTUM-market-research-issues.md`
  - `runtime/market-research-batch-20260701/QTUP/2026-07-01/QTUP-market-research-issues.md`
  - `runtime/market-research-batch-20260701/WQTM/2026-07-01/WQTM-market-research-issues.md`
- Final validations:
  - `reports/QTUM/2026-07-01/QTUM-validation.md`
  - `reports/QTUP/2026-07-01/QTUP-validation.md`
  - `reports/WQTM/2026-07-01/WQTM-validation.md`
- Current code touchpoints:
  - `market-research/shared/scripts/deterministic_research_collector.py`
  - `market-research/shared/scripts/deterministic_data_usage.py`
  - `market-research/shared/scripts/validate_market_research.py`
  - `market-research/shared/scripts/report_language_lint.py`
  - `market-research/batch-supervisor/scripts/research_loop.py`
  - `market-research/shared/scripts/procedural_source_helper.py`
  - `market-research/shared/scripts/md-to-pdf.sh`

## File Structure

- Modify `market-research/shared/scripts/deterministic_research_collector.py`: ETF asset-type evidence ranking, ETF profile normalization, ETF holdings normalization from available raw payloads.
- Create `market-research/shared/scripts/source_registry_reconcile.py`: reusable source-ID extraction, deterministic source registration, and report-local path rewriting.
- Modify `market-research/batch-supervisor/scripts/research_loop.py`: call the reconciliation/path rewrite helper during runtime-to-report sync and strengthen remediation prompt wording.
- Modify `market-research/shared/scripts/validate_market_research.py`: include source-registry reconciliation findings and better final-report input hints.
- Modify `market-research/shared/scripts/deterministic_data_usage.py`: detect boilerplate/repeated deterministic usage rationales.
- Modify `market-research/shared/scripts/report_language_lint.py`: flag runtime-local paths in final report evidence sections when report-local source copies exist.
- Modify `market-research/shared/scripts/procedural_source_helper.py`: make dependent commands auto-initialize dated run directories or fail with a clearer message.
- Modify `market-research/shared/scripts/md-to-pdf.sh`: emit machine-readable PDF status.
- Modify references:
  - `market-research/researcher/references/etf-research.md`
  - `market-research/researcher/references/researcher-workflow.md`
  - `market-research/verifier/references/verifier-workflow.md`
  - `market-research/batch-supervisor/references/supervisor-workflow.md`
  - `docs/quality-bar.md`
- Add tests:
  - `tests/test_deterministic_etf_normalization.py`
  - `tests/test_source_registry_reconcile.py`
  - Extend `tests/test_research_loop.py`
  - Extend `tests/test_deterministic_data_usage.py`
  - Extend `tests/test_report_language_lint.py`
  - Extend `tests/test_procedural_source_helper.py`

### Task 1: ETF Asset-Type Resolver

**Files:**
- Modify: `market-research/shared/scripts/deterministic_research_collector.py`
- Test: `tests/test_deterministic_etf_normalization.py`

- [ ] **Step 1: Add a failing test for FMP ETF evidence overriding generic equity**

Create `tests/test_deterministic_etf_normalization.py` with a fixture that writes raw SEC submissions implying generic `equity` and raw FMP profile containing `{"symbol": "QTUM", "companyName": "Defiance Quantum ETF", "isEtf": true}`. Assert `normalized/identity.json` has `asset_type.value == "etf"` and an explanation field such as `selection_reason` or `alternates`.

Run: `python3 -m pytest tests/test_deterministic_etf_normalization.py::test_fmp_is_etf_overrides_generic_equity -v`

Expected: FAIL because current `normalize_identity()` does not override an existing generic asset type.

- [ ] **Step 2: Implement ranked asset-type evidence**

In `deterministic_research_collector.py`, add helper functions near `normalize_identity()`:

```python
def asset_type_signal(value: str, provider: str, url: str, endpoint: str, raw: Path, strength: int, reason: str) -> dict[str, Any]:
    point = provenance(value, provider, url, endpoint, raw)
    point["strength"] = strength
    point["reason"] = reason
    return point

def choose_asset_type(signals: list[dict[str, Any]]) -> dict[str, Any]:
    if not signals:
        return provenance("unknown", "deterministic_classifier", "", "classification", Path(""), status="gap")
    return sorted(signals, key=lambda item: item.get("strength", 0), reverse=True)[0]
```

Use signals from SEC forms, EOD type/category, FMP `isEtf`, FMP name tokens, Twelve Data type text, and Alpha Vantage ETF profile. Assign explicit ETF flags higher strength than generic SEC equity.

- [ ] **Step 3: Preserve alternates**

After selecting the winning `asset_type`, add lower-ranked signals under `identity["asset_type"]["alternates"]`. Include provider, value, strength, and reason. Do not include secrets or raw payload bodies.

- [ ] **Step 4: Run the focused test**

Run: `python3 -m pytest tests/test_deterministic_etf_normalization.py::test_fmp_is_etf_overrides_generic_equity -v`

Expected: PASS.

### Task 2: ETF Profile And Holdings Normalization

**Files:**
- Modify: `market-research/shared/scripts/deterministic_research_collector.py`
- Test: `tests/test_deterministic_etf_normalization.py`

- [ ] **Step 1: Add failing tests for Alpha Vantage ETF profile output**

Add tests that create raw Alpha Vantage `ETF_PROFILE` payloads with fund name, net assets, expense ratio, dividend yield, and holdings. Build a bundle with `asset_type=auto`. Assert:

- `normalized/etf_profile.json` exists for ETF output.
- `normalized/etf_holdings.json` exists and includes top holdings with weights.
- `deterministic_data_usage.json` includes required/review ETF fields when profile or holdings values are `ok`.

Run: `python3 -m pytest tests/test_deterministic_etf_normalization.py -v`

Expected: FAIL because the collector currently only emits `etf_holdings.json` for selected ETF/fund asset types and does not normalize Alpha Vantage ETF profile into ETF profile/holdings files.

- [ ] **Step 2: Add ETF profile normalizer**

Implement `normalize_etf_profile(cache_root, symbol, providers, endpoint_plan)` in `deterministic_research_collector.py`. Read Alpha Vantage `etf_profile`, FMP `etf_holdings`, and any existing free ETF profile evidence. Return DataPoint-style fields for fund name, net assets/AUM, NAV if present, expense ratio, dividend/SEC yield if present, benchmark if present, and holdings count if present.

- [ ] **Step 3: Expand ETF holdings normalizer**

Update `normalize_etf_holdings()` so Alpha Vantage ETF holdings are accepted when FMP ETF holdings are unavailable or plan-gated. Preserve provider/source URL/raw path provenance on each holding row or on the holdings collection.

- [ ] **Step 4: Emit ETF files when ETF signals exist**

In `build_bundle()`, write `normalized/etf_profile.json` and `normalized/etf_holdings.json` when selected `asset_type` is `etf` or `fund`. Write structured unavailable JSON with `status: "unavailable"` and `gaps_recorded: true` only when no usable ETF payload exists.

- [ ] **Step 5: Run focused and hygiene tests**

Run:

```bash
python3 -m pytest tests/test_deterministic_etf_normalization.py tests/test_normalized_artifact_hygiene.py -v
```

Expected: PASS.

### Task 3: Source Registry Reconciliation Helper

**Files:**
- Create: `market-research/shared/scripts/source_registry_reconcile.py`
- Modify: `market-research/shared/scripts/validate_market_research.py`
- Test: `tests/test_source_registry_reconcile.py`

- [ ] **Step 1: Add failing tests for missing deterministic source IDs**

Create report fixtures where Markdown cites `det_prices_daily` and JSON material claims cite `det_technical_signals`, but `reports/EWW/2026-07-01/sources.json` lacks those IDs. Include deterministic files under `data/EWW/2026-07-01/normalized/`.

Assert the new helper reports missing IDs and can write deterministic source records pointing to normalized artifacts.

- [ ] **Step 2: Implement source-ID extraction**

Implement pure functions:

```python
def source_ids_from_markdown(text: str) -> set[str]:
    ...

def source_ids_from_report_json(report: dict[str, Any]) -> set[str]:
    ...
```

Cover source IDs in Markdown tables, bracketed source references, `material_claims[*].source_id`, `source_ids`, `source_ids_cited`, risks, catalysts, source coverage, and calculation audit input aliases.

- [ ] **Step 3: Implement deterministic source registration**

Map accepted deterministic aliases to normalized artifacts:

- `det_market_snapshot`, `deterministic_market_snapshot` -> `normalized/market_snapshot.json`
- `det_technical_signals`, `deterministic_technical_signals` -> `normalized/technical_signals.json`
- `det_prices_daily`, `deterministic_prices_daily`, `market_prices` -> `normalized/prices_daily.json`
- `det_news`, `deterministic_news` -> `normalized/news.json`
- `deterministic_manifest` -> `manifest.json`, `source_manifest.json`, and `gaps.json`

Each generated source record should include source ID, title, kind, local artifact path, SHA-256, size, source date or as-of date, confidence, and notes pointing validators to field-level provenance inside the normalized artifact and `source_manifest.json`.

- [ ] **Step 4: Add CLI modes**

Support:

```bash
python3 market-research/shared/scripts/source_registry_reconcile.py check reports/EWW/2026-07-01 --data-dir data/EWW/2026-07-01
python3 market-research/shared/scripts/source_registry_reconcile.py fix reports/EWW/2026-07-01 --data-dir data/EWW/2026-07-01
```

`check` exits non-zero on missing IDs. `fix` updates only `sources.json` and prints JSON with added IDs.

- [ ] **Step 5: Surface findings in validation scaffold**

Import the helper from `validate_market_research.py`. Add source-registry findings to the scaffold JSON and Markdown. Missing cited source IDs are moderate when material claims depend on them, minor when only the evidence appendix references them.

- [ ] **Step 6: Run tests**

Run:

```bash
python3 -m pytest tests/test_source_registry_reconcile.py tests/test_research_loop.py -v
```

Expected: PASS.

### Task 4: Report-Local Source Bundle Path Rewriting

**Files:**
- Modify: `market-research/batch-supervisor/scripts/research_loop.py`
- Modify: `market-research/shared/scripts/source_registry_reconcile.py`
- Modify: `market-research/shared/scripts/report_language_lint.py`
- Test: `tests/test_research_loop.py`
- Test: `tests/test_report_language_lint.py`

- [ ] **Step 1: Add failing sync test**

In `tests/test_research_loop.py`, create a runtime `sources.json` with `local_artifact` under `runtime/market-research-batch-20260701/QTUP/2026-07-01/source_bundle/example.pdf` and a report output dir. Call `sync_runtime_sources_to_report()`. Assert copied `reports/QTUP/2026-07-01/sources.json` points to `reports/QTUP/2026-07-01/source_bundle/example.pdf`.

- [ ] **Step 2: Implement path rewriting**

Update `sync_runtime_sources_to_report()` to copy `source_bundle/` before writing final `sources.json`. Rewrite any `local_artifact` under the runtime source bundle to the equivalent report-local path when the report-local file exists.

- [ ] **Step 3: Add final-report lint**

In `report_language_lint.py`, flag `runtime/` paths in `Sources And Evidence` as minor final-package findings when a report-local `source_bundle/` path exists. Keep allowing `data/` deterministic paths in `Sources And Evidence`.

- [ ] **Step 4: Run tests**

Run:

```bash
python3 -m pytest tests/test_research_loop.py tests/test_report_language_lint.py -v
```

Expected: PASS.

### Task 5: Deterministic Usage Rationale Quality

**Files:**
- Modify: `market-research/shared/scripts/deterministic_data_usage.py`
- Modify: `market-research/shared/scripts/validate_market_research.py`
- Test: `tests/test_deterministic_data_usage.py`

- [ ] **Step 1: Add failing boilerplate-rationale test**

Add a test with three required/review entries whose rationales only vary by field path and repeat `was used to anchor market, liquidity, performance, or technical context`. Assert the audit returns a finding such as `boilerplate_rationale`.

- [ ] **Step 2: Implement heuristic**

Normalize rationales by lowercasing, removing field paths and symbols, and comparing repeated phrases. Also flag rationales that do not include either the field name, field value, or a specific investor relevance phrase.

- [ ] **Step 3: Wire into validation output**

Add rationale-quality findings to deterministic scaffold output. Classify repeated boilerplate as minor by default and moderate when the field is required and the disposition is `used` without specific value relevance.

- [ ] **Step 4: Run tests**

Run:

```bash
python3 -m pytest tests/test_deterministic_data_usage.py -v
```

Expected: PASS.

### Task 6: PDF Status And Validator CLI Ergonomics

**Files:**
- Modify: `market-research/shared/scripts/md-to-pdf.sh`
- Modify: `market-research/shared/scripts/validate_market_research.py`
- Test: add or extend relevant tests under `tests/`

- [ ] **Step 1: Add PDF helper status test**

Add a test that runs `md-to-pdf.sh --help` and, if feasible without TeX, a fixture report with `PATH` adjusted so `pandoc` is unavailable. Assert stdout includes machine-readable status or a status file is written with `generated: false`.

- [ ] **Step 2: Emit PDF status**

Update `md-to-pdf.sh` to print a final JSON line with `input`, `output`, `generated`, and `reason`. Keep the script non-blocking for missing optional tooling unless callers opt into strict mode later.

- [ ] **Step 3: Add validator input hint test**

Add a test where `validate_market_research.py data/EWW/2026-07-01 --report-md reports/EWW/2026-07-01/EWW-research.md --report-json reports/EWW/2026-07-01/EWW-research.json` fails with a message that names the canonical report-dir invocation.

- [ ] **Step 4: Implement clearer message**

Update the error path around `FINAL_REPORT_LOCATION_MESSAGE` to include:

```text
For final report validation, pass reports/SYMBOL/YYYY-MM-DD as run_dir. Use data/SYMBOL/YYYY-MM-DD only for deterministic scaffold lint.
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
python3 -m pytest tests -k 'pdf or validate_market_research or validator' -v
```

Expected: PASS.

### Task 7: Procedural Helper Dependency Guard

**Files:**
- Modify: `market-research/shared/scripts/procedural_source_helper.py`
- Modify: `market-research/researcher/references/researcher-workflow.md`
- Test: `tests/test_procedural_source_helper.py`

- [ ] **Step 1: Add failing classify-before-init test**

Call `procedural_source_helper.py classify WQTM --output-root TMP --as-of 2026-07-01 --security-type etf` without calling `init-run` first. Decide desired behavior: auto-create the run directory and manifest using the same layout as `init-run`.

- [ ] **Step 2: Implement auto-initialization**

Centralize dated run-dir creation so `classify`, `record-source`, `record-source-gap`, and `record-gap-fill` call the same initializer when the manifest is missing.

- [ ] **Step 3: Update workflow docs**

In `researcher-workflow.md`, keep `init-run` as the recommended first step but state that mutating helper commands auto-create the dated runtime directory when needed.

- [ ] **Step 4: Run helper tests**

Run:

```bash
python3 -m pytest tests/test_procedural_source_helper.py -v
```

Expected: PASS.

## Final Verification

Run:

```bash
python3 -m pytest tests
python3 market-research/shared/scripts/deterministic_research_collector.py --help
python3 market-research/shared/scripts/validate_market_research.py --help
python3 market-research/batch-supervisor/scripts/research_loop.py --help
bash market-research/shared/scripts/md-to-pdf.sh --help
git diff --check
```

Expected:

- All pytest tests pass.
- Helper CLIs print help successfully.
- `git diff --check` reports no whitespace errors.

## Risks

- ETF classification override can misclassify operating companies whose names include "fund" or "ETF" incidentally. Mitigation: only give high strength to explicit structured flags or ETF endpoint payloads; name-token evidence should be lower strength.
- Source-ID extraction can over-match ordinary bracketed text. Mitigation: restrict auto-registration to known deterministic aliases and IDs already present in JSON source fields.
- Rewriting `local_artifact` paths can hide a failed copy. Mitigation: rewrite only when the report-local file exists and checksum or size matches.
- PDF status JSON can break callers that parse the last stdout line as human text. Mitigation: append, do not replace, existing human messages and document the machine-readable line.
