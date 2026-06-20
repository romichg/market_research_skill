from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OLD_ACTIVE_DIRS = ["market-research", "validate-market-research", "market-research-loop"]


def test_only_market_research_full_is_active_skill_tree():
    assert (ROOT / "market-research-full" / "SKILL.md").exists()
    for name in OLD_ACTIVE_DIRS:
        assert not (ROOT / name).exists(), f"{name} must be moved into market-research-full"


def test_active_files_do_not_reference_old_skill_paths():
    forbidden = [
        "market-research" + "/scripts/",
        "validate-market-research" + "/scripts/",
        "market-research-loop" + "/scripts/",
        "$" + "market-research ",
        "$" + "validate-market-research ",
        "$" + "market-research-loop ",
        "market-research" + "-runs",
    ]
    allowed_prefixes = {"OLD", ".git"}
    allowed_files = {Path("docs/plans/20260619_rework_plan.md")}
    offenders = []
    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT)
        if not path.is_file():
            continue
        if rel.parts and rel.parts[0] in allowed_prefixes:
            continue
        if rel in allowed_files:
            continue
        if path.suffix not in {".md", ".py", ".json", ".yaml", ".yml", ".toml"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for needle in forbidden:
            if needle in text:
                offenders.append(f"{rel}: {needle}")
    assert offenders == []
