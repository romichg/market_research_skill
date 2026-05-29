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


def test_classify_manual_updates_manifest(tmp_path):
    run_helper("init-run", "vti", "--output-root", str(tmp_path))
    result = run_helper("classify", "VTI", "--output-root", str(tmp_path), "--security-type", "etf", "--name", "Vanguard Total Stock Market ETF")
    assert result.returncode == 0, result.stderr
    classification = json.loads((tmp_path / "VTI" / "source_bundle" / "classification.json").read_text())
    assert classification["security_type"] == "etf"
    assert classification["source"] == "manual"
    manifest = json.loads((tmp_path / "VTI" / "run_manifest.json").read_text())
    assert manifest["security_type"] == "etf"


def test_record_source_and_prepare_sparse_context(tmp_path):
    run_helper("init-run", "ECH", "--output-root", str(tmp_path))
    run_helper("classify", "ECH", "--output-root", str(tmp_path), "--security-type", "etf", "--name", "iShares MSCI Chile ETF")
    result = run_helper(
        "record-source",
        "ECH",
        "--output-root",
        str(tmp_path),
        "--id",
        "issuer_page",
        "--title",
        "iShares ECH product page",
        "--url",
        "https://www.ishares.com/us/products/239618/",
        "--kind",
        "issuer_product_page",
    )
    assert result.returncode == 0, result.stderr
    result = run_helper("prepare-research-context", "ECH", "--output-root", str(tmp_path))
    assert result.returncode == 0, result.stderr
    context = json.loads((tmp_path / "ECH" / "research_context.json").read_text())
    assert context["symbol"] == "ECH"
    assert context["context_quality"]["is_sparse"] is True
    assert "expense_ratio" in context["context_quality"]["missing_material_fields"]


def test_record_gap_fill_updates_context_and_manifest(tmp_path):
    run_helper("init-run", "ECH", "--output-root", str(tmp_path))
    run_helper("classify", "ECH", "--output-root", str(tmp_path), "--security-type", "etf")
    result = run_helper(
        "record-gap-fill",
        "ECH",
        "--output-root",
        str(tmp_path),
        "--field",
        "expense_ratio",
        "--value",
        "0.59%",
        "--source-id",
        "issuer_fact_sheet",
        "--confidence",
        "high",
        "--note",
        "Procedurally filled from issuer fact sheet.",
    )
    assert result.returncode == 0, result.stderr
    context = json.loads((tmp_path / "ECH" / "research_context.json").read_text())
    assert context["data_points"][0]["key"] == "expense_ratio"
    manifest = json.loads((tmp_path / "ECH" / "run_manifest.json").read_text())
    assert manifest["procedural_gap_fills"][0]["field"] == "expense_ratio"
