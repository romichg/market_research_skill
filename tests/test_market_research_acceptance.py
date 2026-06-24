import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = ROOT / "market-research" / "shared" / "scripts" / "deterministic_research_collector.py"
VALIDATOR = ROOT / "market-research" / "shared" / "scripts" / "validate_market_research.py"
AS_OF = "2026-06-16"


def run_cli(*args):
    return subprocess.run(
        [sys.executable, *map(str, args)],
        text=True,
        capture_output=True,
        check=False,
    )


def write_research_report(report_dir: Path, symbol: str, security_type: str) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "symbol": symbol,
        "security_type": security_type,
        "as_of_date": AS_OF,
        "material_claims": [],
        "data_gaps": [
            {
                "field": "intraday liquidity",
                "status": "not_required_for_acceptance_fixture",
                "attempted_sources": ["synthetic fixture"],
                "notes": "Offline acceptance fixture uses deterministic collector layout only.",
            }
        ],
        "technical_analysis": {
            "trend": "neutral",
            "price_context": {
                "latest_close": 100.0,
                "sma_50": 101.5,
                "sma_200": 98.25,
            },
        },
        "valuation_or_performance": {
            "primary_metric": "total_return" if security_type == "etf" else "forward_pe",
            "summary": "Synthetic offline acceptance value.",
            "metrics": {
                "price": 100.0,
                "year_to_date_return": 0.08,
            },
        },
        "decision_factors": {
            "bull_case": ["durable demand", "strong balance sheet"],
            "bear_case": ["valuation sensitivity", "macro uncertainty"],
            "watch_items": ["next earnings date", "fund flows" if security_type == "etf" else "services growth"],
        },
        "risks": [
            {"risk": "market drawdown", "severity": "medium", "time_horizon": "12 months"},
            {"risk": "fixture-only data", "severity": "low", "time_horizon": "test runtime"},
        ],
        "catalysts": [
            {"catalyst": "earnings update" if security_type == "equity" else "index rebalance", "expected_window": "next quarter"}
        ],
        "source_coverage": {
            "deterministic_bundle": "present",
            "offline_fixture": True,
            "providers": ["synthetic"],
        },
        "calculation_audit": [
            {
                "calculation": "year_to_date_return",
                "formula": "(current - start) / start",
                "inputs": {"current": 108.0, "start": 100.0},
                "result": 0.08,
            }
        ],
    }
    (report_dir / f"{symbol}-research.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (report_dir / f"{symbol}-research.md").write_text(
        "\n".join(
            [
                f"# {symbol} Research",
                "",
                f"As of: {AS_OF}",
                f"Security type: {security_type}",
                "",
                "Synthetic offline acceptance report.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


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


def test_researcher_guidance_requires_provider_impact_mapping():
    text = (ROOT / "market-research" / "researcher" / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "provider-limit impact" in text
    assert "affected analysis area" in text


def test_report_template_includes_provider_limit_impact_example():
    text = (ROOT / "market-research" / "researcher" / "references" / "report-template.md").read_text(encoding="utf-8").lower()
    assert "provider_limit_impact" in text
    assert "affected_analysis_area" in text


def test_report_template_moves_provider_and_skill_internals_to_appendix():
    text = (ROOT / "market-research" / "researcher" / "references" / "report-template.md").read_text(encoding="utf-8").lower()
    assert "routine data vendors" in text
    assert "data issues and discrepancies" in text
    assert "sources and evidence" in text
    assert "time-sensitive" in text
    assert "latest available" in text
    assert "cache mechanics" in text


def test_verifier_flags_unnecessary_provider_provenance_in_main_body():
    text = (ROOT / "market-research" / "verifier" / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "routine data-vendor names" in text
    assert "main body" in text
    assert "data issues and discrepancies" in text


def test_self_improvement_lessons_prioritize_investor_product_over_runtime_packaging():
    investor_lessons = (ROOT / "docs" / "superpowers" / "lessons" / "2026-06-22-investor-grade-report-quality.md").read_text(encoding="utf-8").lower()
    self_improvement_lessons = (ROOT / "docs" / "superpowers" / "lessons" / "2026-06-22-deterministic-usage-and-self-improvement.md").read_text(encoding="utf-8").lower()
    supervisor = (ROOT / "market-research" / "batch-supervisor" / "SKILL.md").read_text(encoding="utf-8").lower()

    assert "final report is the investor product" in investor_lessons
    assert "field-specific, not cache-specific" in investor_lessons
    assert "finished investor experience before artifact ergonomics" in self_improvement_lessons
    assert "reports/` is for polished final deliverables" in self_improvement_lessons
    assert "field-level freshness guidance over cache-mechanics disclosure" in supervisor


def test_report_template_requires_potential_value_not_booked_revenue_framing():
    text = (ROOT / "market-research" / "researcher" / "references" / "report-template.md").read_text(encoding="utf-8").lower()
    assert "potential value" in text
    assert "booked revenue" in text
    assert "milestone" in text


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


def test_report_template_requires_executive_summary_bottom_line():
    text = (ROOT / "market-research" / "researcher" / "references" / "report-template.md").read_text(encoding="utf-8").lower()
    assert "executive summary" in text
    assert "introduce the market value or valuation range before discussing whether it is justified" in text
    assert "do not make the bottom line a compressed one-paragraph thesis" in text


def test_report_template_requires_plain_language_business_and_technology_explanation():
    text = (ROOT / "market-research" / "researcher" / "references" / "report-template.md").read_text(encoding="utf-8").lower()
    assert "plain language" in text
    assert "explain specialized technology" in text
    assert "what the product does" in text
    assert "who pays" in text
    assert "acquisition contribution" in text


def test_report_template_forbids_routine_vendor_names_in_main_narrative():
    text = (ROOT / "market-research" / "researcher" / "references" / "report-template.md").read_text(encoding="utf-8").lower()
    assert "do not name routine data vendors in the main investment narrative" in text
    assert "state the data, range, conflict, and investment implication" in text
    assert "put vendor attribution" in text


def test_researcher_skill_requires_procedural_research_for_business_understanding():
    text = (ROOT / "market-research" / "researcher" / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "targeted procedural research" in text
    assert "business model" in text
    assert "technology explanation" in text
    assert "acquisition contribution" in text


def test_researcher_requires_same_day_sec_check_for_event_driven_news():
    text = (ROOT / "market-research" / "researcher" / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "same-day sec" in text
    assert "8-k" in text
    assert "issuer filings page" in text or "sec company browse" in text


def test_verifier_requires_business_depth_not_just_filing_facts():
    text = (ROOT / "market-research" / "verifier" / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "business profile depth" in text
    assert "technology explanation" in text
    assert "procedural research" in text


def test_verifier_requires_analysis_not_number_recital():
    text = (ROOT / "market-research" / "verifier" / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "data recital" in text
    assert "support and resistance" in text
    assert "valuation analysis" in text
    assert "risk section should not include data-quality risk" in text


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


def test_verifier_checks_potential_value_news_framing():
    text = (ROOT / "market-research" / "verifier" / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "potential" in text
    assert "booked revenue" in text
    assert "framework" in text


def test_verifier_documents_schema_validation_fallback():
    text = (ROOT / "market-research" / "verifier" / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "json schema" in text
    assert "fallback" in text
    assert "manual required-field checks" in text


def test_readme_presents_self_improve_as_batch_supervisor_mode():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "$market-research batch-supervisor self-improve runtime/market-research-batch-20260620" in text
    assert "underlying helper can also be run directly" in text.lower()


def test_readme_mentions_environment_preflight():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "preflight_environment.py" in text
    assert "jsonschema" in text
    assert "lmodern" in text


def test_market_research_offline_acceptance_for_equity_and_etf(tmp_path):
    data_dir = tmp_path / "data"
    cache_dir = tmp_path / "cache"
    reports_dir = tmp_path / "reports"

    for symbol, security_type in [("AAPL", "equity"), ("SPY", "etf")]:
        collector = run_cli(
            COLLECTOR,
            "fetch",
            symbol,
            "--offline",
            "--asset-type",
            security_type,
            "--as-of",
            AS_OF,
            "--data-dir",
            data_dir,
            "--cache-dir",
            cache_dir,
            "--reports-dir",
            reports_dir,
        )

        assert collector.returncode == 0, collector.stderr
        manifest = data_dir / symbol / AS_OF / "manifest.json"
        assert manifest.exists()

        report_dir = reports_dir / symbol / AS_OF
        write_research_report(report_dir, symbol, security_type)

        validator = run_cli(VALIDATOR, report_dir)

        assert validator.returncode == 0, validator.stderr
        validation_path = report_dir / f"{symbol}-validation-scaffold.json"
        assert validation_path.exists()
        validation = json.loads(validation_path.read_text(encoding="utf-8"))
        assert validation["blocking_issue_count"] == 0
