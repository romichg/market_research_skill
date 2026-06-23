import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "market-research" / "shared" / "scripts" / "deterministic_research_collector.py"
DETERMINISTIC_SCHEMA = ROOT / "market-research" / "shared" / "schemas" / "deterministic-bundle.schema.json"
PROVIDER_MAP = ROOT / "market-research" / "researcher" / "references" / "provider-data-map.md"


def load_module():
    spec = importlib.util.spec_from_file_location("deterministic_research_collector", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def run_cli(*args, cwd=None, env=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_env_starter_parsing_redacts_secrets_and_detects_providers(tmp_path):
    module = load_module()
    env_file = tmp_path / ".env-starter"
    env_file.write_text(
        "\n".join(
            [
                "Twelve Data",
                "API Token: twelve-secret",
                "Docs:",
                "https://twelvedata.com/docs",
                "Limits:",
                "8 credits per minute",
                "",
                "SEC_USER_AGENT=person@example.com",
                "TIINGO_API_TOKEN=tiingo-secret",
            ]
        ),
        encoding="utf-8",
    )

    config = module.load_env_files(tmp_path)

    assert config.values["SEC_USER_AGENT"] == "person@example.com"
    assert config.values["TWELVE_DATA_API_KEY"] == "twelve-secret"
    assert config.values["TIINGO_API_TOKEN"] == "tiingo-secret"
    assert config.docs["twelve_data"] == ["https://twelvedata.com/docs"]
    assert "8 credits per minute" in config.limits["twelve_data"]
    assert module.redact("https://x.test?apikey=twelve-secret&token=tiingo-secret", config) == "https://x.test?apikey=REDACTED&token=REDACTED"
    assert set(module.configured_providers(config)) >= {"sec", "twelve_data", "tiingo"}


def test_cache_key_is_stable_and_order_independent():
    module = load_module()

    first = module.cache_key("tiingo", "prices", {"b": "2", "a": "1"})
    second = module.cache_key("tiingo", "prices", {"a": "1", "b": "2"})

    assert first == second
    assert first.startswith("tiingo_prices_")


def test_generate_env_example_contains_no_real_values(tmp_path):
    module = load_module()
    config = module.ProviderConfig(
        values={"SEC_USER_AGENT": "person@example.com", "TIINGO_API_TOKEN": "secret"},
        docs={},
        limits={},
        loaded_files=[],
    )

    output = module.write_env_example(tmp_path, config)
    text = output.read_text(encoding="utf-8")

    assert "SEC_USER_AGENT=" in text
    assert "HTTP_USER_AGENT=" in text
    assert "TIINGO_API_TOKEN=" in text
    assert "person@example.com" not in text
    assert "secret" not in text


def test_offline_fetch_builds_bundle_with_provenance_analytics_and_gaps(tmp_path):
    module = load_module()
    cache = tmp_path / "cache"
    output_root = tmp_path / "data"
    symbol = "AAPL"
    as_of = "2026-06-01"
    prices = [
        {"date": "2025-06-02", "open": 100, "high": 101, "low": 99, "close": 100, "adjClose": 100, "volume": 1000},
        {"date": "2025-06-03", "open": 101, "high": 102, "low": 100, "close": 101, "adjClose": 101, "volume": 1100},
        {"date": "2025-06-04", "open": 102, "high": 103, "low": 101, "close": 102, "adjClose": 102, "volume": 1200},
        {"date": "2026-05-29", "open": 130, "high": 133, "low": 129, "close": 132, "adjClose": 132, "volume": 2000},
    ]
    module.write_raw(
        cache,
        symbol,
        "sec",
        "submissions",
        {"cik": "0000320193"},
        {"name": "APPLE INC", "tickers": ["AAPL"], "exchanges": ["Nasdaq"], "sic": "3571", "filings": {"recent": {"form": ["10-K"], "accessionNumber": ["0000320193-25-000079"], "filingDate": ["2025-10-31"], "primaryDocument": ["aapl-20250927.htm"]}}},
        source_url="https://data.sec.gov/submissions/CIK0000320193.json",
    )
    module.write_raw(
        cache,
        symbol,
        "eodhd",
        "fundamentals",
        {},
        {"General": {"Name": "Apple Inc", "Exchange": "NASDAQ", "MarketCapitalization": 3000000000000}, "Highlights": {"PERatio": 30}},
        source_url="https://eodhd.example/fundamentals/AAPL.US",
    )
    module.write_raw(
        cache,
        symbol,
        "tiingo",
        "prices",
        {"startDate": "2025-06-01", "endDate": as_of},
        prices,
        source_url="https://api.tiingo.com/tiingo/daily/AAPL/prices",
    )

    bundle = module.build_bundle(symbol, as_of, cache, output_root, providers=["sec", "eodhd", "tiingo"], offline=True)

    bundle_dir = Path(bundle["bundle_dir"])
    identity = json.loads((bundle_dir / "normalized" / "identity.json").read_text(encoding="utf-8"))
    snapshot = json.loads((bundle_dir / "normalized" / "market_snapshot.json").read_text(encoding="utf-8"))
    technicals = json.loads((bundle_dir / "normalized" / "technical_signals.json").read_text(encoding="utf-8"))
    gaps = json.loads((bundle_dir / "gaps.json").read_text(encoding="utf-8"))
    pack = (bundle_dir / "research_input_pack.md").read_text(encoding="utf-8")

    assert identity["company_name"]["value"] == "APPLE INC"
    assert identity["company_name"]["provider"] == "sec"
    assert identity["company_name"]["raw_path"].endswith(".json")
    assert snapshot["latest_close"]["value"] == 132
    assert technicals["sma_20"]["status"] == "insufficient_data"
    assert any(gap["field"] == "short_interest" for gap in gaps["gaps"])
    assert "Latest close: 132" in pack
    assert "Source: tiingo" in pack
    assert "data/cache" not in pack
    assert "raw/tiingo/" in pack


def test_cli_doctor_redacts_secrets(tmp_path):
    (tmp_path / ".env-starter").write_text("Tiingo\nAPI Token: secret-token\nDocs:\nhttps://www.tiingo.com/docs\n", encoding="utf-8")

    result = run_cli("doctor", "--repo-root", str(tmp_path), "--no-network")

    assert result.returncode == 0, result.stderr
    assert "secret-token" not in result.stdout
    assert "tiingo" in result.stdout


def test_fetch_respects_zero_provider_budget(tmp_path, monkeypatch):
    module = load_module()
    calls = []

    def fake_fetch(symbol, provider, as_of, cache_root, config, refresh=False, endpoints=None):
        calls.append(provider)
        return []

    monkeypatch.setattr(module, "fetch_provider", fake_fetch)
    args = type(
        "Args",
        (),
        {
            "repo_root": str(tmp_path),
            "symbol": "AAPL",
            "as_of": "2026-06-01",
            "data_dir": str(tmp_path / "data"),
            "cache_dir": str(tmp_path / "cache"),
            "providers": "sec,tiingo",
            "max_provider_calls": ["sec=0", "tiingo=1"],
            "offline": False,
            "refresh": False,
        },
    )()

    module.cmd_fetch(args)

    assert calls == ["tiingo"]


def test_fetch_trims_provider_to_affordable_endpoints_when_estimated_cost_exceeds_budget(tmp_path, monkeypatch):
    module = load_module()
    calls = []

    def fake_fetch(symbol, provider, as_of, cache_root, config, refresh=False, endpoints=None):
        calls.append((provider, tuple(sorted(endpoints or []))))
        return []

    monkeypatch.setattr(module, "fetch_provider", fake_fetch)
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
            "providers": "eodhd,tiingo",
            "max_provider_calls": ["eodhd=1", "tiingo=1"],
            "offline": False,
            "refresh": False,
            "asset_type": "auto",
        },
    )()

    module.cmd_fetch(args)

    assert calls == [("eodhd", ("news",)), ("tiingo", ("prices",))]
    manifest_path = tmp_path / "data" / "AAPL" / "2026-06-01" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert any("eodhd" in warning and "budget" in warning and "Limited" in warning for warning in manifest["warnings"])


def test_budget_trimmed_endpoint_plan_controls_bundle_outputs(tmp_path, monkeypatch):
    module = load_module()
    cache = tmp_path / "cache"
    module.write_raw(
        cache,
        "AAPL",
        "eodhd",
        "fundamentals",
        {},
        {"General": {"Name": "Stale EODHD Name", "MarketCapitalization": 123}},
        source_url="https://eodhd.example/fundamentals/AAPL.US",
    )

    def fake_fetch(symbol, provider, as_of, cache_root, config, refresh=False, endpoints=None):
        if provider == "eodhd" and endpoints == {"news"}:
            return [
                module.write_raw(
                    cache_root,
                    symbol,
                    "eodhd",
                    "news",
                    {"s": "AAPL.US"},
                    [{"title": "Budgeted EODHD news", "link": "https://example.test/eodhd"}],
                    source_url="https://eodhd.com/api/news?s=AAPL.US",
                )
            ]
        return []

    monkeypatch.setattr(module, "fetch_provider", fake_fetch)
    args = type(
        "Args",
        (),
        {
            "repo_root": str(tmp_path),
            "symbol": "AAPL",
            "as_of": "2026-06-01",
            "data_dir": str(tmp_path / "data"),
            "cache_dir": str(cache),
            "reports_dir": str(tmp_path / "reports"),
            "providers": "eodhd",
            "max_provider_calls": ["eodhd=1"],
            "offline": False,
            "refresh": False,
            "asset_type": "auto",
        },
    )()

    module.cmd_fetch(args)

    bundle_dir = tmp_path / "data" / "AAPL" / "2026-06-01"
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    source_manifest = json.loads((bundle_dir / "source_manifest.json").read_text(encoding="utf-8"))
    identity = json.loads((bundle_dir / "normalized" / "identity.json").read_text(encoding="utf-8"))

    assert manifest["endpoint_plan"]["eodhd"] == ["news"]
    assert [source["endpoint"] for source in source_manifest["sources"]] == ["news"]
    assert "company_name" not in identity


def test_storage_paths_default_to_data_reports_runtime(tmp_path):
    module = load_module()
    config = module.ProviderConfig(values={}, docs={}, limits={}, loaded_files=[])

    paths = module.resolve_storage_paths(tmp_path, config)

    assert paths["data_dir"] == tmp_path / "data"
    assert paths["reports_dir"] == tmp_path / "reports"
    assert paths["runtime_dir"] == tmp_path / "runtime"
    assert paths["cache_dir"] == tmp_path / "data" / "cache"


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


def test_fetch_rejects_runtime_data_dir_for_deterministic_output(tmp_path, monkeypatch, capsys):
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
            "data_dir": str(tmp_path / "runtime"),
            "cache_dir": str(tmp_path / "cache"),
            "reports_dir": str(tmp_path / "reports"),
            "runtime_dir": str(tmp_path / "runtime"),
            "providers": "sec",
            "max_provider_calls": ["sec=3"],
            "offline": False,
            "refresh": False,
            "asset_type": "equity",
        },
    )()

    with pytest.raises(SystemExit) as exc:
        module.cmd_fetch(args)

    assert exc.value.code == 2
    assert "Deterministic output root must be a directory named data" in capsys.readouterr().err
    assert not (tmp_path / "runtime" / "AAPL" / "2026-06-16" / "manifest.json").exists()


def test_fetch_rejects_reports_data_dir_for_deterministic_output(tmp_path, monkeypatch, capsys):
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
            "data_dir": str(tmp_path / "reports"),
            "cache_dir": str(tmp_path / "runtime" / "_cache"),
            "reports_dir": str(tmp_path / "reports"),
            "runtime_dir": str(tmp_path / "runtime"),
            "providers": "sec",
            "max_provider_calls": ["sec=3"],
            "offline": False,
            "refresh": False,
            "asset_type": "equity",
        },
    )()

    with pytest.raises(SystemExit) as exc:
        module.cmd_fetch(args)

    assert exc.value.code == 2
    assert "Deterministic output root must be a directory named data" in capsys.readouterr().err
    assert not (tmp_path / "reports" / "AAPL" / "2026-06-16" / "manifest.json").exists()


@pytest.mark.parametrize(
    ("as_of", "artifact_path"),
    [
        ("../../reports/AAPL/2026-06-16", Path("reports/AAPL/2026-06-16/manifest.json")),
        ("2026-99-99", Path("data/AAPL/2026-99-99/manifest.json")),
        ("2026-06-16;touch", Path("data/AAPL/2026-06-16;touch/manifest.json")),
    ],
)
def test_fetch_rejects_invalid_as_of_path_components(tmp_path, monkeypatch, capsys, as_of, artifact_path):
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
            "as_of": as_of,
            "data_dir": str(tmp_path / "data"),
            "cache_dir": str(tmp_path / "cache"),
            "reports_dir": str(tmp_path / "reports"),
            "runtime_dir": str(tmp_path / "runtime"),
            "providers": "sec",
            "max_provider_calls": ["sec=3"],
            "offline": False,
            "refresh": False,
            "asset_type": "equity",
        },
    )()

    with pytest.raises(SystemExit) as exc:
        module.cmd_fetch(args)

    assert exc.value.code == 2
    assert "Invalid as-of" in capsys.readouterr().err
    assert not (tmp_path / artifact_path).exists()


@pytest.mark.parametrize(
    ("symbol", "artifact_path"),
    [
        (".", Path("data/2026-06-16/manifest.json")),
        ("..", Path("2026-06-16/manifest.json")),
    ],
)
def test_fetch_rejects_dot_symbol_path_components(tmp_path, monkeypatch, capsys, symbol, artifact_path):
    module = load_module()

    def fake_fetch(symbol, provider, as_of, cache_root, config, refresh=False, endpoints=None):
        return []

    monkeypatch.setattr(module, "fetch_provider", fake_fetch)
    args = type(
        "Args",
        (),
        {
            "repo_root": str(tmp_path),
            "symbol": symbol,
            "as_of": "2026-06-16",
            "data_dir": str(tmp_path / "data"),
            "cache_dir": str(tmp_path / "cache"),
            "reports_dir": str(tmp_path / "reports"),
            "runtime_dir": str(tmp_path / "runtime"),
            "providers": "sec",
            "max_provider_calls": ["sec=3"],
            "offline": False,
            "refresh": False,
            "asset_type": "equity",
        },
    )()

    with pytest.raises(SystemExit) as exc:
        module.cmd_fetch(args)

    assert exc.value.code == 2
    assert "Invalid symbol" in capsys.readouterr().err
    assert not (tmp_path / artifact_path).exists()


def test_fetch_accepts_project_under_runtime_parent(tmp_path, monkeypatch):
    module = load_module()
    project = tmp_path / "runtime" / "project"

    def fake_fetch(symbol, provider, as_of, cache_root, config, refresh=False, endpoints=None):
        return []

    monkeypatch.setattr(module, "fetch_provider", fake_fetch)
    args = type(
        "Args",
        (),
        {
            "repo_root": str(project),
            "symbol": "AAPL",
            "as_of": "2026-06-16",
            "data_dir": str(project / "data"),
            "cache_dir": str(project / "cache"),
            "reports_dir": str(project / "reports"),
            "runtime_dir": str(project / "runtime"),
            "providers": "sec",
            "max_provider_calls": ["sec=3"],
            "offline": False,
            "refresh": False,
            "asset_type": "equity",
        },
    )()

    module.cmd_fetch(args)

    assert (project / "data" / "AAPL" / "2026-06-16" / "manifest.json").exists()


def test_endpoint_plan_avoids_duplicate_price_fetches(tmp_path, monkeypatch):
    module = load_module()
    calls = []

    def fake_http_json(url, headers=None, timeout=20, retry_policy=None, provider=None):
        calls.append(url)
        return {} if "fundamentals" in url or "OVERVIEW" in url else []

    monkeypatch.setattr(module, "http_json", fake_http_json)
    config = module.ProviderConfig(
        values={
            "EODHD_API_KEY": "eod-secret",
            "ALPHAVANTAGE_API_KEY": "av-secret",
            "TIINGO_API_TOKEN": "tiingo-secret",
        },
        docs={},
        limits={},
        loaded_files=[],
    )

    module.fetch_provider("QBTS", "eodhd", "2026-06-17", tmp_path, config, refresh=True, endpoints={"fundamentals"})
    module.fetch_provider("QBTS", "alphavantage", "2026-06-17", tmp_path, config, refresh=True, endpoints={"overview"})
    module.fetch_provider("QBTS", "tiingo", "2026-06-17", tmp_path, config, refresh=True, endpoints={"prices"})

    assert any("/fundamentals/QBTS.US" in url for url in calls)
    assert any("function=OVERVIEW" in url for url in calls)
    assert any("/tiingo/daily/QBTS/prices" in url for url in calls)
    assert not any("/eod/QBTS.US" in url for url in calls)
    assert not any("TIME_SERIES_DAILY_ADJUSTED" in url for url in calls)


def test_default_endpoint_plan_includes_unique_provider_data():
    module = load_module()

    plan = module.default_endpoint_plan(["tiingo", "eodhd", "alphavantage", "twelve_data", "marketaux", "fmp"])

    assert plan["tiingo"] == {"metadata", "prices"}
    assert {"fundamentals", "news", "historical_market_cap"} <= plan["eodhd"]
    assert {"overview", "income_statement", "balance_sheet", "cash_flow", "earnings", "etf_profile", "news_sentiment"} <= plan["alphavantage"]
    assert {"quote", "profile"} <= plan["twelve_data"]
    assert plan["marketaux"] == {"news"}
    assert {"profile", "key_metrics_ttm", "ratios_ttm", "income_statement", "balance_sheet", "cash_flow", "stock_news", "press_releases", "dividends", "earnings", "splits", "insider_trading", "insider_statistics", "etf_holdings"} <= plan["fmp"]


def test_default_provider_budgets_cover_expanded_endpoint_plans(tmp_path):
    module = load_module()
    plan = module.default_endpoint_plan(["tiingo", "eodhd", "alphavantage", "twelve_data", "marketaux", "fmp"])

    for provider in ["eodhd", "alphavantage"]:
        budget = module.provider_call_budget(provider, {})
        endpoints = plan[provider]

        assert module.estimated_provider_call_cost(tmp_path, "AAPL", provider, endpoints=endpoints) <= budget
        assert module.endpoints_within_budget(tmp_path, "AAPL", provider, budget, endpoints=endpoints) == endpoints


def test_endpoint_budget_trimming_keeps_affordable_later_endpoints(tmp_path):
    module = load_module()

    endpoints = {"overview", "income_statement", "earnings", "etf_profile", "news_sentiment"}

    assert module.endpoints_within_budget(tmp_path, "AAPL", "alphavantage", 3, endpoints=endpoints) == {"earnings", "etf_profile", "news_sentiment"}


def test_endpoint_plan_filters_cached_raw_and_price_normalization(tmp_path):
    module = load_module()
    cache = tmp_path / "cache"
    module.write_raw(cache, "QBTS", "eodhd", "fundamentals", {}, {"General": {"Name": "D-Wave Quantum Inc.", "MarketCapitalization": 100}}, source_url="https://eodhd.example/fundamentals/QBTS.US")
    module.write_raw(cache, "QBTS", "eodhd", "prices", {}, [{"date": "2026-06-16", "adjusted_close": 10}], source_url="https://eodhd.example/eod/QBTS.US")

    result = module.build_bundle(
        "QBTS",
        "2026-06-17",
        cache,
        tmp_path / "data",
        providers=["eodhd"],
        endpoint_plan={"eodhd": {"fundamentals"}},
        asset_type="equity",
    )

    bundle_dir = Path(result["bundle_dir"])
    source_manifest = json.loads((bundle_dir / "source_manifest.json").read_text(encoding="utf-8"))
    prices = json.loads((bundle_dir / "normalized" / "prices_daily.json").read_text(encoding="utf-8"))

    assert [source["endpoint"] for source in source_manifest["sources"]] == ["fundamentals"]
    assert prices["prices"] == []


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


def test_malformed_ok_expanded_payloads_do_not_crash(tmp_path):
    module = load_module()
    cache = tmp_path / "cache"
    module.write_raw(
        cache,
        "SPY",
        "alphavantage",
        "news_sentiment",
        {"function": "NEWS_SENTIMENT", "tickers": "SPY"},
        [],
        source_url="https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers=SPY",
    )
    module.write_raw(
        cache,
        "SPY",
        "twelve_data",
        "quote",
        {"symbol": "SPY"},
        [],
        source_url="https://api.twelvedata.com/quote?symbol=SPY",
    )

    news = module.normalize_news(cache, "SPY", providers=["alphavantage"], endpoint_plan={"alphavantage": {"news_sentiment"}})
    snapshot = module.normalize_market_snapshot(cache, "SPY", [], None, "", "", providers=["twelve_data"], endpoint_plan={"twelve_data": {"quote"}})

    assert news == {"items": [], "status": "empty"}
    assert snapshot == {}


def test_news_normalization_includes_eodhd_and_consistent_provenance(tmp_path):
    module = load_module()
    cache = tmp_path / "cache"
    module.write_raw(
        cache,
        "AAPL",
        "marketaux",
        "news",
        {"symbols": "AAPL"},
        {"data": [{"title": "MarketAux headline", "source": "MarketAux Source", "url": "https://example.test/marketaux", "published_at": "2026-06-16"}]},
        source_url="https://api.marketaux.com/v1/news/all?symbols=AAPL",
    )
    module.write_raw(
        cache,
        "AAPL",
        "alphavantage",
        "news_sentiment",
        {"function": "NEWS_SENTIMENT", "tickers": "AAPL"},
        {"feed": [{"title": "Alpha headline", "source": "Alpha Source", "url": "https://example.test/alpha", "time_published": "20260616T120000"}]},
        source_url="https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers=AAPL",
    )
    module.write_raw(
        cache,
        "AAPL",
        "fmp",
        "stock_news",
        {"symbols": "AAPL"},
        [{"title": "FMP headline", "site": "FMP Source", "url": "https://example.test/fmp", "publishedDate": "2026-06-16"}],
        source_url="https://financialmodelingprep.com/stable/news/stock?symbols=AAPL",
    )
    module.write_raw(
        cache,
        "AAPL",
        "eodhd",
        "news",
        {"s": "AAPL.US"},
        [{"title": "EODHD headline", "source": "EODHD Source", "link": "https://example.test/eodhd", "date": "2026-06-16"}],
        source_url="https://eodhd.com/api/news?s=AAPL.US",
    )

    news = module.normalize_news(
        cache,
        "AAPL",
        providers=["marketaux", "alphavantage", "fmp", "eodhd"],
        endpoint_plan={"marketaux": {"news"}, "alphavantage": {"news_sentiment"}, "fmp": {"stock_news"}, "eodhd": {"news"}},
    )

    assert {item["provider"] for item in news["items"]} == {"marketaux", "alphavantage", "fmp", "eodhd"}
    for item in news["items"]:
        assert {"provider", "endpoint", "source_url", "raw_path", "status"} <= set(item)
        assert item["status"] == "ok"
        assert item["source_url"]
        assert item["raw_path"].endswith(".json")


def test_twelve_data_profile_normalizes_identity_fields(tmp_path):
    module = load_module()
    cache = tmp_path / "cache"
    module.write_raw(
        cache,
        "SPY",
        "twelve_data",
        "profile",
        {"symbol": "SPY"},
        {"name": "SPDR S&P 500 ETF Trust", "exchange": "NYSE Arca", "type": "ETF", "currency": "USD"},
        source_url="https://api.twelvedata.com/profile?symbol=SPY",
    )

    identity = module.normalize_identity(cache, "SPY", providers=["twelve_data"], endpoint_plan={"twelve_data": {"profile"}})

    assert identity["company_name"]["value"] == "SPDR S&P 500 ETF Trust"
    assert identity["company_name"]["provider"] == "twelve_data"
    assert identity["exchange"]["value"] == "NYSE Arca"
    assert identity["asset_type"]["value"] == "etf"
    assert identity["currency"]["value"] == "USD"


def test_marketaux_fetch_sends_general_http_user_agent_header(tmp_path, monkeypatch):
    module = load_module()
    seen = []

    def fake_http_json(url, headers=None, timeout=20, retry_policy=None, provider=None):
        seen.append({"url": url, "headers": headers or {}})
        return {"data": []}

    monkeypatch.setattr(module, "http_json", fake_http_json)
    config = module.ProviderConfig(
        values={
            "MARKETAUX_API_TOKEN": "marketaux-secret",
            "HTTP_USER_AGENT": "general-agent/1.0",
            "SEC_USER_AGENT": "sec-agent/1.0 sec@example.com",
        },
        docs={},
        limits={},
        loaded_files=[],
    )

    paths = module.fetch_provider("AAPL", "marketaux", "2026-06-19", tmp_path, config, refresh=True, endpoints={"news"})

    assert len(paths) == 1
    assert seen[0]["headers"]["Accept"] == "application/json"
    assert seen[0]["headers"]["User-Agent"] == "general-agent/1.0"
    assert "sec-agent" not in seen[0]["headers"]["User-Agent"]
    payload = json.loads(paths[0].read_text(encoding="utf-8"))
    assert "marketaux-secret" in seen[0]["url"]
    assert "marketaux-secret" not in payload["provider_result"]["url"]


def test_sec_fetch_uses_descriptive_user_agent_without_custom_config(tmp_path, monkeypatch):
    module = load_module()
    seen = []

    def fake_http_json(url, headers=None, timeout=20, retry_policy=None, provider=None):
        seen.append({"url": url, "headers": headers or {}})
        return {"0": {"ticker": "AAPL", "cik_str": 320193, "title": "Apple Inc."}}

    monkeypatch.setattr(module, "http_json", fake_http_json)
    config = module.ProviderConfig(values={}, docs={}, limits={}, loaded_files=[])

    paths = module.fetch_provider("AAPL", "sec", "2026-06-19", tmp_path, config, refresh=True, endpoints={"company_tickers"})

    assert len(paths) == 1
    assert seen[0]["url"].endswith("company_tickers.json")
    assert seen[0]["headers"]["User-Agent"] == module.DEFAULT_SEC_USER_AGENT
    assert "@" in seen[0]["headers"]["User-Agent"]
    assert "Mozilla/5.0" not in seen[0]["headers"]["User-Agent"]


def test_marketaux_fetch_uses_browser_like_default_without_general_http_user_agent(tmp_path, monkeypatch):
    module = load_module()
    seen = []

    def fake_http_json(url, headers=None, timeout=20, retry_policy=None, provider=None):
        seen.append(headers or {})
        return {"data": []}

    monkeypatch.setattr(module, "http_json", fake_http_json)
    config = module.ProviderConfig(values={"MARKETAUX_API_TOKEN": "marketaux-secret"}, docs={}, limits={}, loaded_files=[])

    module.fetch_provider("AAPL", "marketaux", "2026-06-19", tmp_path, config, refresh=True, endpoints={"news"})

    assert seen[0]["User-Agent"] == module.DEFAULT_HTTP_USER_AGENT
    assert "Mozilla/5.0" in seen[0]["User-Agent"]


def test_sec_fetch_ignores_general_http_user_agent(tmp_path, monkeypatch):
    module = load_module()
    seen = []

    def fake_http_json(url, headers=None, timeout=20, retry_policy=None, provider=None):
        seen.append(headers or {})
        return {"0": {"ticker": "AAPL", "cik_str": 320193, "title": "Apple Inc."}}

    monkeypatch.setattr(module, "http_json", fake_http_json)
    config = module.ProviderConfig(
        values={
            "HTTP_USER_AGENT": "general-agent/1.0",
            "SEC_USER_AGENT": "sec-agent/1.0 sec@example.com",
        },
        docs={},
        limits={},
        loaded_files=[],
    )

    module.fetch_provider("AAPL", "sec", "2026-06-19", tmp_path, config, refresh=True, endpoints={"company_tickers"})

    assert seen[0]["User-Agent"] == "sec-agent/1.0 sec@example.com"
    assert "general-agent" not in seen[0]["User-Agent"]


def test_browser_like_legacy_project_user_agent_is_not_sent(tmp_path, monkeypatch):
    module = load_module()
    seen = []

    def fake_http_json(url, headers=None, timeout=20, retry_policy=None, provider=None):
        seen.append(headers or {})
        return {"0": {"ticker": "AAPL", "cik_str": 320193, "title": "Apple Inc."}}

    monkeypatch.setattr(module, "http_json", fake_http_json)
    config = module.ProviderConfig(
        values={"SEC_USER_AGENT": "Mozilla/5.0 market-research-skill deterministic collector"},
        docs={},
        limits={},
        loaded_files=[],
    )

    module.fetch_provider("AAPL", "sec", "2026-06-19", tmp_path, config, refresh=True, endpoints={"company_tickers"})

    assert seen[0]["User-Agent"] == module.DEFAULT_SEC_USER_AGENT
    assert "Chrome/" not in seen[0]["User-Agent"]


def test_sec_user_agent_uses_sec_env_not_http_env(tmp_path, monkeypatch):
    module = load_module()
    monkeypatch.delenv("HTTP_USER_AGENT", raising=False)
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    (tmp_path / ".env").write_text(
        "HTTP_USER_AGENT=general-agent/1.0\n"
        "SEC_USER_AGENT=market-research-skill/1.0 research@example.com\n",
        encoding="utf-8",
    )
    config = module.load_env_files(tmp_path)

    assert module.sec_user_agent(config) == "market-research-skill/1.0 research@example.com"


def test_sec_user_agent_rejects_browser_like_legacy_override(tmp_path, monkeypatch):
    module = load_module()
    monkeypatch.delenv("HTTP_USER_AGENT", raising=False)
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    (tmp_path / ".env").write_text(
        "SEC_USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0 Safari/537.36\n",
        encoding="utf-8",
    )
    config = module.load_env_files(tmp_path)

    assert module.sec_user_agent(config) == module.DEFAULT_SEC_USER_AGENT
    assert "@" in module.sec_user_agent(config)


def test_general_http_user_agent_defaults_to_browser_like(tmp_path, monkeypatch):
    module = load_module()
    monkeypatch.delenv("HTTP_USER_AGENT", raising=False)
    (tmp_path / ".env").write_text("SEC_USER_AGENT=market-research-skill/1.0 research@example.com\n", encoding="utf-8")
    config = module.load_env_files(tmp_path)

    assert module.http_user_agent(config) == module.DEFAULT_HTTP_USER_AGENT
    assert "Mozilla/5.0" in module.http_user_agent(config)


def test_eodhd_news_uses_country_qualified_symbol(tmp_path, monkeypatch):
    module = load_module()
    seen = []

    def fake_http_json(url, headers=None, timeout=20, retry_policy=None, provider=None):
        seen.append(url)
        return []

    monkeypatch.setattr(module, "http_json", fake_http_json)
    config = module.ProviderConfig(values={"EODHD_API_KEY": "eod-secret"}, docs={}, limits={}, loaded_files=[])

    module.fetch_provider("AAPL", "eodhd", "2026-06-17", tmp_path, config, refresh=True, endpoints={"news"})

    assert len(seen) == 1
    assert "s=AAPL.US" in seen[0]


def test_fmp_fetches_and_normalizes_unique_equity_data(tmp_path, monkeypatch):
    module = load_module()
    cache = tmp_path / "cache"
    seen = []

    def fake_http_json(url, headers=None, timeout=20, retry_policy=None, provider=None):
        seen.append(url)
        if "/stable/profile" in url:
            return [{"companyName": "D-Wave Quantum Inc.", "exchangeShortName": "NYSE", "industry": "Computer Hardware", "mktCap": 1230000000, "beta": 1.4}]
        if "key-metrics-ttm" in url:
            return [{"revenuePerShareTTM": 1.2, "netIncomePerShareTTM": -0.4, "enterpriseValueTTM": 1400000000}]
        if "ratios-ttm" in url:
            return [{"grossProfitMarginTTM": 0.52, "currentRatioTTM": 4.1}]
        if "income-statement" in url:
            return [{"date": "2025-12-31", "revenue": 100000000, "netIncome": -50000000, "eps": -0.2}]
        if "balance-sheet-statement" in url:
            return [{"date": "2025-12-31", "totalAssets": 400000000, "totalDebt": 20000000}]
        if "cash-flow-statement" in url:
            return [{"date": "2025-12-31", "freeCashFlow": -60000000}]
        if "/news/stock" in url:
            return [{"title": "D-Wave announces customer win", "site": "Example News", "url": "https://example.test/news", "publishedDate": "2026-06-10"}]
        if "/news/press-releases" in url:
            return [{"title": "D-Wave press release", "url": "https://example.test/pr", "publishedDate": "2026-06-09"}]
        if "insider-trading/statistics" in url:
            return [{"symbol": "QBTS", "totalPurchases": 1, "totalSales": 2}]
        return []

    monkeypatch.setattr(module, "http_json", fake_http_json)
    config = module.ProviderConfig(values={"FMP_API_KEY": "fmp-secret"}, docs={}, limits={}, loaded_files=[])

    paths = module.fetch_provider(
        "QBTS",
        "fmp",
        "2026-06-17",
        cache,
        config,
        refresh=True,
        endpoints={"profile", "key_metrics_ttm", "ratios_ttm", "income_statement", "balance_sheet", "cash_flow", "stock_news", "press_releases", "insider_statistics"},
    )

    assert len(paths) == 9
    assert all("fmp-secret" in url for url in seen)
    assert all("fmp-secret" not in json.loads(path.read_text(encoding="utf-8"))["provider_result"]["url"] for path in paths)

    result = module.build_bundle("QBTS", "2026-06-17", cache, tmp_path / "data", providers=["fmp"], asset_type="equity")
    bundle_dir = Path(result["bundle_dir"])
    identity = json.loads((bundle_dir / "normalized" / "identity.json").read_text(encoding="utf-8"))
    snapshot = json.loads((bundle_dir / "normalized" / "market_snapshot.json").read_text(encoding="utf-8"))
    fundamentals = json.loads((bundle_dir / "normalized" / "equity_fundamentals.json").read_text(encoding="utf-8"))
    news = json.loads((bundle_dir / "normalized" / "news.json").read_text(encoding="utf-8"))
    insiders = json.loads((bundle_dir / "normalized" / "equity_insiders.json").read_text(encoding="utf-8"))

    assert identity["company_name"]["provider"] == "fmp"
    assert identity["industry"]["value"] == "Computer Hardware"
    assert snapshot["market_capitalization"]["provider"] == "fmp"
    assert fundamentals["latest_revenue"]["value"] == 100000000
    assert fundamentals["gross_profit_margin_ttm"]["provider"] == "fmp"
    assert news["items"][0]["provider"] == "fmp"
    assert insiders["statistics"]["provider"] == "fmp"


def test_non_ok_fmp_news_raw_does_not_create_empty_news_items(tmp_path):
    module = load_module()
    cache = tmp_path / "cache"
    module.write_raw(
        cache,
        "QBTS",
        "fmp",
        "stock_news",
        {"symbols": "QBTS", "limit": "10"},
        {},
        source_url="https://financialmodelingprep.com/stable/news/stock?symbols=QBTS&limit=10",
        status="plan_gated",
        error="HTTP 402",
    )

    news = module.normalize_news(cache, "QBTS", providers=["fmp"], endpoint_plan={"fmp": {"stock_news"}})

    assert news == {"items": [], "status": "empty"}


def test_semantic_error_cached_payloads_do_not_normalize_provider_facts(tmp_path):
    module = load_module()
    cache = tmp_path / "cache"
    module.write_raw(
        cache,
        "AAPL",
        "eodhd",
        "fundamentals",
        {},
        {"Error Message": "Invalid API token", "General": {"Name": "Should Not Normalize"}, "Highlights": {"PERatio": 99}},
        source_url="https://eodhd.example/fundamentals/AAPL.US",
        status="ok",
    )
    module.write_raw(
        cache,
        "AAPL",
        "alphavantage",
        "overview",
        {"function": "OVERVIEW", "symbol": "AAPL"},
        {"Information": "API rate limit reached.", "MarketCapitalization": "123", "RevenueTTM": "456"},
        source_url="https://alphavantage.example/query?function=OVERVIEW&symbol=AAPL",
        status="ok",
    )
    module.write_raw(
        cache,
        "AAPL",
        "fmp",
        "profile",
        {"symbol": "AAPL"},
        {"Error Message": "Invalid API key", "companyName": "Should Not Normalize", "mktCap": 789},
        source_url="https://financialmodelingprep.com/stable/profile?symbol=AAPL",
        status="ok",
    )
    module.write_raw(
        cache,
        "AAPL",
        "fmp",
        "stock_news",
        {"symbols": "AAPL"},
        {"Error Message": "Invalid API key", "title": "Should Not Normalize", "url": "https://example.test/bad"},
        source_url="https://financialmodelingprep.com/stable/news/stock?symbols=AAPL",
        status="ok",
    )
    module.write_raw(
        cache,
        "AAPL",
        "fmp",
        "dividends",
        {"symbol": "AAPL"},
        {"Error Message": "Invalid API key", "date": "2026-06-01", "dividend": 1.23},
        source_url="https://financialmodelingprep.com/stable/dividends?symbol=AAPL",
        status="ok",
    )
    module.write_raw(
        cache,
        "AAPL",
        "fmp",
        "insider_trading",
        {"symbol": "AAPL"},
        {"Error Message": "Invalid API key", "transactionDate": "2026-06-01"},
        source_url="https://financialmodelingprep.com/stable/insider-trading?symbol=AAPL",
        status="ok",
    )

    identity = module.normalize_identity(cache, "AAPL", providers=["eodhd", "alphavantage", "fmp"])
    snapshot = module.normalize_market_snapshot(cache, "AAPL", [], None, "", "", providers=["eodhd", "alphavantage", "fmp"])
    fundamentals = module.normalize_equity_fundamentals(cache, "AAPL", providers=["alphavantage", "fmp"])
    news = module.normalize_news(cache, "AAPL", providers=["fmp"], endpoint_plan={"fmp": {"stock_news"}})
    events = module.normalize_equity_events(cache, "AAPL", providers=["fmp"], endpoint_plan={"fmp": {"dividends"}})
    insiders = module.normalize_equity_insiders(cache, "AAPL", providers=["fmp"], endpoint_plan={"fmp": {"insider_trading"}})

    assert "company_name" not in identity
    assert "market_capitalization" not in snapshot
    assert fundamentals == {}
    assert news == {"items": [], "status": "empty"}
    assert events == {"status": "empty", "items": []}
    assert insiders == {"status": "empty", "items": []}


def test_fmp_equity_event_rows_include_source_provenance(tmp_path):
    module = load_module()
    cache = tmp_path / "cache"
    module.write_raw(
        cache,
        "AAPL",
        "fmp",
        "dividends",
        {"symbol": "AAPL"},
        [{"date": "2026-06-01", "dividend": 1.23}],
        source_url="https://financialmodelingprep.com/stable/dividends?symbol=AAPL",
    )

    events = module.normalize_equity_events(cache, "AAPL", providers=["fmp"], endpoint_plan={"fmp": {"dividends"}})

    row = events["items"][0]
    assert row["date"] == "2026-06-01"
    assert row["dividend"] == 1.23
    assert row["provider"] == "fmp"
    assert row["endpoint"] == "dividends"
    assert row["source_url"] == "https://financialmodelingprep.com/stable/dividends?symbol=AAPL"
    assert row["raw_path"].endswith(".json")
    assert row["status"] == "ok"


def test_fmp_insider_trading_rows_include_source_provenance(tmp_path):
    module = load_module()
    cache = tmp_path / "cache"
    module.write_raw(
        cache,
        "AAPL",
        "fmp",
        "insider_trading",
        {"symbol": "AAPL"},
        [{"transactionDate": "2026-06-01", "transactionType": "P-Purchase"}],
        source_url="https://financialmodelingprep.com/stable/insider-trading?symbol=AAPL",
    )

    insiders = module.normalize_equity_insiders(cache, "AAPL", providers=["fmp"], endpoint_plan={"fmp": {"insider_trading"}})

    row = insiders["items"][0]
    assert row["transactionDate"] == "2026-06-01"
    assert row["transactionType"] == "P-Purchase"
    assert row["provider"] == "fmp"
    assert row["endpoint"] == "insider_trading"
    assert row["source_url"] == "https://financialmodelingprep.com/stable/insider-trading?symbol=AAPL"
    assert row["raw_path"].endswith(".json")
    assert row["status"] == "ok"


def test_fetch_provider_reuses_cached_price_endpoint_when_as_of_changes(tmp_path, monkeypatch):
    module = load_module()
    cache = tmp_path / "cache"
    cached = module.write_raw(
        cache,
        "AAPL",
        "tiingo",
        "prices",
        {"startDate": "2021-01-01", "endDate": "2026-06-01"},
        [{"date": "2026-05-29", "adjClose": 132}],
        source_url="https://api.tiingo.com/tiingo/daily/AAPL/prices?startDate=2021-01-01&endDate=2026-06-01",
    )
    calls = []

    def fake_http_json(url, headers=None, timeout=20, retry_policy=None, provider=None):
        calls.append(url)
        return [{"date": "2026-06-15", "adjClose": 133}]

    monkeypatch.setattr(module, "http_json", fake_http_json)
    config = module.ProviderConfig(values={"TIINGO_API_TOKEN": "secret-token"}, docs={}, limits={}, loaded_files=[])

    paths = module.fetch_provider("AAPL", "tiingo", "2026-06-15", cache, config, refresh=False)

    assert paths == [cached]
    assert calls == []


def test_live_fetch_urls_do_not_store_tokens_in_source_url(tmp_path, monkeypatch):
    module = load_module()
    seen = []

    def fake_http_json(url, headers=None, timeout=20, retry_policy=None, provider=None):
        seen.append(url)
        return []

    monkeypatch.setattr(module, "http_json", fake_http_json)
    config = module.ProviderConfig(values={"TIINGO_API_TOKEN": "secret-token"}, docs={}, limits={}, loaded_files=[])

    paths = module.fetch_provider("AAPL", "tiingo", "2026-06-01", tmp_path, config, refresh=True)

    assert len(paths) == 1
    payload = json.loads(paths[0].read_text(encoding="utf-8"))
    assert "secret-token" in seen[0]
    assert "secret-token" not in payload["provider_result"]["url"]


def test_sec_company_tickers_cache_is_shared_across_symbols(tmp_path, monkeypatch):
    module = load_module()
    calls = []

    def fake_http_json(url, headers=None, timeout=20, retry_policy=None, provider=None):
        calls.append(url)
        if url.endswith("company_tickers.json"):
            return {
                "0": {"ticker": "AAPL", "cik_str": 320193, "title": "Apple Inc."},
                "1": {"ticker": "VTI", "cik_str": 36405, "title": "Vanguard Total Stock Market ETF"},
            }
        if "CIK0000320193" in url:
            return {"name": "Apple Inc.", "filings": {"recent": {"form": ["10-K"]}}}
        if "CIK0000036405" in url:
            return {"name": "Vanguard Total Stock Market ETF", "filings": {"recent": {"form": ["N-1A"]}}}
        return {}

    monkeypatch.setattr(module, "http_json", fake_http_json)
    config = module.ProviderConfig(values={"SEC_USER_AGENT": "test@example.com"}, docs={}, limits={}, loaded_files=[])

    module.fetch_provider("AAPL", "sec", "2026-06-16", tmp_path, config, refresh=False)
    module.fetch_provider("VTI", "sec", "2026-06-16", tmp_path, config, refresh=False)

    assert sum(1 for url in calls if url.endswith("company_tickers.json")) == 1
    assert (tmp_path / "_global" / "sec").exists()


def test_fetch_raises_clear_error_on_provider_auth_failure(tmp_path, monkeypatch):
    module = load_module()

    def fake_fetch(symbol, provider, as_of, cache_root, config, refresh=False, endpoints=None):
        return [
            module.write_raw(
                cache_root,
                symbol,
                provider,
                "prices",
                {},
                {},
                source_url="https://example.test/prices",
                status="unauthorized",
                error="HTTP 403",
            )
        ]

    monkeypatch.setattr(module, "fetch_provider", fake_fetch)
    args = type(
        "Args",
        (),
        {
            "repo_root": str(tmp_path),
            "symbol": "AAPL",
            "as_of": "2026-06-16",
            "data_dir": str(tmp_path / "data"),
            "cache_dir": str(tmp_path / "cache"),
            "reports_dir": str(tmp_path / "reports"),
            "providers": "tiingo",
            "max_provider_calls": ["tiingo=1"],
            "offline": False,
            "refresh": False,
            "asset_type": "auto",
        },
    )()

    try:
        module.cmd_fetch(args)
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("cmd_fetch should fail on provider authentication errors")


def test_plan_gated_http_bodies_are_not_classified_as_auth_failures():
    module = load_module()

    eod_status, eod_error = module.classify_http_error(
        "eodhd",
        403,
        "Only EOD data allowed for free users. Please, contact our support team.",
    )
    twelve_status, twelve_error = module.classify_http_error(
        "twelve_data",
        403,
        '{"code":403,"message":"/profile is available exclusively with grow or pro plans. Consider upgrading now","status":"error"}',
    )
    twelve_payload_status, twelve_payload_error = module.classify_provider_payload(
        "twelve_data",
        {"code": 403, "message": "/profile is available exclusively with grow or pro plans.", "status": "error"},
    )

    assert eod_status == "plan_gated"
    assert "Only EOD data allowed" in eod_error
    assert twelve_status == "plan_gated"
    assert "available exclusively" in twelve_error
    assert twelve_payload_status == "plan_gated"
    assert "available exclusively" in twelve_payload_error


def test_fetch_preserves_provider_good_data_when_one_endpoint_is_unauthorized(tmp_path, monkeypatch):
    module = load_module()

    def fake_fetch(symbol, provider, as_of, cache_root, config, refresh=False, endpoints=None):
        return [
            module.write_raw(
                cache_root,
                symbol,
                provider,
                "prices",
                {"symbol": symbol},
                {"values": [{"datetime": "2026-06-16", "close": "10", "volume": "1000"}]},
                source_url="https://example.test/prices",
                status="ok",
            ),
            module.write_raw(
                cache_root,
                symbol,
                provider,
                "profile",
                {"symbol": symbol},
                {},
                source_url="https://example.test/profile",
                status="unauthorized",
                error="HTTP 403",
            ),
        ]

    monkeypatch.setattr(module, "fetch_provider", fake_fetch)
    args = type(
        "Args",
        (),
        {
            "repo_root": str(tmp_path),
            "symbol": "AAPL",
            "as_of": "2026-06-16",
            "data_dir": str(tmp_path / "data"),
            "cache_dir": str(tmp_path / "cache"),
            "reports_dir": str(tmp_path / "reports"),
            "providers": "twelve_data",
            "provider_endpoints": ["twelve_data=prices,profile"],
            "max_provider_calls": ["twelve_data=2"],
            "offline": False,
            "refresh": False,
            "asset_type": "auto",
        },
    )()

    module.cmd_fetch(args)

    manifest = json.loads((tmp_path / "data" / "AAPL" / "2026-06-16" / "manifest.json").read_text(encoding="utf-8"))
    prices = json.loads((tmp_path / "data" / "AAPL" / "2026-06-16" / "normalized" / "prices_daily.json").read_text(encoding="utf-8"))
    assert prices["prices"][0]["adjusted_close"] == 10
    assert manifest["provider_status"][0]["ok_files"] == 1
    assert manifest["provider_status"][0]["errors"] == 1
    endpoint_status = {(item["provider"], item["endpoint"]): item for item in manifest["endpoint_status"]}
    assert endpoint_status[("twelve_data", "prices")]["status"] == "ok"
    assert endpoint_status[("twelve_data", "prices")]["raw_path"].endswith(".json")
    assert endpoint_status[("twelve_data", "profile")]["status"] == "unauthorized"
    assert endpoint_status[("twelve_data", "profile")]["error"] == "HTTP 403"
    assert any("usable endpoint data was preserved" in warning for warning in manifest["warnings"])


def test_fetch_logs_rate_limit_status_in_manifest(tmp_path, monkeypatch):
    module = load_module()

    def fake_fetch(symbol, provider, as_of, cache_root, config, refresh=False, endpoints=None):
        return [
            module.write_raw(
                cache_root,
                symbol,
                provider,
                "prices",
                {},
                {"Information": "API rate limit reached."},
                source_url="https://example.test/query",
                status="ok",
            )
        ]

    monkeypatch.setattr(module, "fetch_provider", fake_fetch)
    args = type(
        "Args",
        (),
        {
            "repo_root": str(tmp_path),
            "symbol": "AAPL",
            "as_of": "2026-06-16",
            "data_dir": str(tmp_path / "data"),
            "cache_dir": str(tmp_path / "cache"),
            "reports_dir": str(tmp_path / "reports"),
            "providers": "alphavantage",
            "max_provider_calls": ["alphavantage=2"],
            "offline": False,
            "refresh": False,
            "asset_type": "auto",
        },
    )()

    module.cmd_fetch(args)

    manifest = json.loads((tmp_path / "data" / "AAPL" / "2026-06-16" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["provider_status"][0]["status"] == "rate_limited"
    assert any("rate_limited" in warning and "alphavantage" in warning for warning in manifest["warnings"])


def test_fetch_logs_provider_error_status_in_manifest(tmp_path, monkeypatch):
    module = load_module()

    def fake_fetch(symbol, provider, as_of, cache_root, config, refresh=False, endpoints=None):
        return [
            module.write_raw(
                cache_root,
                symbol,
                provider,
                "companyfacts",
                {},
                {},
                source_url="https://data.sec.gov/api/xbrl/companyfacts/CIK0000884394.json",
                status="error",
                error="HTTP 404",
            )
        ]

    monkeypatch.setattr(module, "fetch_provider", fake_fetch)
    args = type(
        "Args",
        (),
        {
            "repo_root": str(tmp_path),
            "symbol": "SPY",
            "as_of": "2026-06-16",
            "data_dir": str(tmp_path / "data"),
            "cache_dir": str(tmp_path / "cache"),
            "reports_dir": str(tmp_path / "reports"),
            "providers": "sec",
            "max_provider_calls": ["sec=3"],
            "offline": False,
            "refresh": False,
            "asset_type": "etf",
        },
    )()

    module.cmd_fetch(args)

    manifest = json.loads((tmp_path / "data" / "SPY" / "2026-06-16" / "manifest.json").read_text(encoding="utf-8"))
    source_manifest = json.loads((tmp_path / "data" / "SPY" / "2026-06-16" / "source_manifest.json").read_text(encoding="utf-8"))
    assert manifest["provider_status"][0]["status"] == "error"
    assert any("error" in warning and "sec" in warning for warning in manifest["warnings"])
    assert source_manifest["sources"][0]["error"] == "HTTP 404"


def test_explicit_asset_type_overrides_auto_classification(tmp_path):
    module = load_module()
    cache = tmp_path / "cache"
    module.write_raw(
        cache,
        "SPY",
        "sec",
        "submissions",
        {"cik": "0000884394"},
        {"name": "SPDR S&P 500 ETF TRUST", "filings": {"recent": {"form": ["10-K"]}}},
        source_url="https://data.sec.gov/submissions/CIK0000884394.json",
    )

    result = module.build_bundle("SPY", "2026-06-01", cache, tmp_path / "data", providers=["sec"], asset_type="etf")

    manifest = json.loads((Path(result["bundle_dir"]) / "manifest.json").read_text(encoding="utf-8"))
    identity = json.loads((Path(result["bundle_dir"]) / "normalized" / "identity.json").read_text(encoding="utf-8"))
    assert manifest["asset_type"] == "etf"
    assert identity["asset_type"]["value"] == "etf"
    assert identity["asset_type"]["provider"] == "cli"


def test_sec_companyfacts_promote_equity_fundamentals_without_extra_provider(tmp_path):
    module = load_module()
    cache = tmp_path / "cache"
    module.write_raw(
        cache,
        "AAPL",
        "sec",
        "companyfacts",
        {"cik": "0000320193"},
        {
            "entityName": "Apple Inc.",
            "facts": {
                "us-gaap": {
                    "RevenueFromContractWithCustomerExcludingAssessedTax": {
                        "units": {"USD": [{"form": "10-K", "fp": "FY", "fy": 2025, "end": "2025-09-27", "filed": "2025-10-31", "val": 416161000000}]}
                    },
                    "NetIncomeLoss": {
                        "units": {"USD": [{"form": "10-K", "fp": "FY", "fy": 2025, "end": "2025-09-27", "filed": "2025-10-31", "val": 112010000000}]}
                    },
                }
            },
        },
        source_url="https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json",
    )

    result = module.build_bundle("AAPL", "2026-06-16", cache, tmp_path / "data", providers=["sec"], offline=True)

    fundamentals = json.loads((Path(result["bundle_dir"]) / "normalized" / "equity_fundamentals.json").read_text(encoding="utf-8"))
    assert fundamentals["revenue"]["value"]["value"] == 416161000000
    assert fundamentals["revenue"]["provider"] == "sec"
    assert fundamentals["net_income"]["value"]["value"] == 112010000000


def test_gaps_record_only_attempted_providers(tmp_path):
    module = load_module()

    result = module.build_bundle("SPY", "2026-06-16", tmp_path / "cache", tmp_path / "data", providers=["sec", "tiingo"], asset_type="etf")

    gaps = json.loads((Path(result["bundle_dir"]) / "gaps.json").read_text(encoding="utf-8"))
    assert gaps["gaps"]
    assert {tuple(gap["attempted_sources"]) for gap in gaps["gaps"]} == {("sec", "tiingo")}


def test_build_bundle_ignores_cached_providers_not_selected(tmp_path):
    module = load_module()
    cache = tmp_path / "cache"
    module.write_raw(
        cache,
        "AAPL",
        "alphavantage",
        "overview",
        {"function": "OVERVIEW", "symbol": "AAPL"},
        {"MarketCapitalization": "3000000000000", "PERatio": "30", "RevenueTTM": "400000000000"},
        source_url="https://www.alphavantage.co/query?function=OVERVIEW&symbol=AAPL",
    )

    result = module.build_bundle("AAPL", "2026-06-16", cache, tmp_path / "data", providers=["sec"], asset_type="equity")

    bundle_dir = Path(result["bundle_dir"])
    source_manifest = json.loads((bundle_dir / "source_manifest.json").read_text(encoding="utf-8"))
    snapshot = json.loads((bundle_dir / "normalized" / "market_snapshot.json").read_text(encoding="utf-8"))
    fundamentals = json.loads((bundle_dir / "normalized" / "equity_fundamentals.json").read_text(encoding="utf-8"))
    assert source_manifest["sources"] == []
    assert "market_capitalization" not in snapshot
    assert fundamentals == {"gaps_recorded": True, "status": "unavailable"}


def test_copy_raw_files_deduplicates_global_and_legacy_symbol_sec_cache(tmp_path):
    module = load_module()
    cache = tmp_path / "cache"
    module.write_raw(cache, "ECH", "sec", "company_tickers", {}, {"0": {"ticker": "ECH"}}, source_url="https://www.sec.gov/files/company_tickers.json")
    global_path = cache / "_global" / "sec" / "sec_company_tickers_44136fa355b3678a.json"
    legacy_path = cache / "ECH" / "sec" / "sec_company_tickers_44136fa355b3678a.json"
    legacy_path.parent.mkdir(parents=True)
    legacy_path.write_text(global_path.read_text(encoding="utf-8"), encoding="utf-8")

    result = module.build_bundle("ECH", "2026-06-17", cache, tmp_path / "data", providers=["sec"], asset_type="etf")

    source_manifest = json.loads((Path(result["bundle_dir"]) / "source_manifest.json").read_text(encoding="utf-8"))
    company_tickers = [source for source in source_manifest["sources"] if source["endpoint"] == "company_tickers"]
    assert len(company_tickers) == 1


def test_provider_status_reports_cached_errors(tmp_path):
    module = load_module()
    cache = tmp_path / "cache"
    module.write_raw(cache, "AAPL", "eodhd", "fundamentals", {}, {}, source_url="https://example.test", status="unauthorized", error="HTTP 403")

    statuses = module.collect_provider_status(cache, "AAPL", ["eodhd"])

    assert statuses == [{"provider": "eodhd", "raw_files": 1, "ok_files": 0, "status": "unauthorized", "errors": 1}]


def test_provider_status_counts_global_sec_cache(tmp_path):
    module = load_module()
    cache = tmp_path / "cache"
    module.write_raw(cache, "AAPL", "sec", "company_tickers", {}, {"0": {"ticker": "AAPL", "cik_str": 320193}}, source_url="https://www.sec.gov/files/company_tickers.json")

    statuses = module.collect_provider_status(cache, "VTI", ["sec"])

    assert statuses == [{"provider": "sec", "raw_files": 1, "ok_files": 1, "status": "ok"}]


def test_provider_status_reclassifies_cached_semantic_errors(tmp_path):
    module = load_module()
    cache = tmp_path / "cache"
    module.write_raw(cache, "AAPL", "alphavantage", "prices", {}, {"Information": "API rate limit reached."}, source_url="https://example.test")

    statuses = module.collect_provider_status(cache, "AAPL", ["alphavantage"])

    assert statuses == [{"provider": "alphavantage", "raw_files": 1, "ok_files": 0, "status": "rate_limited", "errors": 1}]


def test_http_json_retries_rate_limit_with_exponential_backoff(monkeypatch):
    module = load_module()
    calls = []
    sleeps = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"ok": true}'

    def fake_urlopen(request, timeout=20):
        calls.append(request)
        if len(calls) < 3:
            raise HTTPError(request.full_url, 429, "rate limited", {}, None)
        return Response()

    monkeypatch.setattr(module, "urlopen", fake_urlopen)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: sleeps.append(seconds))

    assert module.http_json("https://example.test/data", retry_policy=module.retry_policy_for_provider("alphavantage")) == {"ok": True}
    assert len(calls) == 3
    assert sleeps == [1.0, 2.0]


def test_http_json_does_not_retry_unauthorized(monkeypatch):
    module = load_module()
    calls = []

    def fake_urlopen(request, timeout=20):
        calls.append(request)
        raise HTTPError(request.full_url, 403, "forbidden", {}, None)

    monkeypatch.setattr(module, "urlopen", fake_urlopen)

    try:
        module.http_json("https://example.test/data", retry_policy=module.retry_policy_for_provider("marketaux"))
    except HTTPError:
        pass
    else:
        raise AssertionError("HTTP 403 should be raised without retries")

    assert len(calls) == 1


def test_fetch_with_cache_preserves_http_error_body_and_headers(tmp_path, monkeypatch):
    module = load_module()

    class FakeHeaders(dict):
        def get(self, key, default=None):
            return super().get(key, default)

    class FakeHTTPError(HTTPError):
        def __init__(self):
            super().__init__(
                url="https://www.sec.gov/files/company_tickers.json",
                code=403,
                msg="Forbidden",
                hdrs=FakeHeaders({"content-type": "text/html", "server": "AkamaiGHost"}),
                fp=None,
            )

        def read(self, amt=None):
            body = b"<html><title>SEC.gov | Request Rate Threshold Exceeded</title></html>"
            return body if amt is None else body[:amt]

    def fake_http_json(*args, **kwargs):
        raise FakeHTTPError()

    monkeypatch.setattr(module, "http_json", fake_http_json)
    config = module.ProviderConfig(values={}, docs={}, limits={}, loaded_files=[])

    raw = module.fetch_with_cache(
        tmp_path,
        "DPC",
        "sec",
        "company_tickers",
        {},
        "https://www.sec.gov/files/company_tickers.json",
        "https://www.sec.gov/files/company_tickers.json",
        config,
        headers={"User-Agent": "market-research-skill/1.0 research@example.com"},
        refresh=True,
    )
    payload = json.loads(raw.read_text(encoding="utf-8"))
    result = payload["provider_result"]

    assert result["status"] == "rate_limited"
    assert result["error"] == "HTTP 403: SEC.gov | Request Rate Threshold Exceeded"
    assert result["http_status"] == 403
    assert result["response_headers"]["content-type"] == "text/html"
    assert "Request Rate Threshold Exceeded" in result["error_body_snippet"]


def test_sec_rate_threshold_http_403_retries_when_user_agent_is_descriptive(monkeypatch):
    module = load_module()
    calls = {"count": 0}

    class FakeHeaders(dict):
        def get(self, key, default=None):
            return super().get(key, default)

    class RateThresholdHTTPError(HTTPError):
        def __init__(self):
            super().__init__(
                url="https://www.sec.gov/files/company_tickers.json",
                code=403,
                msg="Forbidden",
                hdrs=FakeHeaders({"content-type": "text/html"}),
                fp=None,
            )

        def read(self, amt=None):
            body = b"<html><title>SEC.gov | Request Rate Threshold Exceeded</title></html>"
            return body if amt is None else body[:amt]

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"0":{"ticker":"DPC","cik_str":2107018,"title":"DPC Holdings Ltd"}}'

    def fake_urlopen(request, timeout=20):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RateThresholdHTTPError()
        return Response()

    monkeypatch.setattr(module, "urlopen", fake_urlopen)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)

    payload = module.http_json(
        "https://www.sec.gov/files/company_tickers.json",
        headers={"User-Agent": "market-research-skill/1.0 research@example.com"},
        retry_policy=module.retry_policy_for_provider("sec"),
        provider="sec",
    )

    assert calls["count"] == 2
    assert payload["0"]["ticker"] == "DPC"


def test_default_paths_separate_data_reports_runtime_and_cache(tmp_path):
    module = load_module()
    config = module.ProviderConfig(values={}, docs={}, limits={}, loaded_files=[])

    paths = module.resolve_storage_paths(tmp_path, config, data_dir=None, cache_dir=None, reports_dir=None)

    assert paths["data_dir"] == tmp_path / "data"
    assert paths["reports_dir"] == tmp_path / "reports"
    assert paths["runtime_dir"] == tmp_path / "runtime"
    assert paths["cache_dir"] == tmp_path / "data" / "cache"


def test_deterministic_schema_covers_normalized_outputs():
    schema = json.loads(DETERMINISTIC_SCHEMA.read_text(encoding="utf-8"))
    normalized = schema["properties"]["normalized"]["properties"]

    assert set(normalized) >= {
        "identity",
        "market_snapshot",
        "prices_daily",
        "technical_signals",
        "news",
        "sec_filings_index",
        "sec_filing_sections",
        "equity_fundamentals",
        "equity_events",
        "equity_insiders",
        "etf_profile",
        "etf_holdings",
        "etf_distributions",
        "etf_performance",
    }
    data_point = schema["$defs"]["data_point"]
    assert set(data_point["required"]) >= {"value", "provider", "source_url", "endpoint", "raw_path", "status"}


def test_provider_map_schema_and_docs_are_in_sync():
    schema = json.loads(DETERMINISTIC_SCHEMA.read_text(encoding="utf-8"))
    provider_map = PROVIDER_MAP.read_text(encoding="utf-8")
    normalized = set(schema["properties"]["normalized"]["properties"])

    for section in [
        "identity",
        "market_snapshot",
        "prices_daily",
        "technical_signals",
        "news",
        "sec_filings_index",
        "sec_filing_sections",
        "equity_fundamentals",
        "equity_events",
        "equity_insiders",
        "etf_profile",
        "etf_holdings",
        "etf_distributions",
        "etf_performance",
    ]:
        assert section in normalized
        assert f"`{section}`" in provider_map


def test_active_market_research_docs_use_new_script_names():
    active_files = [
        ROOT / "market-research" / "SKILL.md",
        ROOT / "market-research" / "researcher" / "SKILL.md",
        ROOT / "market-research" / "researcher" / "references" / "equity-research.md",
        ROOT / "market-research" / "researcher" / "references" / "etf-research.md",
        ROOT / "market-research" / "researcher" / "references" / "report-template.md",
        ROOT / "market-research" / "shared" / "schemas" / "research-output.schema.json",
        ROOT / "market-research" / "batch-supervisor" / "scripts" / "research_loop.py",
        ROOT / "market-research" / "verifier" / "SKILL.md",
        ROOT / "AGENTS.md",
    ]

    for path in active_files:
        text = path.read_text(encoding="utf-8")
        assert "research_data.py" not in text
        assert "market_research_helper.py" not in text
    researcher_skill = (ROOT / "market-research" / "researcher" / "SKILL.md").read_text(encoding="utf-8")
    assert "deterministic_research_collector.py" in researcher_skill
    assert "procedural_source_helper.py" in researcher_skill


def test_duplicate_provider_values_keep_primary_and_candidates(tmp_path):
    module = load_module()
    cache = tmp_path / "cache"
    module.write_raw(
        cache,
        "AAPL",
        "eodhd",
        "fundamentals",
        {},
        {"General": {"Name": "Apple Inc", "MarketCapitalization": 3000000000000}, "Highlights": {"PERatio": 30}},
        source_url="https://eodhd.example/fundamentals/AAPL.US",
    )
    module.write_raw(
        cache,
        "AAPL",
        "alphavantage",
        "overview",
        {},
        {"Name": "Apple Inc.", "MarketCapitalization": "2990000000000", "PERatio": "31"},
        source_url="https://alphavantage.example/query?function=OVERVIEW&symbol=AAPL",
    )

    snapshot = module.normalize_market_snapshot(cache, "AAPL", [], None, "", "")

    assert snapshot["market_capitalization"]["provider"] == "eodhd"
    assert snapshot["market_capitalization"]["alternates"][0]["provider"] == "alphavantage"
    assert snapshot["pe_ratio"]["provider"] == "eodhd"
    assert snapshot["pe_ratio"]["alternates"][0]["value"] == 31


def test_fetch_with_cache_marks_alpha_vantage_information_as_rate_limited(tmp_path, monkeypatch):
    module = load_module()

    monkeypatch.setattr(module, "http_json", lambda *args, **kwargs: {"Information": "API rate limit reached."})
    config = module.ProviderConfig(values={}, docs={}, limits={}, loaded_files=[])

    path = module.fetch_with_cache(tmp_path, "AAPL", "alphavantage", "prices", {"symbol": "AAPL"}, "https://example.test", "https://example.test", config, refresh=True)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["provider_result"]["status"] == "rate_limited"
    assert "Information" in payload["provider_result"]["error"]


def test_alpha_vantage_overview_promotes_equity_fundamentals(tmp_path):
    module = load_module()
    cache = tmp_path / "cache"
    module.write_raw(
        cache,
        "NIO",
        "alphavantage",
        "overview",
        {"function": "OVERVIEW", "symbol": "NIO"},
        {
            "Name": "Nio Inc Class A ADR",
            "MarketCapitalization": "15184593000",
            "PERatio": "31",
            "RevenueTTM": "65173150000",
            "GrossProfitTTM": "15855288000",
            "EBITDA": "-467509504",
            "EPS": "-0.56",
            "Beta": "0.975",
            "AnalystTargetPrice": "18.33",
            "AnalystRatingStrongBuy": "0",
            "AnalystRatingBuy": "4",
            "AnalystRatingHold": "2",
            "AnalystRatingSell": "0",
            "AnalystRatingStrongSell": "0",
        },
        source_url="https://alphavantage.example/query?function=OVERVIEW&symbol=NIO",
    )

    fundamentals = module.normalize_equity_fundamentals(cache, "NIO")

    assert fundamentals["revenue_ttm"]["value"] == 65173150000
    assert fundamentals["gross_profit_ttm"]["provider"] == "alphavantage"
    assert fundamentals["eps"]["value"] == -0.56
    assert fundamentals["analyst_target_price"]["value"] == 18.33
    assert fundamentals["analyst_rating_buy"]["value"] == 4
    assert fundamentals["analyst_rating_hold"]["provider"] == "alphavantage"


def test_analyst_context_gap_not_recorded_when_overview_has_analyst_fields(tmp_path):
    module = load_module()
    cache = tmp_path / "cache"
    module.write_raw(
        cache,
        "NIO",
        "alphavantage",
        "overview",
        {"function": "OVERVIEW", "symbol": "NIO"},
        {
            "Name": "Nio Inc Class A ADR",
            "AnalystTargetPrice": "18.33",
            "AnalystRatingBuy": "4",
            "AnalystRatingHold": "2",
        },
        source_url="https://alphavantage.example/query?function=OVERVIEW&symbol=NIO",
    )

    result = module.build_bundle(
        "NIO",
        "2026-06-21",
        cache,
        tmp_path / "data",
        providers=["alphavantage"],
        endpoint_plan={"alphavantage": {"overview"}},
        asset_type="equity",
    )

    gaps = json.loads((Path(result["bundle_dir"]) / "gaps.json").read_text(encoding="utf-8"))["gaps"]
    assert "analyst_context" not in {gap["field"] for gap in gaps}


def test_build_bundle_emits_deterministic_data_usage_requirements(tmp_path):
    module = load_module()
    cache = tmp_path / "cache"
    module.write_raw(
        cache,
        "NIO",
        "alphavantage",
        "overview",
        {"function": "OVERVIEW", "symbol": "NIO"},
        {
            "Name": "Nio Inc Class A ADR",
            "MarketCapitalization": "15184593000",
            "RevenueTTM": "65173150000",
            "AnalystTargetPrice": "18.33",
        },
        source_url="https://alphavantage.example/query?function=OVERVIEW&symbol=NIO",
    )

    result = module.build_bundle(
        "NIO",
        "2026-06-21",
        cache,
        tmp_path / "data",
        providers=["alphavantage"],
        endpoint_plan={"alphavantage": {"overview"}},
        asset_type="equity",
    )

    bundle_dir = Path(result["bundle_dir"])
    usage_path = bundle_dir / "deterministic_data_usage.json"
    assert usage_path.exists()
    usage = json.loads(usage_path.read_text(encoding="utf-8"))
    by_path = {item["field_path"]: item for item in usage["datapoints"]}
    assert by_path["market_snapshot.market_capitalization"]["materiality"] == "required"
    assert by_path["equity_fundamentals.revenue_ttm"]["materiality"] == "required"
    assert by_path["equity_fundamentals.analyst_target_price"]["materiality"] == "review"
    pack = (bundle_dir / "research_input_pack.md").read_text(encoding="utf-8")
    assert "## Deterministic Data Usage Requirements" in pack


def test_build_bundle_uses_lifecycle_hints_for_usage_requirements(tmp_path):
    module = load_module()
    cache = tmp_path / "cache"
    module.write_raw(
        cache,
        "QUBT",
        "alphavantage",
        "overview",
        {"function": "OVERVIEW", "symbol": "QUBT"},
        {
            "Name": "Quantum Computing Inc.",
            "RevenueTTM": "4334000",
            "EPS": "-0.26",
            "BookValue": "7.08",
            "OperatingMarginTTM": "-5.57",
        },
        source_url="https://alphavantage.example/query?function=OVERVIEW&symbol=QUBT",
    )

    result = module.build_bundle(
        "QUBT",
        "2026-06-21",
        cache,
        tmp_path / "data",
        providers=["alphavantage"],
        endpoint_plan={"alphavantage": {"overview"}},
        asset_type="equity",
    )

    usage = json.loads((Path(result["bundle_dir"]) / "deterministic_data_usage.json").read_text(encoding="utf-8"))
    by_path = {item["field_path"]: item for item in usage["datapoints"]}
    assert by_path["equity_fundamentals.book_value"]["materiality"] == "review"
    assert by_path["equity_fundamentals.operating_margin_ttm"]["materiality"] == "review"
