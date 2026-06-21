# Market Research Quality Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the quality gaps found in the DPC, QBIT, and QUBT research runs by improving deterministic provider usage, bundle hygiene, SEC ticker caching, technical analysis coverage, report language, and validation strength.

**Architecture:** Keep the existing `market-research/` layout. Add tests first around provider planning, bundle raw-copy behavior, normalized artifact emission, report-language linting, and technical-signal fields. Then update the deterministic collector, validator, and researcher guidance so future runs produce richer, cleaner, more reproducible artifacts with less procedural patching.

**Tech Stack:** Python 3 standard library CLI helpers, pytest, JSON/Markdown artifacts, existing provider APIs.

---

## Findings Driving This Plan

- The three producer runs invoked `--providers sec,tiingo` even though `doctor` showed configured credentials for SEC, Tiingo, EODHD, Alpha Vantage, MarketAux, FMP, and Twelve Data.
- `sec_company_tickers` is a global 10,433-entry SEC mapping. It is correctly useful for symbol-to-CIK lookup, but it is copied into every per-symbol bundle and rewritten with a symbol-specific `raw_path`, creating redundant 1.2 MB copies and different hashes for identical source data.
- Normalized bundles include placeholder files such as `etf_profile.json`, `etf_distributions.json`, `etf_performance.json`, `sec_filings_index.json`, and `sec_filing_sections.json` with `not_implemented_in_core_pass`, even when they are irrelevant to the asset type.
- QBIT investor-facing report text still uses internal validation language such as "freeze" and "frozen."
- Self-check outputs still say "frozen artifacts" and are marked `scaffold: true` with `sources_inspected: []`, so they are deterministic lint outputs rather than fresh verifier validations.
- Technical signals are deterministic when prices exist, but coverage is basic: SMA, returns, 52-week range, average volume, and max drawdown. There is no RSI, MACD, realized volatility, relative volume, beta/benchmark-relative return, support/resistance, drawdown duration, trend classification, or venue-aware ETF quote/NAV handling.

## Files

- Modify: `market-research/shared/scripts/deterministic_research_collector.py`
- Modify: `market-research/shared/scripts/validate_market_research.py`
- Modify: `market-research/researcher/SKILL.md`
- Modify: `market-research/researcher/references/report-template.md`
- Modify: `market-research/researcher/references/source-policy.md`
- Modify: `market-research/verifier/SKILL.md`
- Create: `tests/test_provider_plan_quality.py`
- Create: `tests/test_sec_company_tickers_bundle_policy.py`
- Create: `tests/test_normalized_artifact_hygiene.py`
- Create: `tests/test_report_language_lint.py`
- Create: `tests/test_technical_signal_quality.py`

## Task 1: Make Deterministic Provider Breadth Explicit

- [ ] **Step 1: Write a failing test for default provider breadth**

Create `tests/test_provider_plan_quality.py`:

```python
from pathlib import Path
import importlib.util


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "market-research" / "shared" / "scripts" / "deterministic_research_collector.py"


def load_module():
    spec = importlib.util.spec_from_file_location("collector", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_default_endpoint_plan_includes_all_configured_price_fallbacks():
    c = load_module()
    plan = c.default_endpoint_plan(["sec", "tiingo", "eodhd", "alphavantage", "fmp", "twelve_data", "marketaux"])
    assert "prices" in plan["tiingo"]
    assert "prices" in plan["eodhd"]
    assert "prices" in plan["alphavantage"]
    assert "prices" in plan["twelve_data"]
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
python3 -m pytest tests/test_provider_plan_quality.py -v
```

Expected now: fail, because `default_endpoint_plan()` only adds `prices` to the first configured price provider.

- [ ] **Step 3: Update `default_endpoint_plan()`**

In `market-research/shared/scripts/deterministic_research_collector.py`, change the price logic so all configured fallback price providers get their `prices` endpoint unless the caller restricts endpoints explicitly:

```python
for provider in PRICE_PROVIDER_PRIORITY:
    if provider in providers:
        plan.setdefault(provider, set()).add("prices")
```

- [ ] **Step 4: Add researcher guidance**

In `market-research/researcher/SKILL.md`, add: default researcher runs should not restrict providers unless the user requests it or a provider budget/access issue forces narrowing. If narrowing is necessary, the report must say which deterministic providers were skipped and why.

- [ ] **Step 5: Verify**

Run:

```bash
python3 -m pytest tests/test_provider_plan_quality.py tests/test_deterministic_research_collector.py -v
```

Expected: pass.

## Task 2: Stop Duplicating Global SEC Company Tickers In Every Bundle

- [ ] **Step 1: Write a failing test for global raw-copy policy**

Create `tests/test_sec_company_tickers_bundle_policy.py`:

```python
from pathlib import Path
import importlib.util


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "market-research" / "shared" / "scripts" / "deterministic_research_collector.py"


def load_module():
    spec = importlib.util.spec_from_file_location("collector", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_company_tickers_cache_is_global():
    c = load_module()
    assert c.cache_symbol_for_endpoint("AAPL", "sec", "company_tickers") == "_global"


def test_global_sec_tickers_can_be_referenced_without_symbol_bundle_copy(tmp_path):
    c = load_module()
    cache_root = tmp_path / "cache"
    source = c.write_raw(
        cache_root,
        "AAPL",
        "sec",
        "company_tickers",
        {},
        {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}},
        "https://www.sec.gov/files/company_tickers.json",
    )
    bundle_dir = tmp_path / "data" / "AAPL" / "2026-06-21"
    entries, path_map = c.copy_raw_files(cache_root, "AAPL", bundle_dir, ["sec"], {"sec": {"company_tickers"}})
    assert entries[0]["raw_path"] == str(source)
    assert entries[0]["cache_raw_path"] == str(source)
    assert not (bundle_dir / "raw" / "sec" / source.name).exists()
    assert path_map[str(source)] == str(source)
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
python3 -m pytest tests/test_sec_company_tickers_bundle_policy.py -v
```

Expected now: fail, because `copy_raw_files()` writes a per-symbol raw copy.

- [ ] **Step 3: Update `copy_raw_files()`**

Special-case `provider == "sec"` and `endpoint == "company_tickers"` so the bundle source manifest references the global cache artifact directly and records its SHA, without rewriting `provider_result.raw_path` or copying the 1.2 MB file into each symbol bundle.

- [ ] **Step 4: Verify**

Run:

```bash
python3 -m pytest tests/test_sec_company_tickers_bundle_policy.py tests/test_deterministic_research_collector.py -v
```

Expected: pass.

## Task 3: Remove Irrelevant Placeholder Normalized Files

- [ ] **Step 1: Write a failing hygiene test**

Create `tests/test_normalized_artifact_hygiene.py`:

```python
from pathlib import Path
import subprocess
import json


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "market-research" / "shared" / "scripts" / "deterministic_research_collector.py"


def run_fetch(tmp_path, symbol="AAPL", asset_type="equity"):
    subprocess.run(
        [
            "python3", str(SCRIPT), "fetch", symbol,
            "--providers", "sec",
            "--asset-type", asset_type,
            "--as-of", "2026-06-21",
            "--data-dir", str(tmp_path / "data"),
            "--cache-dir", str(tmp_path / "cache"),
        ],
        cwd=ROOT,
        check=True,
    )
    return tmp_path / "data" / symbol / "2026-06-21" / "normalized"


def test_equity_bundle_does_not_emit_etf_placeholders(tmp_path):
    normalized = run_fetch(tmp_path, "AAPL", "equity")
    assert not (normalized / "etf_profile.json").exists()
    assert not (normalized / "etf_distributions.json").exists()
    assert not (normalized / "etf_performance.json").exists()
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
python3 -m pytest tests/test_normalized_artifact_hygiene.py -v
```

Expected now: fail, because placeholder ETF files are always emitted.

- [ ] **Step 3: Update bundle writing**

Only write asset-type-relevant normalized files. For unavailable but relevant files, write a clear structured gap object. For irrelevant asset-type files, omit them and rely on `manifest.json` plus `gaps.json`.

- [ ] **Step 4: Verify**

Run:

```bash
python3 -m pytest tests/test_normalized_artifact_hygiene.py tests/test_deterministic_research_collector.py -v
```

Expected: pass.

## Task 4: Add Report-Language Lint For Investor-Facing Markdown

- [ ] **Step 1: Write a failing lint test**

Create `tests/test_report_language_lint.py`:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_investor_reports_do_not_use_internal_frozen_language():
    offenders = []
    for path in (ROOT / "reports").glob("*/*/*-research.md"):
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        if "frozen" in text or "freeze" in text:
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
python3 -m pytest tests/test_report_language_lint.py -v
```

Expected now: fail on QBIT report language.

- [ ] **Step 3: Update report template and existing QBIT report**

Replace investor-facing "frozen" language with "saved source copy," "captured source artifact," or "captured static page." Keep verifier-internal "frozen" terminology only in verifier docs and machine-oriented self-check output if needed.

- [ ] **Step 4: Verify**

Run:

```bash
python3 -m pytest tests/test_report_language_lint.py -v
```

Expected: pass.

## Task 5: Upgrade Deterministic Technical Signals

- [ ] **Step 1: Write a failing technical-signal test**

Create `tests/test_technical_signal_quality.py`:

```python
from pathlib import Path
import importlib.util


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "market-research" / "shared" / "scripts" / "deterministic_research_collector.py"


def load_module():
    spec = importlib.util.spec_from_file_location("collector", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def rows(n=260):
    return [
        {"date": f"2025-01-{(i % 28) + 1:02d}", "adjusted_close": 100 + i * 0.1, "volume": 1_000_000 + i * 1000}
        for i in range(n)
    ]


def test_technical_signals_include_investor_expected_fields():
    c = load_module()
    out = c.technicals_from_prices(rows(), "test", Path("raw.json"), "source")
    for key in [
        "rsi_14",
        "macd_12_26_9",
        "realized_volatility_30",
        "relative_volume_30_vs_90",
        "trend_classification",
    ]:
        assert key in out
        assert out[key]["status"] == "ok"
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
python3 -m pytest tests/test_technical_signal_quality.py -v
```

Expected now: fail because the fields are absent.

- [ ] **Step 3: Implement deterministic calculations**

Add local deterministic functions for RSI(14), EMA, MACD(12,26,9), 30-day annualized realized volatility from daily returns, relative volume 30-day versus 90-day, and a simple trend classification based on close versus SMA20/SMA50/SMA200.

- [ ] **Step 4: Update report template guidance**

Require reports to use deterministic technical signals when price history exists. If price history is absent, require lifecycle context instead. For non-US/ETF lines, require venue/NAV/quote source clarity and explicit currency.

- [ ] **Step 5: Verify**

Run:

```bash
python3 -m pytest tests/test_technical_signal_quality.py tests/test_deterministic_research_collector.py -v
```

Expected: pass.

## Task 6: Distinguish Self-Check From True Verifier Runs

- [ ] **Step 1: Add validator output language test**

Add to `tests/test_validate_market_research.py` a check that self-check output says "deterministic lint" and does not imply completed verification when `sources_inspected` is empty.

- [ ] **Step 2: Update validator terminology**

In `validate_market_research.py`, keep `blocking_issue_count`, but rename or add fields:

```json
"validation_level": "deterministic_lint",
"requires_fresh_verifier": true
```

Keep `scaffold` temporarily for compatibility, but document it as deprecated.

- [ ] **Step 3: Update researcher final instruction**

In `market-research/researcher/SKILL.md`, require final responses to distinguish "self-check/lint passed" from "fresh verifier passed."

- [ ] **Step 4: Verify**

Run:

```bash
python3 -m pytest tests/test_validate_market_research.py tests/test_market_research_acceptance.py -v
```

Expected: pass.

## Task 7: Re-run The Three Research Cases After Fixes

- [ ] **Step 1: Run deterministic collection without provider narrowing**

Run each symbol with the default configured provider set into a fresh date or test output root:

```bash
python3 market-research/shared/scripts/deterministic_research_collector.py fetch DPC --asset-type auto --as-of 2026-06-21 --data-dir ./data --reports-dir ./reports --refresh
python3 market-research/shared/scripts/deterministic_research_collector.py fetch QBIT --asset-type auto --as-of 2026-06-21 --data-dir ./data --reports-dir ./reports --refresh
python3 market-research/shared/scripts/deterministic_research_collector.py fetch QUBT --asset-type auto --as-of 2026-06-21 --data-dir ./data --reports-dir ./reports --refresh
```

- [ ] **Step 2: Compare provider coverage**

For each symbol, inspect `manifest.json`, `source_manifest.json`, `gaps.json`, and normalized files. Confirm skipped providers are explained by missing credentials, rate limits, plan gates, endpoint errors, or true symbol unavailability.

- [ ] **Step 3: Regenerate reports**

Regenerate DPC, QBIT, and QUBT reports using the updated deterministic bundles and procedural source helper. Remove investor-facing internal validation language.

- [ ] **Step 4: Run validation**

Run:

```bash
python3 market-research/shared/scripts/validate_market_research.py reports/DPC/2026-06-21 --report-md reports/DPC/2026-06-21/DPC-research.md --report-json reports/DPC/2026-06-21/DPC-research.json --output-prefix reports/DPC/2026-06-21/DPC-self-check --force
python3 market-research/shared/scripts/validate_market_research.py reports/QBIT/2026-06-21 --report-md reports/QBIT/2026-06-21/QBIT-research.md --report-json reports/QBIT/2026-06-21/QBIT-research.json --output-prefix reports/QBIT/2026-06-21/QBIT-self-check --force
python3 market-research/shared/scripts/validate_market_research.py reports/QUBT/2026-06-21 --report-md reports/QUBT/2026-06-21/QUBT-research.md --report-json reports/QUBT/2026-06-21/QUBT-research.json --output-prefix reports/QUBT/2026-06-21/QUBT-self-check --force
```

Expected: zero blocking issues, with clear `validation_level`.

## Final Verification

Run:

```bash
python3 -m pytest tests
rg -n "frozen|freeze" reports/*/*/*-research.md
```

Expected: pytest passes; no investor-facing research Markdown contains `frozen` or `freeze`.
