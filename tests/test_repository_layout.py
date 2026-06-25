from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
LEGACY_SKILL_DIRS = ["market-research-full", "validate-market-research", "market-research-loop"]


def test_only_market_research_is_active_skill_tree():
    assert (ROOT / "market-research" / "SKILL.md").exists()
    assert (ROOT / "market-research" / "batch-supervisor" / "SKILL.md").exists()
    assert not (ROOT / "market-research" / "loop-runner").exists()
    for name in LEGACY_SKILL_DIRS:
        assert not (ROOT / name).exists(), f"{name} must be moved into market-research"


def test_generated_artifact_roots_are_ignored():
    ignore_text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    ignored = {line.strip() for line in ignore_text.splitlines() if line.strip() and not line.startswith("#")}

    assert {"data/", "reports/", "runtime/", "archives/"} <= ignored


def test_active_files_do_not_reference_old_skill_paths():
    forbidden = [
        "market-research-full" + "/",
        "validate-market-research" + "/scripts/",
        "market-research-loop" + "/scripts/",
        "$" + "market-research-full ",
        "$" + "validate-market-research ",
        "$" + "market-research-loop ",
        "market-research" + "-runs",
    ]
    allowed_files = set()
    offenders = []
    tracked_files = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.splitlines()
    for file_name in tracked_files:
        rel = Path(file_name)
        if rel in allowed_files:
            continue
        if rel.suffix not in {".md", ".py", ".json", ".yaml", ".yml", ".toml"}:
            continue
        path = ROOT / rel
        text = path.read_text(encoding="utf-8", errors="ignore")
        for needle in forbidden:
            if needle in text:
                offenders.append(f"{rel}: {needle}")
    assert offenders == []


def test_active_docs_use_canonical_consolidated_structure():
    required_docs = [
        Path("docs/README.md"),
        Path("docs/architecture.md"),
        Path("docs/quality-bar.md"),
        Path("docs/operations.md"),
    ]
    expected_active_docs = {
        Path("docs/README.md"),
        Path("docs/architecture.md"),
        Path("docs/operations.md"),
        Path("docs/quality-bar.md"),
    }
    actual_active_docs = {
        path.relative_to(ROOT)
        for path in (ROOT / "docs").rglob("*")
        if path.is_file()
    }

    assert actual_active_docs == expected_active_docs
    for rel in required_docs:
        assert (ROOT / rel).exists(), f"{rel} should be an active canonical doc"

    index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    for rel in required_docs[1:]:
        assert str(rel) in index


def test_historical_generated_docs_do_not_remain_active():
    forbidden_active = [
        Path("docs/plans/20260619_rework_plan.md"),
        Path("docs/superpowers/lessons/2026-06-22-deterministic-usage-and-self-improvement.md"),
        Path("docs/superpowers/lessons/2026-06-22-investor-grade-report-quality.md"),
        Path("docs/superpowers/plans/2026-06-23-market-research-self-improvement.json"),
        Path("docs/superpowers/plans/2026-06-24-docs-instruction-consolidation.md"),
        Path("docs/superpowers/plans/2026-06-24-full-skill-and-helper-optimization.md"),
        Path("docs/superpowers/plans/2026-06-24-post-optimization-run-handoff.md"),
        Path("docs/superpowers/plans/2026-06-24-skill-token-and-helper-optimization.md"),
        Path("docs/superpowers/specs/2026-06-21-market-research-skill-rename-and-quality-design.md"),
        Path("docs/superpowers/specs/2026-06-24-docs-instruction-consolidation-design.md"),
        Path("docs/superpowers/specs/2026-06-25-report-language-and-etf-holdings-design.md"),
    ]
    for rel in forbidden_active:
        assert not (ROOT / rel).exists(), f"{rel} should not remain active"
