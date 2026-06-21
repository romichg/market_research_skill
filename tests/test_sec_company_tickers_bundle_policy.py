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
