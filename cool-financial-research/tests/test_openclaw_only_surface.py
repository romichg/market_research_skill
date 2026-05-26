import importlib
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_pyproject_has_only_openclaw_helper_entry_point():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'cfr-helper = "cool_financial_research.openclaw_helper:main"' in text
    assert "cool-financial-research-dev" not in text
    assert "typer" not in text
    assert "rich" not in text


def test_cfr_helper_help_lists_deterministic_commands():
    result = subprocess.run(
        ["python3", "scripts/cfr_helper.py", "--help"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "classify" in result.stdout
    assert "verify-artifacts" in result.stdout
    assert "render-pdf" in result.stdout
    assert "cool-financial-research-dev" not in result.stdout


def test_legacy_cli_module_is_gone():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("cool_financial_research.cli")


def test_docs_do_not_describe_a_standalone_package_cli():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "cool-financial-research-dev" not in readme
    assert "cool-financial-research-dev" not in skill
    assert "Optional Typer/Rich developer CLI" not in readme
    assert "Optional `cool-financial-research-dev` CLI" not in skill
