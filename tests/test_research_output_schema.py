import json
from pathlib import Path


SCHEMA = (
    Path(__file__).resolve().parents[1]
    / "market-research"
    / "shared"
    / "schemas"
    / "research-output.schema.json"
)


def test_research_output_schema_requires_expanded_report_sections():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    assert schema["required"] == [
        "symbol",
        "security_type",
        "as_of_date",
        "material_claims",
        "data_gaps",
        "technical_analysis",
        "valuation_or_performance",
        "decision_factors",
        "risks",
        "catalysts",
        "source_coverage",
        "calculation_audit",
    ]

    assert schema["properties"]["technical_analysis"]["type"] == "object"
    assert schema["properties"]["valuation_or_performance"]["type"] == "object"
    assert schema["properties"]["decision_factors"]["type"] == "object"
    assert schema["properties"]["risks"]["type"] == "array"
    assert schema["properties"]["catalysts"]["type"] == "array"
    assert schema["properties"]["source_coverage"]["type"] == "object"
    assert schema["properties"]["calculation_audit"]["type"] == "array"
