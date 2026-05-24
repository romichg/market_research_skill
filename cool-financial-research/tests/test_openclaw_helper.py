import json

from typer.testing import CliRunner

from cool_financial_research.openclaw_helper import app, prompt_key

runner = CliRunner()


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
