from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_investor_reports_do_not_use_internal_frozen_language():
    offenders = []
    for path in (ROOT / "reports").glob("*/*/*-research.md"):
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        if "frozen" in text or "freeze" in text:
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []
