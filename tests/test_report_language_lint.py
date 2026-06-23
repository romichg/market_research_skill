from pathlib import Path
import importlib.util


ROOT = Path(__file__).resolve().parents[1]
LINT = ROOT / "market-research" / "shared" / "scripts" / "report_language_lint.py"


def load_module():
    spec = importlib.util.spec_from_file_location("report_language_lint", LINT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_investor_reports_do_not_use_internal_frozen_language():
    offenders = []
    for path in (ROOT / "reports").glob("*/*/*-research.md"):
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        if "frozen" in text or "freeze" in text:
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_report_language_lint_rejects_skill_internal_paths_in_main_body():
    module = load_module()
    text = """# QUBT Research

## Bottom Line

Primary evidence consists of the deterministic bundle under `data/QUBT/2026-06-23/`.

## Evidence Appendix

`data/QUBT/2026-06-23/source_manifest.json`
"""

    findings = module.lint_report_language(text)

    assert any("skill-internal provenance belongs in an appendix" in finding["message"] for finding in findings)


def test_report_language_lint_allows_internal_paths_in_appendix():
    module = load_module()
    text = """# QUBT Research

## Bottom Line

The investment case depends on contract conversion.

## Evidence Appendix

`data/QUBT/2026-06-23/source_manifest.json`
"""

    findings = module.lint_report_language(text)

    assert findings == []
