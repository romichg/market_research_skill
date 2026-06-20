import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PDF_HELPER = ROOT / "market-research-full" / "shared" / "scripts" / "md-to-pdf.sh"
BASH = shutil.which("bash") or "/bin/bash"


def run_pdf_helper(*args, env=None):
    return subprocess.run(
        [BASH, str(PDF_HELPER), *args],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def test_pdf_helper_is_best_effort_when_pandoc_is_missing(tmp_path):
    report = tmp_path / "reports" / "AAPL" / "2026-06-19" / "AAPL-research.md"
    report.parent.mkdir(parents=True)
    report.write_text("# AAPL Research\n", encoding="utf-8")
    empty_path = tmp_path / "bin"
    empty_path.mkdir()
    env = {**os.environ, "PATH": str(empty_path)}

    result = run_pdf_helper(str(report), env=env)

    assert result.returncode == 0
    assert "PDF not generated" in result.stderr
    assert "pandoc" in result.stderr
    assert not report.with_suffix(".pdf").exists()


def test_pdf_helper_requires_existing_markdown_input(tmp_path):
    missing_report = tmp_path / "missing.md"

    result = run_pdf_helper(str(missing_report))

    assert result.returncode != 0
    assert "Markdown input not found" in result.stderr


def test_pdf_helper_prints_usage_for_help():
    result = run_pdf_helper("--help")

    assert result.returncode == 0
    assert "Usage:" in result.stdout
