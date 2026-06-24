#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime
import json
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
import re

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared" / "scripts"))
from script_metrics import add_metrics_arg, start_timer, write_metrics

BLOCKING_SEVERITIES = {"critical", "moderate"}
OPEN_STATUSES = {"open", "new", "unresolved"}
SYMBOL_RE = re.compile(r"^(?=.*[A-Z0-9])[A-Z0-9][A-Z0-9.\-]{0,11}$")
AS_OF_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DEFAULT_CODEX_COMMAND = (
    "codex exec -C {cwd} "
    "--dangerously-bypass-approvals-and-sandbox - < {prompt_file}"
)
DEFAULT_COMMAND_TIMEOUT_SECONDS = 1800
DEFAULT_SELF_IMPROVEMENT_ROOT = Path("docs") / "superpowers" / "plans" / "self-improvement"
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

Add deferred feature requests here, for example browser/captcha handoff, alternate report formats, or new data sources.
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


def validate_as_of(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    if not AS_OF_RE.fullmatch(value):
        die(f"Invalid as-of {value!r}; expected YYYY-MM-DD.")
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        die(f"Invalid as-of {value!r}; expected a real calendar date.")
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
    metrics_start = getattr(args, "_metrics_start", start_timer())
    payload = read_json(Path(args.validation_json))
    result = inspect_validation_payload(payload)
    write_metrics(
        getattr(args, "metrics_json", None),
        start=metrics_start,
        script="research_loop.py",
        command=getattr(args, "command", "inspect-validation"),
        validation_json=args.validation_json,
        passes_gate=result["passes_gate"],
        open_blocking_issue_count=result["open_blocking_issue_count"],
    )
    print(json.dumps(result, indent=2, sort_keys=True))


def dated_layout_dir(prefix: str, symbol: str, run_dir: str) -> str:
    path = Path(run_dir)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", path.name):
        return f"{prefix}/{symbol}/{path.name}"
    return f"{prefix}/{symbol}/YYYY-MM-DD"


def report_dir_for_prompt(symbol: str, run_dir: str) -> str:
    path = Path(run_dir)
    if len(path.parts) >= 3 and path.parts[-3] == "reports" and path.parts[-2].upper() == symbol:
        return run_dir
    return dated_layout_dir("reports", symbol, run_dir)


def runtime_dir_for_prompt(symbol: str, run_dir: str) -> str:
    path = Path(run_dir)
    if len(path.parts) >= 3 and path.parts[-3] == "runtime" and path.parts[-2].upper() == symbol:
        return run_dir
    if len(path.parts) >= 3 and path.parts[-3] == "reports" and path.parts[-2].upper() == symbol:
        return str(path.parent.parent.parent / "runtime" / symbol / path.name)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", path.name) and path.parent.name.upper() == symbol and "reports" not in path.parts:
        return run_dir
    return dated_layout_dir("runtime", symbol, run_dir)


def producer_initial_prompt(symbol: str, run_dir: str) -> str:
    report_dir = report_dir_for_prompt(symbol, run_dir)
    runtime_dir = runtime_dir_for_prompt(symbol, run_dir)
    return "\n".join(
        [
            f"$market-research researcher {symbol}",
            "",
            "Run the market-research researcher workflow in this fresh Codex context.",
            f"Use deterministic evidence first: `python3 market-research/shared/scripts/deterministic_research_collector.py fetch {symbol} --data-dir ./data --reports-dir ./reports --as-of YYYY-MM-DD`.",
            f"Use the deterministic bundle under `data/{symbol}/YYYY-MM-DD/` as evidence.",
            f"Write final research markdown and JSON under `{report_dir}`.",
            f"Attempt best-effort PDF generation for the final markdown with `bash market-research/shared/scripts/md-to-pdf.sh {report_dir}/{symbol}-research.md`; continue if pandoc or xelatex is unavailable.",
            f"Use `{runtime_dir}` for transient runtime notes, prompts, logs, and issue files.",
            "As you run the skill, identify any market-research skill issues separately.",
            f"Write producer skill issues to `{runtime_dir}/{symbol}-market-research-issues.md`.",
            f"Report the exact generated `{report_dir}` artifact path.",
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
            f"$market-research verifier {run_dir}",
            "",
            "Run the market-research verifier workflow in this fresh Codex context.",
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
        candidates = sorted(symbol_dir.glob("**/*-validation.json"))
    if reports_symbol_dir and reports_symbol_dir.exists():
        candidates.extend(sorted(reports_symbol_dir.glob("**/*-validation.json")))
    return candidates[-1] if candidates else None


def collect_skill_issue_files(root: Path) -> list[str]:
    files = sorted(root.glob("**/*skill-issues.md")) + sorted(root.glob("**/*skill-issues.json"))
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


def self_improvement_runs_prompt(run_roots: list[Path], output_dir: Path) -> str:
    run_lines = []
    for root in run_roots:
        run_lines.extend(
            [
                f"- Run root: `{root}`",
                f"  - Summary: `{root / 'research-loop-summary.json'}`",
                f"  - Loop notes: `{root / 'loop-skill-issues.md'}`",
                f"  - Operator notes: `{root / 'operator-notes.md'}`",
            ]
        )
    return "\n".join(
        [
            "$superpowers",
            "",
            "Run a self-improvement review for completed market-research batches in this Codex session.",
            "",
            "Goal: analyze the listed runs, their reports, validation artifacts, skill issue notes, prior plans/specs, and recent code changes. Write improvement ideas and an implementation plan. Do not edit production skill files in this pass.",
            "",
            "Inputs to inspect:",
            *run_lines,
            "- Existing plans/specs: `docs/superpowers/plans`, `docs/`, `AGENTS.md`, and `README.md`",
            "- Recent repository changes: `git status --short` and relevant `git diff`/`git log` output",
            "",
            "Review questions:",
            "- Did the researcher use all useful deterministic data, especially fields marked required or review in `deterministic_data_usage.json`?",
            "- Did reports omit material investor-relevant facts, risks, source limits, or data gaps?",
            "- Evaluate investor-grade reporting/memo quality. Does the report read like an investor memo rather than a deterministic-data recital or citation-heavy audit trail?",
            "- Evaluate the `Bottom Line` as an executive summary: it should introduce the company/security, what it does, market value or valuation range, core upside, main risks, and monitoring questions before judging valuation.",
            "- Check whether routine data-vendor names, provider mechanics, local paths, deterministic artifacts, manifests, raw/normalized paths, or cache details leaked into the main investment narrative. The main body should state the data, range, conflict, and investment implication; vendor attribution belongs in `Data Issues And Discrepancies`, `Sources And Evidence`, sidecars, or validation artifacts.",
            "- Check whether `Key Facts` is an at-a-glance table or similarly consumable snapshot without internal provenance references.",
            "- Evaluate `Business Profile` and business-model depth. The report should explain the product, technology, customers, who pays, revenue model, acquisition contribution, and demand drivers in plain language; require targeted procedural research when deterministic data leaves these unclear.",
            "- Evaluate `Market Snapshot And Technical Analysis`: market data should be presented as a snapshot plus actual analysis, including trend, moving averages, volume, volatility, drawdown, support/resistance, and technical interpretation when price history exists.",
            "- Confirm financials and valuation are organized for investor consumption with tables or concise snapshots plus analysis, not citation-heavy paragraphs or provider-conflict narration.",
            "- Confirm company/security risks stay in `Risks And Invalidation Points`; research/data-quality issues should be moved to `Data Issues And Discrepancies` near the bottom.",
            "- Did deterministic coverage support synthesis and judgment, or did it crowd out thesis, materiality, variant view, risks, and monitoring triggers?",
            "- Preserve `reports/` as final product and `runtime/` as intermediate work product. Do not recommend bundling runtime artifacts into reports unless the final investor deliverable itself needs a specific appendix or reference artifact.",
            "- Evaluate field-level freshness: which fields required a fresh/latest-available query, which durable filed/source-dated evidence could be reused, and whether missing or stale data changed investor interpretation.",
            "- Do not recommend main-body cache mechanics disclosure unless stale or unavailable data changes investor interpretation. Cache/provider mechanics belong in references, appendices, sidecars, or validation artifacts.",
            "- Did validator/remediation behavior surface the right problems with enough specificity?",
            "- Which recurring failures should become deterministic checks, prompt requirements, helper scripts, or tests?",
            "",
            "Write outputs under:",
            f"- `{output_dir / 'self-improvement-ideas.md'}`",
            f"- `{output_dir / 'self-improvement-plan.md'}`",
            f"- `{output_dir / 'self-improvement.json'}`",
            "",
            "The plan should use superpowers planning style: concrete phases, files to change, tests to add, verification commands, and explicit risks. Keep recommendations evidence-based and cite local artifact paths.",
            "",
        ]
    )


def timestamp_slug() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S-%f")


def cmd_self_improve(args: argparse.Namespace) -> None:
    run_roots = [Path(path) for path in args.run_roots]
    for root in run_roots:
        if not root.exists() or not root.is_dir():
            die(f"Run root not found: {root}")
    output_root = Path(args.output_root) if args.output_root else DEFAULT_SELF_IMPROVEMENT_ROOT
    output_dir = output_root / timestamp_slug()
    output_dir.mkdir(parents=True, exist_ok=False)
    prompt_path = output_dir / "self-improvement.md"
    prompt_path.write_text(self_improvement_runs_prompt(run_roots, output_dir), encoding="utf-8")
    print(
        json.dumps(
            {
                "prompt": str(prompt_path),
                "output_dir": str(output_dir),
                "run_roots": [str(root) for root in run_roots],
            },
            indent=2,
            sort_keys=True,
        )
    )


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
    args.as_of = validate_as_of(args.as_of or date.today().isoformat())
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
        "{prompt_file}": shlex.quote(str(prompt_file)),
        "{symbol}": symbol,
        "{run_dir}": shlex.quote(str(run_dir)),
        "{iteration_dir}": shlex.quote(str(iteration_dir)),
        "{validation_output_dir}": shlex.quote(str(validation_output_dir)),
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


def final_report_exists(path: Path, symbol: str) -> bool:
    return (path / f"{symbol}-research.md").exists() and (path / f"{symbol}-research.json").exists()


def artifact_mtime(path: Path, symbol: str) -> float:
    files = [path]
    if final_report_exists(path, symbol):
        files.extend([path / f"{symbol}-research.md", path / f"{symbol}-research.json"])
    if deterministic_bundle_exists(path):
        files.extend(
            [
                path / "research_input_pack.md",
                path / "manifest.json",
                path / "source_manifest.json",
                path / "gaps.json",
                path / "normalized",
            ]
        )
    return max(candidate.stat().st_mtime for candidate in files if candidate.exists())


def loop_root_for_run_dir(run_dir: Path, symbol: str) -> Path:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", run_dir.name) and run_dir.parent.name == symbol:
        return run_dir.parent.parent
    return run_dir


def reports_root_for_loop(root: Path) -> Path:
    return storage_base_for_loop(root) / "reports"


def data_root_for_loop(root: Path) -> Path:
    return storage_base_for_loop(root) / "data"


def storage_base_for_loop(root: Path) -> Path:
    if root.name == "runtime":
        return root.parent
    if root.parent.name == "runtime":
        return root.parent.parent
    return root.parent


def report_date_for_artifact(artifact_run_dir: Path, fallback_as_of: str) -> str:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", artifact_run_dir.name):
        return validate_as_of(artifact_run_dir.name) or artifact_run_dir.name
    return validate_as_of(fallback_as_of) or fallback_as_of


def validation_output_dir_for_artifact(root: Path, symbol: str, artifact_run_dir: Path, fallback_as_of: str) -> Path:
    return reports_root_for_loop(root) / symbol / report_date_for_artifact(artifact_run_dir, fallback_as_of)


def canonical_data_symbol_dirs(run_dir: Path, symbol: str) -> list[Path]:
    loop_root = loop_root_for_run_dir(run_dir, symbol)
    candidates = [data_root_for_loop(loop_root) / symbol]
    seen: set[Path] = set()
    out: list[Path] = []
    for path in candidates:
        resolved = path.resolve(strict=False)
        if resolved not in seen:
            out.append(path)
            seen.add(resolved)
    return out


def canonical_report_symbol_dirs(run_dir: Path, symbol: str) -> list[Path]:
    loop_root = loop_root_for_run_dir(run_dir, symbol)
    candidates = [reports_root_for_loop(loop_root) / symbol]
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
    for report_symbol_dir in canonical_report_symbol_dirs(run_dir, symbol):
        if report_symbol_dir.exists():
            candidates.extend(
                path
                for path in report_symbol_dir.iterdir()
                if path.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", path.name) and final_report_exists(path, symbol)
            )
    for data_symbol_dir in canonical_data_symbol_dirs(run_dir, symbol):
        if data_symbol_dir.exists():
            candidates.extend(
                path
                for path in data_symbol_dir.iterdir()
                if path.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", path.name) and deterministic_bundle_exists(path)
            )
    if modified_since is not None:
        candidates = [path for path in candidates if artifact_mtime(path, symbol) >= modified_since]
    if not candidates:
        return None
    return max(candidates, key=lambda path: artifact_mtime(path, symbol))


def validation_candidates(run_dir: Path, symbol: str) -> list[Path]:
    names = [
        run_dir / f"{symbol}-validation.json",
    ]
    globbed = sorted(run_dir.glob("*-validation.json"))
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
    as_of = validate_as_of(args.as_of) or date.today().isoformat()
    args.as_of = as_of
    run_dir = root / symbol / as_of
    symbol_dir = root / symbol / as_of
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
    args.as_of = validate_as_of(args.as_of or date.today().isoformat())
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
    summary_json = root / "research-loop-summary.json"
    write_json(summary_json, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Orchestrate market-research researcher and verifier artifacts.")
    sub = parser.add_subparsers(dest="command", required=True)

    inspect = sub.add_parser("inspect-validation", help="Report whether validation JSON passes the no critical/moderate gate.")
    inspect.add_argument("validation_json")
    add_metrics_arg(inspect)
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

    self_improve = sub.add_parser("self-improve", help="Write a central prompt-only self-improvement review for one or more batch run roots.")
    self_improve.add_argument("run_roots", nargs="+")
    self_improve.add_argument(
        "--output-root",
        help="Directory for self-improvement prompt runs. Defaults to docs/superpowers/plans/self-improvement.",
    )
    self_improve.set_defaults(func=cmd_self_improve)

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
    args._metrics_start = start_timer()
    args.func(args)


if __name__ == "__main__":
    main()
