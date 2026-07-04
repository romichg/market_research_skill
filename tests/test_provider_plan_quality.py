from pathlib import Path
import importlib.util
import json


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


def test_price_live_fetch_selects_highest_priority_provider(tmp_path):
    c = load_module()
    plan = c.default_endpoint_plan(["tiingo", "eodhd", "alphavantage", "twelve_data"])
    # No cache anywhere: the highest-priority price provider fetches, others are suppressed.
    assert c.price_provider_to_live_fetch(tmp_path, "AAPL", plan) == "tiingo"


def test_price_live_fetch_skips_when_top_priority_cache_exists(tmp_path):
    c = load_module()
    plan = c.default_endpoint_plan(["tiingo", "eodhd", "alphavantage", "twelve_data"])
    c.write_raw(
        tmp_path,
        "AAPL",
        "tiingo",
        "prices",
        {"startDate": "2021-01-01", "endDate": "2026-06-16"},
        [{"date": "2026-06-15", "adjClose": 100}],
        source_url="https://api.tiingo.com/tiingo/daily/AAPL/prices",
    )
    # Cached top-priority prices satisfy normalization, so nothing needs a live price call.
    assert c.price_provider_to_live_fetch(tmp_path, "AAPL", plan) is None


def test_price_live_fetch_promotes_next_provider_when_top_priority_absent(tmp_path):
    c = load_module()
    plan = c.default_endpoint_plan(["eodhd", "alphavantage", "twelve_data"])
    assert c.price_provider_to_live_fetch(tmp_path, "AAPL", plan) == "eodhd"


def test_fetch_suppresses_duplicate_live_price_calls(tmp_path, monkeypatch):
    c = load_module()
    calls = []

    def fake_http_json(url, headers=None, timeout=20, retry_policy=None, provider=None):
        calls.append(url)
        return {} if "fundamentals" in url or "OVERVIEW" in url else []

    monkeypatch.setattr(c, "http_json", fake_http_json)
    monkeypatch.setattr(c.time, "sleep", lambda seconds: None)
    config = c.ProviderConfig(
        values={
            "TIINGO_API_TOKEN": "tiingo-secret",
            "EODHD_API_KEY": "eod-secret",
            "ALPHAVANTAGE_API_KEY": "av-secret",
        },
        docs={},
        limits={},
        loaded_files=[],
    )

    class Args:
        repo_root = str(tmp_path)
        symbol = "AAPL"
        as_of = "2026-06-16"
        providers = "tiingo,eodhd,alphavantage"
        offline = False
        refresh = True
        provider_endpoints = None
        max_provider_calls = None
        asset_type = "auto"
        data_dir = str(tmp_path / "data")
        reports_dir = str(tmp_path / "reports")
        runtime_dir = str(tmp_path / "runtime")
        cache_dir = str(tmp_path / "cache")
        command = "fetch"
        metrics_json = None

    monkeypatch.setattr(c, "load_env_files", lambda root: config)
    c.cmd_fetch(Args())

    # Only Tiingo (highest priority) should live-fetch prices.
    assert any("/tiingo/daily/AAPL/prices" in url for url in calls)
    assert not any("/eod/AAPL.US" in url for url in calls)
    assert not any("TIME_SERIES_DAILY_ADJUSTED" in url for url in calls)


def _seed_reusable_overview(c, cache_root):
    c.write_raw(
        cache_root,
        "AAPL",
        "alphavantage",
        "overview",
        {"function": "OVERVIEW", "symbol": "AAPL"},
        {"Symbol": "AAPL", "MarketCapitalization": "123"},
        source_url="https://www.alphavantage.co/query",
    )


def test_endpoints_within_budget_keeps_cached_endpoint_free_of_charge(tmp_path):
    # G1: a reusable cached endpoint must stay in the plan without consuming budget, so an expensive
    # cached endpoint early in ENDPOINT_BUDGET_PRIORITY (overview, cost 10) no longer eats the whole
    # budget on a call that never happens. Budget 10 then also buys the next affordable uncached ones.
    c = load_module()
    _seed_reusable_overview(c, tmp_path)
    endpoints = {"overview", "income_statement", "balance_sheet", "cash_flow", "earnings", "etf_profile", "news_sentiment"}
    allowed = c.endpoints_within_budget(tmp_path, "AAPL", "alphavantage", 10, endpoints=endpoints)
    assert allowed == {"overview", "income_statement", "balance_sheet"}


def test_fetch_trims_to_cached_plus_affordable_uncached_endpoints(tmp_path, monkeypatch):
    # G1 end-to-end: cached overview + suppressed prices + budget 10 → alphavantage "fetches" the
    # cached overview (served from cache) plus the highest-priority uncached endpoints within budget.
    c = load_module()
    _seed_reusable_overview(c, tmp_path / "cache")
    calls = []

    def fake_fetch(symbol, provider, as_of, cache_root, config, refresh=False, endpoints=None):
        calls.append((provider, tuple(sorted(endpoints or []))))
        return []

    monkeypatch.setattr(c, "fetch_provider", fake_fetch)
    args = type(
        "Args",
        (),
        {
            "repo_root": str(tmp_path),
            "symbol": "AAPL",
            "as_of": "2026-06-01",
            "data_dir": str(tmp_path / "data"),
            "cache_dir": str(tmp_path / "cache"),
            "reports_dir": str(tmp_path / "reports"),
            "providers": "tiingo,alphavantage",
            "max_provider_calls": ["alphavantage=10"],
            "offline": False,
            "refresh": False,
            "asset_type": "auto",
        },
    )()

    c.cmd_fetch(args)

    by_provider = dict(calls)
    assert by_provider["alphavantage"] == ("balance_sheet", "income_statement", "overview")
    manifest = json.loads((tmp_path / "data" / "AAPL" / "2026-06-01" / "manifest.json").read_text(encoding="utf-8"))
    assert any("Limited alphavantage" in warning for warning in manifest["warnings"])
