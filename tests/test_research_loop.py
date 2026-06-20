import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

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
    assert "EWW-validator-skill-issues.md" in validator
    assert "Fix only open critical/moderate issues" in remediation
    assert "EWW-market-research-skill-issues.md" in remediation
    assert "Do not delete validator outputs" in remediation


def test_loop_prompts_separate_data_reports_and_runtime(tmp_path):
    out_dir = tmp_path / "prompts"

    result = run_harness("write-prompts", "AAPL", "--run-dir", "reports/AAPL/2026-06-16", "--output-dir", str(out_dir))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert set(payload) == {"producer_initial_prompt", "producer_remediation_prompt", "validator_prompt"}
    producer = Path(payload["producer_initial_prompt"]).read_text(encoding="utf-8")
    validator = Path(payload["validator_prompt"]).read_text(encoding="utf-8")
    assert "--data-dir ./data" in producer
    assert "--reports-dir ./reports" in producer
    assert (
        "Use deterministic evidence first: `python3 market-research-full/shared/scripts/deterministic_research_collector.py fetch "
        "AAPL --data-dir ./data --reports-dir ./reports --as-of YYYY-MM-DD`."
    ) in producer
    assert "Use the deterministic bundle under `data/AAPL/YYYY-MM-DD/` as evidence." in producer
    assert "Write final research markdown and JSON under `reports/AAPL/2026-06-16`." in producer
    assert "Write producer skill issues to `runtime/AAPL/2026-06-16/AAPL-market-research-full-issues.md`." in producer
    assert "$market-research-full verifier reports/AAPL/2026-06-16" in validator


def test_loop_prompt_preserves_custom_runtime_root_for_transient_artifacts(tmp_path):
    out_dir = tmp_path / "prompts"
    run_dir = "runtime/market-research-loop-20260620/AAPL/2026-06-16"

    result = run_harness("write-prompts", "AAPL", "--run-dir", run_dir, "--output-dir", str(out_dir))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    producer = Path(payload["producer_initial_prompt"]).read_text(encoding="utf-8")
    assert f"Use `{run_dir}` for transient runtime notes, prompts, logs, and issue files." in producer
    assert f"Write producer skill issues to `{run_dir}/AAPL-market-research-full-issues.md`." in producer


def test_loop_prompt_maps_absolute_reports_dir_to_sibling_runtime_dir(tmp_path):
    out_dir = tmp_path / "prompts"
    absolute_run_dir = tmp_path / "reports" / "AAPL" / "2026-06-16"
    expected_runtime_dir = tmp_path / "runtime" / "AAPL" / "2026-06-16"

    result = run_harness("write-prompts", "AAPL", "--run-dir", str(absolute_run_dir), "--output-dir", str(out_dir))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    producer = Path(payload["producer_initial_prompt"]).read_text(encoding="utf-8")
    assert f"Write final research markdown and JSON under `{absolute_run_dir}`." in producer
    assert f"Use `{expected_runtime_dir}` for transient runtime notes, prompts, logs, and issue files." in producer
    assert f"Write producer skill issues to `{expected_runtime_dir / 'AAPL-market-research-full-issues.md'}`." in producer


def test_write_prompts_default_validator_output_uses_reports_placeholder(tmp_path):
    out_dir = tmp_path / "prompts"

    result = run_harness("write-prompts", "EWW", "--output-dir", str(out_dir))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    validator = Path(payload["validator_prompt"]).read_text(encoding="utf-8")
    assert "$market-research-full verifier runtime/EWW" in validator
    assert "Write validation markdown and JSON artifacts under `reports/EWW/YYYY-MM-DD`." in validator
    assert "Write validation markdown and JSON artifacts under `runtime/EWW`." not in validator


def test_init_batch_validator_prompts_use_reports_as_of_output(tmp_path):
    root = tmp_path / "runtime" / "batch"

    result = run_harness("init-batch", "EWW", "--run-root", str(root), "--as-of", "2026-06-16")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    validator = (Path(payload["prompt_dirs"]["EWW"]) / "EWW-validator.md").read_text(encoding="utf-8")
    assert f"$market-research-full verifier {root / 'EWW' / '2026-06-16'}" in validator
    assert "Write validation markdown and JSON artifacts under `reports/EWW/2026-06-16`." in validator
    assert f"Write validation markdown and JSON artifacts under `{root / 'EWW' / '2026-06-16'}`." not in validator


def test_invalid_shell_symbol_rejected_by_loop(tmp_path):
    result = run_harness("run-batch", "AAPL;touch", "--run-root", str(tmp_path), "--dry-run")

    assert result.returncode != 0
    assert "Invalid symbol" in result.stderr


@pytest.mark.parametrize(
    ("symbol", "artifact_path"),
    [
        (".", Path("runs/2026-06-16/iteration-01")),
        ("..", Path("2026-06-16/iteration-01")),
    ],
)
def test_dot_symbol_path_components_rejected_by_loop(tmp_path, symbol, artifact_path):
    root = tmp_path / "runs"
    result = run_harness("run-batch", symbol, "--run-root", str(root), "--as-of", "2026-06-16", "--dry-run")

    assert result.returncode != 0
    assert "Invalid symbol" in result.stderr
    assert not (tmp_path / artifact_path).exists()


def test_run_batch_rejects_traversal_as_of(tmp_path):
    result = run_harness("run-batch", "EWW", "--run-root", str(tmp_path), "--as-of", "../outside", "--dry-run")

    assert result.returncode != 0
    assert "Invalid as-of" in result.stderr
    assert not (tmp_path / "outside" / "iteration-01").exists()


def test_run_batch_finds_reports_when_project_parent_is_named_runtime(tmp_path):
    project = tmp_path / "runtime" / "project"
    root = project / "batch"
    reports_bundle = project / "reports" / "EWW" / "2026-06-16"
    producer = (
        f"{sys.executable} -c \""
        "from pathlib import Path; "
        f"run_dir = Path(r'{reports_bundle}'); "
        "run_dir.mkdir(parents=True, exist_ok=True); "
        "(run_dir / '{symbol}-research.md').write_text('ok', encoding='utf-8'); "
        "(run_dir / '{symbol}-research.json').write_text('{{}}', encoding='utf-8')"
        "\""
    )
    validator = (
        f"{sys.executable} -c \""
        "from pathlib import Path; "
        "run_dir = Path(r'{run_dir}'); "
        f"assert run_dir == Path(r'{reports_bundle}'), run_dir; "
        "(run_dir / '{symbol}-validation.json').write_text('{{\\\"issues\\\": []}}', encoding='utf-8')"
        "\""
    )

    result = run_harness(
        "run-batch",
        "EWW",
        "--run-root",
        str(root),
        "--as-of",
        "2026-06-16",
        "--producer-command",
        producer,
        "--validator-command",
        validator,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["symbols"]["EWW"]["status"] == "passed"
    assert payload["symbols"]["EWW"]["artifact_run_dir"] == str(reports_bundle)


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


def test_summarize_finds_validation_json_in_sibling_reports_tree(tmp_path):
    root = tmp_path / "runtime" / "batch"
    runtime_symbol = root / "EWW" / "2026-06-16"
    reports_symbol = tmp_path / "reports" / "EWW" / "2026-06-16"
    runtime_symbol.mkdir(parents=True)
    reports_symbol.mkdir(parents=True)
    (reports_symbol / "EWW-validation.json").write_text(json.dumps({"issues": []}), encoding="utf-8")

    result = run_harness("summarize", str(root))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["passed"] == ["EWW"]
    assert payload["failed"] == []


def test_summarize_does_not_treat_validation_scaffold_as_completed_validation(tmp_path):
    root = tmp_path / "runtime" / "batch"
    runtime_symbol = root / "EWW" / "2026-06-16"
    reports_symbol = tmp_path / "reports" / "EWW" / "2026-06-16"
    runtime_symbol.mkdir(parents=True)
    reports_symbol.mkdir(parents=True)
    (reports_symbol / "EWW-validation-scaffold.json").write_text(json.dumps({"scaffold": True, "issues": []}), encoding="utf-8")

    result = run_harness("summarize", str(root))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["passed"] == []
    assert payload["failed"] == ["EWW"]
    assert payload["unresolved_blocking_issues"]["EWW"] == ["missing-validation-json"]


def test_run_batch_dry_run_writes_iteration_plan_without_executing(tmp_path):
    root = tmp_path / "batch"
    as_of = "2026-06-16"

    result = run_harness(
        "run-batch",
        "EWW",
        "--run-root",
        str(root),
        "--as-of",
        as_of,
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
    iteration = root / "EWW" / as_of / "iteration-01"
    assert (iteration / "producer-initial.prompt.md").exists()
    assert (iteration / "validator.prompt.md").exists()
    commands = json.loads((iteration / "commands.json").read_text(encoding="utf-8"))
    assert commands["producer"] == f"producer {iteration / 'producer-initial.prompt.md'}"
    assert commands["validator"] == f"validator {iteration / 'validator.prompt.md'}"
    assert (root / "loop-skill-issues.md").exists()
    assert (root / "operator-notes.md").exists()


def test_run_batch_dry_run_quotes_path_placeholders(tmp_path):
    root = tmp_path / "mr loop review;echo injected"
    as_of = "2026-06-16"

    result = run_harness(
        "run-batch",
        "EWW",
        "--run-root",
        str(root),
        "--as-of",
        as_of,
        "--producer-command",
        "producer {prompt_file} {run_dir} {iteration_dir}",
        "--validator-command",
        "validator {prompt_file} {run_dir} {iteration_dir} {validation_output_dir}",
        "--dry-run",
    )

    assert result.returncode == 0, result.stderr
    iteration = root / "EWW" / as_of / "iteration-01"
    run_dir = root / "EWW" / as_of
    commands = json.loads((iteration / "commands.json").read_text(encoding="utf-8"))
    assert commands["producer"] == (
        f"producer {shlex.quote(str(iteration / 'producer-initial.prompt.md'))} "
        f"{shlex.quote(str(run_dir))} "
        f"{shlex.quote(str(iteration))}"
    )
    assert commands["validator"] == (
        f"validator {shlex.quote(str(iteration / 'validator.prompt.md'))} "
        f"{shlex.quote(str(run_dir))} "
        f"{shlex.quote(str(iteration))} "
        f"{shlex.quote(str(run_dir))}"
    )


def test_run_batch_defaults_to_supported_codex_exec_command(tmp_path):
    root = tmp_path / "batch"
    as_of = "2026-06-16"

    result = run_harness("run-batch", "EWW", "--run-root", str(root), "--as-of", as_of, "--dry-run")

    assert result.returncode == 0, result.stderr
    iteration = root / "EWW" / as_of / "iteration-01"
    commands = json.loads((iteration / "commands.json").read_text(encoding="utf-8"))
    assert "--dangerously-bypass-approvals-and-sandbox" in commands["producer"]
    assert "--dangerously-bypass-approvals-and-sandbox" in commands["validator"]
    assert "--ask-for-approval" not in commands["producer"]
    assert "--ask-for-approval" not in commands["validator"]


def test_run_batch_dry_run_uses_runtime_symbol_date_layout(tmp_path):
    root = tmp_path / "runtime"

    result = run_harness(
        "run-batch",
        "EWW",
        "--run-root",
        str(root),
        "--as-of",
        "2026-06-16",
        "--dry-run",
    )

    assert result.returncode == 0, result.stderr
    iteration = root / "EWW" / "2026-06-16" / "iteration-01"
    assert (iteration / "producer-initial.prompt.md").exists()
    commands = json.loads((iteration / "commands.json").read_text(encoding="utf-8"))
    assert "market-research-full" in commands["producer"]


def test_run_batch_continues_when_timed_out_producer_wrote_artifacts(tmp_path):
    root = tmp_path / "batch"
    reports_bundle = tmp_path / "reports" / "EWW" / "2026-06-16"
    as_of = "2026-06-16"
    producer = (
        f"{sys.executable} -c \""
        "from pathlib import Path; import time; "
        f"run_dir = Path(r'{reports_bundle}'); "
        "run_dir.mkdir(parents=True, exist_ok=True); "
        "(run_dir / '{symbol}-research.md').write_text('ok', encoding='utf-8'); "
        "(run_dir / '{symbol}-research.json').write_text('{{}}', encoding='utf-8'); "
        "time.sleep(5)"
        "\""
    )
    validator = (
        f"{sys.executable} -c \""
        "from pathlib import Path; "
        "run_dir = Path(r'{run_dir}'); "
        f"assert run_dir == Path(r'{reports_bundle}'), run_dir; "
        "(run_dir / '{symbol}-validation.json').write_text('{{\\\"issues\\\": []}}', encoding='utf-8')"
        "\""
    )

    result = run_harness(
        "run-batch",
        "EWW",
        "--run-root",
        str(root),
        "--as-of",
        as_of,
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
    assert payload["symbols"]["EWW"]["artifact_run_dir"] == str(reports_bundle)
    assert payload["symbols"]["EWW"]["validation_json"] == str(reports_bundle / "EWW-validation.json")
    producer_log = root / "EWW" / as_of / "iteration-01" / "producer.log"
    assert "timed_out=True" in producer_log.read_text(encoding="utf-8")


def test_run_batch_failed_producer_does_not_use_stale_runtime_research_report(tmp_path):
    runtime_root = tmp_path / "runtime" / "batch"
    as_of = "2026-06-16"
    stale_runtime_report = runtime_root / "EWW" / as_of
    stale_runtime_report.mkdir(parents=True)
    (stale_runtime_report / "EWW-research.md").write_text("stale", encoding="utf-8")
    (stale_runtime_report / "EWW-research.json").write_text("{}", encoding="utf-8")
    validator_marker = tmp_path / "validator-used"
    producer = f"{sys.executable} -c \"import sys; sys.exit(7)\""
    validator = f"{sys.executable} -c \"from pathlib import Path; Path(r'{validator_marker}').write_text('used', encoding='utf-8')\""

    result = run_harness(
        "run-batch",
        "EWW",
        "--run-root",
        str(runtime_root),
        "--as-of",
        as_of,
        "--producer-command",
        producer,
        "--validator-command",
        validator,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["symbols"]["EWW"]["status"] == "producer_failed"
    assert payload["symbols"]["EWW"]["exit_code"] == 7
    assert not validator_marker.exists()


def test_run_batch_ignores_nested_runtime_reports_and_data_dirs(tmp_path):
    runtime_root = tmp_path / "runtime" / "batch"
    as_of = "2026-06-16"
    nested_reports = runtime_root / "EWW" / as_of / "reports" / "EWW" / "2026-06-01"
    nested_reports.mkdir(parents=True)
    (nested_reports / "EWW-research.md").write_text("nested", encoding="utf-8")
    (nested_reports / "EWW-research.json").write_text("{}", encoding="utf-8")
    nested_data = runtime_root / "EWW" / as_of / "data" / "EWW" / "2026-06-01"
    (nested_data / "normalized").mkdir(parents=True)
    (nested_data / "research_input_pack.md").write_text("nested", encoding="utf-8")
    (nested_data / "manifest.json").write_text(json.dumps({"symbol": "EWW", "asset_type": "etf"}), encoding="utf-8")
    (nested_data / "source_manifest.json").write_text(json.dumps({"sources": []}), encoding="utf-8")
    (nested_data / "gaps.json").write_text(json.dumps({"gaps": []}), encoding="utf-8")
    validator_marker = tmp_path / "validator-used"
    producer = f"{sys.executable} -c \"import sys; sys.exit(0)\""
    validator = f"{sys.executable} -c \"from pathlib import Path; Path(r'{validator_marker}').write_text('used', encoding='utf-8')\""

    result = run_harness(
        "run-batch",
        "EWW",
        "--run-root",
        str(runtime_root),
        "--as-of",
        as_of,
        "--producer-command",
        producer,
        "--validator-command",
        validator,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["symbols"]["EWW"]["status"] == "producer_failed"
    assert payload["symbols"]["EWW"]["exit_code"] == 0
    assert not validator_marker.exists()


def test_run_batch_exit_zero_does_not_use_stale_canonical_artifacts(tmp_path):
    runtime_root = tmp_path / "runtime" / "batch"
    as_of = "2026-06-16"
    stale_reports = tmp_path / "reports" / "EWW" / "2026-01-01"
    stale_reports.mkdir(parents=True)
    (stale_reports / "EWW-research.md").write_text("stale", encoding="utf-8")
    (stale_reports / "EWW-research.json").write_text("{}", encoding="utf-8")
    stale_data = tmp_path / "data" / "EWW" / "2026-01-01"
    (stale_data / "normalized").mkdir(parents=True)
    (stale_data / "research_input_pack.md").write_text("stale", encoding="utf-8")
    (stale_data / "manifest.json").write_text(json.dumps({"symbol": "EWW", "asset_type": "etf"}), encoding="utf-8")
    (stale_data / "source_manifest.json").write_text(json.dumps({"sources": []}), encoding="utf-8")
    (stale_data / "gaps.json").write_text(json.dumps({"gaps": []}), encoding="utf-8")
    old_time = 1_700_000_000
    for directory in [stale_reports, stale_data]:
        for path in [directory, *directory.iterdir()]:
            os.utime(path, (old_time, old_time))
    validator_marker = tmp_path / "validator-used"
    producer = f"{sys.executable} -c \"import sys; sys.exit(0)\""
    validator = f"{sys.executable} -c \"from pathlib import Path; Path(r'{validator_marker}').write_text('used', encoding='utf-8')\""

    result = run_harness(
        "run-batch",
        "EWW",
        "--run-root",
        str(runtime_root),
        "--as-of",
        as_of,
        "--producer-command",
        producer,
        "--validator-command",
        validator,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["symbols"]["EWW"]["status"] == "producer_failed"
    assert payload["symbols"]["EWW"]["exit_code"] == 0
    assert not validator_marker.exists()


def test_run_batch_continues_when_timed_out_producer_wrote_deterministic_bundle(tmp_path):
    root = tmp_path / "batch"
    data_bundle = tmp_path / "data" / "EWW" / "2026-06-16"
    reports_root = tmp_path / "reports"
    as_of = "2026-06-16"
    producer = (
        f"{sys.executable} -c \""
        "from pathlib import Path; import json, time; "
        f"run_dir = Path(r'{data_bundle}'); "
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
        "output_dir = Path(r'{validation_output_dir}'); "
        f"assert run_dir == Path(r'{data_bundle}'), run_dir; "
        f"expected = Path(r'{reports_root}') / '{{symbol}}' / '2026-06-16'; "
        "assert output_dir == expected, f'{output_dir} != {expected}'; "
        "output_dir.mkdir(parents=True, exist_ok=True); "
        "(output_dir / '{symbol}-validation.json').write_text('{{\\\"issues\\\": []}}', encoding='utf-8')"
        "\""
    )

    result = run_harness(
        "run-batch",
        "EWW",
        "--run-root",
        str(root),
        "--as-of",
        as_of,
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
    assert payload["symbols"]["EWW"]["artifact_run_dir"] == str(data_bundle)
    assert payload["symbols"]["EWW"]["validation_json"] == str(reports_root / "EWW" / "2026-06-16" / "EWW-validation.json")


def test_run_batch_requires_completed_validation_json_not_scaffold(tmp_path):
    root = tmp_path / "batch"
    reports_bundle = tmp_path / "reports" / "EWW" / "2026-06-16"
    as_of = "2026-06-16"
    producer = (
        f"{sys.executable} -c \""
        "from pathlib import Path; "
        f"run_dir = Path(r'{reports_bundle}'); "
        "run_dir.mkdir(parents=True, exist_ok=True); "
        "(run_dir / '{symbol}-research.md').write_text('ok', encoding='utf-8'); "
        "(run_dir / '{symbol}-research.json').write_text('{{}}', encoding='utf-8')"
        "\""
    )
    validator = (
        f"{sys.executable} -c \""
        "from pathlib import Path; "
        "run_dir = Path(r'{run_dir}'); "
        "(run_dir / '{symbol}-validation-scaffold.json').write_text('{{\\\"scaffold\\\": true, \\\"issues\\\": []}}', encoding='utf-8')"
        "\""
    )

    result = run_harness(
        "run-batch",
        "EWW",
        "--run-root",
        str(root),
        "--as-of",
        as_of,
        "--producer-command",
        producer,
        "--validator-command",
        validator,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["symbols"]["EWW"]["status"] == "missing_validation"
    assert payload["symbols"]["EWW"]["run_dir"] == str(root / "EWW" / as_of)


def test_run_batch_ignores_runtime_dated_deterministic_bundle(tmp_path):
    root = tmp_path / "batch"
    as_of = "2026-06-16"
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
    validator_marker = tmp_path / "validator-used"
    validator = f"{sys.executable} -c \"from pathlib import Path; Path(r'{validator_marker}').write_text('used', encoding='utf-8')\""

    result = run_harness(
        "run-batch",
        "EWW",
        "--run-root",
        str(root),
        "--as-of",
        as_of,
        "--producer-command",
        producer,
        "--validator-command",
        validator,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["symbols"]["EWW"]["status"] == "producer_failed"
    assert payload["symbols"]["EWW"]["exit_code"] == 0
    assert not validator_marker.exists()


def test_run_batch_validates_canonical_data_bundle_when_run_dir_is_runtime(tmp_path):
    runtime_root = tmp_path / "runtime" / "batch"
    data_root = tmp_path / "data"
    reports_root = tmp_path / "reports"
    as_of = "2026-06-16"
    producer = (
        f"{sys.executable} -c \""
        "from pathlib import Path; import json; "
        f"data_root = Path(r'{data_root}'); "
        "artifact_dir = data_root / '{symbol}' / '2026-06-01'; "
        "(artifact_dir / 'normalized').mkdir(parents=True, exist_ok=True); "
        "(artifact_dir / 'research_input_pack.md').write_text('ok', encoding='utf-8'); "
        "(artifact_dir / 'manifest.json').write_text(json.dumps({'symbol':'{symbol}','asset_type':'equity'}), encoding='utf-8'); "
        "(artifact_dir / 'source_manifest.json').write_text(json.dumps({'sources':[]}), encoding='utf-8'); "
        "(artifact_dir / 'gaps.json').write_text(json.dumps({'gaps':[]}), encoding='utf-8')"
        "\""
    )
    validator = (
        f"{sys.executable} -c \""
        "from pathlib import Path; "
        "run_dir = Path(r'{run_dir}'); "
        "output_dir = Path(r'{validation_output_dir}'); "
        f"expected = Path(r'{data_root}') / '{{symbol}}' / '2026-06-01'; "
        "assert run_dir == expected, f'{run_dir} != {expected}'; "
        f"expected_output = Path(r'{reports_root}') / '{{symbol}}' / '2026-06-01'; "
        "assert output_dir == expected_output, f'{output_dir} != {expected_output}'; "
        "output_dir.mkdir(parents=True, exist_ok=True); "
        "(output_dir / '{symbol}-validation.json').write_text('{{\\\"issues\\\": []}}', encoding='utf-8')"
        "\""
    )

    result = run_harness(
        "run-batch",
        "EWW",
        "--run-root",
        str(runtime_root),
        "--as-of",
        as_of,
        "--producer-command",
        producer,
        "--validator-command",
        validator,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["symbols"]["EWW"]["status"] == "passed"
    assert payload["symbols"]["EWW"]["run_dir"] == str(runtime_root / "EWW" / as_of)
    assert payload["symbols"]["EWW"]["artifact_run_dir"] == str(data_root / "EWW" / "2026-06-01")
    assert payload["symbols"]["EWW"]["validation_json"] == str(reports_root / "EWW" / "2026-06-01" / "EWW-validation.json")


def test_run_batch_failed_producer_does_not_use_stale_canonical_data_bundle(tmp_path):
    runtime_root = tmp_path / "runtime" / "batch"
    data_root = tmp_path / "data"
    stale_bundle = data_root / "EWW" / "2026-01-01"
    (stale_bundle / "normalized").mkdir(parents=True)
    (stale_bundle / "research_input_pack.md").write_text("stale", encoding="utf-8")
    (stale_bundle / "manifest.json").write_text(json.dumps({"symbol": "EWW", "asset_type": "etf"}), encoding="utf-8")
    (stale_bundle / "source_manifest.json").write_text(json.dumps({"sources": []}), encoding="utf-8")
    (stale_bundle / "gaps.json").write_text(json.dumps({"gaps": []}), encoding="utf-8")
    old_time = 1_700_000_000
    for path in [stale_bundle, stale_bundle / "normalized", *stale_bundle.iterdir()]:
        os.utime(path, (old_time, old_time))
    validator_marker = tmp_path / "validator-used"
    producer = f"{sys.executable} -c \"import sys; sys.exit(7)\""
    validator = (
        f"{sys.executable} -c \""
        "from pathlib import Path; "
        f"Path(r'{validator_marker}').write_text('used', encoding='utf-8'); "
        "run_dir = Path(r'{run_dir}'); "
        "(run_dir / '{symbol}-validation-scaffold.json').write_text('{{\\\"issues\\\": []}}', encoding='utf-8')"
        "\""
    )

    result = run_harness(
        "run-batch",
        "EWW",
        "--run-root",
        str(runtime_root),
        "--producer-command",
        producer,
        "--validator-command",
        validator,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["symbols"]["EWW"]["status"] == "producer_failed"
    assert payload["symbols"]["EWW"]["exit_code"] == 7
    assert not validator_marker.exists()


def test_run_batch_failed_producer_can_continue_with_fresh_canonical_data_bundle(tmp_path):
    runtime_root = tmp_path / "runtime" / "batch"
    data_root = tmp_path / "data"
    reports_root = tmp_path / "reports"
    data_bundle = data_root / "EWW" / "2026-06-01"
    producer = (
        f"{sys.executable} -c \""
        "from pathlib import Path; import json, sys; "
        f"artifact_dir = Path(r'{data_bundle}'); "
        "(artifact_dir / 'normalized').mkdir(parents=True, exist_ok=True); "
        "(artifact_dir / 'research_input_pack.md').write_text('ok', encoding='utf-8'); "
        "(artifact_dir / 'manifest.json').write_text(json.dumps({'symbol':'EWW','asset_type':'etf'}), encoding='utf-8'); "
        "(artifact_dir / 'source_manifest.json').write_text(json.dumps({'sources':[]}), encoding='utf-8'); "
        "(artifact_dir / 'gaps.json').write_text(json.dumps({'gaps':[]}), encoding='utf-8'); "
        "sys.exit(7)"
        "\""
    )
    validator = (
        f"{sys.executable} -c \""
        "from pathlib import Path; "
        "run_dir = Path(r'{run_dir}'); "
        "output_dir = Path(r'{validation_output_dir}'); "
        f"expected = Path(r'{data_bundle}'); "
        "assert run_dir == expected, f'{run_dir} != {expected}'; "
        f"expected_output = Path(r'{reports_root}') / '{{symbol}}' / '2026-06-01'; "
        "assert output_dir == expected_output, f'{output_dir} != {expected_output}'; "
        "output_dir.mkdir(parents=True, exist_ok=True); "
        "(output_dir / '{symbol}-validation.json').write_text('{{\\\"issues\\\": []}}', encoding='utf-8')"
        "\""
    )

    result = run_harness(
        "run-batch",
        "EWW",
        "--run-root",
        str(runtime_root),
        "--producer-command",
        producer,
        "--validator-command",
        validator,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["symbols"]["EWW"]["status"] == "passed"
    assert payload["symbols"]["EWW"]["artifact_run_dir"] == str(data_bundle)
    assert payload["symbols"]["EWW"]["validation_json"] == str(reports_root / "EWW" / "2026-06-01" / "EWW-validation.json")


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
