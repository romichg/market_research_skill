# Market Research Investor-Grade Report Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve market-research quality after the 2026-06-22 QUBT batch by making reports read like investor-grade research while preserving deterministic evidence coverage, validation, and auditability.

**Architecture:** Separate reader-facing narrative quality from machine-facing evidence coverage. Keep local artifact paths and field-level deterministic usage in JSON sidecars or consolidated evidence sections, while the Markdown report prioritizes thesis, synthesis, judgment, risks, variant view, and monitoring triggers. Add tests first around citation density, investor-grade rubric guidance, weak usage-disposition rationales, reference-audit precision, filing-section gap severity/actionability, lifecycle-aware usage materiality, and provider-impact disclosure.

**Tech Stack:** Python 3 standard library CLI helpers, pytest, JSON/Markdown artifacts, Agent Skills Markdown.

---

## Evidence Base

- Batch summary: `runtime/market-research-batch-20260622/research-loop-summary.json`
- Final report: `reports/QUBT/2026-06-22/QUBT-research.md`
- Final report JSON: `reports/QUBT/2026-06-22/QUBT-research.json`
- Deterministic usage contract: `data/QUBT/2026-06-22/deterministic_data_usage.json`
- Deterministic validation scaffold: `reports/QUBT/2026-06-22/QUBT-validation-scaffold.json`
- Fresh validation: `reports/QUBT/2026-06-22/QUBT-validation.json`
- Provider status and limitations: `data/QUBT/2026-06-22/manifest.json`
- Data gaps: `data/QUBT/2026-06-22/gaps.json`
- Prior lesson: `docs/superpowers/lessons/2026-06-22-deterministic-usage-and-self-improvement.md`
- Existing remediation plan: `docs/superpowers/plans/2026-06-21-market-research-quality-remediation.md`

## File Structure

- Modify: `market-research/shared/scripts/deterministic_data_usage.py`
  - Add rationale-quality checks and lifecycle-aware materiality helpers.
- Modify: `market-research/shared/scripts/validate_market_research.py`
  - Emit weak-disposition issues, split usage-reference categories, check citation-density guidance where practical, and improve filing-section gap issue detail.
- Modify: `market-research/shared/scripts/deterministic_research_collector.py`
  - Add lifecycle hints to usage requirement generation where current normalized data supports them.
- Modify: `market-research/researcher/SKILL.md`
  - Require investor-grade narrative quality, field-specific deterministic usage rationales, and provider-impact disclosure.
- Modify: `market-research/researcher/references/report-template.md`
  - Move detailed citations toward consolidated evidence sections and sidecars; add concrete JSON-sidecar examples for `latest_volume`, provider-impact mapping, and potential contract value wording.
- Modify: `market-research/verifier/SKILL.md`
  - Require verifier review of investor usefulness, weak sidecar rationales, and narrative-use versus artifact-reference distinction.
- Test: `tests/test_market_research_acceptance.py`
- Test: `tests/test_deterministic_data_usage.py`
- Test: `tests/test_validate_market_research.py`
- Test: `tests/test_deterministic_research_collector.py`

## Task 1: Add Investor-Grade Narrative And Citation-Density Guidance

**Files:**
- Modify: `market-research/researcher/SKILL.md`
- Modify: `market-research/researcher/references/report-template.md`
- Modify: `market-research/verifier/SKILL.md`
- Test: `tests/test_market_research_acceptance.py`

- [ ] **Step 1: Add failing acceptance tests for narrative quality guidance**

Add to `tests/test_market_research_acceptance.py`:

```python
def test_report_template_prioritizes_investor_grade_narrative_over_citation_dump():
    text = (ROOT / "market-research" / "researcher" / "references" / "report-template.md").read_text(encoding="utf-8").lower()
    assert "investor-grade" in text
    assert "do not turn the report into an audit trail" in text
    assert "consolidated evidence" in text
    assert "local artifact paths" in text


def test_verifier_checks_investor_usefulness_not_only_deterministic_coverage():
    text = (ROOT / "market-research" / "verifier" / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "investor usefulness" in text
    assert "deterministic coverage is not sufficient" in text
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
python3 -m pytest tests/test_market_research_acceptance.py::test_report_template_prioritizes_investor_grade_narrative_over_citation_dump tests/test_market_research_acceptance.py::test_verifier_checks_investor_usefulness_not_only_deterministic_coverage -v
```

Expected: fail because the guidance does not yet contain these phrases.

- [ ] **Step 3: Update researcher guidance**

In `market-research/researcher/SKILL.md`, add:

```markdown
The Markdown report must read like investor-grade research, not a validation transcript. Use deterministic data aggressively, but do not make deterministic coverage the organizing principle of the prose. Lead with thesis, variant view, what matters, what can go wrong, what would change the view, and what to monitor. Keep detailed local artifact paths in the JSON sidecar or a consolidated evidence section unless an inline citation is necessary for a contentious, surprising, or source-sensitive claim.
```

- [ ] **Step 4: Update report template**

In `market-research/researcher/references/report-template.md`, add a section before the Markdown skeleton:

```markdown
## Reader Experience And Evidence Placement

Write the main Markdown as an investor memo. Do not turn the report into an audit trail. Local artifact paths are important for validation, but they should usually live in `sources.json`, `material_claims`, `deterministic_data_usage`, or a consolidated evidence section rather than after every paragraph.

Use inline citations sparingly:

- Use them for highly material numbers, controversial claims, direct filing language, or places where source quality itself matters.
- Avoid appending `Source:` to every paragraph when the paragraph is ordinary synthesis from already captured evidence.
- Prefer one consolidated `Sources And Evidence` section that maps major claim groups to local artifacts.
```

- [ ] **Step 5: Update verifier guidance**

In `market-research/verifier/SKILL.md`, add:

```markdown
Investor usefulness is a validation dimension. Deterministic coverage is not sufficient if the report reads like a source inventory or compliance transcript. Check whether the report has a clear thesis, prioritizes material facts, explains variant view and risks, and keeps citations from overwhelming the prose. Treat excessive path-level citation density as a minor quality issue; treat missing thesis or purely mechanical deterministic recitation as moderate.
```

- [ ] **Step 6: Verify focused tests**

Run:

```bash
python3 -m pytest tests/test_market_research_acceptance.py -v
```

Expected: pass.

## Task 2: Flag Weak Deterministic Usage Rationales

**Files:**
- Modify: `market-research/shared/scripts/deterministic_data_usage.py`
- Modify: `market-research/shared/scripts/validate_market_research.py`
- Test: `tests/test_deterministic_data_usage.py`
- Test: `tests/test_validate_market_research.py`

- [ ] **Step 1: Add a failing unit test for boilerplate rationales**

Add to `tests/test_deterministic_data_usage.py`:

```python
def test_compare_usage_dispositions_flags_weak_required_rationale():
    module = load_module()
    requirements = {
        "datapoints": [
            {
                "field_path": "equity_fundamentals.ebitda",
                "materiality": "required",
                "field_name": "ebitda",
                "value": -57941000,
            }
        ]
    }
    report = {
        "deterministic_data_usage": [
            {
                "field_path": "equity_fundamentals.ebitda",
                "disposition": "used",
                "rationale": "Used in the report as part of identity, market snapshot, financial profile, valuation/performance context, or technical context.",
                "report_section": "Financials, Holdings, And Balance Sheet",
            }
        ]
    }
    comparison = module.compare_usage_dispositions(requirements, report)
    assert comparison["summary"]["weak_required"] == 1
    assert comparison["weak_required"][0]["field_path"] == "equity_fundamentals.ebitda"
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
python3 -m pytest tests/test_deterministic_data_usage.py::test_compare_usage_dispositions_flags_weak_required_rationale -v
```

Expected: fail because `weak_required` is not implemented.

- [ ] **Step 3: Implement rationale-quality checks**

In `market-research/shared/scripts/deterministic_data_usage.py`, add:

```python
GENERIC_RATIONALE_PHRASES = {
    "used in the report as part of identity, market snapshot, financial profile, valuation/performance context, or technical context",
    "used in the report",
    "not material",
}


def weak_usage_rationale(entry: dict[str, Any], requirement: dict[str, Any]) -> str | None:
    rationale = str(entry.get("rationale") or "").strip()
    disposition = entry.get("disposition")
    field_name = str(requirement.get("field_name") or "").lower()
    if len(rationale) < 24:
        return "rationale_too_short"
    if rationale.lower().rstrip(".") in GENERIC_RATIONALE_PHRASES:
        return "generic_rationale"
    if disposition == "used" and not entry.get("report_section"):
        return "used_without_report_section"
    if disposition == "used" and field_name and field_name not in rationale.lower() and field_name.replace("_", " ") not in rationale.lower():
        return "rationale_not_field_specific"
    return None
```

Update `compare_usage_dispositions()` so it returns `weak_required`, `weak_review`, and summary counts.

- [ ] **Step 4: Add validator issue generation**

In `market-research/shared/scripts/validate_market_research.py`, update `usage_disposition_issues()` to emit minor issues for weak required/review rationales:

```python
for item in comparison.get("weak_required", []):
    field_path = item.get("field_path", "unknown")
    reason = item.get("weak_reason", "weak_rationale")
    issues.append({
        "id": f"deterministic-usage-weak-required-{str(field_path).replace('.', '-')}",
        "severity": "minor",
        "status": "open",
        "description": f"Report JSON disposition for required deterministic datapoint {field_path} is weak: {reason}. Use a field-specific rationale and report section.",
    })
```

- [ ] **Step 5: Verify focused tests**

Run:

```bash
python3 -m pytest tests/test_deterministic_data_usage.py tests/test_validate_market_research.py -v
```

Expected: pass after updating any existing assertions for new summary fields.

## Task 3: Split Narrative Use From Artifact Reference In The Usage Audit

**Files:**
- Modify: `market-research/shared/scripts/deterministic_data_usage.py`
- Modify: `market-research/shared/scripts/validate_market_research.py`
- Test: `tests/test_deterministic_data_usage.py`
- Test: `tests/test_validate_market_research.py`

- [ ] **Step 1: Add a failing audit test**

Add to `tests/test_deterministic_data_usage.py`:

```python
def test_usage_audit_does_not_treat_raw_path_only_as_narrative_use(tmp_path):
    module = load_module()
    normalized = tmp_path / "normalized"
    normalized.mkdir()
    raw_path = "data/QUBT/2026-06-22/raw/alphavantage/example.json"
    (normalized / "equity_fundamentals.json").write_text(
        json.dumps({
            "operating_margin_ttm": {
                "value": -5.57,
                "provider": "alphavantage",
                "source_url": "https://example.test/overview",
                "raw_path": raw_path,
                "status": "ok",
            }
        }),
        encoding="utf-8",
    )
    report_md = tmp_path / "report.md"
    report_md.write_text(f"Sources: `{raw_path}`.", encoding="utf-8")
    audit = module.deterministic_data_usage_audit(
        {"normalized": normalized, "report_markdown": report_md, "report_json": None},
        {},
    )
    item = audit["datapoints"][0]
    assert item["usage_status"] == "evidence_only_reference"
    assert "raw_path" in item["reference_reasons"]
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
python3 -m pytest tests/test_deterministic_data_usage.py::test_usage_audit_does_not_treat_raw_path_only_as_narrative_use -v
```

Expected: fail because the audit currently returns `referenced`.

- [ ] **Step 3: Implement status categories**

In `deterministic_data_usage.py`, update audit classification:

```python
def usage_status_from_reasons(reasons: list[str]) -> str:
    narrative_reasons = {"value"}
    structural_reasons = {"field_path", "field_name", "raw_path", "source_url"}
    if any(reason in narrative_reasons for reason in reasons):
        return "narrative_used"
    if any(reason in structural_reasons for reason in reasons):
        return "evidence_only_reference"
    return "not_referenced"
```

Update summary keys to include `narrative_used`, `evidence_only_reference`, and `not_referenced`. Keep `referenced` temporarily as `narrative_used + evidence_only_reference` for compatibility.

- [ ] **Step 4: Update scaffold markdown wording**

In `validate_market_research.py`, change scaffold text from:

```text
Deterministic data usage: X referenced, Y not referenced...
```

to:

```text
Deterministic data usage: X narrative-used, Y evidence-only references, Z not referenced...
```

- [ ] **Step 5: Verify focused tests**

Run:

```bash
python3 -m pytest tests/test_deterministic_data_usage.py tests/test_validate_market_research.py -v
```

Expected: pass.

## Task 4: Add Lifecycle-Aware Review Materiality For Early-Stage Volatile Equities

**Files:**
- Modify: `market-research/shared/scripts/deterministic_data_usage.py`
- Modify: `market-research/shared/scripts/deterministic_research_collector.py`
- Test: `tests/test_deterministic_data_usage.py`
- Test: `tests/test_deterministic_research_collector.py`

- [ ] **Step 1: Add failing materiality tests**

Add to `tests/test_deterministic_data_usage.py`:

```python
def test_early_stage_volatile_equity_promotes_selected_context_fields_to_review():
    module = load_module()
    hints = {
        "asset_type": "equity",
        "negative_eps": True,
        "high_realized_volatility": True,
        "micro_or_early_revenue": True,
    }
    assert module.classify_materiality("market_snapshot.latest_volume", "equity", hints) == "review"
    assert module.classify_materiality("equity_fundamentals.book_value", "equity", hints) == "review"
    assert module.classify_materiality("equity_fundamentals.operating_margin_ttm", "equity", hints) == "review"
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
python3 -m pytest tests/test_deterministic_data_usage.py::test_early_stage_volatile_equity_promotes_selected_context_fields_to_review -v
```

Expected: fail because `classify_materiality()` does not accept lifecycle hints.

- [ ] **Step 3: Implement lifecycle hints**

Update `classify_materiality(field_path, asset_type=None, lifecycle_hints=None)` and promote these field paths to `review` when hints identify early-stage volatile equities:

```python
EARLY_STAGE_REVIEW_FIELD_PATHS = {
    "market_snapshot.latest_volume",
    "equity_fundamentals.book_value",
    "equity_fundamentals.operating_margin_ttm",
    "equity_fundamentals.return_on_assets_ttm",
    "equity_fundamentals.return_on_equity_ttm",
    "equity_fundamentals.quarterly_revenue_growth_yoy",
}
```

Treat an equity as early-stage volatile when at least two hints are true among negative EPS/EBITDA, high realized volatility, very low revenue, and recent revenue step-up.

- [ ] **Step 4: Generate hints from normalized data**

In `deterministic_research_collector.py`, before `build_usage_requirements()`, derive hints from normalized fundamentals and technical signals:

```python
lifecycle_hints = infer_lifecycle_hints(normalized_dir, asset_type)
usage_requirements = build_usage_requirements(normalized_dir, asset_type, lifecycle_hints)
```

Add `infer_lifecycle_hints()` with deterministic thresholds:

```python
negative_eps = eps < 0 if eps is not None else False
negative_ebitda = ebitda < 0 if ebitda is not None else False
high_realized_volatility = realized_volatility_30 is not None and realized_volatility_30 >= 0.8
micro_or_early_revenue = revenue_ttm is not None and revenue_ttm < 50_000_000
```

- [ ] **Step 5: Verify focused tests**

Run:

```bash
python3 -m pytest tests/test_deterministic_data_usage.py tests/test_deterministic_research_collector.py -v
```

Expected: pass.

## Task 5: Make Filing-Section Gaps Actionable

**Files:**
- Modify: `market-research/shared/scripts/validate_market_research.py`
- Modify: `market-research/verifier/SKILL.md`
- Test: `tests/test_validate_market_research.py`

- [ ] **Step 1: Add a failing validator test**

Add to `tests/test_validate_market_research.py`:

```python
def test_validator_filing_section_gap_issue_includes_remediation_targets(tmp_path):
    run_dir = make_minimal_report_bundle(tmp_path)
    data_dir = tmp_path / "data" / "QUBT" / "2026-06-22"
    data_dir.mkdir(parents=True)
    (data_dir / "gaps.json").write_text(
        json.dumps({
            "gaps": [
                {
                    "field": "filing_section_extracts",
                    "status": "workflow_output_absent",
                    "attempted_sources": ["sec_submissions", "sec_companyfacts"],
                    "notes": "No filing sections.",
                }
            ]
        }),
        encoding="utf-8",
    )
    validation = run_validation(run_dir, data_bundle=data_dir)
    issue = next(item for item in validation["issues"] if item["id"] == "filing-section-extracts-missing")
    assert "market-research/shared/scripts/deterministic_research_collector.py" in issue["description"]
    assert "market-research/researcher/references/report-template.md" in issue["description"]
```

If existing test helpers have different names, reuse the local helper pattern already present in `tests/test_validate_market_research.py`.

- [ ] **Step 2: Run the failing test**

Run:

```bash
python3 -m pytest tests/test_validate_market_research.py::test_validator_filing_section_gap_issue_includes_remediation_targets -v
```

Expected: fail until validator emits a structured filing-section issue.

- [ ] **Step 3: Implement filing-section issue details**

In `validate_market_research.py`, when `gaps.json` contains `filing_section_extracts` or no `normalized/sec_filing_sections.json` exists for an equity with recent 10-K/10-Q metadata, add an issue:

```python
{
    "id": "filing-section-extracts-missing",
    "severity": "minor",
    "status": "open",
    "description": "Deterministic bundle lacks SEC filing-section extracts. Remediation targets: add extraction or explicit unavailable status in market-research/shared/scripts/deterministic_research_collector.py; require report disclosure in market-research/researcher/references/report-template.md; verifier should treat undisclosed filing-specific risk limitations as moderate.",
}
```

Keep severity minor when the report discloses the limitation; escalate to moderate when the report omits the gap.

- [ ] **Step 4: Update verifier guidance**

In `market-research/verifier/SKILL.md`, add a short rule:

```markdown
If filing-section extracts are absent for an equity, check whether the report discloses that limitation. Treat disclosed absence as a minor evidence-depth issue; treat undisclosed absence as moderate when the report discusses filing-specific risks, MD&A, litigation, liquidity, or going-concern claims.
```

- [ ] **Step 5: Verify focused tests**

Run:

```bash
python3 -m pytest tests/test_validate_market_research.py -v
```

Expected: pass.

## Task 6: Require Provider-Limit Impact Mapping

**Files:**
- Modify: `market-research/researcher/SKILL.md`
- Modify: `market-research/researcher/references/report-template.md`
- Modify: `market-research/verifier/SKILL.md`
- Test: `tests/test_market_research_acceptance.py` or `tests/test_repository_layout.py`

- [ ] **Step 1: Add documentation acceptance assertions**

Add assertions to the existing documentation/acceptance test suite:

```python
def test_researcher_guidance_requires_provider_impact_mapping():
    text = (ROOT / "market-research" / "researcher" / "SKILL.md").read_text(encoding="utf-8")
    assert "provider-limit impact" in text.lower()
    assert "affected analysis area" in text.lower()
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
python3 -m pytest tests/test_market_research_acceptance.py::test_researcher_guidance_requires_provider_impact_mapping -v
```

Expected: fail until guidance is added.

- [ ] **Step 3: Update researcher guidance**

In `market-research/researcher/SKILL.md`, add:

```markdown
When provider endpoints are rate-limited, plan-gated, protected, or unavailable, map each material limitation to the affected analysis area. Examples: unavailable short interest affects crowding/squeeze analysis; unavailable forward estimates affects valuation; unavailable insider statistics affects dilution/governance analysis; unavailable filing sections affects direct risk-factor and MD&A validation.
```

- [ ] **Step 4: Update report template JSON**

In `market-research/researcher/references/report-template.md`, extend `source_coverage` example:

```json
"provider_limit_impact": [
  {
    "provider_or_gap": "FMP insider statistics plan-gated",
    "affected_analysis_area": "Dilution and governance monitoring",
    "report_handling": "Used SEC filing index evidence; did not quantify insider activity."
  }
]
```

- [ ] **Step 5: Update verifier guidance**

In `market-research/verifier/SKILL.md`, require validation to check that material provider limits are tied to affected analysis areas, not only listed.

- [ ] **Step 6: Verify focused tests**

Run:

```bash
python3 -m pytest tests/test_market_research_acceptance.py tests/test_repository_layout.py -v
```

Expected: pass.

## Task 7: Add Potential-Value News Wording Guidance

**Files:**
- Modify: `market-research/researcher/references/report-template.md`
- Modify: `market-research/verifier/SKILL.md`
- Test: `tests/test_market_research_acceptance.py`

- [ ] **Step 1: Add guidance assertion**

Add:

```python
def test_report_template_requires_potential_value_not_booked_revenue_framing():
    text = (ROOT / "market-research" / "researcher" / "references" / "report-template.md").read_text(encoding="utf-8").lower()
    assert "potential value" in text
    assert "booked revenue" in text
    assert "milestone" in text
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
python3 -m pytest tests/test_market_research_acceptance.py::test_report_template_requires_potential_value_not_booked_revenue_framing -v
```

Expected: fail until guidance is added.

- [ ] **Step 3: Update report template**

Add under news/catalyst guidance:

```markdown
For framework agreements, letters of intent, milestone-dependent values, or "up to" contract announcements, state whether the amount is booked revenue, backlog, a firm order, a non-binding framework, or potential value dependent on milestones. Do not let potential program value read like recognized revenue.
```

- [ ] **Step 4: Update verifier guidance**

Add:

```markdown
When reports cite news with "potential", "up to", "framework", or milestone language, verify that the report does not present it as booked revenue unless a filing or company source supports that treatment.
```

- [ ] **Step 5: Verify focused tests**

Run:

```bash
python3 -m pytest tests/test_market_research_acceptance.py -v
```

Expected: pass.

## Final Verification

Run:

```bash
python3 -m pytest tests
python3 market-research/shared/scripts/validate_market_research.py reports/QUBT/2026-06-22 --report-md reports/QUBT/2026-06-22/QUBT-research.md --report-json reports/QUBT/2026-06-22/QUBT-research.json --output-prefix /tmp/qubt-validation-check --force
```

Expected:

- Full pytest suite passes.
- QUBT validation still has zero critical/moderate issues.
- Validation output now distinguishes narrative use from evidence-only references.
- Weak generic deterministic usage rationales are surfaced as minor issues or improved in regenerated reports.

## Risks

- Rationale-quality checks can become noisy if they overfit phrase length rather than actual quality. Keep weak-rationale findings minor at first.
- Lifecycle-aware materiality can force too much detail into reports if thresholds are too broad. Limit the first pass to early-stage, volatile, loss-making equities.
- Filing-section extraction can be brittle across SEC filing formats. This plan first improves issue actionability; full extraction should remain a separate implementation if needed.
- Existing generated reports may fail new lint checks. Tests should use controlled fixtures unless the implementation pass explicitly chooses to regenerate reports.
