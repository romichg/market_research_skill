#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
import json
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
import re

BLOCKING_SEVERITIES = {"critical", "moderate"}
OPEN_STATUSES = {"open", "new", "unresolved"}
SYMBOL_RE = re.compile(r"^[A-Z0-9.\-]{1,12}$")
DEFAULT_CODEX_COMMAND = (
    "codex exec -C {cwd} "
    "--dangerously-bypass-approvals-and-sandbox - < {prompt_file}"
)
DEFAULT_COMMAND_TIMEOUT_SECONDS = 1800
LOOP_ISSUES_TEMPLATE = """# Loop Skill Issues

Use this file for issues with the supervised orchestration skill itself, not investment research defects.

## Harness Orchestration Issues

## Child Codex Command Issues

## Timeout Or Artifact-Contract Issues

## Suggested Loop Skill Improvements
"""
OPERATOR_NOTES_TEMPLATE = """# Operator Notes

Use this file for human operator notes that should not automatically change any skill.

## Run-Specific Notes

## Future User-Requested Changes

Add deferred feature requests here, for example PDF output, browser/captcha handoff, alternate report formats, or new data sources.
"""


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    timed_out: bool = False


def die(message: str, code: int = 2) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        die(f"JSON file not found: {path}")
    except json.JSONDecodeError as exc:
        die(f"Could not parse JSON {path}: {exc}")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_if_missing(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(text.rstrip() + "\n", encoding="utf-8")


def ensure_improvement_note_files(root: Path) -> dict[str, str]:
    loop_issues = root / "loop-skill-issues.md"
    operator_notes = root / "operator-notes.md"
    write_if_missing(loop_issues, LOOP_ISSUES_TEMPLATE)
    write_if_missing(operator_notes, OPERATOR_NOTES_TEMPLATE)
    return {"loop_skill_issues": str(loop_issues), "operator_notes": str(operator_notes)}


def normalize_symbol(symbol: str) -> str:
    value = symbol.strip().upper()
    if not SYMBOL_RE.fullmatch(value):
        die(f"Invalid symbol: {symbol!r}")
    return value


def is_open_blocking(issue: dict[str, Any]) -> bool:
    severity = str(issue.get("severity", "")).lower()
    status = str(issue.get("status", "open")).lower()
    return severity in BLOCKING_SEVERITIES and status in OPEN_STATUSES


def inspect_validation_payload(payload: dict[str, Any]) -> dict[str, Any]:
    issues = payload.get("issues", [])
    if not isinstance(issues, list):
        issues = []
    open_blocking = [issue for issue in issues if isinstance(issue, dict) and is_open_blocking(issue)]
    return {
        "passes_gate": len(open_blocking) == 0,
        "open_blocking_issue_count": len(open_blocking),
        "open_blocking_issue_ids": [str(issue.get("id", "unknown")) for issue in open_blocking],
    }


def cmd_inspect_validation(args: argparse.Namespace) -> None:
    payload = read_json(Path(args.validation_json))
    print(json.dumps(inspect_validation_payload(payload), indent=2, sort_keys=True))


def producer_initial_prompt(symbol: str, run_dir: str) -> str:
    return "\n".join(
        [
            f"$market-research-full researcher {symbol}",
            "",
            "Run the market-research-full researcher workflow in this fresh Codex context.",
            f"Use the deterministic producer first: `python3 market-research-full/shared/scripts/deterministic_research_collector.py fetch {symbol} --data-dir ./data --reports-dir ./reports --as-of YYYY-MM-DD`.",
            f"Use `{run_dir}` for runtime notes, prompts, and logs. Write final report and validation artifacts under `reports/{symbol}/YYYY-MM-DD/`.",
            "As you run the skill, identify any market-research skill issues separately.",
            f"Write producer skill issues to `{run_dir}/{symbol}-market-research-skill-issues.md`.",
            f"Report the exact generated `reports/{symbol}/YYYY-MM-DD/` artifact path.",
            "Use public/free APIs, cache raw responses, preserve provenance, and disclose data gaps.",
            "",
        ]
    )


def default_validation_output_dir(symbol: str, run_dir: str) -> str:
    path = Path(run_dir)
    if "runtime" not in path.parts:
        return run_dir
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", path.name):
        return f"reports/{symbol}/{path.name}"
    return f"reports/{symbol}/YYYY-MM-DD"


def validator_prompt(symbol: str, run_dir: str, validation_output_dir: str | None = None) -> str:
    output_dir = validation_output_dir or default_validation_output_dir(symbol, run_dir)
    return "\n".join(
        [
            f"$market-research-full verifier {run_dir}",
            "",
            "Run the market-research-full verifier workflow in this fresh Codex context.",
            f"Validate the input artifacts in `{run_dir}`.",
            "Record validator skill issues separately.",
            f"Write validator skill issues to `{output_dir}/{symbol}-validator-skill-issues.md`.",
            f"Write validation markdown and JSON artifacts under `{output_dir}`.",
            "",
        ]
    )


def remediation_prompt(symbol: str, run_dir: str) -> str:
    return "\n".join(
        [
            f"The validator found blocking issues in `{run_dir}`.",
            "",
            "Fix only open critical/moderate issues reported by the validation markdown/JSON.",
            "Verify each finding against frozen artifacts before editing.",
            "Update affected report, context, source registry, and manifest artifacts consistently.",
            f"Append any market-research skill improvements to `{run_dir}/{symbol}-market-research-skill-issues.md`.",
            "Do not delete validator outputs.",
            "",
        ]
    )


def cmd_write_prompts(args: argparse.Namespace) -> None:
    symbol = normalize_symbol(args.symbol)
    run_dir = args.run_dir or f"runtime/{symbol}"
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = {
        "producer_initial_prompt": out / f"{symbol}-producer-initial.md",
        "validator_prompt": out / f"{symbol}-validator.md",
        "producer_remediation_prompt": out / f"{symbol}-producer-remediation.md",
    }
    paths["producer_initial_prompt"].write_text(producer_initial_prompt(symbol, run_dir), encoding="utf-8")
    paths["validator_prompt"].write_text(validator_prompt(symbol, run_dir), encoding="utf-8")
    paths["producer_remediation_prompt"].write_text(remediation_prompt(symbol, run_dir), encoding="utf-8")
    print(json.dumps({key: str(path) for key, path in paths.items()}, indent=2, sort_keys=True))


def latest_validation_for_symbol(symbol_dir: Path, reports_symbol_dir: Path | None = None) -> Path | None:
    candidates = sorted(symbol_dir.glob("iteration-*/validation.json"))
    if not candidates:
        candidates = sorted(symbol_dir.glob("**/*-validation.json")) + sorted(symbol_dir.glob("**/*-validation-scaffold.json"))
    if reports_symbol_dir and reports_symbol_dir.exists():
        candidates.extend(sorted(reports_symbol_dir.glob("**/*-validation.json")))
        candidates.extend(sorted(reports_symbol_dir.glob("**/*-validation-scaffold.json")))
    return candidates[-1] if candidates else None


def collect_skill_issue_files(root: Path) -> list[str]:
    files = sorted(root.glob("**/*skill-issues.md"))
    return [str(path) for path in files]


def collect_feedback(root: Path) -> dict[str, Any]:
    if not root.exists():
        die(f"Run root not found: {root}")
    notes = ensure_improvement_note_files(root)
    issue_files = collect_skill_issue_files(root)
    loop_file = root / "loop-skill-issues.md"
    if loop_file.exists() and str(loop_file) not in issue_files:
        issue_files.append(str(loop_file))
    issue_files = sorted(issue_files)
    operator_notes = root / "operator-notes.md"
    return {
        "run_root": str(root),
        "issue_files": issue_files,
        "issue_file_count": len(issue_files),
        "operator_notes": str(operator_notes),
        "output_markdown": str(root / "skill-improvement-feedback.md"),
        "output_json": str(root / "skill-improvement-feedback.json"),
        "note_files": notes,
    }


def cmd_collect_feedback(args: argparse.Namespace) -> None:
    root = Path(args.run_root)
    feedback = collect_feedback(root)
    issue_sections = []
    for file_name in feedback["issue_files"]:
        path = Path(file_name)
        issue_sections.extend(
            [
                f"## {path.relative_to(root) if path.is_relative_to(root) else path}",
                "",
                path.read_text(encoding="utf-8").strip(),
                "",
            ]
        )
    operator_notes = Path(feedback["operator_notes"]).read_text(encoding="utf-8").strip()
    markdown = "\n".join(
        [
            "# Manual Skill Improvement Package",
            "",
            f"Run root: `{root}`",
            "",
            "Use this package after enough qualified feedback has accumulated. Do not automatically edit skills from one run; review recurring issues, decide scope, then make a separate explicit skill-improvement pass.",
            "",
            "## Operator Notes",
            "",
            operator_notes,
            "",
            "## Collected Skill Issue Files",
            "",
            *issue_sections,
        ]
    ).rstrip() + "\n"
    markdown_path = root / "skill-improvement-feedback.md"
    json_path = root / "skill-improvement-feedback.json"
    markdown_path.write_text(markdown, encoding="utf-8")
    write_json(json_path, feedback)
    print(json.dumps(feedback, indent=2, sort_keys=True))


def summarize_root(root: Path) -> dict[str, Any]:
    if not root.exists():
        die(f"Run root not found: {root}")
    reports_root = reports_root_for_loop(root)
    passed: list[str] = []
    failed: list[str] = []
    unresolved: dict[str, list[str]] = {}
    for symbol_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        validation_path = latest_validation_for_symbol(symbol_dir, reports_root / symbol_dir.name)
        if validation_path is None:
            failed.append(symbol_dir.name)
            unresolved[symbol_dir.name] = ["missing-validation-json"]
            continue
        gate = inspect_validation_payload(read_json(validation_path))
        if gate["passes_gate"]:
            passed.append(symbol_dir.name)
        else:
            failed.append(symbol_dir.name)
            unresolved[symbol_dir.name] = gate["open_blocking_issue_ids"]
    return {
        "symbols_total": len(passed) + len(failed),
        "passed": passed,
        "failed": failed,
        "unresolved_blocking_issues": unresolved,
        "skill_issue_files": collect_skill_issue_files(root),
        "improvement_notes": ensure_improvement_note_files(root),
    }


def cmd_summarize(args: argparse.Namespace) -> None:
    print(json.dumps(summarize_root(Path(args.run_root)), indent=2, sort_keys=True))


def cmd_init_batch(args: argparse.Namespace) -> None:
    symbols = [normalize_symbol(symbol) for symbol in args.symbols]
    args.as_of = args.as_of or date.today().isoformat()
    root = Path(args.run_root)
    root.mkdir(parents=True, exist_ok=True)
    improvement_notes = ensure_improvement_note_files(root)
    config = {
        "symbols": symbols,
        "as_of": args.as_of,
        "max_remediation_loops": args.max_remediation_loops,
        "pass_gate": {"open_critical": 0, "open_moderate": 0},
        "fresh_context_required": True,
    }
    write_json(root / "research-loop-config.json", config)
    prompt_root = root / "prompts"
    prompt_paths = {}
    for symbol in symbols:
        symbol_run_dir = f"{root}/{symbol}/{args.as_of}"
        out = prompt_root / symbol
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{symbol}-producer-initial.md").write_text(producer_initial_prompt(symbol, symbol_run_dir), encoding="utf-8")
        (out / f"{symbol}-validator.md").write_text(validator_prompt(symbol, symbol_run_dir), encoding="utf-8")
        (out / f"{symbol}-producer-remediation.md").write_text(remediation_prompt(symbol, symbol_run_dir), encoding="utf-8")
        prompt_paths[symbol] = str(out)
    print(json.dumps({"run_root": str(root), "config": str(root / "research-loop-config.json"), "prompt_dirs": prompt_paths, "improvement_notes": improvement_notes}, indent=2, sort_keys=True))


def render_command(template: str, *, prompt_file: Path, symbol: str, run_dir: Path, iteration_dir: Path, validation_output_dir: Path | None = None) -> str:
    validation_output_dir = validation_output_dir or run_dir
    replacements = {
        "{prompt_file}": str(prompt_file),
        "{symbol}": symbol,
        "{run_dir}": str(run_dir),
        "{iteration_dir}": str(iteration_dir),
        "{validation_output_dir}": str(validation_output_dir),
        "{cwd}": shlex.quote(str(Path.cwd())),
    }
    rendered = template
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, value)
    return rendered.replace("{{", "{").replace("}}", "}")


def run_shell_command(command: str, log_path: Path, *, timeout_seconds: int | None = None) -> CommandResult:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    timed_out = False
    try:
        result = subprocess.run(
            command,
            shell=True,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
        returncode = result.returncode
        stdout = result.stdout
        stderr = result.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        returncode = 124
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
    log_path.write_text(
        "\n".join(
            [
                f"$ {command}",
                f"exit_code={returncode}",
                f"timed_out={timed_out}",
                f"timeout_seconds={timeout_seconds}",
                "",
                "## stdout",
                stdout,
                "",
                "## stderr",
                stderr,
            ]
        ),
        encoding="utf-8",
    )
    return CommandResult(returncode=returncode, timed_out=timed_out)


def deterministic_bundle_exists(path: Path) -> bool:
    return all(
        (path / name).exists()
        for name in ["research_input_pack.md", "manifest.json", "source_manifest.json", "gaps.json", "normalized"]
    )


def reports_root_for_loop(root: Path) -> Path:
    for parent in (root, *root.parents):
        if parent.name == "runtime":
            return parent.parent / "reports"
    return root.parent / "reports"


def report_date_for_artifact(artifact_run_dir: Path, fallback_as_of: str) -> str:
    return artifact_run_dir.name if re.fullmatch(r"\d{4}-\d{2}-\d{2}", artifact_run_dir.name) else fallback_as_of


def validation_output_dir_for_artifact(root: Path, symbol: str, artifact_run_dir: Path, fallback_as_of: str) -> Path:
    return reports_root_for_loop(root) / symbol / report_date_for_artifact(artifact_run_dir, fallback_as_of)


def canonical_data_symbol_dirs(run_dir: Path, symbol: str) -> list[Path]:
    candidates = [Path.cwd() / "data" / symbol]
    for parent in (run_dir, *run_dir.parents):
        if parent.name == "runtime":
            candidates.append(parent.parent / "data" / symbol)
        candidates.append(parent / "data" / symbol)
    seen: set[Path] = set()
    out: list[Path] = []
    for path in candidates:
        resolved = path.resolve(strict=False)
        if resolved not in seen:
            out.append(path)
            seen.add(resolved)
    return out


def latest_producer_run_dir(run_dir: Path, symbol: str, *, modified_since: float | None = None) -> Path | None:
    candidates: list[Path] = []
    if (run_dir / f"{symbol}-research.md").exists() and (run_dir / f"{symbol}-research.json").exists():
        candidates.append(run_dir)
    for data_symbol_dir in canonical_data_symbol_dirs(run_dir, symbol):
        if deterministic_bundle_exists(data_symbol_dir):
            candidates.append(data_symbol_dir)
        if data_symbol_dir.exists():
            candidates.extend(path for path in data_symbol_dir.iterdir() if path.is_dir() and deterministic_bundle_exists(path))
    if modified_since is not None:
        candidates = [path for path in candidates if path.stat().st_mtime >= modified_since]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def validation_candidates(run_dir: Path, symbol: str) -> list[Path]:
    names = [
        run_dir / f"{symbol}-validation.json",
        run_dir / f"{symbol}-validation-scaffold.json",
    ]
    globbed = sorted(run_dir.glob("*-validation.json")) + sorted(run_dir.glob("*-validation-scaffold.json"))
    seen: set[Path] = set()
    out: list[Path] = []
    for path in names + globbed:
        if path.exists() and path not in seen:
            out.append(path)
            seen.add(path)
    return out


def latest_validation_in_run_dir(run_dir: Path, symbol: str) -> Path | None:
    candidates = validation_candidates(run_dir, symbol)
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def write_iteration_prompts(symbol: str, run_dir: Path, iteration_dir: Path, remediation: bool) -> dict[str, Path]:
    iteration_dir.mkdir(parents=True, exist_ok=True)
    prompts = {
        "producer": iteration_dir / ("producer-remediation.prompt.md" if remediation else "producer-initial.prompt.md"),
        "validator": iteration_dir / "validator.prompt.md",
    }
    prompts["producer"].write_text(
        remediation_prompt(symbol, str(run_dir)) if remediation else producer_initial_prompt(symbol, str(run_dir)),
        encoding="utf-8",
    )
    prompts["validator"].write_text(validator_prompt(symbol, str(run_dir)), encoding="utf-8")
    return prompts


def execute_symbol_loop(args: argparse.Namespace, symbol: str) -> dict[str, Any]:
    root = Path(args.run_root)
    run_dir = root / symbol / args.as_of
    symbol_dir = root / symbol / args.as_of
    max_loops = args.max_remediation_loops
    if args.dry_run:
        iteration_dir = symbol_dir / "iteration-01"
        prompts = write_iteration_prompts(symbol, run_dir, iteration_dir, remediation=False)
        commands = {
            "producer": render_command(args.producer_command, prompt_file=prompts["producer"], symbol=symbol, run_dir=run_dir, iteration_dir=iteration_dir),
            "validator": render_command(args.validator_command, prompt_file=prompts["validator"], symbol=symbol, run_dir=run_dir, iteration_dir=iteration_dir),
        }
        if args.remediation_command:
            commands["remediation"] = render_command(args.remediation_command, prompt_file=iteration_dir / "producer-remediation.prompt.md", symbol=symbol, run_dir=run_dir, iteration_dir=iteration_dir)
        write_json(iteration_dir / "commands.json", commands)
        return {"status": "planned", "iterations": 1, "run_dir": str(run_dir)}

    status = "failed"
    blocking_ids: list[str] = []
    validation_path: Path | None = None
    for iteration in range(1, max_loops + 2):
        remediation = iteration > 1
        iteration_dir = symbol_dir / f"iteration-{iteration:02d}" if not remediation else symbol_dir / f"iteration-{iteration:02d}-remediation"
        prompts = write_iteration_prompts(symbol, run_dir, iteration_dir, remediation=remediation)
        producer_template = args.remediation_command if remediation else args.producer_command
        if not producer_template:
            die("Missing remediation command template.")
        if remediation:
            command_run_dir = latest_producer_run_dir(run_dir, symbol) or run_dir
        else:
            command_run_dir = run_dir
        prompts["producer"].write_text(
            remediation_prompt(symbol, str(command_run_dir)) if remediation else producer_initial_prompt(symbol, str(run_dir)),
            encoding="utf-8",
        )
        commands = {
            "producer": render_command(producer_template, prompt_file=prompts["producer"], symbol=symbol, run_dir=command_run_dir, iteration_dir=iteration_dir),
        }
        write_json(iteration_dir / "commands.json", commands)
        producer_started_at = time.time()
        producer_result = run_shell_command(
            commands["producer"],
            iteration_dir / "producer.log",
            timeout_seconds=args.command_timeout_seconds,
        )
        if producer_result.returncode == 0:
            artifact_run_dir = latest_producer_run_dir(run_dir, symbol)
        else:
            artifact_run_dir = latest_producer_run_dir(run_dir, symbol, modified_since=producer_started_at)
        producer_complete = artifact_run_dir is not None
        if not producer_complete:
            return {
                "status": "producer_failed",
                "iterations": iteration,
                "run_dir": str(run_dir),
                "exit_code": producer_result.returncode,
                "timed_out": producer_result.timed_out,
            }
        effective_run_dir = artifact_run_dir
        validation_output_dir = (
            validation_output_dir_for_artifact(root, symbol, effective_run_dir, args.as_of)
            if deterministic_bundle_exists(effective_run_dir)
            else effective_run_dir
        )
        prompts["validator"].write_text(validator_prompt(symbol, str(effective_run_dir), str(validation_output_dir)), encoding="utf-8")
        commands["validator"] = render_command(
            args.validator_command,
            prompt_file=prompts["validator"],
            symbol=symbol,
            run_dir=effective_run_dir,
            iteration_dir=iteration_dir,
            validation_output_dir=validation_output_dir,
        )
        write_json(iteration_dir / "commands.json", commands)
        validator_result = run_shell_command(
            commands["validator"],
            iteration_dir / "validator.log",
            timeout_seconds=args.command_timeout_seconds,
        )
        validation_path = latest_validation_in_run_dir(validation_output_dir, symbol)
        validator_complete = validator_result.returncode == 0 or validation_path is not None
        if not validator_complete:
            return {
                "status": "validator_failed",
                "iterations": iteration,
                "run_dir": str(run_dir),
                "exit_code": validator_result.returncode,
                "timed_out": validator_result.timed_out,
            }
        if validation_path is None:
            return {"status": "missing_validation", "iterations": iteration, "run_dir": str(run_dir)}
        gate = inspect_validation_payload(read_json(validation_path))
        blocking_ids = gate["open_blocking_issue_ids"]
        if gate["passes_gate"]:
            status = "passed"
            break
        if iteration > max_loops:
            status = "failed_blocking_issues"
            break
    return {
        "status": status,
        "iterations": iteration,
        "run_dir": str(run_dir),
        "artifact_run_dir": str(latest_producer_run_dir(run_dir, symbol) or run_dir),
        "validation_json": str(validation_path) if validation_path else None,
        "open_blocking_issue_ids": blocking_ids,
    }


def cmd_run_batch(args: argparse.Namespace) -> None:
    args.producer_command = args.producer_command or DEFAULT_CODEX_COMMAND
    args.validator_command = args.validator_command or DEFAULT_CODEX_COMMAND
    args.remediation_command = args.remediation_command or DEFAULT_CODEX_COMMAND
    args.as_of = args.as_of or date.today().isoformat()
    symbols = [normalize_symbol(symbol) for symbol in args.symbols]
    root = Path(args.run_root)
    root.mkdir(parents=True, exist_ok=True)
    improvement_notes = ensure_improvement_note_files(root)
    results = {symbol: execute_symbol_loop(args, symbol) for symbol in symbols}
    summary = {
        "dry_run": args.dry_run,
        "as_of": args.as_of,
        "run_root": str(root),
        "symbols": results,
        "improvement_notes": improvement_notes,
    }
    write_json(root / "research-loop-summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Orchestrate market-research-full researcher and verifier artifacts.")
    sub = parser.add_subparsers(dest="command", required=True)

    inspect = sub.add_parser("inspect-validation", help="Report whether validation JSON passes the no critical/moderate gate.")
    inspect.add_argument("validation_json")
    inspect.set_defaults(func=cmd_inspect_validation)

    prompts = sub.add_parser("write-prompts", help="Write producer, validator, and remediation prompts for one symbol.")
    prompts.add_argument("symbol")
    prompts.add_argument("--run-dir")
    prompts.add_argument("--output-dir", required=True)
    prompts.set_defaults(func=cmd_write_prompts)

    summarize = sub.add_parser("summarize", help="Summarize final pass/fail state for a loop run root.")
    summarize.add_argument("run_root")
    summarize.set_defaults(func=cmd_summarize)

    feedback = sub.add_parser("collect-feedback", help="Collect run skill issue notes for a manual improvement pass.")
    feedback.add_argument("run_root")
    feedback.set_defaults(func=cmd_collect_feedback)

    init_batch = sub.add_parser("init-batch", help="Create batch config and prompt files for symbols.")
    init_batch.add_argument("symbols", nargs="+")
    init_batch.add_argument("--run-root", required=True)
    init_batch.add_argument("--as-of")
    init_batch.add_argument("--max-remediation-loops", type=int, default=3)
    init_batch.set_defaults(func=cmd_init_batch)

    run_batch = sub.add_parser("run-batch", help="Run producer/validator/remediation subprocess loop for symbols.")
    run_batch.add_argument("symbols", nargs="+")
    run_batch.add_argument("--run-root", required=True)
    run_batch.add_argument("--as-of")
    run_batch.add_argument("--producer-command", help="Shell template. Variables: {prompt_file}, {symbol}, {run_dir}, {iteration_dir}. Defaults to local codex exec.")
    run_batch.add_argument("--validator-command", help="Shell template. Variables: {prompt_file}, {symbol}, {run_dir}, {iteration_dir}. Defaults to local codex exec.")
    run_batch.add_argument("--remediation-command", help="Shell template used after blocking validation issues. Defaults to local codex exec.")
    run_batch.add_argument("--max-remediation-loops", type=int, default=3)
    run_batch.add_argument("--command-timeout-seconds", type=int, default=DEFAULT_COMMAND_TIMEOUT_SECONDS)
    run_batch.add_argument("--dry-run", action="store_true")
    run_batch.set_defaults(func=cmd_run_batch)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
