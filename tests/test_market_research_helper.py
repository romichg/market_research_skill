import json
import subprocess
import sys
from pathlib import Path

HELPER = Path(__file__).resolve().parents[1] / "market-research" / "scripts" / "market_research_helper.py"


def run_helper(*args, cwd=None):
    return subprocess.run(
        [sys.executable, str(HELPER), *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def test_init_run_creates_manifest(tmp_path):
    result = run_helper("init-run", "aapl", "--output-root", str(tmp_path))
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    run_dir = tmp_path / "AAPL"
    assert payload["symbol"] == "AAPL"
    assert Path(payload["run_dir"]) == run_dir
    manifest = json.loads((run_dir / "run_manifest.json").read_text())
    assert manifest["symbol"] == "AAPL"
    assert manifest["helper_errors"] == []
    assert manifest["procedural_gap_fills"] == []


def test_invalid_symbol_rejected(tmp_path):
    result = run_helper("init-run", "../AAPL", "--output-root", str(tmp_path))
    assert result.returncode != 0
    assert "Invalid symbol" in result.stderr
