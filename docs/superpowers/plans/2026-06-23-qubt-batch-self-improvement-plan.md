# QUBT Batch Self-Improvement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the QUBT batch's non-blocking validation findings into repeatable researcher, verifier, helper, and test improvements.

**Architecture:** Keep this pass focused on skill and helper contracts, not on regenerating the QUBT report. Use tests around the observed QUBT artifacts to prevent recurrence: main-body provenance leakage, weak deterministic usage rationales, incomplete equity risk coverage, missing schema tooling, undefined validator skill issue format, same-day SEC freshness gaps, and PDF preflight noise.

**Tech Stack:** Python 3 standard library, pytest, Markdown skill/reference files, JSON schemas, existing market-research helper scripts.

---

## Files To Change

- Modify: `market-research/shared/scripts/report_language_lint.py`
  - Include section names in findings.
  - Make non-JSON CLI output robust for findings with either `pattern` or `id`.
  - Add optional stricter checks for routine vendor/provenance language in main-body sections.
- Modify: `tests/test_report_language_lint.py`
  - Add regression tests using QUBT-like phrases from `QUBT-VAL-001`.
  - Add CLI test for structural findings without `pattern`.
- Modify: `market-research/shared/scripts/validate_market_research.py`
  - Make deterministic usage weak-rationale output more actionable.
  - Consider `weak_required` a promoted quality finding when count is high, while keeping pass/fail behavior configurable.
- Modify: `tests/test_validate_market_research.py` or the closest existing validation-helper test file.
  - Add weak-rationale examples and expected summary counts.
- Modify: `market-research/researcher/references/report-template.md`
  - Add explicit equity risk checklist treatment instructions.
  - Add main-body wording guidance for market data ranges without vendor names.
- Modify: `market-research/researcher/SKILL.md`
  - Require researcher final verification with report language lint.
  - Require same-day SEC/event freshness checks for event-driven issuer news.
  - Require PDF preflight reporting.
- Modify: `market-research/verifier/SKILL.md`
  - Require validation of equity risk checklist coverage.
  - Document JSON Schema validation helper usage and fallback behavior.
  - Define validator skill issue sidecar expectations.
- Modify: `market-research/shared/schemas/validation-output.schema.json`
  - Add optional `validator_skill_issues` contract or reference a separate schema.
- Create: `market-research/shared/schemas/skill-issue.schema.json`
  - Define reusable skill issue sidecar records.
- Test: `tests/test_research_loop.py`
  - Add coverage that feedback collection recognizes validator skill issue sidecars when JSON is present.

## Task 1: Harden Report Language Lint Around QUBT Findings

**Files:**
- Modify: `market-research/shared/scripts/report_language_lint.py`
- Modify: `tests/test_report_language_lint.py`

- [ ] **Step 1: Add failing tests for the exact QUBT leak shape**

Add to `tests/test_report_language_lint.py`:

```python
def test_report_language_lint_rejects_qubt_style_main_body_provenance():
    module = load_module()
    text = """# QUBT Research

## Bottom Line

The latest deterministic adjusted close was $10.76, with a primary normalized market capitalization.

## Market Snapshot And Technical Analysis

| Metric | Value | Evidence |
| --- | ---: | --- |
| Latest adjusted close | $10.76 | Deterministic Tiingo normalized prices |
| Latest quote volume | 21.44M shares | Twelve Data quote |

## Data Issues And Discrepancies

Provider details are discussed here.
"""

    findings = module.lint_report_language(text)

    patterns = [finding.get("pattern") for finding in findings]
    assert patterns.count("deterministic") >= 1
    assert "vendor-name-main-body" in patterns
```

Add a CLI regression for structural findings:

```python
def test_report_language_lint_cli_prints_structural_findings(tmp_path):
    report = tmp_path / "report.md"
    report.write_text(
        """# ABC Research

## Bottom Line

ABC is speculative.
""",
        encoding="utf-8",
    )

    import subprocess

    result = subprocess.run(
        ["python3", str(LINT), str(report)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert result.returncode == 1
    assert "bottom-line-too-short" in result.stdout
    assert "Traceback" not in result.stderr
```

- [ ] **Step 2: Run the focused tests and confirm they fail**

Run:

```bash
python3 -m pytest tests/test_report_language_lint.py::test_report_language_lint_rejects_qubt_style_main_body_provenance tests/test_report_language_lint.py::test_report_language_lint_cli_prints_structural_findings -q
```

Expected before implementation: first test may pass if current patterns catch the phrases; CLI test should fail if structural findings without `pattern` raise a `KeyError` or do not print the finding id.

- [ ] **Step 3: Update CLI printing**

Change the non-JSON print loop in `market-research/shared/scripts/report_language_lint.py`:

```python
    else:
        for finding in findings:
            identifier = finding.get("pattern") or finding.get("id") or "finding"
            print(f"{finding['severity']}: {finding['message']} ({identifier})")
```

- [ ] **Step 4: Add section context to findings**

When appending findings in `lint_report_language()` and `lint_report_structure()`, include the relevant section:

```python
findings.append(
    {
        "severity": "minor",
        "pattern": pattern,
        "section": heading,
        "message": INTERNAL_PROVENANCE_MESSAGE,
    }
)
```

For structural findings, add `section`, for example:

```python
{
    "severity": "minor",
    "id": "bottom-line-too-short",
    "section": "bottom line",
    "message": "Bottom Line should read as an executive summary, not a compressed thesis.",
}
```

- [ ] **Step 5: Re-run lint tests**

Run:

```bash
python3 -m pytest tests/test_report_language_lint.py -q
```

Expected: all tests pass.

## Task 2: Make Deterministic Usage Weak Rationales Actionable

**Files:**
- Modify: `market-research/shared/scripts/validate_market_research.py`
- Modify: `tests/test_validate_market_research.py` or existing validation-helper tests

- [ ] **Step 1: Add a failing unit test for weak required rationales**

Create or extend a validation-helper test with a minimal report JSON containing a generic rationale:

```python
def test_validation_scaffold_reports_weak_required_rationales_with_examples(tmp_path):
    usage = {
        "version": 1,
        "asset_type": "equity",
        "datapoints": [
            {
                "field_path": "equity_fundamentals.ebitda",
                "field_name": "ebitda",
                "materiality": "required",
                "status": "ok",
                "required_disposition": True,
                "value": -57941000,
                "artifact": "data/QUBT/2026-06-23/normalized/equity_fundamentals.json",
            }
        ],
    }
    report = {
        "symbol": "QUBT",
        "deterministic_data_usage": [
            {
                "field_path": "equity_fundamentals.ebitda",
                "materiality": "required",
                "disposition": "used",
                "rationale": "Used to support operating profile.",
                "report_section": "Financials And Balance Sheet",
            }
        ],
    }

    result = audit_deterministic_data_usage_dispositions(usage, report)

    assert result["summary"]["weak_required"] == 1
    assert result["weak_required"][0]["field_path"] == "equity_fundamentals.ebitda"
    assert result["weak_required"][0]["weak_reason"] == "rationale_not_field_specific"
```

Use the actual function name from `validate_market_research.py`; if it is not importable, first extract the existing disposition logic into an importable function.

- [ ] **Step 2: Run the focused validation-helper test**

Run:

```bash
python3 -m pytest tests/test_validate_market_research.py -q
```

Expected: fail until the helper exposes/imports the disposition audit and weak-rationale details.

- [ ] **Step 3: Improve weak-rationale messages**

In `validate_market_research.py`, make each weak entry include:

```python
{
    "field_path": field_path,
    "field_name": field_name,
    "materiality": materiality,
    "disposition": disposition,
    "report_section": report_section,
    "weak_reason": "rationale_not_field_specific",
    "suggested_fix": "Mention the field or value and why it changed, supported, or did not change the investor view.",
}
```

- [ ] **Step 4: Add verifier/researcher wording**

Update `market-research/researcher/SKILL.md` and `market-research/verifier/SKILL.md` to say:

```markdown
For every required deterministic datapoint, the report JSON `deterministic_data_usage` entry must include a field-specific `rationale` that names the field or value and explains the investor relevance, duplication by better evidence, or reason for omission. Generic rationales such as "used for valuation context" are insufficient for required datapoints.
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
python3 -m pytest tests/test_validate_market_research.py tests/test_research_output_schema.py -q
```

Expected: pass.

## Task 3: Add Equity Risk Checklist Coverage

**Files:**
- Modify: `market-research/researcher/references/report-template.md`
- Modify: `market-research/researcher/SKILL.md`
- Modify: `market-research/verifier/SKILL.md`
- Modify: `tests/test_market_research_acceptance.py`

- [ ] **Step 1: Add acceptance tests for required risk checklist language**

Add:

```python
def test_researcher_template_requires_equity_risk_checklist_treatment():
    text = (ROOT / "market-research" / "researcher" / "references" / "report-template.md").read_text(encoding="utf-8").lower()
    for term in [
        "cybersecurity",
        "litigation",
        "legal proceedings",
        "customer concentration",
        "supplier concentration",
        "dilution",
        "internal controls",
    ]:
        assert term in text
    assert "addressed" in text
    assert "not material" in text
    assert "not found in filed sources" in text
```

- [ ] **Step 2: Run the new acceptance test**

Run:

```bash
python3 -m pytest tests/test_market_research_acceptance.py::test_researcher_template_requires_equity_risk_checklist_treatment -q
```

Expected: fail until the template is updated.

- [ ] **Step 3: Update the template risk section**

Add this instruction under `## Risks And Invalidation Points` in `market-research/researcher/references/report-template.md`:

```markdown
For equities and ADRs, explicitly treat the following risk checklist with one of `addressed`, `not material`, or `not found in filed sources`: commercialization/execution, liquidity/runway, dilution/share issuance, customer concentration, supplier/manufacturing dependence, cybersecurity/data integrity, litigation/legal proceedings, internal controls, related-party/governance, regulatory/export-control, and valuation/multiple compression. The Markdown should summarize only material risks; the JSON sidecar can preserve checklist dispositions.
```

- [ ] **Step 4: Update verifier guidance**

In `market-research/verifier/SKILL.md`, add:

```markdown
For equities and ADRs, check whether the report addresses or dispositions cybersecurity/data-integrity risk and litigation/legal-proceeding status from filed materials. Missing treatment is at least minor; make it moderate when the omitted risk is material to the thesis or when filings contain active proceedings that affect valuation or solvency.
```

- [ ] **Step 5: Re-run acceptance tests**

Run:

```bash
python3 -m pytest tests/test_market_research_acceptance.py -q
```

Expected: pass.

## Task 4: Define Validator Skill Issue Sidecar Contract

**Files:**
- Create: `market-research/shared/schemas/skill-issue.schema.json`
- Modify: `market-research/verifier/SKILL.md`
- Modify: `market-research/batch-supervisor/scripts/research_loop.py`
- Modify: `tests/test_research_loop.py`

- [ ] **Step 1: Add schema file**

Create `market-research/shared/schemas/skill-issue.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["issues"],
  "properties": {
    "issues": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "severity", "status", "description", "suggested_owner", "evidence_path"],
        "properties": {
          "id": {"type": "string"},
          "severity": {"type": "string", "enum": ["critical", "moderate", "minor"]},
          "status": {"type": "string", "enum": ["open", "closed", "deferred"]},
          "description": {"type": "string"},
          "suggested_owner": {"type": "string", "enum": ["researcher", "verifier", "batch-supervisor", "shared-helper", "docs"]},
          "evidence_path": {"type": "string"}
        },
        "additionalProperties": true
      }
    }
  },
  "additionalProperties": true
}
```

- [ ] **Step 2: Add collection test**

In `tests/test_research_loop.py`, create a temporary run root with `QUBT-validator-skill-issues.json` and assert `collect_feedback` includes it.

```python
def test_collect_feedback_includes_json_skill_issue_sidecars(tmp_path):
    root = tmp_path / "run"
    issue = root / "QUBT" / "2026-06-23" / "QUBT-validator-skill-issues.json"
    issue.parent.mkdir(parents=True)
    issue.write_text('{"issues":[{"id":"VSKILL-001","severity":"minor","status":"open","description":"x","suggested_owner":"verifier","evidence_path":"reports/QUBT/2026-06-23/QUBT-validation.md"}]}', encoding="utf-8")

    payload = research_loop.collect_feedback(root)

    assert str(issue) in payload["issue_files"]
```

Use the module import style already used by `tests/test_research_loop.py`.

- [ ] **Step 3: Extend `collect_skill_issue_files`**

In `market-research/batch-supervisor/scripts/research_loop.py`, include both Markdown and JSON sidecars:

```python
def collect_skill_issue_files(root: Path) -> list[str]:
    files = sorted(root.glob("**/*skill-issues.md")) + sorted(root.glob("**/*skill-issues.json"))
    return [str(path) for path in files]
```

- [ ] **Step 4: Update verifier output rule**

In `market-research/verifier/SKILL.md`, require both markdown and JSON when validator skill issues are present:

```markdown
When validator skill issues are found, write `<SYMBOL>-validator-skill-issues.md` for human reading and `<SYMBOL>-validator-skill-issues.json` matching `../shared/schemas/skill-issue.schema.json` for aggregation.
```

- [ ] **Step 5: Run tests**

Run:

```bash
python3 -m pytest tests/test_research_loop.py -q
```

Expected: pass.

## Task 5: Make Schema Validation Operational

**Files:**
- Modify: `market-research/shared/scripts/validate_market_research.py`
- Modify: `market-research/verifier/SKILL.md`
- Test: `tests/test_market_research_acceptance.py`

- [ ] **Step 1: Add acceptance test for documented schema-validation dependency or fallback**

Add:

```python
def test_verifier_documents_schema_validation_fallback():
    text = (ROOT / "market-research" / "verifier" / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "json schema" in text
    assert "fallback" in text
    assert "manual required-field checks" in text
```

- [ ] **Step 2: Run the acceptance test**

Run:

```bash
python3 -m pytest tests/test_market_research_acceptance.py::test_verifier_documents_schema_validation_fallback -q
```

Expected: fail until the verifier documents the fallback.

- [ ] **Step 3: Add verifier guidance**

In `market-research/verifier/SKILL.md`, add:

```markdown
If a JSON Schema validator is unavailable, run the repository validation helper and perform manual required-field checks against the schema files. Record this limitation in validation JSON under `validation_limitations`; do not imply full Draft 2020-12 schema validation passed.
```

- [ ] **Step 4: Add helper output field**

If not already present, ensure completed validation JSON can record:

```json
"validation_limitations": [
  "Python jsonschema was unavailable; manual required-field checks were performed."
]
```

- [ ] **Step 5: Run acceptance tests**

Run:

```bash
python3 -m pytest tests/test_market_research_acceptance.py -q
```

Expected: pass.

## Task 6: Add Same-Day SEC Freshness Guidance

**Files:**
- Modify: `market-research/researcher/SKILL.md`
- Modify: `market-research/researcher/references/report-template.md`
- Test: `tests/test_market_research_acceptance.py`

- [ ] **Step 1: Add acceptance test**

Add:

```python
def test_researcher_requires_same_day_sec_check_for_event_driven_news():
    text = (ROOT / "market-research" / "researcher" / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "same-day sec" in text
    assert "8-k" in text
    assert "issuer filings page" in text or "sec company browse" in text
```

- [ ] **Step 2: Run the acceptance test**

Run:

```bash
python3 -m pytest tests/test_market_research_acceptance.py::test_researcher_requires_same_day_sec_check_for_event_driven_news -q
```

Expected: fail until guidance is added.

- [ ] **Step 3: Add researcher instruction**

In `market-research/researcher/SKILL.md`, add:

```markdown
For event-driven issuer news dated on or after the as-of date, perform a same-day SEC freshness check against the issuer filings page or SEC company browse results, especially for 8-K, 10-Q, 10-K, S-3, S-1, 13D/G, and proxy filings. If deterministic SEC submissions lag, capture the filing procedurally, cite the filing date, and disclose the deterministic omission in `Data Issues And Discrepancies`.
```

- [ ] **Step 4: Re-run acceptance tests**

Run:

```bash
python3 -m pytest tests/test_market_research_acceptance.py -q
```

Expected: pass.

## Task 7: Improve PDF Preflight Notes

**Files:**
- Modify: `market-research/shared/scripts/md-to-pdf.sh`
- Modify: `market-research/researcher/SKILL.md`
- Test: `tests/test_md_to_pdf.py`

- [ ] **Step 1: Add test for missing LaTeX package message**

Add a test that invokes the script in a controlled failure mode already used by `tests/test_md_to_pdf.py`, asserting the stderr/stdout includes:

```text
PDF not generated
Install a TeX distribution with lmodern support or disable PDF generation.
```

- [ ] **Step 2: Run focused PDF tests**

Run:

```bash
python3 -m pytest tests/test_md_to_pdf.py -q
```

Expected: fail until the helper emits the actionable dependency hint.

- [ ] **Step 3: Update `md-to-pdf.sh` failure text**

When `pandoc` fails, print:

```bash
echo "PDF not generated: pandoc failed for ${input}." >&2
echo "If xelatex is installed but LaTeX reports missing lmodern.sty, install a TeX distribution with lmodern support or disable PDF generation for this run." >&2
```

- [ ] **Step 4: Re-run PDF tests**

Run:

```bash
python3 -m pytest tests/test_md_to_pdf.py -q
```

Expected: pass.

## Verification Commands

Run the focused checks first:

```bash
python3 -m pytest tests/test_report_language_lint.py -q
python3 -m pytest tests/test_market_research_acceptance.py -q
python3 -m pytest tests/test_research_loop.py -q
python3 -m pytest tests/test_md_to_pdf.py -q
```

Then run the full suite:

```bash
python3 -m pytest tests
```

Finally, rerun the QUBT report lint as a regression sample:

```bash
python3 market-research/shared/scripts/report_language_lint.py reports/QUBT/2026-06-23/QUBT-research.md --json
```

Expected after implementation and a regenerated report: no main-body provenance or routine vendor-name findings.

## Risks

- Promoting weak deterministic rationales too aggressively could create noisy failures for otherwise acceptable reports. Keep missing required dispositions blocking, but make weak rationales a quality finding unless the user explicitly wants strict mode.
- Report language lint can produce false positives for primary source names or business terms. Keep SEC filings and company releases allowed in main body; restrict routine data-vendor and local-path mechanics.
- Same-day SEC checks add time and network dependence. Apply them when event-driven news or same-day issuer releases matter to the thesis.
- PDF preflight should remain best effort. Do not make missing LaTeX block research completion.

