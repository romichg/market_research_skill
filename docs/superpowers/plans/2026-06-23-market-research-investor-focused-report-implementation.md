# Investor-Focused Market Research Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework the market-research skill so final reports read like useful investor research, not provenance-heavy data recitals.

**Architecture:** Keep `data/`, `runtime/`, and `reports/` separation for evidence and validation, but make the Markdown report a polished investor product. Put internal paths, helper mechanics, routine data-vendor names, and source registries in JSON sidecars, validation artifacts, `Sources And Evidence`, or `Data Issues And Discrepancies`; use the main body for executive synthesis, business explanation, financial/technical/valuation analysis, risks, and decision variables.

**Tech Stack:** Python 3 standard library, pytest, Markdown skill/reference files, existing deterministic and procedural market-research helpers.

---

## Files To Change

- Modify: `market-research/researcher/references/report-template.md`
  - Replace the current audit-flavored outline with an investor-report outline.
  - Make `Bottom Line` an executive summary, not a short thesis stub.
  - Make `Key Facts` a table.
  - Merge `Source Base And Data Quality` and `Explicit Data Gaps` into `Data Issues And Discrepancies` near the bottom.
  - Require fuller business, business model, market/technical, financial, valuation, risk, and take sections.
- Modify: `market-research/researcher/SKILL.md`
  - Update required Markdown sections and procedural research expectations.
  - Require targeted procedural research when deterministic data is insufficient to explain the business, technology, customers, business model, acquisitions, and market context.
- Modify: `market-research/verifier/SKILL.md`
  - Validate investor usefulness, section depth, presentation quality, and absence of main-body internal provenance.
- Modify: `market-research/shared/scripts/report_language_lint.py`
  - Enforce main-body language constraints: no `saved`, `deterministic`, `artifact`, local paths, `manifest.json`, `gaps.json`, `normalized`, `runtime`, or routine data-vendor names outside allowed sections.
  - Add structural checks for executive summary length, key facts table, data issues placement, and technical analysis content.
- Modify: `market-research/shared/schemas/research-output.schema.json`
  - Add optional structured fields that support richer report quality: `executive_summary`, `key_facts`, `business_profile`, `technical_snapshot`, `valuation_snapshot`, and `data_issues`.
- Test: `tests/test_report_language_lint.py`
- Test: `tests/test_market_research_acceptance.py`
- Test: `tests/test_research_output_schema.py`

## Target Report Shape

Final Markdown reports should use this section order:

1. `## Bottom Line`
2. `## Key Facts`
3. `## Business Profile`
4. `## Business Model And Demand Drivers`
5. `## Market Snapshot And Technical Analysis`
6. `## Financials And Balance Sheet`
7. `## Valuation`
8. `## What Looks Attractive`
9. `## What Worries Me`
10. `## Catalysts And Monitoring Triggers`
11. `## Bull/Base/Bear Decision Variables`
12. `## Risks And Invalidation Points`
13. `## My Take`
14. `## Data Issues And Discrepancies`
15. `## Sources And Evidence`
16. `## Not Financial Advice`

Main-body sections from `Bottom Line` through `My Take` should not cite local paths, helper internals, routine data-vendor names, or provider mechanics. State the data, range, conflict, and investment implication in the main body; put vendor attribution and mechanics in `Data Issues And Discrepancies`, `Sources And Evidence`, JSON sidecars, or validation artifacts. Primary source types such as `10-Q`, `10-K`, `proxy statement`, `company release`, and `SEC filing` may be named in the main body because they describe source authority rather than data-vendor plumbing.

## Task 1: Rewrite Report Template Around Investor Consumption

**Files:**
- Modify: `market-research/researcher/references/report-template.md`
- Modify: `market-research/researcher/SKILL.md`
- Test: `tests/test_market_research_acceptance.py`

- [ ] **Step 1: Add failing acceptance tests for section order and investor language**

Add these tests to `tests/test_market_research_acceptance.py`:

```python
def test_report_template_uses_investor_first_section_order():
    text = (ROOT / "market-research" / "researcher" / "references" / "report-template.md").read_text(encoding="utf-8")
    required = [
        "## Bottom Line",
        "## Key Facts",
        "## Business Profile",
        "## Business Model And Demand Drivers",
        "## Market Snapshot And Technical Analysis",
        "## Financials And Balance Sheet",
        "## Valuation",
        "## What Looks Attractive",
        "## What Worries Me",
        "## Catalysts And Monitoring Triggers",
        "## Bull/Base/Bear Decision Variables",
        "## Risks And Invalidation Points",
        "## My Take",
        "## Data Issues And Discrepancies",
        "## Sources And Evidence",
    ]
    positions = [text.index(section) for section in required]
    assert positions == sorted(positions)
    assert "## Source Base And Data Quality" not in text
    assert "## Explicit Data Gaps" not in text
```

```python
def test_report_template_requires_executive_summary_bottom_line():
    text = (ROOT / "market-research" / "researcher" / "references" / "report-template.md").read_text(encoding="utf-8").lower()
    assert "executive summary" in text
    assert "introduce the market value or valuation range before discussing whether it is justified" in text
    assert "do not make the bottom line a compressed one-paragraph thesis" in text
```

```python
def test_researcher_skill_requires_procedural_research_for_business_understanding():
    text = (ROOT / "market-research" / "researcher" / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "targeted procedural research" in text
    assert "business model" in text
    assert "technology explanation" in text
    assert "acquisition contribution" in text
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
python3 -m pytest tests/test_market_research_acceptance.py::test_report_template_uses_investor_first_section_order tests/test_market_research_acceptance.py::test_report_template_requires_executive_summary_bottom_line tests/test_market_research_acceptance.py::test_researcher_skill_requires_procedural_research_for_business_understanding -q
```

Expected: fail until the template and skill guidance are rewritten.

- [ ] **Step 3: Replace the report outline**

In `market-research/researcher/references/report-template.md`, replace the `Full Markdown Report Structure` block with:

```markdown
## Full Markdown Report Structure

```markdown
# SYMBOL Research

As of: YYYY-MM-DD

## Bottom Line

Write this as an executive summary, not a compressed thesis. Use 3-5 substantial paragraphs. Introduce the company/security, what it does, current market value or valuation range, the core upside argument, the main risks, and the most important monitoring questions. Do not discuss whether valuation is justified before stating the market value or valuation range.

## Key Facts

Use a compact Markdown table. Do not cite local paths, helper internals, deterministic artifacts, raw files, or routine data-vendor names in this table.

| Item | Latest / Current | Why It Matters |
| --- | --- | --- |
| Security | US-listed equity / ADR / ETF | Defines what the investor owns. |
| Market value | $X-Y billion or unavailable | Anchors valuation discussion. |
| Revenue base | $X for period/date | Shows scale. |
| Liquidity | Cash/investments/debt | Shows runway and financing risk. |
| Profitability | Gross margin / operating loss / cash burn | Shows business quality. |
| Technical setup | Price, trend, support/resistance | Shows trading context. |
| Near-term monitors | Events and dates | Shows what can change the view. |

## Business Profile

Explain what the company or fund is in plain language. For operating companies, explain the products, technology, customers, end markets, acquisitions, and practical economic exposure. Do not write "not an ETF or ADR"; write what the security is. If the business uses specialized technology, explain the technology in investor-readable terms.

## Business Model And Demand Drivers

Explain how the company makes or expects to make money, who pays, what products or services are sold, what demand drivers matter, and what operating constraints could limit adoption. Avoid vague phrases like "appears" or "business model is forming" unless the uncertainty is explicitly explained.

## Market Snapshot And Technical Analysis

Present the market data in a table, then analyze it. Include price, market value/range, volume/liquidity, 52-week range, moving averages, volatility, relative strength, drawdown, support/resistance levels, and trend interpretation when price history exists.

## Financials And Balance Sheet

Use a table plus analysis. Cover revenue, gross margin, operating expense, net income/loss, operating cash flow, cash/investments, debt/liabilities, working capital, share count/dilution, and acquisition contribution when available. Avoid citation clutter in the main prose.

## Valuation

Choose a valuation basis or range and analyze it. If market capitalization or share count conflicts across sources, state the range in this section without vendor attribution, then explain vendor/source attribution in `Data Issues And Discrepancies`. Discuss revenue multiples, book value, cash-adjusted value, peer/context limits, and what revenue or margin improvement would be needed to make the valuation less speculative.

## What Looks Attractive

Explain the strongest evidence-backed positives with enough depth to help an investor understand why they matter.

## What Worries Me

Explain the strongest evidence-backed concerns with enough depth to help an investor understand what could go wrong.

## Catalysts And Monitoring Triggers

List near-term and medium-term events, dates, filings, operating metrics, commercial milestones, technical levels, and governance items that could change the view.

## Bull/Base/Bear Decision Variables

Use a table or clearly separated bullets. Each case should state what must happen operationally, financially, and in market perception.

## Risks And Invalidation Points

Focus on company, security, market, financial, governance, execution, liquidity, dilution, customer, product, and regulatory risks. Do not include research/data-quality risks here; put those in `Data Issues And Discrepancies`.

## My Take

Give a fuller evidence-backed interpretation. Explain what would make the security interesting, what would keep it out of a portfolio, and what evidence would change the view. Avoid personalized advice.

## Data Issues And Discrepancies

Merge source-base, data-quality, missing-field, stale-field, and vendor-discrepancy discussion here. Use investor-readable explanations first. Routine data-vendor names, local paths, manifests, gaps files, and source registry details may be named here when they explain a discrepancy, missing field, or confidence limit.

## Sources And Evidence

Map major claim groups to source documents and local artifacts for auditability. This is where local paths, source IDs, source registries, manifests, and validation-facing provenance belong.

## Not Financial Advice
This report is research support and is not personalized financial advice.
```
```

- [ ] **Step 4: Update researcher required sections**

In `market-research/researcher/SKILL.md`, replace the required Markdown section list with the target section order above. Add this paragraph before final drafting instructions:

```markdown
If deterministic output does not explain the business, technology, customers, business model, acquisition contribution, valuation context, or current technical setup well enough for an investor, perform targeted procedural research before drafting. The final report is judged on investor usefulness and analysis, not on whether a fact arrived through deterministic or procedural collection.
```

- [ ] **Step 5: Verify focused acceptance tests pass**

Run:

```bash
python3 -m pytest tests/test_market_research_acceptance.py::test_report_template_uses_investor_first_section_order tests/test_market_research_acceptance.py::test_report_template_requires_executive_summary_bottom_line tests/test_market_research_acceptance.py::test_researcher_skill_requires_procedural_research_for_business_understanding -q
```

Expected: pass.

## Task 2: Strengthen Report Language Lint

**Files:**
- Modify: `market-research/shared/scripts/report_language_lint.py`
- Test: `tests/test_report_language_lint.py`

- [ ] **Step 1: Add failing tests for forbidden main-body language**

Add these tests to `tests/test_report_language_lint.py`:

```python
def test_report_language_lint_rejects_saved_deterministic_artifact_language_in_main_body():
    module = load_module()
    text = """# QUBT Research

## Bottom Line

The latest saved 10-Q and deterministic profile show the company has cash.

## Data Issues And Discrepancies

Provider conflicts are discussed here.

## Sources And Evidence

Local artifacts are listed here.
"""

    findings = module.lint_report_language(text)

    patterns = {finding["pattern"] for finding in findings}
    assert "saved" in patterns
    assert "deterministic" in patterns
    assert "artifact" in patterns
```

```python
def test_report_language_lint_allows_provider_names_only_in_data_issues_or_sources():
    module = load_module()
    text = """# QUBT Research

## Valuation

Alpha Vantage says one value and FMP says another.

## Data Issues And Discrepancies

Alpha Vantage and FMP disagreed on market capitalization.
"""

    findings = module.lint_report_language(text)

    assert any(finding["pattern"] == "provider-name-main-body" for finding in findings)
```

```python
def test_report_language_lint_allows_provider_names_in_data_issues():
    module = load_module()
    text = """# QUBT Research

## Valuation

Market capitalization is best read as a range.

## Data Issues And Discrepancies

Alpha Vantage and FMP disagreed on market capitalization.

## Sources And Evidence

Provider details are recorded here.
"""

    findings = module.lint_report_language(text)

    assert findings == []
```

- [ ] **Step 2: Run the failing lint tests**

Run:

```bash
python3 -m pytest tests/test_report_language_lint.py::test_report_language_lint_rejects_saved_deterministic_artifact_language_in_main_body tests/test_report_language_lint.py::test_report_language_lint_allows_provider_names_only_in_data_issues_or_sources tests/test_report_language_lint.py::test_report_language_lint_allows_provider_names_in_data_issues -q
```

Expected: fail until the lint understands allowed and forbidden sections.

- [ ] **Step 3: Implement section-aware linting**

In `report_language_lint.py`, replace `APPENDIX_HEADING_RE`, `INTERNAL_PROVENANCE_PATTERNS`, and `main_body()` with section-aware helpers:

```python
ALLOWED_PROVENANCE_SECTIONS = {
    "data issues and discrepancies",
    "sources and evidence",
    "evidence appendix",
    "appendix",
}

FORBIDDEN_MAIN_BODY_PATTERNS = [
    "saved",
    "deterministic",
    "artifact",
    "runtime/",
    "data/",
    "normalized/",
    "raw/",
    "manifest.json",
    "gaps.json",
    "source_manifest.json",
    "sources.json",
]

PROVIDER_NAMES = [
    "alpha vantage",
    "fmp",
    "tiingo",
    "twelve data",
    "eodhd",
    "marketaux",
]


def iter_sections(text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, list[str]]] = []
    current = "preamble"
    lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            sections.append((current, lines))
            current = line[3:].strip().lower()
            lines = []
            continue
        lines.append(line)
    sections.append((current, lines))
    return [(heading, "\n".join(body)) for heading, body in sections]


def section_allows_provenance(heading: str) -> bool:
    return heading in ALLOWED_PROVENANCE_SECTIONS or "sources" in heading or "evidence" in heading
```

Then update `lint_report_language()`:

```python
def lint_report_language(text: str) -> list[dict[str, str]]:
    findings = []
    for heading, body_text in iter_sections(text):
        if section_allows_provenance(heading):
            continue
        body = body_text.lower()
        for pattern in FORBIDDEN_MAIN_BODY_PATTERNS:
            if pattern in body:
                findings.append({"severity": "minor", "pattern": pattern, "message": INTERNAL_PROVENANCE_MESSAGE})
        if any(provider in body for provider in PROVIDER_NAMES):
            findings.append({
                "severity": "minor",
                "pattern": "provider-name-main-body",
                "message": "routine data-vendor names belong in Data Issues And Discrepancies or Sources And Evidence, not the main investment narrative",
            })
    return findings
```

- [ ] **Step 4: Verify lint tests**

Run:

```bash
python3 -m pytest tests/test_report_language_lint.py -q
```

Expected: pass.

## Task 3: Add Structure And Depth Lint For Executive Summary, Tables, And Technical Analysis

**Files:**
- Modify: `market-research/shared/scripts/report_language_lint.py`
- Test: `tests/test_report_language_lint.py`

- [ ] **Step 1: Add failing structure tests**

Add these tests:

```python
def test_report_language_lint_flags_short_bottom_line_without_market_value():
    module = load_module()
    text = """# QUBT Research

## Bottom Line

QUBT is speculative.

## Key Facts

| Item | Latest / Current | Why It Matters |
| --- | --- | --- |
| Security | US-listed equity | Defines exposure |
"""

    findings = module.lint_report_structure(text)

    ids = {finding["id"] for finding in findings}
    assert "bottom-line-too-short" in ids
    assert "bottom-line-missing-market-value" in ids
```

```python
def test_report_language_lint_requires_key_facts_table_and_technical_analysis_terms():
    module = load_module()
    text = """# QUBT Research

## Bottom Line

This is a long enough executive summary paragraph with market cap context of $2 billion and enough words to avoid the short-summary finding. It explains the business, risk, valuation, and monitoring questions for the investor in a concise way.

## Key Facts

- Security: US-listed equity

## Market Snapshot And Technical Analysis

The stock moved recently.
"""

    findings = module.lint_report_structure(text)

    ids = {finding["id"] for finding in findings}
    assert "key-facts-not-table" in ids
    assert "technical-analysis-too-thin" in ids
```

- [ ] **Step 2: Run failing structure tests**

Run:

```bash
python3 -m pytest tests/test_report_language_lint.py::test_report_language_lint_flags_short_bottom_line_without_market_value tests/test_report_language_lint.py::test_report_language_lint_requires_key_facts_table_and_technical_analysis_terms -q
```

Expected: fail because `lint_report_structure()` does not exist.

- [ ] **Step 3: Implement structure linting**

Add these helpers:

```python
def section_map(text: str) -> dict[str, str]:
    return {heading: body for heading, body in iter_sections(text)}


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def has_market_value(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in ["market cap", "market value", "valuation range", "enterprise value"])


def has_markdown_table(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines()]
    return any(line.startswith("|") and "---" in line for line in lines)


def lint_report_structure(text: str) -> list[dict[str, str]]:
    sections = section_map(text)
    findings = []
    bottom = sections.get("bottom line", "")
    if word_count(bottom) < 120:
        findings.append({"severity": "minor", "id": "bottom-line-too-short", "message": "Bottom Line should read as an executive summary, not a compressed thesis."})
    if bottom and not has_market_value(bottom):
        findings.append({"severity": "minor", "id": "bottom-line-missing-market-value", "message": "Bottom Line should introduce market value or valuation range before judging valuation."})
    key_facts = sections.get("key facts", "")
    if key_facts and not has_markdown_table(key_facts):
        findings.append({"severity": "minor", "id": "key-facts-not-table", "message": "Key Facts should be a compact table."})
    technical = sections.get("market snapshot and technical analysis", "")
    required_terms = ["support", "resistance", "moving average", "volume", "volatility", "trend"]
    if technical and sum(1 for term in required_terms if term in technical.lower()) < 4:
        findings.append({"severity": "minor", "id": "technical-analysis-too-thin", "message": "Technical analysis should interpret support, resistance, moving averages, volume, volatility, and trend when price history exists."})
    return findings
```

Then have the CLI combine both checks:

```python
findings = lint_report_language(text) + lint_report_structure(text)
```

- [ ] **Step 4: Verify structure tests**

Run:

```bash
python3 -m pytest tests/test_report_language_lint.py -q
```

Expected: pass.

## Task 4: Require Business Explanation And Procedural Gap Filling

**Files:**
- Modify: `market-research/researcher/references/report-template.md`
- Modify: `market-research/researcher/SKILL.md`
- Modify: `market-research/verifier/SKILL.md`
- Test: `tests/test_market_research_acceptance.py`

- [ ] **Step 1: Add failing tests for business-depth requirements**

Add:

```python
def test_report_template_requires_plain_language_business_and_technology_explanation():
    text = (ROOT / "market-research" / "researcher" / "references" / "report-template.md").read_text(encoding="utf-8").lower()
    assert "plain language" in text
    assert "explain specialized technology" in text
    assert "what the product does" in text
    assert "who pays" in text
    assert "acquisition contribution" in text
```

```python
def test_verifier_requires_business_depth_not_just_filing_facts():
    text = (ROOT / "market-research" / "verifier" / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "business profile depth" in text
    assert "technology explanation" in text
    assert "procedural research" in text
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
python3 -m pytest tests/test_market_research_acceptance.py::test_report_template_requires_plain_language_business_and_technology_explanation tests/test_market_research_acceptance.py::test_verifier_requires_business_depth_not_just_filing_facts -q
```

Expected: fail until the template and verifier guidance are updated.

- [ ] **Step 3: Update researcher guidance**

Add to `market-research/researcher/SKILL.md` near procedural gap filling:

```markdown
Use targeted procedural research when the deterministic bundle does not explain the business well enough for an investor. For operating companies, fill business-profile gaps on: what the product does, how the technology works in plain language, who pays, revenue model, customer or government/commercial exposure, acquisition contribution, current commercial traction, and practical demand drivers. Do not stop at filing labels or provider profiles when they leave the business unclear.
```

- [ ] **Step 4: Update verifier guidance**

Add to `market-research/verifier/SKILL.md`:

```markdown
Business profile depth is a validation dimension. A report that accurately cites filings but does not explain what the business does, how specialized technology works in plain language, who pays, how revenue is expected to develop, or when procedural research was needed should receive a report-quality issue even if deterministic coverage is complete.
```

- [ ] **Step 5: Verify business-depth tests**

Run:

```bash
python3 -m pytest tests/test_market_research_acceptance.py::test_report_template_requires_plain_language_business_and_technology_explanation tests/test_market_research_acceptance.py::test_verifier_requires_business_depth_not_just_filing_facts -q
```

Expected: pass.

## Task 5: Add Report JSON Fields That Support Richer Presentation

**Files:**
- Modify: `market-research/shared/schemas/research-output.schema.json`
- Test: `tests/test_research_output_schema.py`

- [ ] **Step 1: Add failing schema test for presentation fields**

Add to `tests/test_research_output_schema.py`:

```python
def test_research_output_schema_supports_investor_presentation_fields():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    properties = schema["properties"]
    for field in [
        "executive_summary",
        "key_facts",
        "business_profile",
        "technical_snapshot",
        "valuation_snapshot",
        "data_issues",
    ]:
        assert field in properties

    assert properties["key_facts"]["type"] == "array"
    assert properties["technical_snapshot"]["type"] == "object"
    assert properties["valuation_snapshot"]["type"] == "object"
```

- [ ] **Step 2: Run failing schema test**

Run:

```bash
python3 -m pytest tests/test_research_output_schema.py::test_research_output_schema_supports_investor_presentation_fields -q
```

Expected: fail until the schema includes the optional fields.

- [ ] **Step 3: Add optional schema properties**

In `research-output.schema.json`, add:

```json
"executive_summary": {
  "type": "array",
  "items": {"type": "string"}
},
"key_facts": {
  "type": "array",
  "items": {
    "type": "object",
    "required": ["item", "value", "why_it_matters"],
    "properties": {
      "item": {"type": "string"},
      "value": {},
      "why_it_matters": {"type": "string"}
    },
    "additionalProperties": true
  }
},
"business_profile": {"type": "object"},
"technical_snapshot": {"type": "object"},
"valuation_snapshot": {"type": "object"},
"data_issues": {
  "type": "array",
  "items": {"type": "object"}
}
```

Do not add these fields to `required` in this task; keep backward compatibility while the report generator guidance rolls out.

- [ ] **Step 4: Verify schema tests**

Run:

```bash
python3 -m pytest tests/test_research_output_schema.py -q
```

Expected: pass.

## Task 6: Update Verification To Reject Data Recitals Without Analysis

**Files:**
- Modify: `market-research/verifier/SKILL.md`
- Test: `tests/test_market_research_acceptance.py`

- [ ] **Step 1: Add failing verifier acceptance test**

Add:

```python
def test_verifier_requires_analysis_not_number_recital():
    text = (ROOT / "market-research" / "verifier" / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "data recital" in text
    assert "support and resistance" in text
    assert "valuation analysis" in text
    assert "risk section should not include data-quality risk" in text
```

- [ ] **Step 2: Run failing verifier test**

Run:

```bash
python3 -m pytest tests/test_market_research_acceptance.py::test_verifier_requires_analysis_not_number_recital -q
```

Expected: fail until verifier guidance is strengthened.

- [ ] **Step 3: Add verifier criteria**

Add this section to `market-research/verifier/SKILL.md`:

```markdown
## Investor Analysis Quality Checks

Flag report-quality issues when a report merely recites data instead of analyzing it. In particular:

- `Bottom Line` must be an executive summary and must introduce market value or valuation range before discussing whether valuation is justified.
- `Key Facts` should be a table or equivalent at-a-glance presentation, without internal paths or provider mechanics.
- `Business Profile` must explain what the business does in plain language, including specialized technology, customers, products, and acquisition contribution when material.
- `Market Snapshot And Technical Analysis` must interpret the numbers. When price history exists, expect discussion of trend, volume, volatility, moving averages, support, resistance, and drawdown.
- `Financials And Balance Sheet` should organize numbers in a consumable way and explain scale, liquidity, cash burn, margin quality, and dilution.
- `Valuation` must analyze a selected value or range instead of narrating provider conflicts. Provider conflicts belong in `Data Issues And Discrepancies`.
- `Risks And Invalidation Points` should focus on company/security risks; data-quality risk belongs in `Data Issues And Discrepancies`.
```

- [ ] **Step 4: Verify acceptance test**

Run:

```bash
python3 -m pytest tests/test_market_research_acceptance.py::test_verifier_requires_analysis_not_number_recital -q
```

Expected: pass.

## Verification

Run focused tests:

```bash
python3 -m pytest tests/test_report_language_lint.py tests/test_research_output_schema.py tests/test_market_research_acceptance.py::test_report_template_uses_investor_first_section_order tests/test_market_research_acceptance.py::test_report_template_requires_executive_summary_bottom_line tests/test_market_research_acceptance.py::test_researcher_skill_requires_procedural_research_for_business_understanding tests/test_market_research_acceptance.py::test_report_template_requires_plain_language_business_and_technology_explanation tests/test_market_research_acceptance.py::test_verifier_requires_business_depth_not_just_filing_facts tests/test_market_research_acceptance.py::test_verifier_requires_analysis_not_number_recital -q
```

Run the full suite:

```bash
python3 -m pytest tests
```

Run a smoke batch after implementation:

```bash
python3 market-research/batch-supervisor/scripts/research_loop.py run-batch QUBT --run-root runtime/market-research-batch-report-quality-smoke --as-of 2026-06-23 --max-remediation-loops 1 --command-timeout-seconds 1800
```

Manual smoke-review checklist for the new QUBT report:

- `Bottom Line` reads as a real executive summary and mentions market value/range before valuation judgment.
- `Key Facts` is a table and contains no local paths, artifact names, or routine data-vendor names.
- `Business Profile` explains what QUBT does and what its photonics/quantum technology means in plain language.
- Business model and demand drivers explain who pays, how revenue can develop, and what acquisitions added.
- Market snapshot is a table plus technical analysis, including support/resistance and trend interpretation.
- Financials and valuation are organized and analytical, not citation-heavy paragraphs.
- Risks are company/security risks, not research-data risks.
- `Data Issues And Discrepancies` is near the bottom and includes source/data conflicts, missing fields, and vendor attribution where it explains the issue.
- `Sources And Evidence` contains the local paths and audit trail.

## Risks

- Stronger lint can overfit one report style. Keep findings minor unless the issue blocks investor usefulness.
- A longer executive summary can become bloated. The goal is richer synthesis, not padding.
- Technical analysis should be useful but modest; avoid pretending simple moving-average/support calculations are predictive.
- Routine data-vendor names should be suppressed in main analysis, but not hidden in data-issue or source sections when they explain a material discrepancy.
- Procedural research should fill business understanding gaps, not become open-ended browsing.
