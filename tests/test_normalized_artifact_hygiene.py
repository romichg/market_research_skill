from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "market-research" / "shared" / "scripts" / "deterministic_research_collector.py"


def run_fetch(tmp_path, symbol="AAPL", asset_type="equity"):
    subprocess.run(
        [
            "python3", str(SCRIPT), "fetch", symbol,
            "--offline",
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


def test_rebuild_removes_stale_normalized_placeholders(tmp_path):
    normalized = run_fetch(tmp_path, "AAPL", "equity")
    stale = normalized / "etf_profile.json"
    stale.write_text('{"status": "not_implemented_in_core_pass"}', encoding="utf-8")

    normalized = run_fetch(tmp_path, "AAPL", "equity")

    assert not stale.exists()
