import json
from pathlib import Path

from typer.testing import CliRunner

from cool_financial_research.openclaw_helper import EdgarClassifier, RunPaths, app, prompt_key

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


def test_validate_stage_rejects_unreadable_payload_file(monkeypatch, tmp_path):
    payload = tmp_path / "unreadable.json"
    payload.write_text(json.dumps(valid_stage_payload()), encoding="utf-8")

    def raise_permission_error(self: Path, encoding: str | None = None) -> str:
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "read_text", raise_permission_error)
    result = runner.invoke(app, ["validate-stage", "research", str(payload)])
    assert result.exit_code == 1
    assert "Invalid research stage JSON" in result.output


def research_payload():
    return {
        "symbol": "ABC",
        "security_type": "equity",
        "stage": "research",
        "iteration": 0,
        "markdown_report": "# ABC Research",
        "structured_data": {
            "symbol": "ABC",
            "security_type": "equity",
            "analysis_date": "2026-05-24",
            "summary": "summary",
            "sections": [],
            "sources": [],
        },
    }


def validation_payload_without_blocking_issues():
    return {
        "symbol": "ABC",
        "security_type": "equity",
        "stage": "validation",
        "iteration": 1,
        "markdown_report": "# Validation",
        "structured_data": {
            "symbol": "ABC",
            "security_type": "equity",
            "validation_date": "2026-05-24",
            "overall_verdict": "pass",
            "recommendation_confidence": "medium",
            "critical_count": 0,
            "moderate_count": 0,
            "minor_count": 0,
            "issues": [],
            "summary": "summary",
        },
    }


def test_save_stage_writes_markdown_and_json(tmp_path):
    payload_file = tmp_path / "stage.json"
    payload_file.write_text(json.dumps(research_payload()), encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "save-stage",
            "ABC",
            "first_run",
            "research",
            str(payload_file),
            "--output-root",
            str(tmp_path / "out"),
        ],
    )
    assert result.exit_code == 0
    written = json.loads(result.output)
    assert Path(written["markdown"]).read_text(encoding="utf-8") == "# ABC Research"
    assert Path(written["json"]).exists()


def test_should_stop_outputs_machine_readable_decision(tmp_path):
    payload_file = tmp_path / "validation.json"
    payload_file.write_text(
        json.dumps(validation_payload_without_blocking_issues()),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["should-stop", str(payload_file)])
    assert result.exit_code == 0
    assert json.loads(result.output) == {"should_stop": True, "reason": "no_blocking_issues"}


def test_classify_reports_classifier_errors(monkeypatch):
    def raise_classifier_error(self: EdgarClassifier, symbol: str):
        raise OSError("network unavailable")

    monkeypatch.setattr(EdgarClassifier, "classify", raise_classifier_error)
    result = runner.invoke(app, ["classify", "ABC"])
    assert result.exit_code == 1
    assert "Classification failed: network unavailable" in result.output


def test_save_stage_reports_output_write_errors(monkeypatch, tmp_path):
    payload_file = tmp_path / "stage.json"
    payload_file.write_text(json.dumps(research_payload()), encoding="utf-8")

    def raise_write_error(self: RunPaths, label: str, output, markdown: str):
        raise OSError("disk full")

    monkeypatch.setattr(RunPaths, "write_stage", raise_write_error)
    result = runner.invoke(
        app,
        [
            "save-stage",
            "ABC",
            "first_run",
            "research",
            str(payload_file),
            "--output-root",
            str(tmp_path / "out"),
        ],
    )
    assert result.exit_code == 1
    assert "Could not save stage: disk full" in result.output
