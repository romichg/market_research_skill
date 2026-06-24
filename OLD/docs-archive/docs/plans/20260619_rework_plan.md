# Market Research Full Rework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the three active market-research skills with one clean canonical `market-research-full/` skill, expand deterministic/provider coverage, and produce richer research and stricter validation artifacts under the new `data/`, `reports/`, and `runtime/` layout.

**Architecture:** This is a big-bang migration. Move the active skill code into `market-research-full/`, remove the old active top-level skill directories, update every active test/doc/prompt path to the new location, and use tests to enforce that old paths no longer appear outside `OLD/` and this plan. The deterministic collector writes deterministic evidence under `data/`, final research and validation under `reports/`, and loop/runtime scaffolding under `runtime/`.

**Tech Stack:** Python 3.13, pytest, JSON Schema files, Markdown skill/reference docs, public/free market-data APIs, Codex skill instructions.

---

## Source Design

The current repo is green before the rework:

```bash
python3 -m pytest tests
```

Expected baseline: `75 passed`.

The documented `python -m pytest tests` command fails in this environment because `python` is not on PATH. Use `python3` in this plan and update active docs accordingly.

## File Structure

Create this canonical tree:

```text
market-research-full/
  SKILL.md
  researcher/
    SKILL.md
    references/
  verifier/
    SKILL.md
    references/
  loop-runner/
    SKILL.md
    agents/
    scripts/
  shared/
    agents/
    provider-docs/
    references/
    schemas/
    scripts/
```

Responsibilities:

- `market-research-full/SKILL.md`: the only active top-level market research skill entry point. It routes research, validation, and loop use cases.
- `market-research-full/researcher/SKILL.md`: producer workflow, report requirements, deterministic-first usage, procedural gap filling.
- `market-research-full/verifier/SKILL.md`: validation workflow that checks only frozen artifacts and cited sources.
- `market-research-full/loop-runner/SKILL.md`: supervised loop workflow.
- `market-research-full/shared/scripts/deterministic_research_collector.py`: deterministic provider fetch, raw/cache copy, normalization, technical signals, and bundle writing.
- `market-research-full/shared/scripts/procedural_source_helper.py`: procedural source registry, gap fills, issuer extraction, and runtime context.
- `market-research-full/loop-runner/scripts/research_loop.py`: batch loop, prompts, logs, remediation, summaries.
- `market-research-full/shared/scripts/validate_market_research.py`: deterministic validation scaffold/lint helper.
- `market-research-full/shared/provider-docs/*.md`: official provider audit summaries.
- `market-research-full/shared/schemas/*.json`: research, validation, deterministic bundle schemas.

Remove these active directories after moving their contents:

```text
market-research/
validate-market-research/
market-research-loop/
```

Allowed old references after migration:

- `OLD/**`
- `.git/**`
- `docs/plans/20260619_rework_plan.md`

## Official Provider Docs To Audit

Use only official/provider-owned documentation for endpoint decisions:

- Tiingo: `https://www.tiingo.com/documentation/end-of-day`, `https://www.tiingo.com/documentation/fundamentals`
- EODHD: `https://eodhd.com/financial-apis/api-for-historical-data-and-volumes`, `https://eodhd.com/lp/fundamental-data-api`, `https://eodhd.com/financial-apis/user-api`
- Alpha Vantage: `https://www.alphavantage.co/documentation/`
- Twelve Data: `https://twelvedata.com/docs`
- MarketAux: `https://www.marketaux.com/documentation`, `https://www.marketaux.com/pricing`
- FMP: `https://site.financialmodelingprep.com/developer/docs`, `https://site.financialmodelingprep.com/developer/docs/stable/profile-symbol`, `https://site.financialmodelingprep.com/developer/docs/stable/key-metrics`, `https://site.financialmodelingprep.com/developer/docs/stable/metrics-ratios`, `https://site.financialmodelingprep.com/developer/docs/stable/income-statement`

## Task 1: Enforce The New Canonical Layout

**Files:**

- Create: `tests/test_repository_layout.py`
- Move: `market-research/` to `market-research-full/researcher/`
- Move: `validate-market-research/` to `market-research-full/verifier/`
- Move: `market-research-loop/` to `market-research-full/loop-runner/`
- Create: `market-research-full/SKILL.md`
- Move: `market-research-full/researcher/scripts/deterministic_research_collector.py` to `market-research-full/shared/scripts/deterministic_research_collector.py`
- Move: `market-research-full/researcher/scripts/procedural_source_helper.py` to `market-research-full/shared/scripts/procedural_source_helper.py`
- Move: `market-research-full/verifier/scripts/validate_market_research.py` to `market-research-full/shared/scripts/validate_market_research.py`
- Move: `market-research-full/researcher/schemas/` to `market-research-full/shared/schemas/`
- Move: `market-research-full/researcher/agents/` to `market-research-full/shared/agents/`
- Test: `tests/test_repository_layout.py`

- [ ] **Step 1: Write the failing layout test**

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OLD_ACTIVE_DIRS = ["market-research", "validate-market-research", "market-research-loop"]


def test_only_market_research_full_is_active_skill_tree():
    assert (ROOT / "market-research-full" / "SKILL.md").exists()
    for name in OLD_ACTIVE_DIRS:
        assert not (ROOT / name).exists(), f"{name} must be moved into market-research-full"


def test_active_files_do_not_reference_old_skill_paths():
    forbidden = [
        "market-research/scripts/",
        "validate-market-research/scripts/",
        "market-research-loop/scripts/",
        "$market-research ",
        "$validate-market-research ",
        "$market-research-loop ",
        "market-research-runs",
    ]
    allowed_prefixes = {"OLD", ".git"}
    allowed_files = {Path("docs/plans/20260619_rework_plan.md")}
    offenders = []
    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT)
        if not path.is_file():
            continue
        if rel.parts and rel.parts[0] in allowed_prefixes:
            continue
        if rel in allowed_files:
            continue
        if path.suffix not in {".md", ".py", ".json", ".yaml", ".yml", ".toml"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for needle in forbidden:
            if needle in text:
                offenders.append(f"{rel}: {needle}")
    assert offenders == []
```

- [ ] **Step 2: Run the layout test to verify it fails**

Run:

```bash
python3 -m pytest tests/test_repository_layout.py -v
```

Expected: FAIL because `market-research-full/SKILL.md` is missing and old active directories still exist.

- [ ] **Step 3: Move the directories and shared assets**

Run these commands from the repo root:

```bash
mkdir -p market-research-full
git mv market-research market-research-full/researcher
git mv validate-market-research market-research-full/verifier
git mv market-research-loop market-research-full/loop-runner
mkdir -p market-research-full/shared/scripts market-research-full/shared/schemas market-research-full/shared/agents market-research-full/shared/references market-research-full/shared/provider-docs
git mv market-research-full/researcher/scripts/deterministic_research_collector.py market-research-full/shared/scripts/deterministic_research_collector.py
git mv market-research-full/researcher/scripts/procedural_source_helper.py market-research-full/shared/scripts/procedural_source_helper.py
git mv market-research-full/verifier/scripts/validate_market_research.py market-research-full/shared/scripts/validate_market_research.py
git mv market-research-full/researcher/schemas/* market-research-full/shared/schemas/
git mv market-research-full/researcher/agents/* market-research-full/shared/agents/
rmdir market-research-full/researcher/scripts market-research-full/verifier/scripts market-research-full/researcher/schemas market-research-full/researcher/agents
```

- [ ] **Step 4: Create the root canonical skill**

Create `market-research-full/SKILL.md` with this content:

```markdown
---
name: market-research-full
description: Research, validate, and supervise market research runs for US-listed equities, ADRs, and ETFs using deterministic provider data, procedural source capture, and frozen-artifact validation.
---

# Market Research Full

Use this single skill for all market research workflows. This is research support, not personalized financial advice.

## Modes

- Producer/researcher: follow `researcher/SKILL.md`.
- Verifier: follow `verifier/SKILL.md`.
- Supervised loop runner: follow `loop-runner/SKILL.md`.

## Canonical Layout

- Deterministic evidence belongs under `data/SYMBOL/YYYY-MM-DD/`.
- Final reports and validations belong under `reports/SYMBOL/YYYY-MM-DD/`.
- Prompts, logs, source workspaces, validation scaffolds, remediation notes, and other transient artifacts belong under `runtime/SYMBOL/YYYY-MM-DD/`.

Do not write new artifacts to `market-research-runs/`. Do not invoke the removed `$market-research`, `$validate-market-research`, or `$market-research-loop` skills.
```

- [ ] **Step 5: Run the layout test**

Run:

```bash
python3 -m pytest tests/test_repository_layout.py -v
```

Expected: FAIL only on active references still pointing at old paths. Keep this failure for Task 2.

- [ ] **Step 6: Commit the structural move**

Do not create a commit while `tests/test_repository_layout.py` is intentionally failing on old active references. Verify the structural files are staged and proceed directly to Task 2.

Run:

```bash
git add market-research-full tests/test_repository_layout.py
git diff --cached --name-status
```

Expected: staged paths include the `market-research-full/` move and `tests/test_repository_layout.py`.

## Task 2: Update Tests And Active References To New Paths

**Files:**

- Modify: `tests/test_deterministic_research_collector.py`
- Modify: `tests/test_procedural_source_helper.py`
- Modify: `tests/test_validate_market_research.py`
- Modify: `tests/test_research_loop.py`
- Modify: `market-research-full/researcher/SKILL.md`
- Modify: `market-research-full/verifier/SKILL.md`
- Modify: `market-research-full/loop-runner/SKILL.md`
- Modify: `market-research-full/loop-runner/scripts/research_loop.py`
- Test: `tests/test_repository_layout.py`
- Test: `tests/test_deterministic_research_collector.py`
- Test: `tests/test_procedural_source_helper.py`
- Test: `tests/test_validate_market_research.py`
- Test: `tests/test_research_loop.py`

- [ ] **Step 1: Update test constants**

Make these exact path changes:

```python
# tests/test_deterministic_research_collector.py
SCRIPT = ROOT / "market-research-full" / "shared" / "scripts" / "deterministic_research_collector.py"
DETERMINISTIC_SCHEMA = ROOT / "market-research-full" / "shared" / "schemas" / "deterministic-bundle.schema.json"
PROVIDER_MAP = ROOT / "market-research-full" / "researcher" / "references" / "provider-data-map.md"

# tests/test_procedural_source_helper.py
HELPER = ROOT / "market-research-full" / "shared" / "scripts" / "procedural_source_helper.py"

# tests/test_validate_market_research.py
VALIDATOR = Path(__file__).resolve().parents[1] / "market-research-full" / "shared" / "scripts" / "validate_market_research.py"

# tests/test_research_loop.py
HARNESS = Path(__file__).resolve().parents[1] / "market-research-full" / "loop-runner" / "scripts" / "research_loop.py"
```

Add `ROOT = Path(__file__).resolve().parents[1]` to `tests/test_procedural_source_helper.py` if it is not already present.

- [ ] **Step 2: Update loop prompts to the new skill and script paths**

In `market-research-full/loop-runner/scripts/research_loop.py`, make these replacements:

```python
f"$market-research-full researcher {symbol}"
```

```python
f"Use the deterministic producer first: `python3 market-research-full/shared/scripts/deterministic_research_collector.py fetch {symbol} --data-dir ./data --reports-dir ./reports --as-of YYYY-MM-DD`."
```

```python
"Run the market-research-full researcher workflow in this fresh Codex context."
```

```python
f"$market-research-full verifier {run_dir}"
```

```python
"Run the market-research-full verifier workflow in this fresh Codex context."
```

```python
run_dir = args.run_dir or f"runtime/{symbol}"
```

- [ ] **Step 3: Update skill docs to point to shared scripts**

In `market-research-full/researcher/SKILL.md`, replace script/resource references so they use:

```text
../shared/scripts/deterministic_research_collector.py
../shared/scripts/procedural_source_helper.py
../shared/schemas/research-output.schema.json
../shared/schemas/validation-output.schema.json
```

In `market-research-full/verifier/SKILL.md`, replace script/schema references so they use:

```text
../shared/scripts/validate_market_research.py
../shared/schemas/deterministic-bundle.schema.json
../shared/schemas/validation-output.schema.json
```

In `market-research-full/loop-runner/SKILL.md`, replace the runner command with:

```bash
python3 market-research-full/loop-runner/scripts/research_loop.py run-batch SYMBOL ... --run-root runtime/market-research-loop-YYYYMMDD --max-remediation-loops 3
```

- [ ] **Step 4: Run path/reference tests**

Run:

```bash
python3 -m pytest tests/test_repository_layout.py tests/test_research_loop.py -v
```

Expected: PASS.

- [ ] **Step 5: Run all tests**

Run:

```bash
python3 -m pytest tests
```

Expected: PASS.

- [ ] **Step 6: Commit active reference migration**

Run:

```bash
git add tests market-research-full
git commit -m "consolidate market research full skill"
```

## Task 3: Implement `data/`, `reports/`, And `runtime/` Path Semantics

**Files:**

- Modify: `market-research-full/shared/scripts/deterministic_research_collector.py`
- Modify: `market-research-full/shared/scripts/procedural_source_helper.py`
- Modify: `market-research-full/loop-runner/scripts/research_loop.py`
- Modify: `market-research-full/researcher/SKILL.md`
- Modify: `market-research-full/loop-runner/SKILL.md`
- Modify: `tests/test_deterministic_research_collector.py`
- Modify: `tests/test_procedural_source_helper.py`
- Modify: `tests/test_research_loop.py`

- [ ] **Step 1: Add failing deterministic path test**

Append to `tests/test_deterministic_research_collector.py`:

```python
def test_storage_paths_default_to_data_reports_runtime(tmp_path):
    module = load_module()
    config = module.ProviderConfig(values={}, docs={}, limits={}, loaded_files=[])

    paths = module.resolve_storage_paths(tmp_path, config)

    assert paths["data_dir"] == tmp_path / "data"
    assert paths["reports_dir"] == tmp_path / "reports"
    assert paths["runtime_dir"] == tmp_path / "runtime"
    assert paths["cache_dir"] == tmp_path / "data" / "_cache"
```

- [ ] **Step 2: Add failing fetch output test**

Append to `tests/test_deterministic_research_collector.py`:

```python
def test_fetch_writes_deterministic_bundle_under_data_not_reports(tmp_path, monkeypatch):
    module = load_module()

    def fake_fetch(symbol, provider, as_of, cache_root, config, refresh=False, endpoints=None):
        return []

    monkeypatch.setattr(module, "fetch_provider", fake_fetch)
    args = type(
        "Args",
        (),
        {
            "repo_root": str(tmp_path),
            "symbol": "AAPL",
            "as_of": "2026-06-16",
            "data_dir": None,
            "cache_dir": None,
            "reports_dir": None,
            "runtime_dir": None,
            "providers": "sec",
            "max_provider_calls": ["sec=3"],
            "offline": False,
            "refresh": False,
            "asset_type": "equity",
        },
    )()

    module.cmd_fetch(args)

    assert (tmp_path / "data" / "AAPL" / "2026-06-16" / "manifest.json").exists()
    assert not (tmp_path / "reports" / "AAPL" / "2026-06-16" / "manifest.json").exists()
```

- [ ] **Step 3: Add failing procedural runtime test**

Append to `tests/test_procedural_source_helper.py`:

```python
def test_default_output_root_is_runtime_symbol_date(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = run_helper("init-run", "aapl", "--as-of", "2026-06-16")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert Path(payload["run_dir"]) == tmp_path / "runtime" / "AAPL" / "2026-06-16"
    assert (tmp_path / "runtime" / "AAPL" / "2026-06-16" / "run_manifest.json").exists()
```

- [ ] **Step 4: Add failing loop runtime test**

Append to `tests/test_research_loop.py`:

```python
def test_run_batch_dry_run_uses_runtime_symbol_date_layout(tmp_path):
    root = tmp_path / "runtime"

    result = run_harness(
        "run-batch",
        "EWW",
        "--run-root",
        str(root),
        "--as-of",
        "2026-06-16",
        "--dry-run",
    )

    assert result.returncode == 0, result.stderr
    iteration = root / "EWW" / "2026-06-16" / "iteration-01"
    assert (iteration / "producer-initial.prompt.md").exists()
    commands = json.loads((iteration / "commands.json").read_text(encoding="utf-8"))
    assert "market-research-full" in commands["producer"]
```

- [ ] **Step 5: Run the new path tests to verify failure**

Run:

```bash
python3 -m pytest tests/test_deterministic_research_collector.py::test_storage_paths_default_to_data_reports_runtime tests/test_deterministic_research_collector.py::test_fetch_writes_deterministic_bundle_under_data_not_reports tests/test_procedural_source_helper.py::test_default_output_root_is_runtime_symbol_date tests/test_research_loop.py::test_run_batch_dry_run_uses_runtime_symbol_date_layout -v
```

Expected: FAIL because the code still defaults to `.cache`, `reports`, and `market-research-runs` semantics.

- [ ] **Step 6: Update deterministic storage resolution**

In `market-research-full/shared/scripts/deterministic_research_collector.py`, update `load_env_files`, `write_env_example`, and `resolve_storage_paths` so they support these variables:

```python
"RESEARCH_DATA_DIR"
"RESEARCH_REPORTS_DIR"
"RESEARCH_RUNTIME_DIR"
"RESEARCH_CACHE_DIR"
```

Use this body for `resolve_storage_paths`:

```python
def resolve_storage_paths(
    repo_root: Path | str,
    config: ProviderConfig,
    data_dir: str | None = None,
    cache_dir: str | None = None,
    reports_dir: str | None = None,
    runtime_dir: str | None = None,
) -> dict[str, Path]:
    root = Path(repo_root)
    resolved_data = Path(data_dir or config.values.get("RESEARCH_DATA_DIR", root / "data"))
    resolved_reports = Path(reports_dir or config.values.get("RESEARCH_REPORTS_DIR", root / "reports"))
    resolved_runtime = Path(runtime_dir or config.values.get("RESEARCH_RUNTIME_DIR", root / "runtime"))
    resolved_cache = Path(cache_dir or config.values.get("RESEARCH_CACHE_DIR", resolved_data / "_cache"))
    return {
        "data_dir": resolved_data,
        "reports_dir": resolved_reports,
        "runtime_dir": resolved_runtime,
        "cache_dir": resolved_cache,
    }
```

Update `cmd_fetch` so:

```python
cache_root = paths["cache_dir"]
output_root = paths["data_dir"]
```

Add `--runtime-dir` to the parser wherever `--data-dir`, `--cache-dir`, and `--reports-dir` are available.

- [ ] **Step 7: Update procedural helper date-aware runtime roots**

In `market-research-full/shared/scripts/procedural_source_helper.py`, change `run_dir` to:

```python
def run_dir(output_root: Path, symbol: str, as_of: str | None = None) -> Path:
    return output_root / symbol / as_of if as_of else output_root / symbol
```

Thread `args.as_of` through `cmd_init_run`, `manifest_path`, `ensure_run`, `update_manifest`, `append_manifest_gap_fills`, `append_manifest_source_gap`, `build_context`, `merge_data_points`, and commands that call them. Add this parser argument to every subcommand:

```python
parser_or_subcommand.add_argument("--as-of", help="YYYY-MM-DD runtime date directory.")
```

Change every default `--output-root` from:

```python
"./market-research-runs"
```

to:

```python
"./runtime"
```

- [ ] **Step 8: Update loop date-aware runtime layout**

In `market-research-full/loop-runner/scripts/research_loop.py`, add `--as-of` to `init-batch` and `run-batch`. When absent, default to `date.today().isoformat()`.

Use this run directory pattern in `execute_symbol_loop`:

```python
run_dir = root / symbol / args.as_of
symbol_dir = root / symbol / args.as_of
```

Update imports:

```python
from datetime import date
```

- [ ] **Step 9: Run focused path tests**

Run:

```bash
python3 -m pytest tests/test_deterministic_research_collector.py::test_storage_paths_default_to_data_reports_runtime tests/test_deterministic_research_collector.py::test_fetch_writes_deterministic_bundle_under_data_not_reports tests/test_procedural_source_helper.py::test_default_output_root_is_runtime_symbol_date tests/test_research_loop.py::test_run_batch_dry_run_uses_runtime_symbol_date_layout -v
```

Expected: PASS.

- [ ] **Step 10: Run all tests and commit**

Run:

```bash
python3 -m pytest tests
git add market-research-full tests
git commit -m "separate deterministic reports and runtime artifacts"
```

Expected: tests PASS and commit succeeds.

## Task 4: Audit Provider Docs And Expand Endpoint Plans

**Files:**

- Create: `market-research-full/shared/provider-docs/tiingo.md`
- Create: `market-research-full/shared/provider-docs/eodhd.md`
- Create: `market-research-full/shared/provider-docs/alphavantage.md`
- Create: `market-research-full/shared/provider-docs/twelve-data.md`
- Create: `market-research-full/shared/provider-docs/marketaux.md`
- Create: `market-research-full/shared/provider-docs/fmp.md`
- Modify: `market-research-full/shared/scripts/deterministic_research_collector.py`
- Modify: `market-research-full/researcher/references/provider-data-map.md`
- Modify: `tests/test_deterministic_research_collector.py`

- [ ] **Step 1: Write failing endpoint coverage test**

Append to `tests/test_deterministic_research_collector.py`:

```python
def test_default_endpoint_plan_includes_unique_provider_data():
    module = load_module()

    plan = module.default_endpoint_plan(["tiingo", "eodhd", "alphavantage", "twelve_data", "marketaux", "fmp"])

    assert plan["tiingo"] == {"metadata", "prices"}
    assert {"fundamentals", "news", "historical_market_cap"} <= plan["eodhd"]
    assert {"overview", "income_statement", "balance_sheet", "cash_flow", "earnings", "etf_profile", "news_sentiment"} <= plan["alphavantage"]
    assert {"quote", "profile"} <= plan["twelve_data"]
    assert plan["marketaux"] == {"news"}
    assert {"profile", "key_metrics_ttm", "ratios_ttm", "income_statement", "balance_sheet", "cash_flow", "stock_news", "press_releases", "dividends", "earnings", "splits", "insider_trading", "insider_statistics", "etf_holdings"} <= plan["fmp"]
```

- [ ] **Step 2: Run the endpoint coverage test to verify failure**

Run:

```bash
python3 -m pytest tests/test_deterministic_research_collector.py::test_default_endpoint_plan_includes_unique_provider_data -v
```

Expected: FAIL because current plans do not include all listed unique endpoint names.

- [ ] **Step 3: Write provider audit files**

Create `market-research-full/shared/provider-docs/tiingo.md`:

```markdown
# Tiingo Endpoint Audit

Official docs checked:
- https://www.tiingo.com/documentation/end-of-day
- https://www.tiingo.com/documentation/fundamentals

Free/configured endpoints to attempt:
- metadata: symbol metadata from `/tiingo/daily/{symbol}`; unique fields include exchange/name where returned; normalized target is `identity`.
- prices: daily adjusted EOD history from `/tiingo/daily/{symbol}/prices`; primary price source for `prices_daily`, `market_snapshot`, and `technical_signals`.

Plan-gated or fallback endpoints:
- fundamentals: document endpoint availability and do not make it default until a configured key is confirmed to return free data; record `plan_gated` or `unauthorized` when provider payload says so.

Duplicate endpoints intentionally skipped:
- alternative daily prices from EODHD, Alpha Vantage, and Twelve Data are skipped unless Tiingo prices are missing or filtered out by endpoint settings.
```

Create `market-research-full/shared/provider-docs/eodhd.md`:

```markdown
# EODHD Endpoint Audit

Official docs checked:
- https://eodhd.com/financial-apis/api-for-historical-data-and-volumes
- https://eodhd.com/lp/fundamental-data-api
- https://eodhd.com/financial-apis/user-api

Free/configured endpoints to attempt:
- fundamentals: `/api/fundamentals/{symbol}.US`; unique company/fund fundamentals, classifications, valuation fields, ETF fields when returned; normalized targets are `identity`, `market_snapshot`, `equity_fundamentals`, and ETF fields.
- news: `/api/news`; unique provider news; normalized target is `news`.
- historical_market_cap: `/api/historical-market-cap/{symbol}.US`; unique historical market-cap context; normalized target is `market_snapshot` or a future `market_cap_history` artifact.

Plan-gated or fallback endpoints:
- prices: `/api/eod/{symbol}.US`; fallback price source only when Tiingo prices are not available.

Duplicate endpoints intentionally skipped:
- prices: skipped by default when Tiingo prices are selected.
```

Create `market-research-full/shared/provider-docs/alphavantage.md`:

```markdown
# Alpha Vantage Endpoint Audit

Official docs checked:
- https://www.alphavantage.co/documentation/

Free/configured endpoints to attempt:
- overview: `OVERVIEW`; unique overview, valuation, dividend, and classification fields; normalized targets are `identity`, `market_snapshot`, and `equity_fundamentals`.
- income_statement: `INCOME_STATEMENT`; normalized target is `equity_fundamentals`.
- balance_sheet: `BALANCE_SHEET`; normalized target is `equity_fundamentals`.
- cash_flow: `CASH_FLOW`; normalized target is `equity_fundamentals`.
- earnings: `EARNINGS`; normalized target is `equity_events`.
- etf_profile: `ETF_PROFILE`; normalized target is ETF profile/holdings fields when returned.
- news_sentiment: `NEWS_SENTIMENT`; normalized target is `news`.

Plan-gated or fallback endpoints:
- prices: `TIME_SERIES_DAILY_ADJUSTED`; fallback price source only when Tiingo and EODHD prices are unavailable.

Duplicate endpoints intentionally skipped:
- prices: skipped by default when Tiingo prices are selected.
```

Create `market-research-full/shared/provider-docs/twelve-data.md`:

```markdown
# Twelve Data Endpoint Audit

Official docs checked:
- https://twelvedata.com/docs

Free/configured endpoints to attempt:
- quote: `/quote`; unique latest quote fields and exchange/session context where returned; normalized target is `market_snapshot`.
- profile: `/profile`; unique company/fund profile fields where returned; normalized target is `identity`.

Plan-gated or fallback endpoints:
- prices: `/time_series`; fallback price source only when Tiingo, EODHD, and Alpha Vantage prices are unavailable.

Duplicate endpoints intentionally skipped:
- prices: skipped by default when higher-priority price providers are selected.
```

Create `market-research-full/shared/provider-docs/marketaux.md`:

```markdown
# MarketAux Endpoint Audit

Official docs checked:
- https://www.marketaux.com/documentation
- https://www.marketaux.com/pricing

Free/configured endpoints to attempt:
- news: `/v1/news/all`; unique news, entities, sentiment, relevance, source, tags, and published date fields; normalized target is `news`.

Plan-gated or fallback endpoints:
- market stats endpoints: not default on the free plan because entity-stat limits vary by plan; record provider status if attempted explicitly.

Duplicate endpoints intentionally skipped:
- none; MarketAux is the default dedicated news/sentiment source when configured.
```

Create `market-research-full/shared/provider-docs/fmp.md`:

```markdown
# FMP Endpoint Audit

Official docs checked:
- https://site.financialmodelingprep.com/developer/docs
- https://site.financialmodelingprep.com/developer/docs/stable/profile-symbol
- https://site.financialmodelingprep.com/developer/docs/stable/key-metrics
- https://site.financialmodelingprep.com/developer/docs/stable/metrics-ratios
- https://site.financialmodelingprep.com/developer/docs/stable/income-statement

Free/configured endpoints to attempt:
- profile: `/stable/profile`; normalized targets are `identity` and `market_snapshot`.
- key_metrics_ttm: `/stable/key-metrics-ttm`; normalized targets are `market_snapshot` and `equity_fundamentals`.
- ratios_ttm: `/stable/ratios-ttm`; normalized target is `equity_fundamentals`.
- income_statement: `/stable/income-statement`; normalized target is `equity_fundamentals`.
- balance_sheet: `/stable/balance-sheet-statement`; normalized target is `equity_fundamentals`.
- cash_flow: `/stable/cash-flow-statement`; normalized target is `equity_fundamentals`.
- stock_news: `/stable/news/stock`; normalized target is `news`.
- press_releases: `/stable/news/press-releases`; normalized target is `news`.
- dividends: `/stable/dividends`; normalized target is `equity_events`.
- earnings: `/stable/earnings`; normalized target is `equity_events`.
- splits: `/stable/splits`; normalized target is `equity_events`.
- insider_trading: `/stable/insider-trading`; normalized target is `equity_insiders`.
- insider_statistics: `/stable/insider-trading/statistics`; normalized target is `equity_insiders`.
- etf_holdings: `/stable/etf/holdings`; normalized target is `etf_holdings`.

Plan-gated or fallback endpoints:
- bulk endpoints: not default because single-symbol research does not need them and plan limits vary.

Duplicate endpoints intentionally skipped:
- historical prices: skipped because Tiingo is the primary price source.
```

- [ ] **Step 4: Expand endpoint constants**

In `market-research-full/shared/scripts/deterministic_research_collector.py`, update `PROVIDER_ENDPOINT_COSTS` and `UNIQUE_DEFAULT_ENDPOINTS` so they include the endpoint names asserted in Step 1. Assign cost `1` to quote/profile/news/metadata endpoints, cost `5` to financial-statement families, and cost `10` to broad fundamentals endpoints.

- [ ] **Step 5: Implement fetch specs for new endpoints**

In `fetch_provider`, add URL specs for:

```python
# tiingo
"metadata": f"https://api.tiingo.com/tiingo/daily/{symbol}"

# eodhd
"news": "https://eodhd.com/api/news"
"historical_market_cap": f"https://eodhd.com/api/historical-market-cap/{symbol}.US"

# alphavantage
"income_statement": "INCOME_STATEMENT"
"balance_sheet": "BALANCE_SHEET"
"cash_flow": "CASH_FLOW"
"earnings": "EARNINGS"
"etf_profile": "ETF_PROFILE"
"news_sentiment": "NEWS_SENTIMENT"

# twelve_data
"quote": "https://api.twelvedata.com/quote"
"profile": "https://api.twelvedata.com/profile"

# fmp
"etf_holdings": "https://financialmodelingprep.com/stable/etf/holdings"
```

Use provider status classification already present in `classify_provider_payload`; do not promote plan-gated raw data into normalized facts.

- [ ] **Step 6: Run endpoint tests**

Run:

```bash
python3 -m pytest tests/test_deterministic_research_collector.py::test_default_endpoint_plan_includes_unique_provider_data tests/test_deterministic_research_collector.py::test_endpoint_plan_avoids_duplicate_price_fetches -v
```

Expected: PASS.

- [ ] **Step 7: Run all tests and commit**

Run:

```bash
python3 -m pytest tests
git add market-research-full tests
git commit -m "expand deterministic provider endpoint plan"
```

Expected: tests PASS and commit succeeds.

## Task 5: Normalize Additional Provider Data And Technical Inputs

**Files:**

- Modify: `market-research-full/shared/scripts/deterministic_research_collector.py`
- Modify: `market-research-full/shared/schemas/deterministic-bundle.schema.json`
- Modify: `market-research-full/researcher/references/provider-data-map.md`
- Modify: `tests/test_deterministic_research_collector.py`

- [ ] **Step 1: Add failing normalization test for expanded data**

Append to `tests/test_deterministic_research_collector.py`:

```python
def test_expanded_provider_data_normalizes_news_events_and_etf_holdings(tmp_path):
    module = load_module()
    cache = tmp_path / "cache"
    module.write_raw(cache, "SPY", "fmp", "etf_holdings", {"symbol": "SPY"}, [{"asset": "AAPL", "weightPercentage": 7.0}], source_url="https://financialmodelingprep.com/stable/etf/holdings?symbol=SPY")
    module.write_raw(cache, "SPY", "alphavantage", "news_sentiment", {"function": "NEWS_SENTIMENT", "tickers": "SPY"}, {"feed": [{"title": "ETF flows rise", "url": "https://example.test/spy-news", "time_published": "20260616T120000"}]}, source_url="https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers=SPY")
    module.write_raw(cache, "SPY", "twelve_data", "quote", {"symbol": "SPY"}, {"close": "600.00", "volume": "1000000"}, source_url="https://api.twelvedata.com/quote?symbol=SPY")

    result = module.build_bundle("SPY", "2026-06-16", cache, tmp_path / "data", providers=["fmp", "alphavantage", "twelve_data"], asset_type="etf")

    bundle_dir = Path(result["bundle_dir"])
    holdings = json.loads((bundle_dir / "normalized" / "etf_holdings.json").read_text(encoding="utf-8"))
    news = json.loads((bundle_dir / "normalized" / "news.json").read_text(encoding="utf-8"))
    snapshot = json.loads((bundle_dir / "normalized" / "market_snapshot.json").read_text(encoding="utf-8"))
    assert holdings["top_holdings"][0]["ticker"]["value"] == "AAPL"
    assert holdings["top_holdings"][0]["weight"]["value"] == 7.0
    assert news["items"][0]["provider"] == "alphavantage"
    assert snapshot["latest_close"]["provider"] == "twelve_data"
```

- [ ] **Step 2: Run the new normalization test to verify failure**

Run:

```bash
python3 -m pytest tests/test_deterministic_research_collector.py::test_expanded_provider_data_normalizes_news_events_and_etf_holdings -v
```

Expected: FAIL because the normalized outputs do not yet include the expanded data.

- [ ] **Step 3: Add normalizers**

In `deterministic_research_collector.py`, add or extend these functions:

```python
normalize_news(cache_root: Path, symbol: str, providers: list[str], endpoint_plan: dict[str, set[str]] | None = None) -> dict[str, Any]
normalize_market_snapshot(cache_root: Path, symbol: str, providers: list[str], endpoint_plan: dict[str, set[str]] | None = None) -> dict[str, Any]
normalize_etf_holdings(cache_root: Path, symbol: str, providers: list[str], endpoint_plan: dict[str, set[str]] | None = None) -> dict[str, Any]
```

For every normalized value, use `provenance(...)` or an equivalent object with `value`, `provider`, `source_url`, `endpoint`, `raw_path`, and `status`.

- [ ] **Step 4: Write `normalized/etf_holdings.json` from `build_bundle`**

Update `build_bundle` so ETF bundles write:

```python
normalized_outputs["etf_holdings"] = normalize_etf_holdings(cache_root, symbol, selected_providers, endpoint_plan)
```

and emit `normalized/etf_holdings.json`.

- [ ] **Step 5: Update deterministic schema**

In `market-research-full/shared/schemas/deterministic-bundle.schema.json`, add `etf_holdings` as an optional normalized artifact object. Keep `identity`, `market_snapshot`, `prices_daily`, `technical_signals`, and `news` required.

- [ ] **Step 6: Run normalization tests**

Run:

```bash
python3 -m pytest tests/test_deterministic_research_collector.py::test_expanded_provider_data_normalizes_news_events_and_etf_holdings -v
```

Expected: PASS.

- [ ] **Step 7: Run all tests and commit**

Run:

```bash
python3 -m pytest tests
git add market-research-full tests
git commit -m "normalize expanded provider evidence"
```

## Task 6: Require Rich Research JSON And Report Sections

**Files:**

- Modify: `market-research-full/shared/schemas/research-output.schema.json`
- Modify: `market-research-full/researcher/SKILL.md`
- Modify: `market-research-full/researcher/references/report-template.md`
- Modify: `market-research-full/researcher/references/equity-research.md`
- Modify: `market-research-full/researcher/references/etf-research.md`
- Test: `tests/test_research_output_schema.py`

- [ ] **Step 1: Add failing schema test**

Create `tests/test_research_output_schema.py`:

```python
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "market-research-full" / "shared" / "schemas" / "research-output.schema.json"


def test_research_schema_requires_expanded_analysis_sections():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    required = set(schema["required"])

    assert {
        "technical_analysis",
        "valuation_or_performance",
        "decision_factors",
        "risks",
        "catalysts",
        "source_coverage",
        "calculation_audit",
    } <= required
```

- [ ] **Step 2: Run the schema test to verify failure**

Run:

```bash
python3 -m pytest tests/test_research_output_schema.py -v
```

Expected: FAIL because the current schema requires only legacy fields.

- [ ] **Step 3: Expand `research-output.schema.json`**

Set the top-level required list to:

```json
[
  "symbol",
  "security_type",
  "as_of_date",
  "material_claims",
  "data_gaps",
  "technical_analysis",
  "valuation_or_performance",
  "decision_factors",
  "risks",
  "catalysts",
  "source_coverage",
  "calculation_audit"
]
```

Add each new property as an object or array:

```json
"technical_analysis": {"type": "object", "additionalProperties": true},
"valuation_or_performance": {"type": "object", "additionalProperties": true},
"decision_factors": {"type": "object", "additionalProperties": true},
"risks": {"type": "array", "items": {"type": "object", "additionalProperties": true}},
"catalysts": {"type": "array", "items": {"type": "object", "additionalProperties": true}},
"source_coverage": {"type": "object", "additionalProperties": true},
"calculation_audit": {"type": "array", "items": {"type": "object", "additionalProperties": true}}
```

- [ ] **Step 4: Update report instructions**

In researcher docs, require these markdown sections:

```markdown
## Source Base And Data Quality
## Business Or Fund Profile
## Market And Technical Snapshot
## Financials Or Holdings And Exposures
## Valuation Or Performance Context
## Catalysts And Monitoring Triggers
## Bull/Base/Bear Decision Variables
## Risks And Invalidation Points
## Explicit Data Gaps
```

Require locally computed technical analysis from `normalized/technical_signals.json` and `normalized/prices_daily.json` when provider technical output is missing.

- [ ] **Step 5: Run schema test and docs reference test**

Run:

```bash
python3 -m pytest tests/test_research_output_schema.py tests/test_repository_layout.py -v
```

Expected: PASS.

- [ ] **Step 6: Run all tests and commit**

Run:

```bash
python3 -m pytest tests
git add market-research-full tests
git commit -m "require richer market research outputs"
```

## Task 7: Make Verifier Validate Frozen Research Instead Of Re-Researching

**Files:**

- Modify: `market-research-full/verifier/SKILL.md`
- Modify: `market-research-full/shared/scripts/validate_market_research.py`
- Modify: `tests/test_validate_market_research.py`

- [ ] **Step 1: Add failing validator tests**

Append to `tests/test_validate_market_research.py`:

```python
def test_validator_flags_missing_expanded_research_sections(tmp_path):
    run_dir = tmp_path / "AAPL" / "2026-06-16"
    run_dir.mkdir(parents=True)
    (run_dir / "AAPL-research.md").write_text("# AAPL Research\n", encoding="utf-8")
    (run_dir / "AAPL-research.json").write_text(json.dumps({"symbol": "AAPL", "security_type": "equity", "material_claims": [], "data_gaps": []}), encoding="utf-8")

    result = run_validator(str(run_dir))

    assert result.returncode == 0, result.stderr
    validation = json.loads((run_dir / "AAPL-validation-scaffold.json").read_text(encoding="utf-8"))
    issue_ids = {issue["id"] for issue in validation["issues"]}
    assert "schema-technical_analysis" in issue_ids
    assert "schema-calculation_audit" in issue_ids


def test_validator_scaffold_instruction_forbids_parallel_research(tmp_path):
    run_dir = tmp_path / "AAPL" / "2026-06-16"
    run_dir.mkdir(parents=True)
    (run_dir / "AAPL-research.md").write_text("# AAPL Research\n", encoding="utf-8")
    (run_dir / "AAPL-research.json").write_text(json.dumps({
        "symbol": "AAPL",
        "security_type": "equity",
        "as_of_date": "2026-06-16",
        "material_claims": [],
        "data_gaps": [],
        "technical_analysis": {},
        "valuation_or_performance": {},
        "decision_factors": {},
        "risks": [],
        "catalysts": [],
        "source_coverage": {},
        "calculation_audit": []
    }), encoding="utf-8")

    result = run_validator(str(run_dir))

    assert result.returncode == 0, result.stderr
    validation = json.loads((run_dir / "AAPL-validation-scaffold.json").read_text(encoding="utf-8"))
    assert "without creating a parallel research thesis" in validation["fresh_context_instruction"]
```

- [ ] **Step 2: Run validator tests to verify failure**

Run:

```bash
python3 -m pytest tests/test_validate_market_research.py::test_validator_flags_missing_expanded_research_sections tests/test_validate_market_research.py::test_validator_scaffold_instruction_forbids_parallel_research -v
```

Expected: FAIL.

- [ ] **Step 3: Expand deterministic report issues**

In `validate_market_research.py`, update `deterministic_issues` so it checks:

```python
for field in [
    "symbol",
    "security_type",
    "as_of_date",
    "material_claims",
    "data_gaps",
    "technical_analysis",
    "valuation_or_performance",
    "decision_factors",
    "risks",
    "catalysts",
    "source_coverage",
    "calculation_audit",
]:
```

Keep missing expanded sections at `critical` severity because the producer contract requires them.

- [ ] **Step 4: Update validation instruction text**

In `cmd_validate`, set:

```python
"fresh_context_instruction": "Use this helper output as deterministic lint only; validate cited sources, procedural calculations, markdown/JSON agreement, and conclusions from frozen artifacts without creating a parallel research thesis.",
```

- [ ] **Step 5: Update verifier skill instructions**

In `market-research-full/verifier/SKILL.md`, include this hard rule:

```markdown
The verifier validates the produced report, source registry, deterministic bundle, and cited artifacts. It must not create a competing investment thesis or browse for uncited thesis material. Targeted browsing is allowed only when a cited source is unreachable, ambiguous, or needs source-date confirmation.
```

- [ ] **Step 6: Run validator tests**

Run:

```bash
python3 -m pytest tests/test_validate_market_research.py -v
```

Expected: PASS.

- [ ] **Step 7: Run all tests and commit**

Run:

```bash
python3 -m pytest tests
git add market-research-full tests
git commit -m "tighten frozen artifact validation"
```

## Task 8: Update Loop Contract For Final Reports And Runtime Artifacts

**Files:**

- Modify: `market-research-full/loop-runner/scripts/research_loop.py`
- Modify: `market-research-full/loop-runner/SKILL.md`
- Modify: `tests/test_research_loop.py`

- [ ] **Step 1: Add failing final report path test**

Append to `tests/test_research_loop.py`:

```python
def test_loop_prompts_separate_data_reports_and_runtime(tmp_path):
    out_dir = tmp_path / "runtime-prompts"

    result = run_harness("write-prompts", "AAPL", "--run-dir", "reports/AAPL/2026-06-16", "--output-dir", str(out_dir))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    producer = Path(payload["producer_initial_prompt"]).read_text(encoding="utf-8")
    validator = Path(payload["validator_prompt"]).read_text(encoding="utf-8")
    assert "--data-dir ./data" in producer
    assert "--reports-dir ./reports" in producer
    assert "Write final research markdown and JSON under `reports/AAPL/2026-06-16`" in producer
    assert "$market-research-full verifier reports/AAPL/2026-06-16" in validator
```

- [ ] **Step 2: Run the prompt test to verify failure**

Run:

```bash
python3 -m pytest tests/test_research_loop.py::test_loop_prompts_separate_data_reports_and_runtime -v
```

Expected: FAIL until prompt strings are updated.

- [ ] **Step 3: Update loop prompt text**

In `producer_initial_prompt`, include:

```python
f"Use deterministic evidence first: `python3 market-research-full/shared/scripts/deterministic_research_collector.py fetch {symbol} --data-dir ./data --reports-dir ./reports --as-of YYYY-MM-DD`."
```

```python
f"Use the deterministic bundle under `data/{symbol}/YYYY-MM-DD/` as evidence."
```

```python
f"Write final research markdown and JSON under `{run_dir}`."
```

```python
f"Write producer skill issues to `runtime/{symbol}/YYYY-MM-DD/{symbol}-market-research-full-issues.md`."
```

In `validator_prompt`, include:

```python
f"$market-research-full verifier {run_dir}"
```

- [ ] **Step 4: Run loop tests**

Run:

```bash
python3 -m pytest tests/test_research_loop.py -v
```

Expected: PASS.

- [ ] **Step 5: Run all tests and commit**

Run:

```bash
python3 -m pytest tests
git add market-research-full tests
git commit -m "align loop artifacts with canonical layout"
```

## Task 9: Full Offline Acceptance With Synthetic Equity And ETF

**Files:**

- Create: `tests/test_market_research_full_acceptance.py`
- Modify: `market-research-full/shared/scripts/deterministic_research_collector.py`
- Modify: `market-research-full/shared/scripts/validate_market_research.py`
- Modify: `market-research-full/loop-runner/scripts/research_loop.py`

- [ ] **Step 1: Add offline acceptance test**

Create `tests/test_market_research_full_acceptance.py`:

```python
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = ROOT / "market-research-full" / "shared" / "scripts" / "deterministic_research_collector.py"
VALIDATOR = ROOT / "market-research-full" / "shared" / "scripts" / "validate_market_research.py"


def run_cmd(*args):
    return subprocess.run([sys.executable, *map(str, args)], text=True, capture_output=True, check=False)


def write_research_report(report_dir: Path, symbol: str, security_type: str):
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "symbol": symbol,
        "security_type": security_type,
        "as_of_date": "2026-06-16",
        "material_claims": [],
        "data_gaps": [],
        "technical_analysis": {"trend": "synthetic acceptance fixture"},
        "valuation_or_performance": {"summary": "synthetic acceptance fixture"},
        "decision_factors": {"base_case": "synthetic acceptance fixture"},
        "risks": [],
        "catalysts": [],
        "source_coverage": {"deterministic_bundle": "present"},
        "calculation_audit": [],
    }
    (report_dir / f"{symbol}-research.json").write_text(json.dumps(payload), encoding="utf-8")
    (report_dir / f"{symbol}-research.md").write_text(f"# {symbol} Research\n", encoding="utf-8")


def test_offline_equity_and_etf_acceptance(tmp_path):
    data_dir = tmp_path / "data"
    reports_dir = tmp_path / "reports"

    for symbol, asset_type in [("AAPL", "equity"), ("SPY", "etf")]:
        result = run_cmd(COLLECTOR, "fetch", symbol, "--offline", "--asset-type", asset_type, "--as-of", "2026-06-16", "--data-dir", data_dir, "--reports-dir", reports_dir)
        assert result.returncode == 0, result.stderr
        assert (data_dir / symbol / "2026-06-16" / "manifest.json").exists()
        report_dir = reports_dir / symbol / "2026-06-16"
        write_research_report(report_dir, symbol, asset_type)
        validation = run_cmd(VALIDATOR, report_dir)
        assert validation.returncode == 0, validation.stderr
        validation_payload = json.loads((report_dir / f"{symbol}-validation-scaffold.json").read_text(encoding="utf-8"))
        assert validation_payload["blocking_issue_count"] == 0
```

- [ ] **Step 2: Run acceptance test to verify failure**

Run:

```bash
python3 -m pytest tests/test_market_research_full_acceptance.py -v
```

Expected: FAIL until the collector and validator agree on the new `data/` and `reports/` layout.

- [ ] **Step 3: Fix layout contract mismatches**

Use the failure output to update only the paths or artifact discovery functions involved:

```python
build_bundle(...)
discover(...)
deterministic_bundle_result(...)
latest_producer_run_dir(...)
producer_artifacts_exist(...)
```

Keep deterministic bundles in `data/`. Keep final report and validation artifacts in `reports/`.

- [ ] **Step 4: Run acceptance test**

Run:

```bash
python3 -m pytest tests/test_market_research_full_acceptance.py -v
```

Expected: PASS.

- [ ] **Step 5: Run all tests and commit**

Run:

```bash
python3 -m pytest tests
git add market-research-full tests
git commit -m "verify market research full acceptance flow"
```

## Task 10: Live Smoke And Final Report Iteration

**Files:**

- Runtime output: `data/<SYMBOL>/<YYYY-MM-DD>/`
- Runtime output: `reports/<SYMBOL>/<YYYY-MM-DD>/`
- Runtime output: `runtime/<SYMBOL>/<YYYY-MM-DD>/`
- Modify only if live results expose defects: `market-research-full/**`

- [ ] **Step 1: Run deterministic doctor**

Run:

```bash
python3 market-research-full/shared/scripts/deterministic_research_collector.py doctor --repo-root .
```

Expected: exits `0`, prints configured providers with secrets redacted.

- [ ] **Step 2: Run live deterministic smoke on one equity and one ETF**

Use `MSFT` for equity and `VTI` for ETF unless quota or provider status suggests a different liquid US-listed symbol.

Run:

```bash
python3 market-research-full/shared/scripts/deterministic_research_collector.py fetch MSFT --asset-type equity --as-of 2026-06-20 --data-dir ./data --reports-dir ./reports
python3 market-research-full/shared/scripts/deterministic_research_collector.py fetch VTI --asset-type etf --as-of 2026-06-20 --data-dir ./data --reports-dir ./reports
```

Expected: each command exits `0`; provider authentication failures exit clearly; rate-limit or plan-gated endpoints are preserved in `manifest.json` and `source_manifest.json`.

- [ ] **Step 3: Run loop dry run**

Run:

```bash
python3 market-research-full/loop-runner/scripts/research_loop.py run-batch MSFT VTI --run-root ./runtime --as-of 2026-06-20 --dry-run
```

Expected: prompts and `commands.json` appear under `runtime/MSFT/2026-06-20/iteration-01/` and `runtime/VTI/2026-06-20/iteration-01/`.

- [ ] **Step 4: Run supervised full loop on two equities and two ETFs**

Run:

```bash
python3 market-research-full/loop-runner/scripts/research_loop.py run-batch MSFT AAPL VTI SPY --run-root ./runtime --as-of 2026-06-20 --max-remediation-loops 2
```

Expected: loop summary writes `runtime/research-loop-summary.json`. At least one equity and one ETF finish with no open critical/moderate verifier issues.

- [ ] **Step 5: Review final equity and ETF reports**

Open the best equity and ETF reports under:

```text
reports/<SYMBOL>/2026-06-20/<SYMBOL>-research.md
reports/<SYMBOL>/2026-06-20/<SYMBOL>-research.json
reports/<SYMBOL>/2026-06-20/<SYMBOL>-validation.json
```

Confirm each report has:

- Source base and data quality.
- Business or fund profile.
- Market and technical snapshot.
- Financials or holdings/exposures.
- Valuation or performance context.
- Catalysts and monitoring triggers.
- Bull/base/bear decision variables.
- Risks and invalidation points.
- Explicit data gaps.
- Zero open critical/moderate verifier issues.

- [ ] **Step 6: Patch defects exposed by live runs**

For each defect, add the smallest failing test first in the relevant test file, run it to confirm failure, patch the responsible code or skill docs, run the focused test to confirm pass, then run:

```bash
python3 -m pytest tests
```

Expected: PASS.

- [ ] **Step 7: Commit live-run polish**

Run:

```bash
git add market-research-full tests docs data reports runtime
git commit -m "polish market research full live reports"
```

If `data/`, `reports/`, or `runtime/` contain private/generated artifacts that should not be committed, leave them uncommitted and commit only code, tests, and docs:

```bash
git add market-research-full tests docs
git commit -m "polish market research full live reports"
```

## Self-Review

Spec coverage:

- Six-provider documentation audit: Task 4.
- Deterministic unique data first: Tasks 4 and 5.
- Researcher uses all available deterministic/procedural data: Task 6.
- Big-bang `market-research-full` cleanup: Tasks 1 and 2.
- `data`/`reports`/`runtime` separation: Tasks 3, 8, and 9.
- Richer ECH-style report requirements and technical analysis: Task 6.
- Verifier validates frozen research instead of parallel research: Task 7.
- Full testing and live loop on ETF/equity symbols: Tasks 9 and 10.

Placeholder scan:

- No unresolved placeholder text or unspecified test commands are intentionally present.

Type and path consistency:

- Canonical script path is `market-research-full/shared/scripts/`.
- Canonical deterministic output path is `data/<SYMBOL>/<YYYY-MM-DD>/`.
- Canonical final report and validation path is `reports/<SYMBOL>/<YYYY-MM-DD>/`.
- Canonical runtime path is `runtime/<SYMBOL>/<YYYY-MM-DD>/`.
- Canonical skill invocation is `$market-research-full`.
