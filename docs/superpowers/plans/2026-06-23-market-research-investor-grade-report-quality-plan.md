# Market Research Investor-Grade Report Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the investor usefulness of market-research reports while preserving the separation between final reports and runtime evidence.

**Architecture:** Keep `reports/` as the final product and `runtime/` as the intermediate evidence/workspace. Improve report templates, verifier checks, source navigation, deterministic summaries, and language lint so reports read like investor memos while validators can still trace evidence through explicit runtime and deterministic pointers.

**Tech Stack:** Python 3 standard library, pytest subprocess tests, Markdown skill/reference files, existing `market-research/shared/scripts/*` helpers.

---

## Files To Change

- Modify: `market-research/shared/scripts/validate_market_research.py`
  - Resolve source IDs from procedural runtime metadata and deterministic source manifests without requiring runtime evidence to be copied into reports.
  - Aggregate weak deterministic usage rationale findings in scaffold issues while preserving field detail in JSON.
  - Improve runtime-root error guidance for supervised batch run directories.
- Modify: `market-research/shared/scripts/procedural_source_helper.py`
  - Add reusable provider-payload unwrap helpers for raw provider JSON inspection.
  - Promote deterministic facts into sparse procedural research context.
- Modify: `market-research/shared/scripts/deterministic_research_collector.py`
  - Emit `normalized/sec_filings_index.json` when SEC submissions are available.
  - Add market-cap discrepancy severity and provider-limit analysis limitation summaries.
- Modify: `market-research/researcher/SKILL.md`
  - Require investor-facing synthesis and field-level freshness handling for time-sensitive datapoints.
  - Require field-specific deterministic-data usage rationales for required/review fields.
- Modify: `market-research/researcher/references/report-template.md`
  - Strengthen buy-side memo structure and deterministic usage rationale examples.
  - Move provider names, source IDs, raw paths, cache details, and skill internals into an appendix unless they affect investment interpretation.
- Modify: `market-research/verifier/SKILL.md`
  - Instruct verifier to treat deterministic scaffold source misses as non-blocking when source artifacts resolve through procedural runtime or deterministic source manifests.
  - Instruct verifier to flag unnecessary provider/tool provenance in the investor-facing body as a report-quality issue.
- Modify: `README.md`
  - Mention optional preflight command.
- Test: `tests/test_validate_market_research.py`
- Test: `tests/test_deterministic_research_collector.py`
- Test: `tests/test_market_research_acceptance.py`

## Non-Goals

- Do not copy runtime evidence into `reports/` by default.
- Do not collapse `runtime/` and `reports/` responsibilities.
- Do not optimize for report portability ahead of report quality.
- Do not remove auditability; keep detailed provenance in JSON sidecars, appendices, validation artifacts, and runtime evidence.

## Task 1: Resolve Procedural Runtime Source Registries In Validation

**Files:**
- Modify: `market-research/shared/scripts/validate_market_research.py`
- Test: `tests/test_validate_market_research.py`

- [ ] **Step 1: Write a failing test for `procedural_runtime.sources_file`**

Add this test to `tests/test_validate_market_research.py`:

```python
def test_validator_uses_procedural_runtime_sources_file(tmp_path):
    report_dir = tmp_path / "reports" / "QUBT" / "2026-06-23"
    runtime_dir = tmp_path / "runtime" / "market-research-batch-20260623" / "QUBT" / "2026-06-23"
    report_dir.mkdir(parents=True)
    runtime_dir.mkdir(parents=True)
    sources_path = runtime_dir / "sources.json"
    sources_path.write_text(
        json.dumps({"sources": [{"id": "planck_framework_pr", "title": "Planck PR"}]}),
        encoding="utf-8",
    )
    (report_dir / "QUBT-research.md").write_text("# QUBT Research\n", encoding="utf-8")
    (report_dir / "QUBT-research.json").write_text(
        json.dumps(
            {
                **complete_research_payload("QUBT", "equity"),
                "material_claims": [
                    {
                        "claim": "Planck issued an initial order.",
                        "source_id": "planck_framework_pr",
                        "confidence": "high",
                    }
                ],
                "procedural_runtime": {"sources_file": str(sources_path)},
            }
        ),
        encoding="utf-8",
    )

    result = run_validator(str(report_dir))

    assert result.returncode == 0, result.stderr
    validation = json.loads((report_dir / "QUBT-validation-scaffold.json").read_text(encoding="utf-8"))
    assert validation["blocking_issue_count"] == 0
    assert validation["issues"] == []
```

- [ ] **Step 2: Run the focused failing test**

Run:

```bash
python3 -m pytest tests/test_validate_market_research.py::test_validator_uses_procedural_runtime_sources_file -q
```

Expected: fail because `load_sources()` does not inspect `procedural_runtime.sources_file`.

- [ ] **Step 3: Implement source candidate collection**

In `market-research/shared/scripts/validate_market_research.py`, replace `load_sources()` with a two-stage helper:

```python
def source_file_candidates(run_dir: Path, report: dict[str, Any] | None = None) -> list[Path]:
    candidates = [run_dir / "sources.json"]
    if isinstance(report, dict):
        sources_file = report.get("sources_file")
        if isinstance(sources_file, str) and sources_file:
            candidates.append(Path(sources_file))
        procedural_runtime = report.get("procedural_runtime")
        if isinstance(procedural_runtime, dict):
            runtime_sources = procedural_runtime.get("sources_file")
            if isinstance(runtime_sources, str) and runtime_sources:
                candidates.append(Path(runtime_sources))
    seen: set[str] = set()
    unique: list[Path] = []
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def load_sources(run_dir: Path, report: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for path in source_file_candidates(run_dir, report):
        if not path.exists():
            continue
        payload = read_json(path)
        sources = payload.get("sources", [])
        if not isinstance(sources, list):
            continue
        for source in sources:
            if isinstance(source, dict) and source.get("id"):
                merged[str(source["id"])] = source
    return merged
```

- [ ] **Step 4: Verify the focused test passes**

Run:

```bash
python3 -m pytest tests/test_validate_market_research.py::test_validator_uses_procedural_runtime_sources_file -q
```

Expected: pass.

- [ ] **Step 5: Run validator tests**

Run:

```bash
python3 -m pytest tests/test_validate_market_research.py -q
```

Expected: pass.

## Task 2: Resolve Deterministic Source IDs And Source Artifact Paths

**Files:**
- Modify: `market-research/shared/scripts/validate_market_research.py`
- Test: `tests/test_validate_market_research.py`

- [ ] **Step 1: Write failing tests for deterministic claim support**

Add these tests to `tests/test_validate_market_research.py`:

```python
def test_validator_accepts_claim_source_id_from_deterministic_source_manifest(tmp_path):
    report_dir = tmp_path / "reports" / "QUBT" / "2026-06-23"
    data_dir = tmp_path / "data" / "QUBT" / "2026-06-23"
    normalized = data_dir / "normalized"
    report_dir.mkdir(parents=True)
    normalized.mkdir(parents=True)
    (report_dir / "QUBT-research.md").write_text("# QUBT Research\n", encoding="utf-8")
    (report_dir / "QUBT-research.json").write_text(
        json.dumps(
            {
                **complete_research_payload("QUBT", "equity"),
                "deterministic_bundle": {"bundle_dir": str(data_dir)},
                "material_claims": [
                    {
                        "claim": "SEC companyfacts support revenue.",
                        "source_id": "deterministic_sec_companyfacts",
                        "confidence": "high",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (data_dir / "research_input_pack.md").write_text("# Pack\n", encoding="utf-8")
    (data_dir / "manifest.json").write_text(json.dumps({"symbol": "QUBT", "asset_type": "equity"}), encoding="utf-8")
    (data_dir / "source_manifest.json").write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "source_id": "deterministic_sec_companyfacts",
                        "provider": "sec",
                        "raw_path": str(data_dir / "raw" / "sec" / "companyfacts.json"),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (data_dir / "gaps.json").write_text(json.dumps({"gaps": []}), encoding="utf-8")
    (normalized / "identity.json").write_text("{}", encoding="utf-8")

    result = run_validator(str(report_dir))

    assert result.returncode == 0, result.stderr
    validation = json.loads((report_dir / "QUBT-validation-scaffold.json").read_text(encoding="utf-8"))
    assert validation["blocking_issue_count"] == 0
    assert validation["issues"] == []


def test_validator_accepts_material_claim_source_artifact(tmp_path):
    report_dir = tmp_path / "reports" / "QUBT" / "2026-06-23"
    artifact = report_dir / "evidence" / "source_bundle" / "latest_10q.htm"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("<html>10-Q</html>", encoding="utf-8")
    (report_dir / "QUBT-research.md").write_text("# QUBT Research\n", encoding="utf-8")
    (report_dir / "QUBT-research.json").write_text(
        json.dumps(
            {
                **complete_research_payload("QUBT", "equity"),
                "material_claims": [
                    {
                        "claim": "Q1 revenue increased.",
                        "source_id": "latest_10q",
                        "source_artifact": str(artifact),
                        "confidence": "high",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = run_validator(str(report_dir))

    assert result.returncode == 0, result.stderr
    validation = json.loads((report_dir / "QUBT-validation-scaffold.json").read_text(encoding="utf-8"))
    assert validation["blocking_issue_count"] == 0
    assert validation["issues"] == []
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
python3 -m pytest \
  tests/test_validate_market_research.py::test_validator_accepts_claim_source_id_from_deterministic_source_manifest \
  tests/test_validate_market_research.py::test_validator_accepts_material_claim_source_artifact -q
```

Expected: fail because deterministic `source_manifest.json` and claim-level `source_artifact` are not accepted.

- [ ] **Step 3: Add deterministic source IDs to source map**

In `validate_market_research.py`, add:

```python
def load_deterministic_sources(bundle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    source_manifest = bundle.get("source_manifest")
    if not isinstance(source_manifest, Path) or not source_manifest.exists():
        return {}
    payload = read_json(source_manifest)
    sources = payload.get("sources", [])
    if not isinstance(sources, list):
        return {}
    resolved: dict[str, dict[str, Any]] = {}
    for source in sources:
        if not isinstance(source, dict):
            continue
        source_id = source.get("id") or source.get("source_id")
        if source_id:
            resolved[str(source_id)] = source
    return resolved


def claim_has_existing_source_artifact(claim: dict[str, Any]) -> bool:
    artifact = claim.get("source_artifact")
    return isinstance(artifact, str) and bool(artifact) and Path(artifact).exists()
```

In `cmd_validate()`, after `sources_by_id = load_sources(...)`, merge deterministic sources:

```python
    sources_by_id.update(load_deterministic_sources(bundle))
```

In `deterministic_issues()`, change the source check to accept an existing claim artifact:

```python
            elif claim.get("source_id") not in sources_by_id and not claim_has_existing_source_artifact(claim):
```

- [ ] **Step 4: Verify the focused tests pass**

Run:

```bash
python3 -m pytest \
  tests/test_validate_market_research.py::test_validator_accepts_claim_source_id_from_deterministic_source_manifest \
  tests/test_validate_market_research.py::test_validator_accepts_material_claim_source_artifact -q
```

Expected: pass.

- [ ] **Step 5: Run all validation tests**

Run:

```bash
python3 -m pytest tests/test_validate_market_research.py -q
```

Expected: pass.

## Task 3: Aggregate Weak Deterministic Usage Rationale Findings

**Files:**
- Modify: `market-research/shared/scripts/validate_market_research.py`
- Test: `tests/test_validate_market_research.py`

- [ ] **Step 1: Write a failing aggregation test**

Add this test to `tests/test_validate_market_research.py`:

```python
def test_validator_aggregates_weak_usage_rationale_issues(tmp_path):
    report_dir = tmp_path / "reports" / "AAPL" / "2026-06-01"
    data_dir = tmp_path / "data" / "AAPL" / "2026-06-01"
    normalized = data_dir / "normalized"
    report_dir.mkdir(parents=True)
    normalized.mkdir(parents=True)
    (report_dir / "AAPL-research.md").write_text("# AAPL Research\n", encoding="utf-8")
    (report_dir / "AAPL-research.json").write_text(
        json.dumps(
            {
                **complete_research_payload("AAPL", "equity"),
                "deterministic_bundle": {"bundle_dir": str(data_dir)},
                "deterministic_data_usage": [
                    {
                        "field_path": "equity_fundamentals.ebitda",
                        "disposition": "used",
                        "rationale": "Used in key facts.",
                        "report_section": "Financials",
                    },
                    {
                        "field_path": "equity_fundamentals.eps",
                        "disposition": "used",
                        "rationale": "Used in key facts.",
                        "report_section": "Financials",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (data_dir / "research_input_pack.md").write_text("# Pack\n", encoding="utf-8")
    (data_dir / "manifest.json").write_text(json.dumps({"symbol": "AAPL", "asset_type": "equity"}), encoding="utf-8")
    (data_dir / "source_manifest.json").write_text(json.dumps({"sources": []}), encoding="utf-8")
    (data_dir / "gaps.json").write_text(json.dumps({"gaps": []}), encoding="utf-8")
    (data_dir / "deterministic_data_usage.json").write_text(
        json.dumps(
            {
                "version": "deterministic-data-usage-v1",
                "datapoints": [
                    {"field_path": "equity_fundamentals.ebitda", "materiality": "required"},
                    {"field_path": "equity_fundamentals.eps", "materiality": "required"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (normalized / "equity_fundamentals.json").write_text(
        json.dumps(
            {
                "ebitda": {"value": -1000, "status": "ok", "provider": "alphavantage"},
                "eps": {"value": -0.26, "status": "ok", "provider": "alphavantage"},
            }
        ),
        encoding="utf-8",
    )

    result = run_validator(str(report_dir))

    assert result.returncode == 0, result.stderr
    validation = json.loads((report_dir / "AAPL-validation-scaffold.json").read_text(encoding="utf-8"))
    issue_ids = [issue["id"] for issue in validation["issues"]]
    assert issue_ids == ["deterministic-usage-weak-required-summary"]
    assert "2 required deterministic datapoints" in validation["issues"][0]["description"]
    assert validation["issue_counts"]["minor"] == 1
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
python3 -m pytest tests/test_validate_market_research.py::test_validator_aggregates_weak_usage_rationale_issues -q
```

Expected: fail because current output emits one issue per field.

- [ ] **Step 3: Replace per-field weak issue emission with aggregate issues**

In `usage_disposition_issues()`, keep `missing_required` as individual moderate issues. Replace loops for `weak_required` and `weak_review` with aggregate issue creation:

```python
def summarize_weak_usage(items: list[dict[str, Any]], materiality: str) -> dict[str, Any] | None:
    if not items:
        return None
    sample = ", ".join(str(item.get("field_path", "unknown")) for item in items[:8])
    extra = "" if len(items) <= 8 else f", and {len(items) - 8} more"
    return {
        "id": f"deterministic-usage-weak-{materiality}-summary",
        "severity": "minor",
        "status": "open",
        "description": (
            f"{len(items)} {materiality} deterministic datapoints have weak report JSON usage rationales. "
            f"Use field-specific rationales and report sections. Sample: {sample}{extra}."
        ),
    }
```

Then append summaries for `weak_required` and `weak_review`.

- [ ] **Step 4: Verify aggregation test passes**

Run:

```bash
python3 -m pytest tests/test_validate_market_research.py::test_validator_aggregates_weak_usage_rationale_issues -q
```

Expected: pass.

- [ ] **Step 5: Update any tests that intentionally assert per-field weak issue IDs**

Update `test_validator_flags_weak_required_deterministic_usage_rationale` so it expects `deterministic-usage-weak-required-summary`.

- [ ] **Step 6: Run validation tests**

Run:

```bash
python3 -m pytest tests/test_validate_market_research.py -q
```

Expected: pass.

## Task 4: Add SEC Filing Index Output

**Files:**
- Modify: `market-research/shared/scripts/deterministic_research_collector.py`
- Test: `tests/test_deterministic_research_collector.py`

- [ ] **Step 1: Write a failing unit test for SEC filing index normalization**

Add a focused test near existing SEC collector tests in `tests/test_deterministic_research_collector.py`:

```python
def test_build_bundle_emits_sec_filings_index(tmp_path):
    bundle_dir = tmp_path / "data" / "QUBT" / "2026-06-23"
    raw_dir = bundle_dir / "raw" / "sec"
    normalized = bundle_dir / "normalized"
    raw_dir.mkdir(parents=True)
    normalized.mkdir(parents=True)
    submissions_raw = raw_dir / "sec_submissions.json"
    submissions_raw.write_text(
        json.dumps(
            {
                "data": {
                    "filings": {
                        "recent": {
                            "accessionNumber": ["0001758009-26-000001"],
                            "form": ["10-Q"],
                            "filingDate": ["2026-05-11"],
                            "reportDate": ["2026-03-31"],
                            "primaryDocument": ["qubt-20260331.htm"],
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    module.emit_sec_filings_index(bundle_dir, submissions_raw, "0001758009")

    index = json.loads((normalized / "sec_filings_index.json").read_text(encoding="utf-8"))
    assert index["filings"][0]["form"] == "10-Q"
    assert index["filings"][0]["accession_number"] == "0001758009-26-000001"
    assert index["filings"][0]["primary_document_url"].endswith("/qubt-20260331.htm")
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
python3 -m pytest tests/test_deterministic_research_collector.py::test_build_bundle_emits_sec_filings_index -q
```

Expected: fail because `emit_sec_filings_index()` does not exist.

- [ ] **Step 3: Implement SEC wrapper unwrapping and index writing**

Add an implementation that:

- reads SEC raw JSON
- unwraps top-level `data` when present
- reads `filings.recent`
- writes `normalized/sec_filings_index.json`
- records each filing with accession number, form, filing date, report date, primary document, primary document URL, and source raw path

- [ ] **Step 4: Call the helper during bundle build**

Find the SEC submissions normalization path in `deterministic_research_collector.py` and call `emit_sec_filings_index()` whenever SEC submissions raw data exists.

- [ ] **Step 5: Verify focused and collector tests**

Run:

```bash
python3 -m pytest tests/test_deterministic_research_collector.py::test_build_bundle_emits_sec_filings_index -q
python3 -m pytest tests/test_deterministic_research_collector.py -q
```

Expected: pass.

## Task 5: Add Investor-Facing Provenance Hygiene And Field-Level Freshness Policy

**Files:**
- Modify: `market-research/researcher/references/report-template.md`
- Modify: `market-research/researcher/SKILL.md`
- Modify: `market-research/verifier/SKILL.md`
- Test: `tests/test_market_research_acceptance.py`
- Test: `tests/test_report_language_lint.py`

- [ ] **Step 1: Add acceptance tests for provider/internal-reference placement**

Add to `tests/test_market_research_acceptance.py`:

```python
def test_report_template_moves_provider_and_skill_internals_to_appendix():
    text = (ROOT / "market-research" / "researcher" / "references" / "report-template.md").read_text(encoding="utf-8").lower()
    assert "provider names" in text
    assert "appendix" in text
    assert "unless they affect investment interpretation" in text
    assert "time-sensitive" in text
    assert "latest available" in text
    assert "cache mechanics" in text


def test_verifier_flags_unnecessary_provider_provenance_in_main_body():
    text = (ROOT / "market-research" / "verifier" / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "provider names" in text
    assert "main body" in text
    assert "appendix" in text
```

- [ ] **Step 2: Add report language lint coverage**

Add a lint fixture to `tests/test_report_language_lint.py` that fails when main-body prose contains local artifact paths or skill internals outside an appendix heading:

```python
def test_report_language_lint_rejects_skill_internal_paths_in_main_body():
    text = """# QUBT Research

## Bottom Line

Primary evidence consists of the deterministic bundle under `data/QUBT/2026-06-23/`.

## Evidence Appendix

`data/QUBT/2026-06-23/source_manifest.json`
"""
    findings = module.lint_report_language(text)
    assert any("skill-internal provenance belongs in an appendix" in finding["message"] for finding in findings)
```

- [ ] **Step 3: Run the failing tests**

Run:

```bash
python3 -m pytest tests/test_market_research_acceptance.py tests/test_report_language_lint.py -q
```

Expected: fail before template, verifier, and lint updates.

- [ ] **Step 4: Update researcher template guidance**

In `market-research/researcher/references/report-template.md`, add:

```markdown
Provider and provenance placement:

- In the main investor narrative, name providers only when the provider identity changes interpretation, such as a material discrepancy, stale source, missing data category, or source-quality caveat.
- Use investor-readable phrases such as "latest available market data", "SEC filings", or "company press release" when provider identity is not material.
- Put source IDs, local paths, raw paths, hashes, deterministic bundle names, runtime directories, cache paths, and skill/tool internals in an Evidence Appendix or JSON sidecar, not in the main body.

Field-level freshness:

- Time-sensitive fields should be fresh or explicitly described as latest available: price, volume, market cap, short interest, forward estimates, recent news, insider transactions, and event-driven catalysts.
- Durable filed evidence may use cached artifacts when source dates are preserved: SEC filings, company releases, historical financial statements, company identity, and risk-factor text.
- Main report disclosure should focus on stale or unavailable material data, not cache mechanics.
- Cache mechanics belong in references, validation artifacts, manifests, or JSON sidecars.
```

- [ ] **Step 5: Update verifier guidance**

In `market-research/verifier/SKILL.md`, add:

```markdown
Assess investor-facing provenance hygiene. Provider names and local tool paths are appropriate in an appendix or sidecar, and appropriate in the main body only when they affect interpretation. Flag main-body references to deterministic bundles, runtime directories, raw paths, source IDs, hashes, cache files, or provider names that do not change the investment conclusion.
```

- [ ] **Step 6: Implement or extend language lint**

In `tests/test_report_language_lint.py` and its target module, add a rule that scans content before headings matching `appendix`, `sources`, `evidence`, or `data quality` and flags patterns:

```python
INTERNAL_PROVENANCE_PATTERNS = [
    "deterministic bundle",
    "runtime/",
    "data/",
    "source_manifest.json",
    "sources.json",
    "normalized/",
    "raw/",
]
```

The message should be:

```text
skill-internal provenance belongs in an appendix unless it changes the investment interpretation
```

- [ ] **Step 7: Verify tests**

Run:

```bash
python3 -m pytest tests/test_market_research_acceptance.py tests/test_report_language_lint.py -q
```

Expected: pass.

## Task 6: Add Provider-Limit And Market-Cap Discrepancy Summaries

**Files:**
- Modify: `market-research/shared/scripts/deterministic_research_collector.py`
- Modify: `market-research/researcher/references/report-template.md`
- Test: `tests/test_deterministic_research_collector.py`

- [ ] **Step 1: Write failing tests for derived limitation summaries**

Add tests that create fixture endpoint statuses for unavailable short interest, unavailable forward estimates, plan-gated insider statistics, and divergent market caps. Assert the collector emits:

```json
{
  "analysis_limitations": [
    {
      "area": "short_interest",
      "impact": "crowding_and_squeeze_analysis_limited",
      "attempted_providers": ["..."],
      "status": "unavailable"
    }
  ],
  "discrepancies": [
    {
      "field_path": "market_snapshot.market_capitalization",
      "severity": "material",
      "primary_provider": "alphavantage",
      "alternate_provider": "fmp"
    }
  ]
}
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
python3 -m pytest tests/test_deterministic_research_collector.py -q
```

Expected: the new tests fail before implementation.

- [ ] **Step 3: Implement derived summaries**

Add deterministic functions with no network dependency:

- `analysis_limitations_from_endpoint_status(endpoint_status: list[dict[str, Any]]) -> list[dict[str, Any]]`
- `market_cap_discrepancy(primary: dict[str, Any], alternate: dict[str, Any]) -> dict[str, Any] | None`

Use a material discrepancy threshold of 20% relative difference for market capitalization. Preserve provider names and raw paths.

- [ ] **Step 4: Add report-template guidance**

In `market-research/researcher/references/report-template.md`, add a concise instruction:

```markdown
If deterministic `analysis_limitations` or `discrepancies` exist, map each material item to the affected analysis area instead of listing provider errors mechanically.
```

- [ ] **Step 5: Verify tests**

Run:

```bash
python3 -m pytest tests/test_deterministic_research_collector.py tests/test_market_research_acceptance.py -q
```

Expected: pass.

## Task 7: Add Environment Preflight

**Files:**
- Create: `market-research/shared/scripts/preflight_environment.py`
- Modify: `README.md`
- Test: `tests/test_market_research_acceptance.py`

- [ ] **Step 1: Create a failing acceptance test**

Add:

```python
def test_readme_mentions_environment_preflight():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "preflight_environment.py" in text
    assert "jsonschema" in text
    assert "lmodern" in text
```

- [ ] **Step 2: Implement the preflight script**

Create `market-research/shared/scripts/preflight_environment.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import shutil


def main() -> None:
    checks = {
        "jsonschema": importlib.util.find_spec("jsonschema") is not None,
        "pandoc": shutil.which("pandoc") is not None,
        "xelatex": shutil.which("xelatex") is not None,
    }
    checks["lmodern"] = False
    if checks["xelatex"] and shutil.which("kpsewhich"):
        checks["lmodern"] = shutil.which("kpsewhich") is not None
    print(json.dumps({"checks": checks}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Update README**

Add:

```markdown
Optional environment preflight:

```bash
python3 market-research/shared/scripts/preflight_environment.py
```

This reports optional `jsonschema`, `pandoc`, `xelatex`, and LaTeX package availability such as `lmodern`. Missing PDF tooling is non-fatal.
```

- [ ] **Step 4: Run acceptance tests**

Run:

```bash
python3 -m pytest tests/test_market_research_acceptance.py -q
```

Expected: pass.

## Task 8: Final Verification

**Files:**
- All changed files from Tasks 1-7

- [ ] **Step 1: Run full test suite**

Run:

```bash
python3 -m pytest tests
```

Expected: all tests pass.

- [ ] **Step 2: Run helper smoke commands**

Run:

```bash
python3 market-research/shared/scripts/validate_market_research.py --help
python3 market-research/shared/scripts/procedural_source_helper.py --help
python3 market-research/shared/scripts/deterministic_research_collector.py --help
python3 market-research/shared/scripts/preflight_environment.py
```

Expected: help commands exit 0; preflight prints JSON.

- [ ] **Step 3: Re-run validation scaffold against QUBT**

Run:

```bash
python3 market-research/shared/scripts/validate_market_research.py reports/QUBT/2026-06-23 --force
```

Expected: no false moderate source misses for resolvable runtime or deterministic sources; weak deterministic usage rationales appear as aggregate minor warnings.

- [ ] **Step 4: Commit**

Run:

```bash
git status --short
git add market-research/shared/scripts/validate_market_research.py \
  market-research/shared/scripts/procedural_source_helper.py \
  market-research/shared/scripts/deterministic_research_collector.py \
  market-research/shared/scripts/preflight_environment.py \
  market-research/researcher/SKILL.md \
  market-research/researcher/references/report-template.md \
  market-research/verifier/SKILL.md \
  README.md \
  tests/test_validate_market_research.py \
  tests/test_procedural_source_helper.py \
  tests/test_deterministic_research_collector.py \
  tests/test_market_research_acceptance.py
git commit -m "harden market research artifact validation"
```

Expected: one focused commit with helper and test changes.

## Risks

- Source resolution must not accept arbitrary missing `source_id` values. Existing artifact paths or registered deterministic sources should be required.
- Runtime and report separation is intentional. Do not introduce changes that copy runtime evidence into final reports by default or make report generation depend on duplicating intermediate artifacts.
- Aggregating weak deterministic rationale issues should not hide missing required dispositions. Missing required fields remain moderate blocking issues.
- SEC filing index generation must tolerate SEC schema drift and wrapped raw payloads without breaking bundle generation.
- Dependency preflight should report missing optional tools without changing batch pass/fail behavior.
