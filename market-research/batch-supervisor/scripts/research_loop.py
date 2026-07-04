#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
import re

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared" / "scripts"))
import producer_self_check
from script_metrics import add_metrics_arg, start_timer, write_metrics
from script_utils import normalize_symbol, read_json, validate_as_of, write_json

BLOCKING_SEVERITIES = {"critical", "moderate"}
OPEN_STATUSES = {"open", "new", "unresolved"}
DEFAULT_CODEX_COMMAND = (
    "codex exec -C {cwd} "
    "--dangerously-bypass-approvals-and-sandbox - < {prompt_file}"
)
CONTROL_DIR_NAMES = {"prompts", "validation_scaffolds", "self-improvement", "logs"}
DEFAULT_CLAUDE_COMMAND = (
    "claude -p --dangerously-skip-permissions --no-session-persistence "
    "--output-format text < {prompt_file}"
)
DEFAULT_COMMANDS_BY_AGENT_CLI = {
    "codex": DEFAULT_CODEX_COMMAND,
    "claude": DEFAULT_CLAUDE_COMMAND,
}
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


RATE_LIMIT_SIGNATURES = [
    "session limit",
    "usage limit",
    "rate limit",
    "rate-limited",
    "quota exceeded",
    "quota exhausted",
]


def looks_rate_limited(*texts: str) -> bool:
    combined = " ".join(texts).lower()
    return any(signature in combined for signature in RATE_LIMIT_SIGNATURES)


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    timed_out: bool = False
    rate_limited: bool = False


def die(message: str, code: int = 2) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


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
    env_root = storage_root_from_env(prefix)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", path.name):
        return str((env_root or Path(prefix)) / symbol / path.name)
    return str((env_root or Path(prefix)) / symbol / "YYYY-MM-DD")


def report_dir_for_prompt(symbol: str, run_dir: str) -> str:
    path = Path(run_dir)
    if len(path.parts) >= 3 and path.parts[-3] == "reports" and path.parts[-2].upper() == symbol:
        return run_dir
    return dated_layout_dir("reports", symbol, run_dir)


def runtime_dir_for_prompt(symbol: str, run_dir: str) -> str:
    path = Path(run_dir)
    if path.name.upper() == symbol and "runtime" in path.parts:
        return run_dir
    if len(path.parts) >= 3 and path.parts[-3] == "runtime" and path.parts[-2].upper() == symbol:
        return run_dir
    if len(path.parts) >= 3 and path.parts[-3] == "reports" and path.parts[-2].upper() == symbol:
        runtime_root = storage_root_from_env("runtime") or path.parent.parent.parent / "runtime"
        return str(runtime_root / symbol / path.name)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", path.name) and path.parent.name.upper() == symbol and "reports" not in path.parts:
        return run_dir
    return dated_layout_dir("runtime", symbol, run_dir)


def data_dir_for_prompt(symbol: str, run_dir: str) -> str:
    return dated_layout_dir("data", symbol, run_dir)


def procedural_output_root_for_prompt(symbol: str, runtime_dir: str) -> str:
    path = Path(runtime_dir)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", path.name) and path.parent.name.upper() == symbol.upper():
        return str(path.parent.parent)
    if path.name.upper() == symbol.upper():
        return str(path.parent)
    return str(path.parent)


def skill_invocation_line(agent_cli: str, mode: str, target: str) -> str:
    if agent_cli == "claude":
        return f"/market-research {mode} {target}"
    return f"$market-research {mode} {target}"


def fresh_context_description(agent_cli: str) -> str:
    return "this fresh Codex context" if agent_cli != "claude" else "this fresh Claude Code session"


def producer_initial_prompt(symbol: str, run_dir: str, agent_cli: str = "codex") -> str:
    report_dir = report_dir_for_prompt(symbol, run_dir)
    runtime_dir = runtime_dir_for_prompt(symbol, run_dir)
    data_dir = data_dir_for_prompt(symbol, run_dir)
    procedural_output_root = procedural_output_root_for_prompt(symbol, runtime_dir)
    return "\n".join(
        [
            skill_invocation_line(agent_cli, "researcher", symbol),
            "",
            f"Run the market-research researcher workflow in {fresh_context_description(agent_cli)}.",
            f"Use deterministic evidence first: `python3 market-research/shared/scripts/deterministic_research_collector.py fetch {symbol} --data-dir ./data --reports-dir ./reports --as-of YYYY-MM-DD`.",
            f"Use the deterministic bundle under `{data_dir}/` as evidence.",
            f"Write final research markdown and JSON under `{report_dir}`.",
            "Use investor-facing language in main report sections; avoid workflow terms such as deterministic, bundle, artifact, normalized, raw, runtime, cache, provider, and local paths except in evidence or data-quality sections where auditability requires them.",
            "In the Bottom Line, introduce market value, net assets, or a valuation range before judging valuation or portfolio attractiveness.",
            "Do not include a Self-Check section in the final investor report.",
            "If report JSON material claims cite deterministic_* source IDs, ensure the final report directory source registry includes matching source entries or use source IDs already present in the final registry.",
            "For ETF reports with holdings, include `Portfolio Companies Snapshot`: cover all holdings when the ETF has 25 or fewer holdings; otherwise cover the top 25 by weight, with compact business, outlook, and price/technical context when available.",
            "For ETF risks, explicitly address authorized participant and creation/redemption mechanics, securities lending, premium/discount, tracking, tax/withholding, liquidity, closure/AUM, and concentration risks when material.",
            f"When running `procedural_source_helper.py` commands from the researcher workflow reference, pass `--output-root {procedural_output_root} --as-of YYYY-MM-DD` so procedural runtime artifacts (source_bundle/, run_manifest.json, sources.json, research_context.*) land under `{runtime_dir}` instead of the reference doc's literal `./runtime` example path.",
            f"Before verifier handoff, run `python3 market-research/shared/scripts/producer_self_check.py {report_dir} --data-dir {data_dir} --runtime-dir {runtime_dir} --fix-safe` and fix open critical/moderate self-check findings.",
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


def validator_prompt(
    symbol: str,
    run_dir: str,
    validation_output_dir: str | None = None,
    skill_issue_dir: str | None = None,
    agent_cli: str = "codex",
) -> str:
    output_dir = validation_output_dir or default_validation_output_dir(symbol, run_dir)
    issue_dir = skill_issue_dir or runtime_dir_for_prompt(symbol, run_dir)
    return "\n".join(
        [
            skill_invocation_line(agent_cli, "verifier", run_dir),
            "",
            f"Run the market-research verifier workflow in {fresh_context_description(agent_cli)}.",
            f"Validate the input artifacts in `{run_dir}`.",
            "Record validator skill issues separately.",
            f"Write validator skill issues to `{issue_dir}/{symbol}-validator-skill-issues.md`.",
            f"Write validation markdown and JSON artifacts under `{output_dir}`.",
            "",
        ]
    )


def remediation_prompt(symbol: str, run_dir: str, skill_issue_dir: str | None = None) -> str:
    issue_dir = skill_issue_dir or runtime_dir_for_prompt(symbol, run_dir)
    procedural_output_root = procedural_output_root_for_prompt(symbol, issue_dir)
    return "\n".join(
        [
            f"The validator or producer self-check found blocking issues in `{run_dir}`.",
            "",
            "Fix only open critical/moderate issues reported by the validation markdown/JSON.",
            "Verify each finding against frozen artifacts before editing.",
            "Update affected report, context, source registry, and manifest artifacts consistently.",
            f"If further `procedural_source_helper.py` capture is needed, pass `--output-root {procedural_output_root} --as-of YYYY-MM-DD` so runtime artifacts land under `{issue_dir}` rather than the reference doc's literal `./runtime` example path.",
            f"Append any market-research skill improvements to `{issue_dir}/{symbol}-market-research-skill-issues.md`.",
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
    paths["producer_initial_prompt"].write_text(producer_initial_prompt(symbol, run_dir, args.agent_cli), encoding="utf-8")
    paths["validator_prompt"].write_text(validator_prompt(symbol, run_dir, agent_cli=args.agent_cli), encoding="utf-8")
    paths["producer_remediation_prompt"].write_text(remediation_prompt(symbol, run_dir), encoding="utf-8")
    print(json.dumps({key: str(path) for key, path in paths.items()}, indent=2, sort_keys=True))


def latest_validation_for_symbol(symbol_dir: Path, reports_symbol_dir: Path | None = None) -> Path | None:
    candidates = sorted(symbol_dir.glob("iteration-*/validation.json"))
    if not candidates:
        candidates = sorted(symbol_dir.glob("**/*-validation.json"))
    if reports_symbol_dir and reports_symbol_dir.exists():
        candidates.extend(sorted(reports_symbol_dir.glob("**/*-validation.json")))
    return candidates[-1] if candidates else None


RESEARCHER_COMMENT_RE = re.compile(r"<@rea?searcher:\s*(.*?)>", re.IGNORECASE)


def collect_skill_issue_files(*roots: Path) -> list[str]:
    seen: set[Path] = set()
    files: list[Path] = []
    patterns = [
        "**/*skill-issues.md",
        "**/*skill-issues.json",
        "**/*market-research-issues.md",
        "**/*researcher-comments.md",
        "**/*researcher-comments.json",
    ]
    for root in roots:
        if not root.exists():
            continue
        for pattern in patterns:
            for path in sorted(root.glob(pattern)):
                resolved = path.resolve(strict=False)
                if resolved not in seen:
                    seen.add(resolved)
                    files.append(path)
    return [str(path) for path in sorted(files, key=lambda item: str(item))]


def summary_report_dirs(root: Path) -> list[Path]:
    summary_path = root / "research-loop-summary.json"
    if not summary_path.exists():
        return []
    try:
        summary = read_json(summary_path)
    except (OSError, json.JSONDecodeError):
        return []
    symbols = summary.get("symbols", {}) if isinstance(summary, dict) else {}
    if not isinstance(symbols, dict):
        return []
    dirs: list[Path] = []
    for result in symbols.values():
        if not isinstance(result, dict):
            continue
        for key in ["artifact_run_dir", "validation_json"]:
            value = result.get(key)
            if not isinstance(value, str) or not value:
                continue
            path = Path(value)
            dirs.append(path.parent if key == "validation_json" else path)
    return dirs


def inferred_report_dirs(root: Path) -> list[Path]:
    reports_root = reports_root_for_loop(root)
    if not reports_root.exists():
        return []
    dirs: list[Path] = []
    for symbol_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        report_symbol_dir = reports_root / symbol_dir.name
        if report_symbol_dir.exists():
            dirs.extend(path for path in sorted(report_symbol_dir.iterdir()) if path.is_dir())
    return dirs


def report_dirs_for_feedback(root: Path) -> list[Path]:
    seen: set[Path] = set()
    dirs: list[Path] = []
    for path in summary_report_dirs(root) + inferred_report_dirs(root):
        resolved = path.resolve(strict=False)
        if resolved not in seen and path.exists() and path.is_dir():
            seen.add(resolved)
            dirs.append(path)
    return dirs


def collect_researcher_comments(report_dirs: list[Path]) -> list[dict[str, Any]]:
    comments: list[dict[str, Any]] = []
    for report_dir in report_dirs:
        for report in sorted(report_dir.glob("*-research.md")):
            try:
                lines = report.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            for line_number, line in enumerate(lines, start=1):
                for match in RESEARCHER_COMMENT_RE.finditer(line):
                    comments.append(
                        {
                            "path": str(report),
                            "line": line_number,
                            "comment": match.group(1).strip(),
                            "line_text": line.strip(),
                        }
                    )
    return comments


def collect_supporting_artifacts(root: Path) -> list[str]:
    patterns = [
        "**/validation_scaffolds/*validation-scaffold.md",
        "**/validation_scaffolds/*validation-scaffold.json",
    ]
    artifacts: list[Path] = []
    seen: set[Path] = set()
    for pattern in patterns:
        for path in sorted(root.glob(pattern)):
            resolved = path.resolve(strict=False)
            if resolved not in seen:
                seen.add(resolved)
                artifacts.append(path)
    return [str(path) for path in sorted(artifacts, key=lambda item: str(item))]


def collect_feedback(root: Path) -> dict[str, Any]:
    if not root.exists():
        die(f"Run root not found: {root}")
    notes = ensure_improvement_note_files(root)
    report_dirs = report_dirs_for_feedback(root)
    issue_files = collect_skill_issue_files(root, *report_dirs)
    loop_file = root / "loop-skill-issues.md"
    if loop_file.exists() and str(loop_file) not in issue_files:
        issue_files.append(str(loop_file))
    issue_files = sorted(issue_files)
    operator_notes = root / "operator-notes.md"
    researcher_comments = collect_researcher_comments(report_dirs)
    supporting_artifacts = collect_supporting_artifacts(root)
    return {
        "run_root": str(root),
        "issue_files": issue_files,
        "issue_file_count": len(issue_files),
        "supporting_artifacts": supporting_artifacts,
        "supporting_artifact_count": len(supporting_artifacts),
        "report_dirs": [str(path) for path in report_dirs],
        "researcher_comments": researcher_comments,
        "researcher_comment_count": len(researcher_comments),
        "operator_notes": str(operator_notes),
        "output_markdown": str(root / "skill-improvement-feedback.md"),
        "output_json": str(root / "skill-improvement-feedback.json"),
        "note_files": notes,
    }


def write_feedback_package(root: Path) -> dict[str, Any]:
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
    comment_sections = []
    for item in feedback["researcher_comments"]:
        comment_sections.extend(
            [
                f"- `{item['path']}:{item['line']}`",
                f"  - Comment: {item['comment']}",
                f"  - Context: {item['line_text']}",
            ]
        )
    if not comment_sections:
        comment_sections.append("- None found.")
    supporting_artifact_sections = [f"- `{path}`" for path in feedback["supporting_artifacts"]]
    if not supporting_artifact_sections:
        supporting_artifact_sections.append("- None found.")
    operator_notes = Path(feedback["operator_notes"]).read_text(encoding="utf-8").strip()
    markdown = "\n".join(
        [
            "# Manual Skill Improvement Package",
            "",
            f"Run root: `{root}`",
            "",
            "Use this runtime package for self-improvement review. It consolidates useful feedback from runtime artifacts and final report-side issue/comment files without making the final `reports/` tree the primary self-improvement input.",
            "",
            "## Operator Notes",
            "",
            operator_notes,
            "",
            "## Report Directories Inspected",
            "",
            *[f"- `{path}`" for path in feedback["report_dirs"]],
            "",
            "## Researcher Inline Comments",
            "",
            *comment_sections,
            "",
            "## Supporting Self-Improvement Artifacts",
            "",
            *supporting_artifact_sections,
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
    return feedback


def cmd_collect_feedback(args: argparse.Namespace) -> None:
    root = Path(args.run_root)
    feedback = write_feedback_package(root)
    print(json.dumps(feedback, indent=2, sort_keys=True))


def self_improvement_runs_prompt(run_roots: list[Path], output_dir: Path, feedback_packages: list[Path] | None = None) -> str:
    feedback_packages = feedback_packages or []
    run_lines = []
    for index, root in enumerate(run_roots):
        run_lines.extend(
            [
                f"- Run root: `{root}`",
                f"  - Summary: `{root / 'research-loop-summary.json'}`",
                f"  - Loop notes: `{root / 'loop-skill-issues.md'}`",
                f"  - Operator notes: `{root / 'operator-notes.md'}`",
            ]
        )
        if index < len(feedback_packages):
            run_lines.append(f"  - Runtime self-improvement package: `{feedback_packages[index]}`")
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
            "- Treat each runtime self-improvement package as the canonical feedback input for report-side skill issues and inline `<@researcher: ...>` comments. Use final `reports/` files only when the runtime package points to them for context.",
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
    feedback_packages = [Path(write_feedback_package(root)["output_markdown"]) for root in run_roots]
    output_root = Path(args.output_root) if args.output_root else DEFAULT_SELF_IMPROVEMENT_ROOT
    output_dir = output_root / timestamp_slug()
    output_dir.mkdir(parents=True, exist_ok=False)
    prompt_path = output_dir / "self-improvement.md"
    prompt_path.write_text(self_improvement_runs_prompt(run_roots, output_dir, feedback_packages), encoding="utf-8")
    print(
        json.dumps(
            {
                "prompt": str(prompt_path),
                "output_dir": str(output_dir),
                "run_roots": [str(root) for root in run_roots],
                "feedback_packages": [str(path) for path in feedback_packages],
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
    for symbol_dir in summary_symbol_dirs(root):
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
        "feedback_package": feedback_package_summary(root),
    }


def cmd_summarize(args: argparse.Namespace) -> None:
    print(json.dumps(summarize_root(Path(args.run_root)), indent=2, sort_keys=True))


def feedback_package_summary(root: Path) -> dict[str, Any]:
    path = root / "skill-improvement-feedback.json"
    if not path.exists():
        return {"path": str(path), "exists": False}
    payload = read_json(path)
    stat = path.stat()
    return {
        "path": str(path),
        "exists": True,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "issue_file_count": payload.get("issue_file_count", 0) if isinstance(payload, dict) else 0,
        "researcher_comment_count": payload.get("researcher_comment_count", 0) if isinstance(payload, dict) else 0,
        "supporting_artifact_count": payload.get("supporting_artifact_count", 0) if isinstance(payload, dict) else 0,
    }


def storage_root_from_env(prefix: str) -> Path | None:
    env_by_prefix = {
        "data": "RESEARCH_DATA_DIR",
        "reports": "RESEARCH_REPORTS_DIR",
        "runtime": "RESEARCH_RUNTIME_DIR",
    }
    key = env_by_prefix.get(prefix)
    value = os.environ.get(key, "").strip() if key else ""
    return Path(value) if value else None


def config_symbols(root: Path) -> list[str]:
    config_path = root / "research-loop-config.json"
    if not config_path.exists():
        return []
    try:
        payload = read_json(config_path)
    except SystemExit:
        return []
    symbols = payload.get("symbols", []) if isinstance(payload, dict) else []
    out: list[str] = []
    for symbol in symbols:
        if isinstance(symbol, str) and re.fullmatch(r"(?=.*[A-Z0-9])[A-Z0-9][A-Z0-9.\-]{0,11}", symbol.upper()):
            out.append(symbol.upper())
    return sorted(dict.fromkeys(out))


def summary_symbol_dirs(root: Path) -> list[Path]:
    configured = config_symbols(root)
    if configured:
        return [root / symbol for symbol in configured]
    return [
        path
        for path in sorted(root.iterdir())
        if path.is_dir()
        and path.name not in CONTROL_DIR_NAMES
        and re.fullmatch(r"(?=.*[A-Z0-9])[A-Z0-9][A-Z0-9.\-]{0,11}", path.name.upper())
    ]


def default_child_command(agent_cli: str, *, dry_run: bool) -> str | None:
    default_command = DEFAULT_COMMANDS_BY_AGENT_CLI[agent_cli]
    if dry_run or shutil.which(agent_cli) is not None:
        return default_command
    return None


def missing_child_launcher_message(missing: list[str], agent_cli: str) -> str:
    missing_list = ", ".join(missing)
    return (
        f"Missing child launcher for {missing_list}: `{agent_cli}` is not on PATH. "
        "Pass explicit --producer-command/--validator-command/--remediation-command templates, "
        "or use the batch-supervisor agent-native workflow: write/init prompts, launch fresh child "
        "sessions with the current agent's subagent mechanism, then run self-check, validation, "
        "refresh-summary, and collect-feedback."
    )


def latest_validation_for_summary_result(result: dict[str, Any]) -> Path | None:
    candidates: list[Path] = []
    validation_json = result.get("validation_json")
    if isinstance(validation_json, str):
        candidates.append(Path(validation_json))
    artifact_run_dir = result.get("artifact_run_dir")
    if isinstance(artifact_run_dir, str):
        report_dir = Path(artifact_run_dir)
        symbol = report_dir.parent.name
        candidates.extend(validation_candidates(report_dir, symbol))
    existing = [path for path in candidates if path.exists() and path.name.endswith("-validation.json")]
    if not existing:
        return None
    return max(existing, key=lambda path: path.stat().st_mtime)


def cmd_refresh_summary(args: argparse.Namespace) -> None:
    root = Path(args.run_root)
    summary_path = root / "research-loop-summary.json"
    if not summary_path.exists():
        die(f"Summary not found: {summary_path}")
    summary = read_json(summary_path)
    symbols = summary.get("symbols", {}) if isinstance(summary, dict) else {}
    if not isinstance(symbols, dict):
        die(f"Summary has no symbols object: {summary_path}")
    for symbol, result in symbols.items():
        if not isinstance(result, dict):
            continue
        validation_path = latest_validation_for_summary_result(result)
        if validation_path is None:
            continue
        gate = inspect_validation_payload(read_json(validation_path))
        old_status = result.get("status")
        current_status = "passed" if gate["passes_gate"] else "failed_blocking_issues"
        if old_status != current_status and "historical_status" not in result:
            result["historical_status"] = old_status
        result["status"] = current_status
        result["validation_json"] = str(validation_path)
        result["open_blocking_issue_ids"] = gate["open_blocking_issue_ids"]
        result["post_loop_refresh"] = {
            "refreshed_at": datetime.now().isoformat(),
            "validation_json": str(validation_path),
            "previous_status": old_status,
        }
    write_json(summary_path, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


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
        (out / f"{symbol}-producer-initial.md").write_text(producer_initial_prompt(symbol, symbol_run_dir, args.agent_cli), encoding="utf-8")
        (out / f"{symbol}-validator.md").write_text(validator_prompt(symbol, symbol_run_dir, agent_cli=args.agent_cli), encoding="utf-8")
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
    return CommandResult(returncode=returncode, timed_out=timed_out, rate_limited=looks_rate_limited(stdout, stderr))


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
    env_root = storage_root_from_env("reports")
    if env_root:
        return env_root
    return storage_base_for_loop(root) / "reports"


def data_root_for_loop(root: Path) -> Path:
    env_root = storage_root_from_env("data")
    if env_root:
        return env_root
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


def sync_runtime_sources_to_report(runtime_dir: Path, artifact_run_dir: Path) -> None:
    if runtime_dir.resolve(strict=False) == artifact_run_dir.resolve(strict=False):
        return
    for name in ["run_manifest.json", "research_context.json", "research_context.md"]:
        source = runtime_dir / name
        if source.exists():
            artifact_run_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, artifact_run_dir / name)
    source_bundle = runtime_dir / "source_bundle"
    report_source_bundle = artifact_run_dir / "source_bundle"
    if source_bundle.exists() and source_bundle.is_dir():
        shutil.copytree(source_bundle, report_source_bundle, dirs_exist_ok=True)
    runtime_bundle_resolved = source_bundle.resolve(strict=False)

    def report_source_bundle_path(value: str) -> str | None:
        local_artifact = Path(value)
        relative: Path | None = None
        try:
            relative = local_artifact.resolve(strict=False).relative_to(runtime_bundle_resolved)
        except ValueError:
            parts = local_artifact.parts
            if "source_bundle" in parts:
                bundle_index = parts.index("source_bundle")
                relative = Path(*parts[bundle_index + 1 :])
        if relative is None:
            return None
        report_artifact = report_source_bundle / relative if relative.parts else report_source_bundle
        if report_artifact.exists():
            return str(report_artifact)
        return None

    def rewrite_json_source_bundle_paths(path: Path) -> None:
        if not path.exists():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        changed = False

        def rewrite_value(value: Any) -> Any:
            nonlocal changed
            if isinstance(value, dict):
                return {key: rewrite_value(child) for key, child in value.items()}
            if isinstance(value, list):
                return [rewrite_value(child) for child in value]
            if isinstance(value, str) and "source_bundle" in value:
                rewritten = report_source_bundle_path(value)
                if rewritten is not None:
                    changed = True
                    return rewritten
            return value

        rewritten_payload = rewrite_value(payload)
        if changed:
            write_json(path, rewritten_payload)

    sources = runtime_dir / "sources.json"
    if sources.exists() or (artifact_run_dir / "sources.json").exists():
        artifact_run_dir.mkdir(parents=True, exist_ok=True)
        payload = read_json(sources) if sources.exists() else {"sources": []}
        report_payload = read_json(artifact_run_dir / "sources.json") if (artifact_run_dir / "sources.json").exists() else {"sources": []}

        def rewrite_source_local_artifact(source: dict[str, Any]) -> None:
            if not isinstance(source.get("local_artifact"), str):
                return
            rewritten = report_source_bundle_path(source["local_artifact"])
            if rewritten is not None:
                source["local_artifact"] = rewritten

        for source in payload.get("sources", []) if isinstance(payload, dict) else []:
            if isinstance(source, dict):
                rewrite_source_local_artifact(source)
        for source in report_payload.get("sources", []) if isinstance(report_payload, dict) else []:
            if isinstance(source, dict):
                rewrite_source_local_artifact(source)
        merged: dict[str, dict[str, Any]] = {}
        for source in report_payload.get("sources", []) if isinstance(report_payload, dict) else []:
            if isinstance(source, dict):
                source_id = source.get("id") or source.get("source_id")
                if source_id:
                    merged[str(source_id)] = source
        for source in payload.get("sources", []) if isinstance(payload, dict) else []:
            if isinstance(source, dict):
                source_id = source.get("id") or source.get("source_id")
                if source_id and str(source_id) not in merged:
                    merged[str(source_id)] = source
        output_payload = report_payload if isinstance(report_payload, dict) else {}
        output_payload["sources"] = list(merged.values())
        write_json(artifact_run_dir / "sources.json", output_payload)
    json_sidecars = [
        artifact_run_dir / "run_manifest.json",
        artifact_run_dir / "research_context.json",
        *sorted(artifact_run_dir.glob("*-research.json")),
    ]
    if report_source_bundle.exists():
        json_sidecars.extend(sorted(report_source_bundle.glob("*.json")))
    for json_path in json_sidecars:
        rewrite_json_source_bundle_paths(json_path)
    for report_md in sorted(artifact_run_dir.glob("*-research.md")):
        rewrite_markdown_source_bundle_paths(report_md)


def rewrite_markdown_source_bundle_paths(report_md: Path) -> list[dict[str, str]]:
    text = report_md.read_text(encoding="utf-8")
    report_bundle = report_md.parent / "source_bundle"
    if not report_bundle.exists():
        return []
    replacements: list[dict[str, str]] = []
    rewritten_lines: list[str] = []
    in_evidence_section = False
    pattern = re.compile(r"(?P<path>[^\s|`)]*runtime/[^\s|`)]*/source_bundle/(?P<relative>[^\s|`)]+))")
    for line in text.splitlines():
        if line.startswith("## "):
            heading = line[3:].strip().lower()
            in_evidence_section = (
                "sources" in heading
                or "evidence" in heading
                or "appendix" in heading
                or "data issues" in heading
                or "discrepanc" in heading
            )
        if in_evidence_section and "runtime/" in line and "/source_bundle/" in line:
            def replace_match(match: re.Match[str]) -> str:
                relative_text = match.group("relative")
                trailing = ""
                while relative_text and relative_text[-1] in ".,;:":
                    trailing = relative_text[-1] + trailing
                    relative_text = relative_text[:-1]
                relative_artifact = Path(relative_text)
                report_artifact = report_bundle / relative_artifact
                if not report_artifact.exists():
                    report_artifact = report_bundle / relative_artifact.name
                if report_artifact.exists():
                    replacement = str(report_artifact) + trailing
                    replacements.append({"from": match.group(0), "to": replacement})
                    return replacement
                return match.group(0)

            line = pattern.sub(replace_match, line)
        rewritten_lines.append(line)
    if replacements:
        report_md.write_text("\n".join(rewritten_lines) + "\n", encoding="utf-8")
    return replacements


def data_dir_for_report(root: Path, symbol: str, artifact_run_dir: Path) -> Path | None:
    if not final_report_exists(artifact_run_dir, symbol):
        return None
    candidate = data_root_for_loop(root) / symbol / artifact_run_dir.name
    return candidate if deterministic_bundle_exists(candidate) else None


def run_producer_self_check(root: Path, symbol: str, report_dir: Path, runtime_dir: Path) -> dict[str, Any] | None:
    data_dir = data_dir_for_report(root, symbol, report_dir)
    if not final_report_exists(report_dir, symbol) or data_dir is None:
        return None
    return producer_self_check.run_self_check(report_dir, data_dir, runtime_dir, fix_safe=True)


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


def move_intermediate_validation_scaffolds(report_dir: Path, runtime_dir: Path, symbol: str) -> list[str]:
    if report_dir.resolve(strict=False) == runtime_dir.resolve(strict=False):
        return []
    canonical_stems = {f"{symbol}-validation-scaffold"}
    moved: list[str] = []
    destination = runtime_dir / "validation_scaffolds"
    for path in sorted(report_dir.glob(f"{symbol}-*validation-scaffold.*")):
        if path.stem in canonical_stems:
            continue
        destination.mkdir(parents=True, exist_ok=True)
        target = destination / path.name
        shutil.move(str(path), str(target))
        moved.append(str(target))
    return moved


def latest_validation_in_run_dir(run_dir: Path, symbol: str) -> Path | None:
    candidates = validation_candidates(run_dir, symbol)
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def write_iteration_prompts(symbol: str, run_dir: Path, iteration_dir: Path, remediation: bool, agent_cli: str = "codex") -> dict[str, Path]:
    iteration_dir.mkdir(parents=True, exist_ok=True)
    prompts = {
        "producer": iteration_dir / ("producer-remediation.prompt.md" if remediation else "producer-initial.prompt.md"),
        "validator": iteration_dir / "validator.prompt.md",
    }
    prompts["producer"].write_text(
        remediation_prompt(symbol, str(run_dir), str(run_dir)) if remediation else producer_initial_prompt(symbol, str(run_dir), agent_cli),
        encoding="utf-8",
    )
    prompts["validator"].write_text(validator_prompt(symbol, str(run_dir), agent_cli=agent_cli), encoding="utf-8")
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
        prompts = write_iteration_prompts(symbol, run_dir, iteration_dir, remediation=False, agent_cli=args.agent_cli)
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
        prompts = write_iteration_prompts(symbol, run_dir, iteration_dir, remediation=remediation, agent_cli=args.agent_cli)
        producer_template = args.remediation_command if remediation else args.producer_command
        if not producer_template:
            die("Missing remediation command template.")
        if remediation:
            command_run_dir = latest_producer_run_dir(run_dir, symbol) or run_dir
        else:
            command_run_dir = run_dir
        prompts["producer"].write_text(
            remediation_prompt(symbol, str(command_run_dir), str(run_dir)) if remediation else producer_initial_prompt(symbol, str(run_dir), args.agent_cli),
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
                "status": "producer_rate_limited" if producer_result.rate_limited else "producer_failed",
                "iterations": iteration,
                "run_dir": str(run_dir),
                "exit_code": producer_result.returncode,
                "timed_out": producer_result.timed_out,
            }
        effective_run_dir = artifact_run_dir
        sync_runtime_sources_to_report(run_dir, effective_run_dir)
        self_check = run_producer_self_check(root, symbol, effective_run_dir, run_dir)
        if self_check and self_check["blocking_issue_count"]:
            blocking_ids = [
                str(issue.get("id", "unknown"))
                for issue in self_check.get("issues", [])
                if is_open_blocking(issue)
            ]
            if iteration > max_loops:
                status = "failed_producer_self_check"
                validation_path = Path(self_check["runtime_dir"]) / "producer-self-check.json"
                break
            continue
        validation_output_dir = (
            validation_output_dir_for_artifact(root, symbol, effective_run_dir, args.as_of)
            if deterministic_bundle_exists(effective_run_dir)
            else effective_run_dir
        )
        prompts["validator"].write_text(
            validator_prompt(symbol, str(effective_run_dir), str(validation_output_dir), str(run_dir), agent_cli=args.agent_cli),
            encoding="utf-8",
        )
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
                "status": "validator_rate_limited" if validator_result.rate_limited else "validator_failed",
                "iterations": iteration,
                "run_dir": str(run_dir),
                "exit_code": validator_result.returncode,
                "timed_out": validator_result.timed_out,
            }
        if validation_path is None:
            return {"status": "missing_validation", "iterations": iteration, "run_dir": str(run_dir)}
        move_intermediate_validation_scaffolds(validation_output_dir, run_dir, symbol)
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


def existing_iteration_conflict(root: Path, symbol: str, as_of: str) -> Path | None:
    iteration_dir = root / symbol / as_of / "iteration-01"
    if (iteration_dir / "producer.log").exists() or (iteration_dir / "commands.json").exists():
        return iteration_dir
    return None


def cmd_run_batch(args: argparse.Namespace) -> None:
    default_command = default_child_command(args.agent_cli, dry_run=args.dry_run)
    missing_launchers: list[str] = []
    if not args.producer_command:
        if default_command is None:
            missing_launchers.append("producer")
        else:
            args.producer_command = default_command
    if not args.validator_command:
        if default_command is None:
            missing_launchers.append("validator")
        else:
            args.validator_command = default_command
    if not args.remediation_command:
        if default_command is not None:
            args.remediation_command = default_command
    if missing_launchers:
        die(missing_child_launcher_message(missing_launchers, args.agent_cli))
    args.as_of = validate_as_of(args.as_of or date.today().isoformat())
    symbols = [normalize_symbol(symbol) for symbol in args.symbols]
    root = Path(args.run_root)
    root.mkdir(parents=True, exist_ok=True)
    if not args.dry_run and not args.resume:
        for symbol in symbols:
            conflict = existing_iteration_conflict(root, symbol, args.as_of)
            if conflict is not None:
                die(
                    f"Refusing to overwrite existing run at {conflict}: this run-root/symbol/as-of already has "
                    "iteration-01 logs from a prior run-batch invocation. Use a new --run-root (for example, one "
                    "with a time-of-day suffix) for a fresh run, or pass --resume to continue writing into this "
                    "run-root."
                )
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
    prompts.add_argument("--agent-cli", choices=sorted(DEFAULT_COMMANDS_BY_AGENT_CLI), default="codex", help="Which coding-agent CLI convention to use for the skill-invocation line in generated prompts.")
    prompts.set_defaults(func=cmd_write_prompts)

    summarize = sub.add_parser("summarize", help="Summarize final pass/fail state for a loop run root.")
    summarize.add_argument("run_root")
    summarize.set_defaults(func=cmd_summarize)

    refresh = sub.add_parser("refresh-summary", help="Refresh persisted summary status from latest final validation JSON.")
    refresh.add_argument("run_root")
    refresh.set_defaults(func=cmd_refresh_summary)

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
    init_batch.add_argument("--agent-cli", choices=sorted(DEFAULT_COMMANDS_BY_AGENT_CLI), default="codex", help="Which coding-agent CLI convention to use for the skill-invocation line in generated prompts.")
    init_batch.set_defaults(func=cmd_init_batch)

    run_batch = sub.add_parser("run-batch", help="Run producer/validator/remediation subprocess loop for symbols.")
    run_batch.add_argument("symbols", nargs="+")
    run_batch.add_argument("--run-root", required=True)
    run_batch.add_argument("--as-of")
    run_batch.add_argument("--agent-cli", choices=sorted(DEFAULT_COMMANDS_BY_AGENT_CLI), default="codex", help="Which local coding-agent CLI to use for child sessions when --producer/validator/remediation-command are not given. Also selects the skill-invocation syntax ($market-research vs /market-research) baked into generated prompts.")
    run_batch.add_argument("--producer-command", help="Shell template. Variables: {prompt_file}, {symbol}, {run_dir}, {iteration_dir}. Defaults based on --agent-cli.")
    run_batch.add_argument("--validator-command", help="Shell template. Variables: {prompt_file}, {symbol}, {run_dir}, {iteration_dir}. Defaults based on --agent-cli.")
    run_batch.add_argument("--remediation-command", help="Shell template used after blocking validation issues. Defaults based on --agent-cli.")
    run_batch.add_argument("--max-remediation-loops", type=int, default=3)
    run_batch.add_argument("--command-timeout-seconds", type=int, default=DEFAULT_COMMAND_TIMEOUT_SECONDS)
    run_batch.add_argument("--dry-run", action="store_true")
    run_batch.add_argument("--resume", action="store_true", help="Allow reusing an existing --run-root/SYMBOL/AS_OF directory that already has iteration-01 logs, instead of refusing to avoid silently overwriting a prior run's logs.")
    run_batch.set_defaults(func=cmd_run_batch)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    args._metrics_start = start_timer()
    args.func(args)


if __name__ == "__main__":
    main()
