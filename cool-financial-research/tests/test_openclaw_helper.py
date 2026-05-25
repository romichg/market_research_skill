import json

from typer.testing import CliRunner

from cool_financial_research.openclaw_helper import app, prompt_key

runner = CliRunner()


def valid_stage_payload(stage: str = "research") -> dict:
    return {
        "symbol": "ABC",
        "security_type": "equity",
        "stage": stage,
        "iteration": 0,
        "markdown_report": "# ABC",
        "structured_data": {
            "symbol": "ABC",
            "security_type": "equity",
            "analysis_date": "2026-05-24",
            "summary": "Summary",
            "sections": [],
            "sources": [],
        },
    }


def test_prompt_key_maps_adr_to_equity_prompts():
    assert prompt_key("adr", "research") == ("adr", "research")
    assert prompt_key("etf", "validation") == ("etf", "validation")


def test_prompt_command_prints_runtime_contract():
    result = runner.invoke(app, ["prompt", "equity", "research"])
    assert result.exit_code == 0
    assert "Comprehensive Equity Research Report Prompt" in result.output
    assert "Runtime Output Contract" in result.output


def test_validate_stage_rejects_missing_markdown_report(tmp_path):
    payload = tmp_path / "bad.json"
    payload.write_text(
        json.dumps({"symbol": "ABC", "security_type": "equity", "stage": "research"}),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["validate-stage", "research", str(payload)])
    assert result.exit_code == 1
    assert "Invalid research stage JSON" in result.output


def test_validate_stage_rejects_stage_mismatch(tmp_path):
    payload = tmp_path / "fix.json"
    payload.write_text(json.dumps(valid_stage_payload(stage="fix")), encoding="utf-8")
    result = runner.invoke(app, ["validate-stage", "research", str(payload)])
    assert result.exit_code == 1
    assert "Invalid research stage JSON" in result.output
    assert "Expected research stage JSON but found fix" in result.output


def test_validate_stage_rejects_missing_payload_file(tmp_path):
    payload = tmp_path / "missing.json"
    result = runner.invoke(app, ["validate-stage", "research", str(payload)])
    assert result.exit_code == 1
    assert "Invalid research stage JSON" in result.output
