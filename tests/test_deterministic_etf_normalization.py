import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "market-research" / "shared" / "scripts" / "deterministic_research_collector.py"


def load_module():
    spec = importlib.util.spec_from_file_location("deterministic_research_collector", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_fmp_is_etf_overrides_generic_equity(tmp_path):
    module = load_module()
    cache = tmp_path / "cache"
    output_root = tmp_path / "data"
    symbol = "QTUM"
    as_of = "2026-07-01"

    module.write_raw(
        cache,
        symbol,
        "sec",
        "submissions",
        {},
        {
            "name": "Defiance Quantum ETF",
            "tickers": [symbol],
            "exchanges": ["NYSE Arca"],
            "filings": {"recent": {"form": ["10-K"]}},
        },
        source_url="https://data.sec.gov/submissions/CIK0000000000.json",
    )
    module.write_raw(
        cache,
        symbol,
        "fmp",
        "profile",
        {"symbol": symbol},
        [
            {
                "symbol": symbol,
                "companyName": "Defiance Quantum ETF",
                "exchangeShortName": "NYSE",
                "industry": "Asset Management",
                "isEtf": True,
            }
        ],
        source_url="https://financialmodelingprep.com/stable/profile?symbol=QTUM",
    )

    bundle = module.build_bundle(symbol, as_of, cache, output_root, providers=["sec", "fmp"], offline=True)

    identity = json.loads((Path(bundle["bundle_dir"]) / "normalized" / "identity.json").read_text(encoding="utf-8"))
    asset_type = identity["asset_type"]
    assert asset_type["value"] == "etf"
    assert asset_type["selection_reason"] == "fmp profile isEtf flag"
    assert any(item["value"] == "equity" and item["provider"] == "sec" for item in asset_type["alternates"])


def test_alpha_vantage_etf_profile_emits_profile_holdings_and_usage(tmp_path):
    module = load_module()
    cache = tmp_path / "cache"
    output_root = tmp_path / "data"
    symbol = "QTUM"
    as_of = "2026-07-01"

    module.write_raw(
        cache,
        symbol,
        "alphavantage",
        "etf_profile",
        {"function": "ETF_PROFILE", "symbol": symbol},
        {
            "net_assets": "6110000000",
            "net_expense_ratio": "0.40",
            "dividend_yield": "0.53",
            "asset_allocation": {},
            "sectors": [],
            "holdings": [
                {"symbol": "NVDA", "description": "NVIDIA Corp", "weight": "3.2"},
                {"symbol": "MSFT", "description": "Microsoft Corp", "weight": "2.7"},
            ],
        },
        source_url="https://www.alphavantage.co/query?function=ETF_PROFILE&symbol=QTUM",
    )

    bundle = module.build_bundle(symbol, as_of, cache, output_root, providers=["alphavantage"], offline=True)
    bundle_dir = Path(bundle["bundle_dir"])
    normalized = bundle_dir / "normalized"

    identity = json.loads((normalized / "identity.json").read_text(encoding="utf-8"))
    profile = json.loads((normalized / "etf_profile.json").read_text(encoding="utf-8"))
    holdings = json.loads((normalized / "etf_holdings.json").read_text(encoding="utf-8"))
    usage = json.loads((bundle_dir / "deterministic_data_usage.json").read_text(encoding="utf-8"))

    assert identity["asset_type"]["value"] == "etf"
    assert profile["net_assets"]["value"] == 6110000000
    assert profile["net_expense_ratio"]["value"] == 0.4
    assert profile["dividend_yield"]["value"] == 0.53
    assert holdings["top_holdings"][0]["ticker"]["value"] == "NVDA"
    assert holdings["top_holdings"][0]["weight"]["value"] == 3.2
    required_paths = {item["field_path"] for item in usage["datapoints"] if item["required_disposition"]}
    assert "etf_profile.net_assets" in required_paths
    assert "etf_holdings.top_holdings.0.weight" in required_paths
