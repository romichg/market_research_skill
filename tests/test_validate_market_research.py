import json
import subprocess
import sys
from pathlib import Path

VALIDATOR = Path(__file__).resolve().parents[1] / "validate-market-research" / "scripts" / "validate_market_research.py"


def run_validator(*args):
    return subprocess.run([sys.executable, str(VALIDATOR), *args], text=True, capture_output=True, check=False)


def test_validator_discovers_research_bundle(tmp_path):
    run_dir = tmp_path / "AAPL"
    run_dir.mkdir()
    (run_dir / "run_manifest.json").write_text(json.dumps({"symbol": "AAPL"}), encoding="utf-8")
    (run_dir / "AAPL-research.md").write_text("# AAPL Research\n", encoding="utf-8")
    (run_dir / "AAPL-research.json").write_text(json.dumps({"symbol": "AAPL", "security_type": "equity", "material_claims": [], "data_gaps": []}), encoding="utf-8")
    result = run_validator(str(run_dir))
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["symbol"] == "AAPL"
    assert payload["blocking_issue_count"] == 0
    assert (run_dir / "AAPL-validation.json").exists()
    assert (run_dir / "AAPL-validation.md").exists()


def test_validator_flags_missing_json(tmp_path):
    run_dir = tmp_path / "MSFT"
    run_dir.mkdir()
    (run_dir / "MSFT-research.md").write_text("# MSFT Research\n", encoding="utf-8")
    result = run_validator(str(run_dir))
    assert result.returncode != 0
    assert "research JSON" in result.stderr
