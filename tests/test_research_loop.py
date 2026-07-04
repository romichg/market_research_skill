import json
import importlib.util
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

HARNESS = Path(__file__).resolve().parents[1] / "market-research" / "batch-supervisor" / "scripts" / "research_loop.py"


def run_harness(*args, env=None):
    return subprocess.run([sys.executable, str(HARNESS), *args], text=True, capture_output=True, check=False, env=env)


def load_module():
    spec = importlib.util.spec_from_file_location("research_loop", HARNESS)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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


def test_inspect_validation_writes_opt_in_metrics_without_changing_stdout_json(tmp_path):
    validation = tmp_path / "validation.json"
    metrics = tmp_path / "metrics" / "loop.json"
    validation.write_text(
        json.dumps(
            {
                "issues": [
                    {"id": "critical-open", "severity": "critical", "status": "open"},
                    {"id": "minor-open", "severity": "minor", "status": "open"},
                ]
            }
        ),
        encoding="utf-8",
    )

    result = run_harness("inspect-validation", str(validation), "--metrics-json", str(metrics))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["passes_gate"] is False
    sidecar = json.loads(metrics.read_text(encoding="utf-8"))
    assert sidecar["script"] == "research_loop.py"
    assert sidecar["command"] == "inspect-validation"
    assert sidecar["open_blocking_issue_count"] == 1
    assert sidecar["elapsed_seconds"] >= 0


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
    assert "$market-research verifier reports/EWW/2026-06-01" in validator
    assert "Write validator skill issues to `runtime/EWW/2026-06-01/EWW-validator-skill-issues.md`." in validator
    assert "Fix only open critical/moderate issues" in remediation
    assert "Append any market-research skill improvements to `runtime/EWW/2026-06-01/EWW-market-research-skill-issues.md`." in remediation
    assert "Do not delete validator outputs" in remediation


def test_write_prompts_agent_cli_claude_uses_slash_invocation(tmp_path):
    out_dir = tmp_path / "prompts"

    result = run_harness(
        "write-prompts",
        "EWW",
        "--run-dir",
        "reports/EWW/2026-06-01",
        "--output-dir",
        str(out_dir),
        "--agent-cli",
        "claude",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    producer = Path(payload["producer_initial_prompt"]).read_text(encoding="utf-8")
    validator = Path(payload["validator_prompt"]).read_text(encoding="utf-8")
    assert producer.startswith("/market-research researcher EWW")
    assert "$market-research" not in producer
    assert "fresh Claude Code session" in producer
    assert validator.startswith("/market-research verifier reports/EWW/2026-06-01")
    assert "$market-research" not in validator
    assert "fresh Claude Code session" in validator


def test_run_batch_defaults_to_claude_command_and_prompts_when_agent_cli_is_claude(tmp_path):
    module = load_module()
    runtime_root = tmp_path / "runtime" / "batch"

    result = run_harness(
        "run-batch",
        "EWW",
        "--run-root",
        str(runtime_root),
        "--as-of",
        "2026-07-03",
        "--agent-cli",
        "claude",
        "--dry-run",
    )

    assert result.returncode == 0, result.stderr
    commands = json.loads((runtime_root / "EWW" / "2026-07-03" / "iteration-01" / "commands.json").read_text(encoding="utf-8"))
    assert commands["producer"].startswith("claude -p --dangerously-skip-permissions")
    assert commands["validator"].startswith("claude -p --dangerously-skip-permissions")
    producer_prompt = (runtime_root / "EWW" / "2026-07-03" / "iteration-01" / "producer-initial.prompt.md").read_text(encoding="utf-8")
    assert producer_prompt.startswith("/market-research researcher EWW")
    assert module.DEFAULT_COMMANDS_BY_AGENT_CLI["claude"] == module.DEFAULT_CLAUDE_COMMAND


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
        "Use deterministic evidence first: `python3 market-research/shared/scripts/deterministic_research_collector.py fetch "
        "AAPL --data-dir ./data --reports-dir ./reports --as-of YYYY-MM-DD`."
    ) in producer
    assert "Use the deterministic bundle under `data/AAPL/2026-06-16/` as evidence." in producer
    assert (
        "producer_self_check.py reports/AAPL/2026-06-16 --data-dir data/AAPL/2026-06-16 "
        "--runtime-dir runtime/AAPL/2026-06-16 --fix-safe"
    ) in producer
    assert "Write final research markdown and JSON under `reports/AAPL/2026-06-16`." in producer
    assert "Attempt best-effort PDF generation for the final markdown" in producer
    assert "Write producer skill issues to `runtime/AAPL/2026-06-16/AAPL-market-research-issues.md`." in producer
    assert "$market-research verifier reports/AAPL/2026-06-16" in validator
    assert "Write validator skill issues to `runtime/AAPL/2026-06-16/AAPL-validator-skill-issues.md`." in validator


def test_producer_prompt_requires_investor_language_and_etf_company_snapshot(tmp_path):
    out_dir = tmp_path / "prompts"

    result = run_harness("write-prompts", "ECH", "--run-dir", "reports/ECH/2026-06-25", "--output-dir", str(out_dir))

    assert result.returncode == 0, result.stderr
    producer = Path(json.loads(result.stdout)["producer_initial_prompt"]).read_text(encoding="utf-8")
    assert "Use investor-facing language in main report sections" in producer
    assert "introduce market value, net assets, or a valuation range" in producer
    assert "Do not include a Self-Check section" in producer
    assert "deterministic_* source IDs" in producer
    assert "Portfolio Companies Snapshot" in producer
    assert "all holdings when the ETF has 25 or fewer holdings; otherwise cover the top 25 by weight" in producer
    assert "peer/competitor ETF comparison" in producer
    assert "disclose in Data Issues And Discrepancies why peer data was unavailable" in producer
    assert "authorized participant and creation/redemption mechanics" in producer
    assert "securities lending" in producer
    assert "translate support/resistance, moving averages, volatility, drawdown, and momentum" in producer
    assert "entry, sizing, confirmation, or invalidation implications" in producer


def test_producer_prompt_points_procedural_helper_output_root_at_plain_runtime_dir(tmp_path):
    out_dir = tmp_path / "prompts"

    result = run_harness("write-prompts", "AAPL", "--run-dir", "reports/AAPL/2026-06-16", "--output-dir", str(out_dir))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    producer = Path(payload["producer_initial_prompt"]).read_text(encoding="utf-8")
    assert "procedural_source_helper.py` commands" in producer
    assert "pass `--output-root runtime --as-of YYYY-MM-DD`" in producer
    remediation = Path(payload["producer_remediation_prompt"]).read_text(encoding="utf-8")
    assert "pass `--output-root runtime --as-of YYYY-MM-DD`" in remediation


def test_producer_prompt_points_procedural_helper_output_root_at_batch_run_root(tmp_path):
    out_dir = tmp_path / "prompts"
    run_dir = "runtime/market-research-batch-20260703/ECH/2026-07-03"

    result = run_harness("write-prompts", "ECH", "--run-dir", run_dir, "--output-dir", str(out_dir))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    producer = Path(payload["producer_initial_prompt"]).read_text(encoding="utf-8")
    assert "pass `--output-root runtime/market-research-batch-20260703 --as-of YYYY-MM-DD`" in producer
    assert f"land under `{run_dir}`" in producer
    remediation = Path(payload["producer_remediation_prompt"]).read_text(encoding="utf-8")
    assert "pass `--output-root runtime/market-research-batch-20260703 --as-of YYYY-MM-DD`" in remediation


def test_producer_prompt_procedural_output_root_for_non_dated_run_dir(tmp_path):
    out_dir = tmp_path / "prompts"

    result = run_harness("write-prompts", "AAPL", "--run-dir", "reports/AAPL", "--output-dir", str(out_dir))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    producer = Path(payload["producer_initial_prompt"]).read_text(encoding="utf-8")
    assert "pass `--output-root runtime --as-of YYYY-MM-DD`" in producer
    assert "--output-root runtime/AAPL " not in producer


def test_loop_prompt_preserves_custom_runtime_root_for_transient_artifacts(tmp_path):
    out_dir = tmp_path / "prompts"
    run_dir = "runtime/market-research-loop-20260620/AAPL/2026-06-16"

    result = run_harness("write-prompts", "AAPL", "--run-dir", run_dir, "--output-dir", str(out_dir))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    producer = Path(payload["producer_initial_prompt"]).read_text(encoding="utf-8")
    assert f"Use `{run_dir}` for transient runtime notes, prompts, logs, and issue files." in producer
    assert f"Write producer skill issues to `{run_dir}/AAPL-market-research-issues.md`." in producer
    validator = Path(payload["validator_prompt"]).read_text(encoding="utf-8")
    remediation = Path(payload["producer_remediation_prompt"]).read_text(encoding="utf-8")
    assert f"Write validator skill issues to `{run_dir}/AAPL-validator-skill-issues.md`." in validator
    assert f"Append any market-research skill improvements to `{run_dir}/AAPL-market-research-skill-issues.md`." in remediation


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
    assert f"Write producer skill issues to `{expected_runtime_dir / 'AAPL-market-research-issues.md'}`." in producer
    validator = Path(payload["validator_prompt"]).read_text(encoding="utf-8")
    remediation = Path(payload["producer_remediation_prompt"]).read_text(encoding="utf-8")
    assert f"Write validator skill issues to `{expected_runtime_dir / 'AAPL-validator-skill-issues.md'}`." in validator
    assert f"Append any market-research skill improvements to `{expected_runtime_dir / 'AAPL-market-research-skill-issues.md'}`." in remediation


def test_write_prompts_default_validator_output_uses_reports_placeholder(tmp_path):
    out_dir = tmp_path / "prompts"

    result = run_harness("write-prompts", "EWW", "--output-dir", str(out_dir))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    validator = Path(payload["validator_prompt"]).read_text(encoding="utf-8")
    assert "$market-research verifier runtime/EWW" in validator
    assert "Write validation markdown and JSON artifacts under `reports/EWW/YYYY-MM-DD`." in validator
    assert "Write validator skill issues to `runtime/EWW/EWW-validator-skill-issues.md`." in validator
    assert "Write validation markdown and JSON artifacts under `runtime/EWW`." not in validator


def test_init_batch_validator_prompts_use_reports_as_of_output(tmp_path):
    root = tmp_path / "runtime" / "batch"

    result = run_harness("init-batch", "EWW", "--run-root", str(root), "--as-of", "2026-06-16")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    validator = (Path(payload["prompt_dirs"]["EWW"]) / "EWW-validator.md").read_text(encoding="utf-8")
    assert f"$market-research verifier {root / 'EWW' / '2026-06-16'}" in validator
    assert "Write validation markdown and JSON artifacts under `reports/EWW/2026-06-16`." in validator
    assert f"Write validation markdown and JSON artifacts under `{root / 'EWW' / '2026-06-16'}`." not in validator


def test_init_batch_does_not_write_self_improvement_prompt(tmp_path):
    root = tmp_path / "runtime" / "batch"

    result = run_harness("init-batch", "DPC", "QBIT", "--run-root", str(root), "--as-of", "2026-06-16")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert "self_improvement_prompt" not in payload
    assert not (root / "prompts" / "self-improvement.md").exists()


def test_self_improve_writes_central_prompt_for_multiple_run_roots(tmp_path):
    run_a = tmp_path / "runtime" / "batch-a"
    run_b = tmp_path / "runtime" / "batch-b"
    output_root = tmp_path / "runtime" / "self-improvement"
    for root in [run_a, run_b]:
        root.mkdir(parents=True)
        (root / "research-loop-summary.json").write_text(json.dumps({"run_root": str(root)}), encoding="utf-8")

    result = run_harness("self-improve", str(run_a), str(run_b), "--output-root", str(output_root))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    prompt_path = Path(payload["prompt"])
    assert prompt_path.parent.parent == output_root
    assert prompt_path.name == "self-improvement.md"
    assert payload["run_roots"] == [str(run_a), str(run_b)]
    assert "command" not in payload
    prompt = prompt_path.read_text(encoding="utf-8")
    assert "$superpowers" in prompt
    assert str(run_a / "research-loop-summary.json") in prompt
    assert str(run_b / "research-loop-summary.json") in prompt
    assert str(prompt_path.parent / "self-improvement-plan.md") in prompt
    assert "investor-grade reporting/memo quality" in prompt
    assert "Does the report read like an investor memo rather than a deterministic-data recital or citation-heavy audit trail?" in prompt
    assert "Preserve `reports/` as final product and `runtime/` as intermediate work product" in prompt
    assert "field-level freshness" in prompt
    assert "Do not recommend main-body cache mechanics disclosure unless stale or unavailable data changes investor interpretation." in prompt
    assert "Bottom Line" in prompt
    assert "executive summary" in prompt
    assert "routine data-vendor names" in prompt
    assert "Key Facts" in prompt
    assert "table" in prompt
    assert "Business Profile" in prompt
    assert "plain language" in prompt
    assert "Market Snapshot And Technical Analysis" in prompt
    assert "support/resistance" in prompt
    assert "Data Issues And Discrepancies" in prompt
    assert "Validate collector runtime behavior from bundle manifests and fetch metrics" in prompt
    assert "`price_fetch_suppressed`" in prompt
    assert "audit mis-scoring" in prompt
    assert "available_history" in prompt
    assert str(run_a / "skill-improvement-feedback.md") in prompt
    assert str(run_b / "skill-improvement-feedback.md") in prompt


def test_self_improve_defaults_to_docs_superpowers_plans(tmp_path, monkeypatch):
    run_root = tmp_path / "runtime" / "batch"
    run_root.mkdir(parents=True)
    (run_root / "research-loop-summary.json").write_text(json.dumps({"run_root": str(run_root)}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = run_harness("self-improve", str(run_root))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    prompt_path = Path(payload["prompt"])
    assert prompt_path.parts[:4] == ("docs", "superpowers", "plans", "self-improvement")
    assert prompt_path.name == "self-improvement.md"
    assert not (tmp_path / "runtime" / "self-improvement").exists()


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


def test_run_batch_syncs_runtime_sources_to_report_dir_before_validation(tmp_path):
    root = tmp_path / "runtime" / "batch"
    reports_bundle = tmp_path / "reports" / "ECH" / "2026-06-25"
    runtime_bundle = root / "ECH" / "2026-06-25"
    producer = (
        f"{sys.executable} -c \""
        "from pathlib import Path; import json; "
        f"report_dir = Path(r'{reports_bundle}'); "
        f"runtime_dir = Path(r'{runtime_bundle}'); "
        "report_dir.mkdir(parents=True, exist_ok=True); "
        "runtime_dir.mkdir(parents=True, exist_ok=True); "
        "(report_dir / '{symbol}-research.md').write_text('ok', encoding='utf-8'); "
        "(report_dir / '{symbol}-research.json').write_text('{{}}', encoding='utf-8'); "
        "(runtime_dir / 'sources.json').write_text(json.dumps({{'sources': [{{'id': 'issuer'}}]}}), encoding='utf-8'); "
        "(runtime_dir / 'run_manifest.json').write_text(json.dumps({{'cycle': 3}}), encoding='utf-8'); "
        "(runtime_dir / 'research_context.md').write_text('context', encoding='utf-8'); "
        "(runtime_dir / 'research_context.json').write_text(json.dumps({{'context': True}}), encoding='utf-8'); "
        "(runtime_dir / 'source_bundle').mkdir(); "
        "(runtime_dir / 'source_bundle' / 'issuer.html').write_text('issuer source', encoding='utf-8')"
        "\""
    )
    validator = (
        f"{sys.executable} -c \""
        "from pathlib import Path; import json; "
        "run_dir = Path(r'{run_dir}'); "
        "sources = json.loads((run_dir / 'sources.json').read_text(encoding='utf-8')); "
        "assert sources['sources'][0]['id'] == 'issuer'; "
        "assert (run_dir / 'source_bundle' / 'issuer.html').exists(); "
        "(run_dir / '{symbol}-validation.json').write_text('{{\\\"issues\\\": []}}', encoding='utf-8')"
        "\""
    )

    result = run_harness(
        "run-batch",
        "ECH",
        "--run-root",
        str(root),
        "--as-of",
        "2026-06-25",
        "--producer-command",
        producer,
        "--validator-command",
        validator,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["symbols"]["ECH"]["status"] == "passed"
    assert (reports_bundle / "sources.json").exists()
    assert json.loads((reports_bundle / "run_manifest.json").read_text(encoding="utf-8")) == {"cycle": 3}
    assert (reports_bundle / "research_context.md").read_text(encoding="utf-8") == "context"
    assert json.loads((reports_bundle / "research_context.json").read_text(encoding="utf-8")) == {"context": True}
    assert (reports_bundle / "source_bundle" / "issuer.html").exists()


def test_sync_runtime_sources_rewrites_local_artifacts_to_report_bundle(tmp_path):
    spec = importlib.util.spec_from_file_location("research_loop", HARNESS)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["research_loop"] = module
    spec.loader.exec_module(module)
    runtime_dir = tmp_path / "runtime" / "market-research-batch-20260701" / "QTUP" / "2026-07-01"
    report_dir = tmp_path / "reports" / "QTUP" / "2026-07-01"
    source_bundle = runtime_dir / "source_bundle"
    source_bundle.mkdir(parents=True)
    artifact = source_bundle / "qtup_prospectus.pdf"
    artifact.write_bytes(b"prospectus")
    (runtime_dir / "sources.json").write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "id": "qtup_prospectus",
                        "local_artifact": str(artifact),
                        "sha256": "not-used-in-this-test",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    module.sync_runtime_sources_to_report(runtime_dir, report_dir)

    sources = json.loads((report_dir / "sources.json").read_text(encoding="utf-8"))
    assert sources["sources"][0]["local_artifact"] == str(report_dir / "source_bundle" / "qtup_prospectus.pdf")
    assert (report_dir / "source_bundle" / "qtup_prospectus.pdf").read_bytes() == b"prospectus"


def test_sync_runtime_sources_to_report_merges_report_source_records(tmp_path):
    spec = importlib.util.spec_from_file_location("research_loop", HARNESS)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["research_loop"] = module
    spec.loader.exec_module(module)
    runtime_dir = tmp_path / "runtime" / "batch" / "ECH" / "2026-07-02"
    report_dir = tmp_path / "reports" / "ECH" / "2026-07-02"
    runtime_dir.mkdir(parents=True)
    report_dir.mkdir(parents=True)
    (runtime_dir / "sources.json").write_text(json.dumps({"sources": [{"id": "issuer_page"}]}), encoding="utf-8")
    (report_dir / "sources.json").write_text(json.dumps({"sources": [{"id": "deterministic_gaps"}]}), encoding="utf-8")

    module.sync_runtime_sources_to_report(runtime_dir, report_dir)

    sources = json.loads((report_dir / "sources.json").read_text(encoding="utf-8"))["sources"]
    assert {source["id"] for source in sources} == {"issuer_page", "deterministic_gaps"}


def test_sync_runtime_sources_rewrites_preserved_report_source_records(tmp_path):
    spec = importlib.util.spec_from_file_location("research_loop", HARNESS)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["research_loop"] = module
    spec.loader.exec_module(module)
    runtime_dir = tmp_path / "runtime" / "batch" / "EWW" / "2026-07-02"
    report_dir = tmp_path / "reports" / "EWW" / "2026-07-02"
    runtime_bundle = runtime_dir / "source_bundle"
    runtime_bundle.mkdir(parents=True)
    (runtime_bundle / "issuer.html").write_text("issuer", encoding="utf-8")
    report_bundle = report_dir / "source_bundle"
    report_bundle.mkdir(parents=True)
    (report_bundle / "issuer.html").write_text("issuer", encoding="utf-8")
    (runtime_dir / "sources.json").write_text(json.dumps({"sources": []}), encoding="utf-8")
    (report_dir / "sources.json").write_text(
        json.dumps({"sources": [{"id": "issuer_page", "local_artifact": str(runtime_bundle / "issuer.html")}]}),
        encoding="utf-8",
    )

    module.sync_runtime_sources_to_report(runtime_dir, report_dir)

    sources = json.loads((report_dir / "sources.json").read_text(encoding="utf-8"))["sources"]
    assert sources == [{"id": "issuer_page", "local_artifact": str(report_bundle / "issuer.html")}]


def test_sync_runtime_sources_rewrites_markdown_source_bundle_paths(tmp_path):
    spec = importlib.util.spec_from_file_location("research_loop", HARNESS)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["research_loop"] = module
    spec.loader.exec_module(module)
    runtime_dir = tmp_path / "runtime" / "batch" / "ECH" / "2026-07-02"
    report_dir = tmp_path / "reports" / "ECH" / "2026-07-02"
    source_bundle = runtime_dir / "source_bundle"
    source_bundle.mkdir(parents=True)
    (source_bundle / "issuer.html").write_text("issuer", encoding="utf-8")
    report_dir.mkdir(parents=True)
    (report_dir / "ECH-research.md").write_text(
        f"""# ECH Research

## Sources And Evidence

| Source | Evidence |
| --- | --- |
| issuer | {runtime_dir}/source_bundle/issuer.html |

## Data Issues And Discrepancies

The saved source is {runtime_dir}/source_bundle/issuer.html.
""",
        encoding="utf-8",
    )

    module.sync_runtime_sources_to_report(runtime_dir, report_dir)

    text = (report_dir / "ECH-research.md").read_text(encoding="utf-8")
    assert f"| issuer | {report_dir}/source_bundle/issuer.html |" in text
    assert f"The saved source is {report_dir}/source_bundle/issuer.html." in text
    assert f"{runtime_dir}/source_bundle/issuer.html" not in text


def test_sync_runtime_sources_rewrites_json_source_bundle_paths(tmp_path):
    spec = importlib.util.spec_from_file_location("research_loop", HARNESS)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["research_loop"] = module
    spec.loader.exec_module(module)
    runtime_dir = tmp_path / "runtime" / "batch" / "QUBT" / "2026-07-02"
    report_dir = tmp_path / "reports" / "QUBT" / "2026-07-02"
    source_bundle = runtime_dir / "source_bundle"
    source_bundle.mkdir(parents=True)
    (source_bundle / "issuer.html").write_text("issuer", encoding="utf-8")
    (source_bundle / "extracted.json").write_text(
        json.dumps({"source_file": str(source_bundle / "issuer.html")}),
        encoding="utf-8",
    )
    runtime_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True)
    (runtime_dir / "sources.json").write_text(json.dumps({"sources": []}), encoding="utf-8")
    (runtime_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "source_bundle_file": str(source_bundle / "issuer.html"),
                "source_bundle": str(source_bundle),
                "runtime_dir": str(runtime_dir),
            }
        ),
        encoding="utf-8",
    )
    (runtime_dir / "research_context.json").write_text(
        json.dumps({"sources": [{"local_artifact": str(source_bundle / "issuer.html")}]}),
        encoding="utf-8",
    )
    (report_dir / "QUBT-research.json").write_text(
        json.dumps(
            {
                "input_artifacts": [str(source_bundle / "issuer.html")],
                "audit": {"runtime_dir": str(runtime_dir)},
            }
        ),
        encoding="utf-8",
    )

    module.sync_runtime_sources_to_report(runtime_dir, report_dir)

    report_artifact = str(report_dir / "source_bundle" / "issuer.html")
    assert json.loads((report_dir / "run_manifest.json").read_text(encoding="utf-8")) == {
        "runtime_dir": str(runtime_dir),
        "source_bundle": str(report_dir / "source_bundle"),
        "source_bundle_file": report_artifact,
    }
    assert json.loads((report_dir / "research_context.json").read_text(encoding="utf-8")) == {
        "sources": [{"local_artifact": report_artifact}]
    }
    assert json.loads((report_dir / "QUBT-research.json").read_text(encoding="utf-8")) == {
        "audit": {"runtime_dir": str(runtime_dir)},
        "input_artifacts": [report_artifact],
    }
    assert json.loads((report_dir / "source_bundle" / "extracted.json").read_text(encoding="utf-8")) == {
        "source_file": report_artifact
    }


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


def test_summarize_reports_feedback_package_freshness(tmp_path):
    root = tmp_path / "batch"
    root.mkdir()
    feedback = {
        "issue_file_count": 2,
        "researcher_comment_count": 1,
        "supporting_artifact_count": 3,
    }
    feedback_path = root / "skill-improvement-feedback.json"
    feedback_path.write_text(json.dumps(feedback), encoding="utf-8")

    result = run_harness("summarize", str(root))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["feedback_package"]["path"] == str(feedback_path)
    assert payload["feedback_package"]["issue_file_count"] == 2
    assert payload["feedback_package"]["researcher_comment_count"] == 1
    assert payload["feedback_package"]["supporting_artifact_count"] == 3
    assert payload["feedback_package"]["modified_at"]


def test_summarize_ignores_prompt_scaffold_directory(tmp_path):
    root = tmp_path / "runtime" / "batch"
    runtime_symbol = root / "ECH" / "2026-07-03"
    prompts = root / "prompts" / "ECH"
    report_dir = tmp_path / "reports" / "ECH" / "2026-07-03"
    runtime_symbol.mkdir(parents=True)
    prompts.mkdir(parents=True)
    report_dir.mkdir(parents=True)
    (root / "research-loop-config.json").write_text(json.dumps({"symbols": ["ECH"]}), encoding="utf-8")
    (report_dir / "ECH-validation.json").write_text(json.dumps({"issues": []}), encoding="utf-8")

    result = run_harness("summarize", str(root))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["symbols_total"] == 1
    assert payload["passed"] == ["ECH"]
    assert payload["failed"] == []


def test_summarize_uses_reports_dir_environment_fallback(tmp_path):
    root = tmp_path / "runtime" / "batch"
    runtime_symbol = root / "ECH" / "2026-07-03"
    report_dir = tmp_path / "custom-reports" / "ECH" / "2026-07-03"
    runtime_symbol.mkdir(parents=True)
    report_dir.mkdir(parents=True)
    (report_dir / "ECH-validation.json").write_text(json.dumps({"issues": []}), encoding="utf-8")
    env = {**os.environ, "RESEARCH_REPORTS_DIR": str(tmp_path / "custom-reports")}

    result = run_harness("summarize", str(root), env=env)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["passed"] == ["ECH"]
    assert payload["failed"] == []


def test_refresh_summary_records_post_loop_validation(tmp_path):
    root = tmp_path / "runtime" / "batch"
    runtime_symbol = root / "ECH" / "2026-07-02"
    report_dir = tmp_path / "reports" / "ECH" / "2026-07-02"
    runtime_symbol.mkdir(parents=True)
    report_dir.mkdir(parents=True)
    summary_path = root / "research-loop-summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "symbols": {
                    "ECH": {
                        "status": "failed_blocking_issues",
                        "iterations": 4,
                        "run_dir": str(runtime_symbol),
                        "artifact_run_dir": str(report_dir),
                        "validation_json": str(report_dir / "ECH-validation.json"),
                        "open_blocking_issue_ids": ["ECH-V-001"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    (report_dir / "ECH-validation.json").write_text(json.dumps({"final_pass": True, "blocking_issue_count": 0, "issues": []}), encoding="utf-8")

    result = run_harness("refresh-summary", str(root))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    symbol = payload["symbols"]["ECH"]
    assert symbol["status"] == "passed"
    assert symbol["historical_status"] == "failed_blocking_issues"
    assert symbol["post_loop_refresh"]["validation_json"] == str(report_dir / "ECH-validation.json")
    assert symbol["open_blocking_issue_ids"] == []


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


def test_run_batch_does_not_execute_or_plan_self_improvement(tmp_path):
    root = tmp_path / "batch"
    reports_bundle = tmp_path / "reports" / "EWW" / "2026-06-16"
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
    assert "self_improvement" not in payload
    assert not (root / "prompts" / "self-improvement.md").exists()
    assert not (root / "self-improvement").exists()


def test_run_batch_uses_producer_self_check_before_validator(tmp_path):
    root = tmp_path / "runtime" / "batch"
    as_of = "2026-07-01"
    reports_bundle = tmp_path / "reports" / "QTUM" / as_of
    data_bundle = tmp_path / "data" / "QTUM" / as_of
    validator_marker = tmp_path / "validator-used"
    producer = (
        f"{sys.executable} -c \""
        "from pathlib import Path; import json; "
        f"report_dir = Path(r'{reports_bundle}'); data_dir = Path(r'{data_bundle}'); "
        "report_dir.mkdir(parents=True, exist_ok=True); (data_dir / 'normalized').mkdir(parents=True, exist_ok=True); "
        "(data_dir / 'research_input_pack.md').write_text('pack', encoding='utf-8'); "
        "(data_dir / 'manifest.json').write_text(json.dumps({'symbol':'QTUM','asset_type':'etf'}), encoding='utf-8'); "
        "(data_dir / 'source_manifest.json').write_text(json.dumps({'sources':[]}), encoding='utf-8'); "
        "(data_dir / 'gaps.json').write_text(json.dumps({'gaps':[]}), encoding='utf-8'); "
        "(data_dir / 'deterministic_data_usage.json').write_text(json.dumps({'datapoints':[{'field_path':'identity.asset_type','field_name':'asset_type','materiality':'required'}]}), encoding='utf-8'); "
        "(report_dir / 'QTUM-research.md').write_text('# QTUM Research', encoding='utf-8'); "
        "payload = {'symbol':'QTUM','security_type':'etf','as_of_date':'2026-07-01','deterministic_bundle':{'bundle_dir':str(data_dir)},'material_claims':[],'data_gaps':[],'technical_analysis':{},'valuation_or_performance':{},'decision_factors':{},'risks':[],'catalysts':[],'source_coverage':{},'calculation_audit':[]}; "
        "(report_dir / 'QTUM-research.json').write_text(json.dumps(payload), encoding='utf-8'); "
        "(report_dir / 'sources.json').write_text(json.dumps({'sources':[]}), encoding='utf-8')"
        "\""
    )
    validator = (
        f"{sys.executable} -c \""
        "from pathlib import Path; "
        f"Path(r'{validator_marker}').write_text('used', encoding='utf-8')"
        "\""
    )

    result = run_harness(
        "run-batch",
        "QTUM",
        "--run-root",
        str(root),
        "--as-of",
        as_of,
        "--producer-command",
        producer,
        "--validator-command",
        validator,
        "--max-remediation-loops",
        "0",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    result_payload = payload["symbols"]["QTUM"]
    assert result_payload["status"] == "failed_producer_self_check"
    assert "deterministic-usage-missing-required-identity-asset_type" in result_payload["open_blocking_issue_ids"]
    assert not validator_marker.exists()
    assert (root / "QTUM" / as_of / "producer-self-check.json").exists()


def test_run_batch_moves_intermediate_validation_scaffolds_to_runtime(tmp_path):
    root = tmp_path / "runtime" / "batch"
    as_of = "2026-06-16"
    reports_bundle = tmp_path / "reports" / "EWW" / as_of
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
        "run_dir = Path(r'{validation_output_dir}'); "
        "(run_dir / '{symbol}-validation.json').write_text('{{\\\"issues\\\": []}}', encoding='utf-8'); "
        "(run_dir / '{symbol}-validation-scaffold.md').write_text('canonical', encoding='utf-8'); "
        "(run_dir / '{symbol}-validation-scaffold.json').write_text('{{}}', encoding='utf-8'); "
        "(run_dir / '{symbol}-remediation-validation-scaffold.md').write_text('intermediate', encoding='utf-8'); "
        "(run_dir / '{symbol}-remediation-validation-scaffold.json').write_text('{{}}', encoding='utf-8')"
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
    runtime_dir = root / "EWW" / as_of
    assert (reports_bundle / "EWW-validation-scaffold.md").exists()
    assert (reports_bundle / "EWW-validation-scaffold.json").exists()
    assert not (reports_bundle / "EWW-remediation-validation-scaffold.md").exists()
    assert not (reports_bundle / "EWW-remediation-validation-scaffold.json").exists()
    assert (runtime_dir / "validation_scaffolds" / "EWW-remediation-validation-scaffold.md").read_text(encoding="utf-8") == "intermediate"
    assert (runtime_dir / "validation_scaffolds" / "EWW-remediation-validation-scaffold.json").exists()


def test_run_batch_refuses_to_reuse_run_root_with_existing_iteration_logs(tmp_path):
    root = tmp_path / "runtime" / "batch"
    as_of = "2026-06-16"
    reports_bundle = tmp_path / "reports" / "EWW" / as_of
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
        "run_dir = Path(r'{validation_output_dir}'); "
        "(run_dir / '{symbol}-validation.json').write_text('{{\\\"issues\\\": []}}', encoding='utf-8')"
        "\""
    )
    first = run_harness(
        "run-batch", "EWW", "--run-root", str(root), "--as-of", as_of,
        "--producer-command", producer, "--validator-command", validator,
    )
    assert first.returncode == 0, first.stderr

    second = run_harness(
        "run-batch", "EWW", "--run-root", str(root), "--as-of", as_of,
        "--producer-command", producer, "--validator-command", validator,
    )

    assert second.returncode != 0
    assert "Refusing to overwrite existing run" in second.stderr
    assert "--resume" in second.stderr

    resumed = run_harness(
        "run-batch", "EWW", "--run-root", str(root), "--as-of", as_of,
        "--producer-command", producer, "--validator-command", validator, "--resume",
    )
    assert resumed.returncode == 0, resumed.stderr


def test_run_batch_dry_run_does_not_trigger_reuse_guard(tmp_path):
    root = tmp_path / "runtime" / "batch"
    as_of = "2026-06-16"

    first = run_harness("run-batch", "EWW", "--run-root", str(root), "--as-of", as_of, "--dry-run")
    assert first.returncode == 0, first.stderr

    second = run_harness("run-batch", "EWW", "--run-root", str(root), "--as-of", as_of, "--dry-run")
    assert second.returncode == 0, second.stderr


def test_run_batch_dry_run_then_real_run_does_not_trigger_reuse_guard(tmp_path):
    root = tmp_path / "runtime" / "batch"
    as_of = "2026-06-16"
    reports_bundle = tmp_path / "reports" / "EWW" / as_of
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
        "run_dir = Path(r'{validation_output_dir}'); "
        "(run_dir / '{symbol}-validation.json').write_text('{{\\\"issues\\\": []}}', encoding='utf-8')"
        "\""
    )

    dry_run = run_harness(
        "run-batch", "EWW", "--run-root", str(root), "--as-of", as_of,
        "--producer-command", producer, "--validator-command", validator, "--dry-run",
    )
    assert dry_run.returncode == 0, dry_run.stderr
    assert (root / "EWW" / as_of / "iteration-01" / "commands.json").exists()

    real_run = run_harness(
        "run-batch", "EWW", "--run-root", str(root), "--as-of", as_of,
        "--producer-command", producer, "--validator-command", validator,
    )

    assert real_run.returncode == 0, real_run.stderr


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


def test_run_batch_without_codex_requires_explicit_child_launcher(tmp_path):
    root = tmp_path / "batch"
    env = {**os.environ, "PATH": str(tmp_path / "empty-bin")}

    result = run_harness("run-batch", "EWW", "--run-root", str(root), "--as-of", "2026-06-16", env=env)

    assert result.returncode != 0
    assert "`codex` is not on PATH" in result.stderr
    assert "agent-native" in result.stderr


def test_run_batch_without_selected_agent_cli_requires_explicit_child_launcher(tmp_path):
    root = tmp_path / "batch"
    env = {**os.environ, "PATH": str(tmp_path / "empty-bin")}

    result = run_harness(
        "run-batch",
        "EWW",
        "--run-root",
        str(root),
        "--as-of",
        "2026-07-03",
        "--agent-cli",
        "claude",
        env=env,
    )

    assert result.returncode != 0
    assert "`claude` is not on PATH" in result.stderr
    assert "agent-native" in result.stderr


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
    assert "--dangerously-bypass-approvals-and-sandbox" in commands["producer"]
    assert str(iteration / "producer-initial.prompt.md") in commands["producer"]


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


def test_run_batch_marks_producer_rate_limited_distinctly_from_generic_failure(tmp_path):
    runtime_root = tmp_path / "runtime" / "batch"
    as_of = "2026-07-03"
    validator_marker = tmp_path / "validator-used"
    producer = (
        f"{sys.executable} -c \"import sys; "
        "print(\\\"You've hit your session limit · resets 5:30am (America/New_York)\\\"); "
        "sys.exit(1)\""
    )
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
    assert payload["symbols"]["EWW"]["status"] == "producer_rate_limited"
    assert payload["symbols"]["EWW"]["exit_code"] == 1
    assert not validator_marker.exists()


def test_looks_rate_limited_matches_known_signatures_only():
    module = load_module()

    assert module.looks_rate_limited("You've hit your session limit · resets 5:30am (America/New_York)", "")
    assert module.looks_rate_limited("", "Error: rate limit exceeded, try again later")
    assert not module.looks_rate_limited("Traceback (most recent call last): ValueError", "")
    # A rate-limit phrase buried far above the output tail (e.g. narration about provider budgets)
    # must not be treated as a child rate-limit failure.
    narration = "The provider rate limit is 20 calls/day.\n" + "\n".join(f"progress line {i}" for i in range(60))
    assert not module.looks_rate_limited(narration, "")


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
    (symbol_dir / "EWW-market-research-issues.md").write_text("# Researcher Issues\n\n- Capture source fallback better.\n", encoding="utf-8")
    (symbol_dir / "EWW-researcher-comments.md").write_text("# Researcher Comments\n\n- Avoid CYA language.\n", encoding="utf-8")
    (symbol_dir / "EWW-validator-skill-issues.md").write_text("# Validator Issues\n\n- Check checksums.\n", encoding="utf-8")
    (root / "loop-skill-issues.md").write_text("# Loop Skill Issues\n\n- Tune timeout.\n", encoding="utf-8")
    (root / "operator-notes.md").write_text("# Operator Notes\n\n## Future User-Requested Changes\n\n- Add PDF output later.\n", encoding="utf-8")

    result = run_harness("collect-feedback", str(root))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["issue_file_count"] == 5
    feedback_md = root / "skill-improvement-feedback.md"
    feedback_json = root / "skill-improvement-feedback.json"
    assert feedback_md.exists()
    assert feedback_json.exists()
    text = feedback_md.read_text(encoding="utf-8")
    assert "Manual Skill Improvement Package" in text
    assert "Add PDF output later" in text
    assert "Capture source fallback better" in text
    assert "Avoid CYA language" in text


def test_collect_feedback_includes_report_side_issues_and_researcher_comments(tmp_path):
    root = tmp_path / "runtime" / "batch"
    runtime_symbol = root / "EWW" / "2026-07-02"
    report_dir = tmp_path / "reports" / "EWW" / "2026-07-02"
    runtime_symbol.mkdir(parents=True)
    report_dir.mkdir(parents=True)
    (root / "research-loop-summary.json").write_text(
        json.dumps(
            {
                "symbols": {
                    "EWW": {
                        "artifact_run_dir": str(report_dir),
                        "run_dir": str(runtime_symbol),
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    (report_dir / "EWW-market-research-skill-issues.md").write_text(
        "# EWW Skill Issues\n\n- Promotion overwrote fixed report sources from stale runtime sources.\n",
        encoding="utf-8",
    )
    (report_dir / "EWW-research.md").write_text(
        "Clean line.\n"
        "Use the sponsor's <@researcher: stop citing the sponsor in narrative; state the fact plainly> data.\n"
        "Typo marker <@reasearcher: typo marker should still be harvested>.\n",
        encoding="utf-8",
    )

    result = run_harness("collect-feedback", str(root))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert str(report_dir / "EWW-market-research-skill-issues.md") in payload["issue_files"]
    assert payload["researcher_comment_count"] == 2
    feedback_md = root / "skill-improvement-feedback.md"
    text = feedback_md.read_text(encoding="utf-8")
    assert "Promotion overwrote fixed report sources from stale runtime sources" in text
    assert "stop citing the sponsor in narrative; state the fact plainly" in text
    assert "typo marker should still be harvested" in text


def test_self_improve_generates_runtime_feedback_package_and_references_it(tmp_path):
    root = tmp_path / "runtime" / "batch"
    report_dir = tmp_path / "reports" / "EWW" / "2026-07-02"
    output_root = tmp_path / "docs" / "self-improvement"
    report_dir.mkdir(parents=True)
    root.mkdir(parents=True)
    (root / "research-loop-summary.json").write_text(
        json.dumps({"symbols": {"EWW": {"artifact_run_dir": str(report_dir)}}}),
        encoding="utf-8",
    )
    (report_dir / "EWW-market-research-skill-issues.md").write_text(
        "# Issues\n\n- Capture report-side issues for self improvement.\n",
        encoding="utf-8",
    )
    (report_dir / "EWW-research.md").write_text(
        "Report text <@researcher: avoid CYA provenance in the investment narrative>.\n",
        encoding="utf-8",
    )

    result = run_harness("self-improve", str(root), "--output-root", str(output_root))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    feedback_md = root / "skill-improvement-feedback.md"
    assert feedback_md.exists()
    assert payload["feedback_packages"] == [str(feedback_md)]
    prompt = Path(payload["prompt"]).read_text(encoding="utf-8")
    assert str(feedback_md) in prompt
    assert "Capture report-side issues for self improvement" in feedback_md.read_text(encoding="utf-8")
    assert "avoid CYA provenance in the investment narrative" in feedback_md.read_text(encoding="utf-8")


def test_collect_feedback_includes_json_skill_issue_sidecars(tmp_path):
    root = tmp_path / "batch"
    issue = root / "QUBT" / "2026-06-23" / "QUBT-validator-skill-issues.json"
    issue.parent.mkdir(parents=True)
    issue.write_text(
        json.dumps(
            {
                "issues": [
                    {
                        "id": "VSKILL-001",
                        "severity": "minor",
                        "status": "open",
                        "description": "Schema validation dependency is not operationally specified.",
                        "suggested_owner": "verifier",
                        "evidence_path": "reports/QUBT/2026-06-23/QUBT-validation.md",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = run_harness("collect-feedback", str(root))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert str(issue) in payload["issue_files"]


def test_collect_feedback_references_runtime_validation_scaffolds(tmp_path):
    root = tmp_path / "batch"
    scaffold = root / "EWW" / "2026-07-02" / "validation_scaffolds" / "EWW-remediation-validation-scaffold.md"
    scaffold.parent.mkdir(parents=True)
    scaffold.write_text("# Scaffold\n\nBlocking issues: 1\n", encoding="utf-8")

    result = run_harness("collect-feedback", str(root))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["supporting_artifact_count"] == 1
    assert str(scaffold) in payload["supporting_artifacts"]
    feedback_md = root / "skill-improvement-feedback.md"
    assert str(scaffold) in feedback_md.read_text(encoding="utf-8")
