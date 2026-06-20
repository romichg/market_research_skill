import json
import subprocess
import sys
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1] / "market-research-full" / "loop-runner" / "scripts" / "research_loop.py"


def run_harness(*args):
    return subprocess.run([sys.executable, str(HARNESS), *args], text=True, capture_output=True, check=False)


def test_validation_gate_passes_only_without_open_critical_or_moderate(tmp_path):
    validation = tmp_path / "validation.json"
    validation.write_text(
        json.dumps(
            {
                "issue_counts": {"critical": 0, "moderate": 1, "minor": 3},
                "issues": [
                    {"id": "minor-open", "severity": "minor", "status": "open"},
                    {"id": "moderate-closed", "severity": "moderate", "status": "resolved"},
                    {"id": "moderate-open", "severity": "moderate", "status": "open"},
                ],
            }
        ),
        encoding="utf-8",
    )

    result = run_harness("inspect-validation", str(validation))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["passes_gate"] is False
    assert payload["open_blocking_issue_count"] == 1
    assert payload["open_blocking_issue_ids"] == ["moderate-open"]


def test_validation_gate_ignores_closed_blocking_and_open_minor(tmp_path):
    validation = tmp_path / "validation.json"
    validation.write_text(
        json.dumps(
            {
                "issues": [
                    {"id": "critical-fixed", "severity": "critical", "status": "resolved"},
                    {"id": "minor-open", "severity": "minor", "status": "open"},
                ]
            }
        ),
        encoding="utf-8",
    )

    result = run_harness("inspect-validation", str(validation))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["passes_gate"] is True
    assert payload["open_blocking_issue_count"] == 0


def test_prompt_generation_mentions_fresh_contexts_and_artifact_contract(tmp_path):
    out_dir = tmp_path / "prompts"

    result = run_harness("write-prompts", "EWW", "--run-dir", "reports/EWW/2026-06-01", "--output-dir", str(out_dir))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    producer = Path(payload["producer_initial_prompt"]).read_text(encoding="utf-8")
    validator = Path(payload["validator_prompt"]).read_text(encoding="utf-8")
    remediation = Path(payload["producer_remediation_prompt"]).read_text(encoding="utf-8")
    assert "deterministic_research_collector.py fetch EWW" in producer
    assert "reports/" in producer
    assert "fresh Codex context" in validator
    assert "$market-research-full verifier reports/EWW/2026-06-01" in validator
    assert "Fix only open critical/moderate issues" in remediation
    assert "Do not delete validator outputs" in remediation


def test_invalid_shell_symbol_rejected_by_loop(tmp_path):
    result = run_harness("run-batch", "AAPL;touch", "--run-root", str(tmp_path), "--dry-run")

    assert result.returncode != 0
    assert "Invalid symbol" in result.stderr


def test_summarize_batch_counts_pass_fail_and_skill_issue_files(tmp_path):
    root = tmp_path / "runs"
    good = root / "EWW" / "iteration-01"
    bad = root / "AAPL" / "iteration-02-remediation"
    good.mkdir(parents=True)
    bad.mkdir(parents=True)
    (good / "validation.json").write_text(json.dumps({"issues": []}), encoding="utf-8")
    (good / "skill-issues.md").write_text("# Issues\n", encoding="utf-8")
    (bad / "validation.json").write_text(
        json.dumps({"issues": [{"id": "AAPL-1", "severity": "critical", "status": "open"}]}),
        encoding="utf-8",
    )
    (bad / "validation-skill-issues.md").write_text("# Validator Issues\n", encoding="utf-8")

    result = run_harness("summarize", str(root))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["symbols_total"] == 2
    assert payload["passed"] == ["EWW"]
    assert payload["failed"] == ["AAPL"]
    assert payload["skill_issue_files"] == [
        str(bad / "validation-skill-issues.md"),
        str(good / "skill-issues.md"),
    ]


def test_run_batch_dry_run_writes_iteration_plan_without_executing(tmp_path):
    root = tmp_path / "batch"

    result = run_harness(
        "run-batch",
        "EWW",
        "--run-root",
        str(root),
        "--producer-command",
        "producer {prompt_file}",
        "--validator-command",
        "validator {prompt_file}",
        "--remediation-command",
        "remediate {prompt_file}",
        "--dry-run",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True
    assert payload["symbols"]["EWW"]["status"] == "planned"
    iteration = root / "EWW" / "iteration-01"
    assert (iteration / "producer-initial.prompt.md").exists()
    assert (iteration / "validator.prompt.md").exists()
    commands = json.loads((iteration / "commands.json").read_text(encoding="utf-8"))
    assert commands["producer"] == f"producer {iteration / 'producer-initial.prompt.md'}"
    assert commands["validator"] == f"validator {iteration / 'validator.prompt.md'}"
    assert (root / "loop-skill-issues.md").exists()
    assert (root / "operator-notes.md").exists()


def test_run_batch_defaults_to_supported_codex_exec_command(tmp_path):
    root = tmp_path / "batch"

    result = run_harness("run-batch", "EWW", "--run-root", str(root), "--dry-run")

    assert result.returncode == 0, result.stderr
    iteration = root / "EWW" / "iteration-01"
    commands = json.loads((iteration / "commands.json").read_text(encoding="utf-8"))
    assert "--dangerously-bypass-approvals-and-sandbox" in commands["producer"]
    assert "--dangerously-bypass-approvals-and-sandbox" in commands["validator"]
    assert "--ask-for-approval" not in commands["producer"]
    assert "--ask-for-approval" not in commands["validator"]


def test_run_batch_continues_when_timed_out_producer_wrote_artifacts(tmp_path):
    root = tmp_path / "batch"
    producer = (
        f"{sys.executable} -c \""
        "from pathlib import Path; import time; "
        "run_dir = Path(r'{run_dir}'); "
        "(run_dir / '{symbol}-research.md').write_text('ok', encoding='utf-8'); "
        "(run_dir / '{symbol}-research.json').write_text('{{}}', encoding='utf-8'); "
        "time.sleep(5)"
        "\""
    )
    validator = (
        f"{sys.executable} -c \""
        "from pathlib import Path; "
        "run_dir = Path(r'{run_dir}'); "
        "(run_dir / '{symbol}-validation.json').write_text('{{\\\"issues\\\": []}}', encoding='utf-8')"
        "\""
    )

    result = run_harness(
        "run-batch",
        "EWW",
        "--run-root",
        str(root),
        "--producer-command",
        producer,
        "--validator-command",
        validator,
        "--command-timeout-seconds",
        "1",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["symbols"]["EWW"]["status"] == "passed"
    producer_log = root / "EWW" / "iteration-01" / "producer.log"
    assert "timed_out=True" in producer_log.read_text(encoding="utf-8")


def test_run_batch_continues_when_timed_out_producer_wrote_deterministic_bundle(tmp_path):
    root = tmp_path / "batch"
    producer = (
        f"{sys.executable} -c \""
        "from pathlib import Path; import json, time; "
        "run_dir = Path(r'{run_dir}'); "
        "(run_dir / 'normalized').mkdir(parents=True, exist_ok=True); "
        "(run_dir / 'research_input_pack.md').write_text('ok', encoding='utf-8'); "
        "(run_dir / 'manifest.json').write_text(json.dumps({'symbol':'{symbol}','asset_type':'equity'}), encoding='utf-8'); "
        "(run_dir / 'source_manifest.json').write_text(json.dumps({'sources':[]}), encoding='utf-8'); "
        "(run_dir / 'gaps.json').write_text(json.dumps({'gaps':[]}), encoding='utf-8'); "
        "time.sleep(5)"
        "\""
    )
    validator = (
        f"{sys.executable} -c \""
        "from pathlib import Path; "
        "run_dir = Path(r'{run_dir}'); "
        "(run_dir / '{symbol}-validation-scaffold.json').write_text('{{\\\"issues\\\": []}}', encoding='utf-8')"
        "\""
    )

    result = run_harness(
        "run-batch",
        "EWW",
        "--run-root",
        str(root),
        "--producer-command",
        producer,
        "--validator-command",
        validator,
        "--command-timeout-seconds",
        "1",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["symbols"]["EWW"]["status"] == "passed"


def test_run_batch_validates_latest_dated_deterministic_bundle(tmp_path):
    root = tmp_path / "batch"
    producer = (
        f"{sys.executable} -c \""
        "from pathlib import Path; import json; "
        "run_dir = Path(r'{run_dir}') / '2026-06-01'; "
        "(run_dir / 'normalized').mkdir(parents=True, exist_ok=True); "
        "(run_dir / 'research_input_pack.md').write_text('ok', encoding='utf-8'); "
        "(run_dir / 'manifest.json').write_text(json.dumps({'symbol':'{symbol}','asset_type':'equity'}), encoding='utf-8'); "
        "(run_dir / 'source_manifest.json').write_text(json.dumps({'sources':[]}), encoding='utf-8'); "
        "(run_dir / 'gaps.json').write_text(json.dumps({'gaps':[]}), encoding='utf-8')"
        "\""
    )
    validator = (
        f"{sys.executable} -c \""
        "from pathlib import Path; "
        "run_dir = Path(r'{run_dir}'); "
        "assert run_dir.name == '2026-06-01', run_dir; "
        "(run_dir / '{symbol}-validation-scaffold.json').write_text('{{\\\"issues\\\": []}}', encoding='utf-8')"
        "\""
    )

    result = run_harness(
        "run-batch",
        "EWW",
        "--run-root",
        str(root),
        "--producer-command",
        producer,
        "--validator-command",
        validator,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["symbols"]["EWW"]["status"] == "passed"
    assert payload["symbols"]["EWW"]["artifact_run_dir"].endswith("EWW/2026-06-01")
    assert payload["symbols"]["EWW"]["validation_json"].endswith("EWW/2026-06-01/EWW-validation-scaffold.json")


def test_collect_feedback_writes_manual_improvement_package(tmp_path):
    root = tmp_path / "batch"
    symbol_dir = root / "EWW"
    symbol_dir.mkdir(parents=True)
    (symbol_dir / "EWW-market-research-skill-issues.md").write_text("# Producer Issues\n\n- Improve ETF extraction.\n", encoding="utf-8")
    (symbol_dir / "EWW-validator-skill-issues.md").write_text("# Validator Issues\n\n- Check checksums.\n", encoding="utf-8")
    (root / "loop-skill-issues.md").write_text("# Loop Skill Issues\n\n- Tune timeout.\n", encoding="utf-8")
    (root / "operator-notes.md").write_text("# Operator Notes\n\n## Future User-Requested Changes\n\n- Add PDF output later.\n", encoding="utf-8")

    result = run_harness("collect-feedback", str(root))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["issue_file_count"] == 3
    feedback_md = root / "skill-improvement-feedback.md"
    feedback_json = root / "skill-improvement-feedback.json"
    assert feedback_md.exists()
    assert feedback_json.exists()
    text = feedback_md.read_text(encoding="utf-8")
    assert "Manual Skill Improvement Package" in text
    assert "Add PDF output later" in text
