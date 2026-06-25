# Market Research Batch Lessons Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert lessons from the INFQ and ECH batch runs into collector, prompt, lint, and ETF-report improvements without weakening the artifact boundary between evidence, final reports, and runtime work.

**Architecture:** Keep fixes incremental. The collector should emit better normalized facts and discrepancies; prompts should require portable final sidecars; lints should catch internal-language leaks and common memo-quality omissions before validation; ETF report guidance should add company-level snapshots when holdings are available. Validation remains a fresh-context judgment step and should not become a replacement researcher.

**Tech Stack:** Python 3 standard library, pytest subprocess tests, Markdown skill/reference files, existing helper scripts under `market-research/shared/scripts/` and `market-research/batch-supervisor/scripts/`.

---

## Files To Change

- Modify: `market-research/shared/scripts/deterministic_research_collector.py`
  - Preserve SEC CIK in identity.
  - Improve ETF/fund classification from provider profile text.
  - Expand SEC companyfacts normalization.
  - Add filed-share market-cap discrepancy checks.
  - Add structured SEC filing-section extraction gap when submissions exist but sections are not emitted.
- Modify: `market-research/shared/scripts/report_language_lint.py`
  - Add stricter main-body internal-language checks.
  - Add JSON-aware checks for drawdown, ETF risk terms, and ETF portfolio-company snapshots.
  - Keep the existing Markdown-only CLI working.
- Modify: `market-research/batch-supervisor/scripts/research_loop.py`
  - Update producer prompts to require copying small validation-facing sidecars into `reports/`.
- Modify: `market-research/researcher/SKILL.md`
  - Clarify that final report bundles should include copied `sources.json`, `run_manifest.json`, and `research_context.json` when present.
- Modify: `market-research/researcher/references/report-template.md`
  - Clarify investor-facing vocabulary, ETF risk checklist, technical drawdown expectation, and `Portfolio Companies Snapshot`.
- Modify: `market-research/researcher/references/etf-research.md`
  - Add ETF holdings selection and company-snapshot requirements.
- Modify: `market-research/verifier/references/verifier-workflow.md`
  - Treat missing final-bundle sidecars as a portability finding when runtime copies are the only source.
  - Treat missing ETF company snapshots as a report-quality finding when holdings are available.
- Test: `tests/test_deterministic_research_collector.py`
  - Add focused unit tests for CIK/index emission, ETF classification, companyfacts fields, filed-share market-cap discrepancies, and endpoint relevance.
- Test: `tests/test_report_language_lint.py`
  - Add JSON-aware report lint tests for drawdown and ETF risk coverage.
- Test: `tests/test_research_loop.py`
  - Add prompt assertions for final sidecar copying.

## Task 1: Preserve SEC CIK And Emit Filing Index

**Files:**
- Modify: `market-research/shared/scripts/deterministic_research_collector.py`
- Test: `tests/test_deterministic_research_collector.py`

- [ ] **Step 1: Write the failing CIK/index test**

Add this test near `test_emit_sec_filings_index_handles_wrapped_submissions`:

```python
def test_build_bundle_preserves_sec_cik_and_emits_filing_index(tmp_path):
    module = load_module()
    cache = tmp_path / "cache"
    module.write_raw(
        cache,
        "INFQ",
        "sec",
        "submissions",
        {},
        {
            "cik": "0002007825",
            "name": "Infleqtion, Inc.",
            "tickers": ["INFQ"],
            "exchanges": ["NYSE"],
            "sic": "7374",
            "filings": {
                "recent": {
                    "accessionNumber": ["0001193125-26-227206"],
                    "form": ["10-Q"],
                    "filingDate": ["2026-05-15"],
                    "reportDate": ["2026-03-31"],
                    "primaryDocument": ["d131935d10q.htm"],
                }
            },
        },
        source_url="https://data.sec.gov/submissions/CIK0002007825.json",
    )

    result = module.build_bundle("INFQ", "2026-06-24", cache, tmp_path / "data", providers=["sec"], asset_type="equity")

    bundle_dir = Path(result["bundle_dir"])
    identity = json.loads((bundle_dir / "normalized" / "identity.json").read_text(encoding="utf-8"))
    index = json.loads((bundle_dir / "normalized" / "sec_filings_index.json").read_text(encoding="utf-8"))
    gaps = json.loads((bundle_dir / "gaps.json").read_text(encoding="utf-8"))["gaps"]
    assert identity["cik"]["value"] == "0002007825"
    assert index["filings"][0]["form"] == "10-Q"
    assert any(gap["field"] == "sec_filing_sections" for gap in gaps)
```

- [ ] **Step 2: Run the focused test and confirm failure**

Run:

```bash
python3 -m pytest tests/test_deterministic_research_collector.py::test_build_bundle_preserves_sec_cik_and_emits_filing_index -q
```

Expected: FAIL because `identity["cik"]` is missing and `sec_filings_index.json` is not emitted from `build_bundle()`.

- [ ] **Step 3: Implement CIK preservation and structured section gap**

In `normalize_identity()`, add CIK preservation inside the SEC submissions branch:

```python
        cik = data.get("cik")
        if cik:
            identity["cik"] = provenance(str(cik).zfill(10), "sec", url, "submissions", raw)
```

In `build_bundle()`, after computing `gaps = default_gaps(...)` and before writing `gaps.json`, append a structured gap if SEC submissions exist but no section file was written:

```python
    sec_sections_path = normalized / "sec_filing_sections.json"
    if sec_submissions_entry and not sec_sections_path.exists():
        gaps.append(
            {
                "field": "sec_filing_sections",
                "status": "unavailable_free_source",
                "attempted_sources": ["sec_submissions"],
                "notes": "SEC submissions were normalized, but deterministic filing-section extraction is not available in this run.",
            }
        )
```

Keep the existing `emit_sec_filings_index()` call, now fed by `identity["cik"]`.

- [ ] **Step 4: Run the focused test and existing SEC index test**

Run:

```bash
python3 -m pytest tests/test_deterministic_research_collector.py::test_build_bundle_preserves_sec_cik_and_emits_filing_index tests/test_deterministic_research_collector.py::test_emit_sec_filings_index_handles_wrapped_submissions -q
```

Expected: both PASS.

## Task 2: Improve ETF Classification And ETF-Relevant Gaps

**Files:**
- Modify: `market-research/shared/scripts/deterministic_research_collector.py`
- Test: `tests/test_deterministic_research_collector.py`

- [ ] **Step 1: Add a failing ETF classification test**

Add:

```python
def test_fmp_etf_name_classifies_as_etf_not_equity(tmp_path):
    module = load_module()
    cache = tmp_path / "cache"
    module.write_raw(
        cache,
        "ECH",
        "fmp",
        "profile",
        {},
        [{"symbol": "ECH", "companyName": "iShares MSCI Chile ETF", "industry": "Asset Management", "exchangeShortName": "BATS", "mktCap": 1043416444}],
        source_url="https://financialmodelingprep.com/stable/profile?symbol=ECH",
    )
    module.write_raw(
        cache,
        "tiingo",
        "prices",
        {"startDate": "2026-06-01", "endDate": "2026-06-25"},
        [{"date": "2026-06-24", "close": 39.35, "adjClose": 39.35, "volume": 575658}],
        source_url="https://api.tiingo.com/tiingo/daily/ECH/prices",
    )

    result = module.build_bundle("ECH", "2026-06-25", cache, tmp_path / "data", providers=["fmp", "tiingo"])

    bundle_dir = Path(result["bundle_dir"])
    identity = json.loads((bundle_dir / "normalized" / "identity.json").read_text(encoding="utf-8"))
    gaps = json.loads((bundle_dir / "gaps.json").read_text(encoding="utf-8"))["gaps"]
    assert identity["asset_type"]["value"] == "etf"
    assert (bundle_dir / "normalized" / "etf_holdings.json").exists()
    assert {gap["field"] for gap in gaps} >= {"etf_holdings", "nav"}
```

- [ ] **Step 2: Run the focused test and confirm failure**

Run:

```bash
python3 -m pytest tests/test_deterministic_research_collector.py::test_fmp_etf_name_classifies_as_etf_not_equity -q
```

Expected: FAIL because FMP profile currently defaults `asset_type` to `equity`.

- [ ] **Step 3: Implement profile-text classification helper**

Add near the provider classification helpers:

```python
def infer_asset_type_from_profile_text(*values: Any) -> str | None:
    text = " ".join(str(value or "") for value in values).lower()
    if any(term in text for term in [" etf", "exchange traded fund", "ishares", "spdr", "index fund"]):
        return "etf"
    if any(term in text for term in [" closed-end fund", "mutual fund", " fund", " trust"]):
        return "fund"
    if any(term in text for term in ["common stock", "ordinary shares", "inc.", "corporation", "corp.", "ltd."]):
        return "equity"
    return None
```

Use it in the FMP branch before defaulting to equity:

```python
            inferred_asset_type = infer_asset_type_from_profile_text(
                data.get("companyName"),
                data.get("industry"),
                data.get("sector"),
                data.get("description"),
            )
            if "asset_type" not in identity and inferred_asset_type:
                identity["asset_type"] = provenance(inferred_asset_type, "fmp", url, "profile", raw)
            if "asset_type" not in identity:
                identity["asset_type"] = provenance("equity", "fmp", url, "profile", raw)
```

- [ ] **Step 4: Run ETF and normalized hygiene tests**

Run:

```bash
python3 -m pytest tests/test_deterministic_research_collector.py::test_fmp_etf_name_classifies_as_etf_not_equity tests/test_normalized_artifact_hygiene.py -q
```

Expected: PASS.

## Task 3: Expand SEC Companyfacts Normalization

**Files:**
- Modify: `market-research/shared/scripts/deterministic_research_collector.py`
- Test: `tests/test_deterministic_research_collector.py`

- [ ] **Step 1: Add a failing companyfacts breadth test**

Add:

```python
def test_sec_companyfacts_promotes_latest_interim_financial_fields(tmp_path):
    module = load_module()
    cache = tmp_path / "cache"
    facts = {
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [{"form": "10-Q", "fp": "Q1", "fy": 2026, "end": "2026-03-31", "filed": "2026-05-15", "val": 9461000}]}},
                "AssetsCurrent": {"units": {"USD": [{"form": "10-Q", "fp": "Q1", "fy": 2026, "end": "2026-03-31", "filed": "2026-05-15", "val": 575000000}]}},
                "Liabilities": {"units": {"USD": [{"form": "10-Q", "fp": "Q1", "fy": 2026, "end": "2026-03-31", "filed": "2026-05-15", "val": 27356000}]}},
                "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": [{"form": "10-Q", "fp": "Q1", "fy": 2026, "end": "2026-03-31", "filed": "2026-05-15", "val": -19159000}]}},
                "CommonStocksIncludingAdditionalPaidInCapital": {"units": {"USD": [{"form": "10-Q", "fp": "Q1", "fy": 2026, "end": "2026-03-31", "filed": "2026-05-15", "val": 660000000}]}},
                "EntityCommonStockSharesOutstanding": {"units": {"shares": [{"form": "10-Q", "fp": "Q1", "fy": 2026, "end": "2026-05-12", "filed": "2026-05-15", "val": 218196891}]}},
            }
        }
    }
    module.write_raw(cache, "INFQ", "sec", "companyfacts", {}, facts, source_url="https://data.sec.gov/api/xbrl/companyfacts/CIK0002007825.json")

    fundamentals = module.normalize_equity_fundamentals(cache, "INFQ", providers=["sec"])

    assert fundamentals["revenue"]["value"]["value"] == 9461000
    assert fundamentals["assets_current"]["value"]["value"] == 575000000
    assert fundamentals["total_liabilities"]["value"]["value"] == 27356000
    assert fundamentals["operating_cash_flow"]["value"]["value"] == -19159000
    assert fundamentals["shares_outstanding"]["value"]["value"] == 218196891
```

- [ ] **Step 2: Run the focused test and confirm failure**

Run:

```bash
python3 -m pytest tests/test_deterministic_research_collector.py::test_sec_companyfacts_promotes_latest_interim_financial_fields -q
```

Expected: FAIL because only a narrow annual fact set is normalized.

- [ ] **Step 3: Add a latest companyfacts picker by unit**

Replace or extend `latest_companyfacts_usd_fact()` with a more general helper:

```python
def latest_companyfacts_fact(companyfacts: dict[str, Any], names: list[str], unit: str) -> dict[str, Any] | None:
    facts = nested_get(companyfacts, "facts", "us-gaap")
    if not isinstance(facts, dict):
        return None
    candidates: list[dict[str, Any]] = []
    for name in names:
        values = nested_get(facts, name, "units", unit)
        if not isinstance(values, list):
            continue
        for item in values:
            if isinstance(item, dict) and item.get("form") in {"10-K", "10-Q"} and "val" in item:
                candidates.append({**item, "_tag": name})
    if not candidates:
        return None
    item = sorted(candidates, key=lambda row: (str(row.get("end") or ""), str(row.get("filed") or ""), str(row.get("form") or "")))[-1]
    return {
        "tag": item.get("_tag"),
        "value": item.get("val"),
        "fy": item.get("fy"),
        "fp": item.get("fp"),
        "period_end": item.get("end"),
        "filed": item.get("filed"),
        "form": item.get("form"),
        "unit": unit,
    }
```

Keep `latest_companyfacts_usd_fact()` as a wrapper for compatibility:

```python
def latest_companyfacts_usd_fact(companyfacts: dict[str, Any], names: list[str]) -> dict[str, Any] | None:
    return latest_companyfacts_fact(companyfacts, names, "USD")
```

- [ ] **Step 4: Promote additional SEC fields**

Inside `normalize_equity_fundamentals()`, replace the two hard-coded SEC lookups with:

```python
        sec_fields = {
            "revenue": (["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"], "USD"),
            "gross_profit": (["GrossProfit"], "USD"),
            "cost_of_revenue": (["CostOfRevenue", "CostOfGoodsAndServicesSold"], "USD"),
            "net_income": (["NetIncomeLoss", "ProfitLoss"], "USD"),
            "assets_current": (["AssetsCurrent"], "USD"),
            "cash_and_equivalents": (["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"], "USD"),
            "total_assets": (["Assets"], "USD"),
            "total_liabilities": (["Liabilities"], "USD"),
            "operating_cash_flow": (["NetCashProvidedByUsedInOperatingActivities"], "USD"),
            "stockholders_equity": (["StockholdersEquity", "CommonStocksIncludingAdditionalPaidInCapital"], "USD"),
            "shares_outstanding": (["EntityCommonStockSharesOutstanding"], "shares"),
        }
        for out_key, (tags, unit) in sec_fields.items():
            fact = latest_companyfacts_fact(data, tags, unit)
            if fact:
                fundamentals[out_key] = provenance(fact, "sec", url, "companyfacts", raw, unit=unit, as_of=fact.get("period_end"))
```

- [ ] **Step 5: Run companyfacts tests**

Run:

```bash
python3 -m pytest tests/test_deterministic_research_collector.py::test_sec_companyfacts_promotes_latest_interim_financial_fields tests/test_deterministic_research_collector.py::test_sec_companyfacts_promote_equity_fundamentals_without_extra_provider -q
```

Expected: PASS.

## Task 4: Add Filed-Share Market-Cap Reconciliation

**Files:**
- Modify: `market-research/shared/scripts/deterministic_research_collector.py`
- Test: `tests/test_deterministic_research_collector.py`

- [ ] **Step 1: Add a failing discrepancy test**

Add:

```python
def test_market_cap_discrepancy_uses_filed_shares_and_latest_close():
    module = load_module()
    snapshot = {
        "latest_close": {"value": 14.10, "provider": "tiingo", "raw_path": "raw/tiingo/prices.json"},
        "market_capitalization": {"value": 2446699144, "provider": "fmp", "raw_path": "raw/fmp/profile.json"},
    }
    fundamentals = {
        "shares_outstanding": {
            "value": {"value": 218196891, "period_end": "2026-05-12", "filed": "2026-05-15", "unit": "shares"},
            "provider": "sec",
            "raw_path": "raw/sec/companyfacts.json",
        }
    }

    discrepancies = module.discrepancies_from_snapshot(snapshot, fundamentals=fundamentals)

    assert any(item["comparison"] == "filed_shares_times_latest_close" for item in discrepancies)
```

- [ ] **Step 2: Run the focused test and confirm failure**

Run:

```bash
python3 -m pytest tests/test_deterministic_research_collector.py::test_market_cap_discrepancy_uses_filed_shares_and_latest_close -q
```

Expected: FAIL because `discrepancies_from_snapshot()` does not accept fundamentals yet.

- [ ] **Step 3: Extend discrepancy calculation**

Change the signature and add the filed-share check:

```python
def discrepancies_from_snapshot(snapshot: dict[str, Any], threshold: float = 0.15, fundamentals: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    ...
    latest_close = normalized_value(snapshot, "latest_close")
    shares_point = (fundamentals or {}).get("shares_outstanding")
    shares_value = normalized_value({"shares_outstanding": shares_point}, "shares_outstanding") if shares_point else None
    if isinstance(shares_value, dict):
        shares_value = shares_value.get("value")
    if primary_value is not None and latest_close and shares_value:
        implied = float(latest_close) * float(shares_value)
        relative_difference = abs(primary_value - implied) / abs(primary_value)
        if relative_difference >= threshold:
            discrepancies.append(
                {
                    "field_path": "market_snapshot.market_capitalization",
                    "comparison": "filed_shares_times_latest_close",
                    "severity": "material",
                    "primary_provider": point.get("provider"),
                    "primary_value": primary_value,
                    "alternate_provider": "sec_filed_shares",
                    "alternate_value": round(implied, 2),
                    "relative_difference": round(relative_difference, 6),
                    "impact": "valuation_multiples_require_range_or_caveat",
                    "primary_raw_path": point.get("raw_path"),
                    "alternate_raw_path": shares_point.get("raw_path"),
                }
            )
```

Update the caller in `build_bundle()` to pass `fundamentals`.

- [ ] **Step 4: Run discrepancy tests**

Run:

```bash
python3 -m pytest tests/test_deterministic_research_collector.py::test_market_cap_discrepancy_flags_material_alternate tests/test_deterministic_research_collector.py::test_market_cap_discrepancy_uses_filed_shares_and_latest_close -q
```

Expected: PASS.

## Task 5: Require Portable Final Report Sidecars

**Files:**
- Modify: `market-research/batch-supervisor/scripts/research_loop.py`
- Modify: `market-research/researcher/SKILL.md`
- Modify: `market-research/verifier/references/verifier-workflow.md`
- Test: `tests/test_research_loop.py`

- [ ] **Step 1: Add a failing prompt test**

Add to `tests/test_research_loop.py`:

```python
def test_producer_prompt_requires_copying_final_sidecars_to_reports(tmp_path):
    out_dir = tmp_path / "prompts"

    result = run_harness("write-prompts", "INFQ", "--run-dir", "runtime/batch/INFQ/2026-06-24", "--output-dir", str(out_dir))

    assert result.returncode == 0, result.stderr
    producer = Path(json.loads(result.stdout)["producer_initial_prompt"]).read_text(encoding="utf-8")
    assert "Copy validation-facing sidecars into `reports/INFQ/2026-06-24`" in producer
    assert "`sources.json`, `run_manifest.json`, and `research_context.json` when present" in producer
```

- [ ] **Step 2: Run the focused test and confirm failure**

Run:

```bash
python3 -m pytest tests/test_research_loop.py::test_producer_prompt_requires_copying_final_sidecars_to_reports -q
```

Expected: FAIL because the prompt currently asks only for report Markdown/JSON paths and runtime issue files.

- [ ] **Step 3: Update producer prompt**

In `producer_initial_prompt()`, add this line after the final report directory instruction:

```python
            f"Copy validation-facing sidecars into `{report_dir}`: `sources.json`, `run_manifest.json`, and `research_context.json` when present; keep bulky source bundles, prompts, logs, and downloads under `{runtime_dir}`.",
```

- [ ] **Step 4: Update researcher and verifier docs**

In `market-research/researcher/SKILL.md`, add to `Final Artifacts` or `Report Contract`:

```markdown
When procedural runtime sidecars exist, copy small validation-facing sidecars into the final report directory: `sources.json`, `run_manifest.json`, and `research_context.json`. Do not copy bulky source bundles, prompts, logs, downloads, or transient notes into `reports/`.
```

In `market-research/verifier/references/verifier-workflow.md`, add under `Evidence Review`:

```markdown
If a final report references `sources.json`, `run_manifest.json`, or `research_context.json` only under `runtime/`, treat this as a portability finding. It is usually minor when the runtime files exist locally, but it should be reported so final `reports/` bundles can stand on their own.
```

- [ ] **Step 5: Run prompt tests**

Run:

```bash
python3 -m pytest tests/test_research_loop.py::test_producer_prompt_requires_copying_final_sidecars_to_reports tests/test_research_loop.py::test_loop_prompts_separate_data_reports_and_runtime -q
```

Expected: PASS.

## Task 6: Add JSON-Aware Report Quality Lints

**Files:**
- Modify: `market-research/shared/scripts/report_language_lint.py`
- Modify: `market-research/researcher/references/report-template.md`
- Test: `tests/test_report_language_lint.py`

- [ ] **Step 1: Add failing lint tests**

Add:

```python
def test_report_lint_flags_missing_drawdown_when_json_has_drawdown(tmp_path):
    module = load_module()
    report = """# ECH Research

## Market Snapshot And Technical Analysis

Trend, moving averages, volume, volatility, support, and resistance are discussed.
"""
    report_json = {
        "technical_analysis": {
            "max_drawdown_available": -0.370986
        }
    }

    findings = module.lint_report_quality(report, report_json)

    assert any(finding.get("id") == "technical-analysis-missing-drawdown" for finding in findings)


def test_report_lint_flags_etf_risk_checklist_gaps():
    module = load_module()
    report = """# ECH Research

## Risks And Invalidation Points

The main risks are country, currency, concentration, premium/discount, tracking, tax, withholding, liquidity, and closure risk.
"""
    report_json = {"security_type": "etf"}

    findings = module.lint_report_quality(report, report_json)

    assert any(finding.get("id") == "etf-risk-missing-creation-redemption" for finding in findings)
    assert any(finding.get("id") == "etf-risk-missing-securities-lending" for finding in findings)


def test_report_lint_flags_internal_language_before_evidence_sections():
    module = load_module()
    report = """# ECH Research

## Bottom Line

The latest deterministic close came from the deterministic bundle.

## Sources And Evidence

The deterministic bundle is listed for auditability.
"""

    findings = module.lint_report_quality(report, {})

    assert any(finding.get("id") == "main-body-internal-language" for finding in findings)


def test_report_lint_requires_etf_portfolio_companies_snapshot_when_holdings_exist():
    module = load_module()
    report = """# ECH Research

## Risks And Invalidation Points

Creation/redemption, authorized participant, securities lending, premium/discount, tracking, tax, withholding, liquidity, closure, and concentration risks are discussed.
"""
    report_json = {
        "security_type": "etf",
        "holdings": [{"name": "Banco de Chile", "weight": 0.08}],
    }

    findings = module.lint_report_quality(report, report_json)

    assert any(finding.get("id") == "etf-missing-portfolio-companies-snapshot" for finding in findings)
```

- [ ] **Step 2: Run the lint tests and confirm failure**

Run:

```bash
python3 -m pytest tests/test_report_language_lint.py::test_report_lint_flags_missing_drawdown_when_json_has_drawdown tests/test_report_language_lint.py::test_report_lint_flags_etf_risk_checklist_gaps -q
```

Expected: FAIL because `lint_report_quality()` and ETF snapshot checks do not exist.

- [ ] **Step 3: Implement `lint_report_quality()`**

Add:

```python
def has_json_drawdown(report_json: dict[str, Any] | None) -> bool:
    if not isinstance(report_json, dict):
        return False
    technical = report_json.get("technical_analysis") or report_json.get("technical_snapshot") or {}
    if isinstance(technical, dict):
        return any("drawdown" in str(key).lower() and value not in (None, "", "Data not available") for key, value in technical.items())
    return False


def lint_report_quality(text: str, report_json: dict[str, Any] | None = None) -> list[dict[str, str]]:
    findings = lint_report_language(text) + lint_report_structure(text)
    sections = section_map(text)
    technical = sections.get("market snapshot and technical analysis", "")
    if technical and has_json_drawdown(report_json) and "drawdown" not in technical.lower():
        findings.append(
            {
                "severity": "minor",
                "id": "technical-analysis-missing-drawdown",
                "section": "market snapshot and technical analysis",
                "message": "Technical analysis should interpret drawdown when deterministic or report JSON drawdown data exists.",
            }
        )
    risks = sections.get("risks and invalidation points", "")
    security_type = str((report_json or {}).get("security_type", "")).lower()
    if security_type == "etf" and risks:
        if "creation" not in risks.lower() and "redemption" not in risks.lower() and "authorized participant" not in risks.lower():
            findings.append(
                {
                    "severity": "minor",
                    "id": "etf-risk-missing-creation-redemption",
                    "section": "risks and invalidation points",
                    "message": "ETF risks should address authorized participant and creation/redemption mechanics when material.",
                }
            )
        if "securities lending" not in risks.lower() and "securities-lending" not in risks.lower():
            findings.append(
                {
                    "severity": "minor",
                    "id": "etf-risk-missing-securities-lending",
                    "section": "risks and invalidation points",
                    "message": "ETF risks should address securities-lending risk or state why it was not material/found.",
                }
            )
    if security_type == "etf" and has_holdings(report_json) and "portfolio companies snapshot" not in sections:
        findings.append(
            {
                "severity": "minor",
                "id": "etf-missing-portfolio-companies-snapshot",
                "section": "portfolio companies snapshot",
                "message": "ETF reports should include a Portfolio Companies Snapshot when holdings are available.",
            }
        )
    return findings
```

Add helper:

```python
def has_holdings(report_json: dict[str, Any] | None) -> bool:
    if not isinstance(report_json, dict):
        return False
    candidates = [
        report_json.get("holdings"),
        report_json.get("portfolio_holdings"),
        report_json.get("etf_holdings"),
    ]
    for candidate in candidates:
        if isinstance(candidate, list) and candidate:
            return True
        if isinstance(candidate, dict) and candidate.get("holdings"):
            return True
    return False
```

Add imports:

```python
from typing import Any
```

Update `main()` to load an optional JSON sidecar:

```python
    parser.add_argument("--report-json", help="Optional report JSON sidecar for JSON-aware quality checks.")
```

and:

```python
    report_json = json.loads(Path(args.report_json).read_text(encoding="utf-8")) if args.report_json else None
    findings = lint_report_quality(text, report_json)
```

- [ ] **Step 4: Update report template guidance**

In `market-research/researcher/references/report-template.md`, add:

```markdown
Use investor-facing language in the main report. Avoid workflow terms such as deterministic, bundle, artifact, normalized, raw, runtime, cache, provider, and local file paths before `Data Issues And Discrepancies`.

When calculated technical data includes max drawdown, discuss what the drawdown says about risk, volatility, or position sizing. For ETFs, the risk section should explicitly address authorized participants/creation-redemption, securities lending, tracking, premium/discount, tax or withholding drag, liquidity, closure/AUM risk, and concentration where material; if a source does not disclose a topic, state that in investor terms in `Data Issues And Discrepancies` or the JSON sidecar.
```

In `market-research/researcher/references/etf-research.md`, add:

```markdown
When holdings are available, include `Portfolio Companies Snapshot`. If the ETF has 25 or fewer holdings, cover all holdings; otherwise cover the top 25 by portfolio weight. Keep each row compact: company/ticker, weight, sector or industry, what it does, quick outlook, and quick price/technical context when reliable public/free data is available. Follow with a synthesis paragraph about what these holdings imply for concentration, cyclicality, upside drivers, risks, and monitoring.
```

- [ ] **Step 5: Run report lint tests**

Run:

```bash
python3 -m pytest tests/test_report_language_lint.py -q
```

Expected: PASS.

## Task 8: Regenerate Sample Reports And Compare Output

**Files:**
- Generated outputs under `runtime/`, `data/`, and `reports/` only.

- [ ] **Step 1: Run the same-symbol supervised batch**

Run:

```bash
python3 market-research/batch-supervisor/scripts/research_loop.py run-batch INFQ ECH --run-root runtime/market-research-batch-20260625-rerun-1 --as-of 2026-06-25 --max-remediation-loops 3
```

Expected: batch completes with no open critical or moderate validation issues.

- [ ] **Step 2: Compare old and new reports for internal language**

Run:

```bash
python3 market-research/shared/scripts/report_language_lint.py reports/INFQ/2026-06-25/INFQ-research.md --report-json reports/INFQ/2026-06-25/INFQ-research.json
python3 market-research/shared/scripts/report_language_lint.py reports/ECH/2026-06-25/ECH-research.md --report-json reports/ECH/2026-06-25/ECH-research.json
```

Expected: no main-body internal-language findings. Any remaining findings should be either accepted evidence-section language or real report-quality issues to fix.

- [ ] **Step 3: Inspect ETF holdings section**

Run:

```bash
rg -n "Portfolio Companies Snapshot|Banco|Sociedad|LATAM|holdings" reports/ECH/2026-06-25/ECH-research.md
```

Expected: ECH report includes `Portfolio Companies Snapshot` covering all holdings when 25 or fewer are available, or explains unavailable company-level data in investor terms.

- [ ] **Step 4: Repeat improvement cycles if needed**

If validation or report-lint findings show recurring issues, repeat implementation and rerun the same-symbol batch. Stop after at most three full rerun cycles.

## Task 7: Verification And Regression Sweep

**Files:**
- No code changes beyond prior tasks.

- [ ] **Step 1: Run focused helper tests**

Run:

```bash
python3 -m pytest tests/test_deterministic_research_collector.py tests/test_report_language_lint.py tests/test_research_loop.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full test suite**

Run:

```bash
python3 -m pytest tests -q
```

Expected: PASS.

- [ ] **Step 3: Inspect generated artifacts are not accidentally staged**

Run:

```bash
git status --short
```

Expected: only intentional source, test, doc, and plan changes appear. No generated `data/`, `reports/`, or `runtime/` output should be staged or committed unless explicitly requested.

## Risks

- ETF classification by name can produce false positives for operating companies with "trust" or "fund" in their legal name. Mitigation: use conservative terms, preserve provider provenance, and allow explicit `--asset-type` override.
- Companyfacts tags vary widely by issuer. Mitigation: add fields incrementally and preserve tag/unit metadata so researchers can reject low-quality or wrong-period facts.
- Filed-share market-cap reconciliation can compare a recent close with a dated share count. Mitigation: mark it as a discrepancy/caveat, not as a replacement for market cap.
- Report lint should not replace verifier judgment. Keep new lints minor and focused on repeated omissions observed in these runs.
