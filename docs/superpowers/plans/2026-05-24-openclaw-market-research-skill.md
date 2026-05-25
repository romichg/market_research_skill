# OpenClaw Market Research Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the existing direct-OpenAI CLI project into a local OpenClaw skill package where OpenClaw performs model reasoning and Python only handles deterministic workflow support.

**Architecture:** Rename the project folder to `cool-financial-research`, keep the Python package as `cool_financial_research`, add an OpenClaw helper module for classification, prompt loading, stage validation, artifact writing, and manifest writing, then rewrite `SKILL.md` so OpenClaw drives the feedback loop through helper commands. The legacy direct OpenAI CLI may remain, but the OpenClaw path must not require or instantiate OpenAI credentials.

**Tech Stack:** Python 3.10+, Typer, Pydantic v2, pytest, Ruff, mypy, OpenClaw AgentSkills-compatible `SKILL.md`.

---

## File Structure

- Rename: the old CLI-branded project directory -> `cool-financial-research/`
- Modify: `AGENTS.md` to reference `cool-financial-research/`
- Modify: `cool-financial-research/README.md` to document local OpenClaw setup first
- Modify: `cool-financial-research/SKILL.md` to become the OpenClaw-native workflow contract
- Modify: `cool-financial-research/pyproject.toml` to add a helper console script and remove CLI-first wording
- Create: `cool-financial-research/src/cool_financial_research/workflow.py` for shared stop-condition logic
- Create: `cool-financial-research/src/cool_financial_research/openclaw_helper.py` for deterministic helper commands
- Modify: `cool-financial-research/src/cool_financial_research/orchestrator.py` to use `workflow.py`
- Create: `cool-financial-research/scripts/check-openclaw-skill.sh`
- Create: `cool-financial-research/tests/test_openclaw_helper.py`
- Modify: `cool-financial-research/tests/test_loop_stop.py`

## Task 1: Rename Project Folder And References

**Files:**
- Rename: the old CLI-branded project directory -> `cool-financial-research/`
- Modify: `.gitignore`
- Modify: `AGENTS.md`

- [ ] **Step 1: Rename the directory**

Run:

```bash
git mv <old-cli-branded-directory> cool-financial-research
```

Expected: directory is renamed and git tracks the move.

- [ ] **Step 2: Update ignore patterns**

Edit `.gitignore` so the generated output ignore uses the new folder:

```gitignore
.env
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
*.egg-info/
dist/
build/
cool-financial-research/cool-financial-research/
```

- [ ] **Step 3: Update contributor guide paths**

Replace old CLI-branded directory references with `cool-financial-research/` in `AGENTS.md`.

- [ ] **Step 4: Verify references**

Run:

```bash
grep -R "<old-cli-branded-directory>" -n .
```

Expected: only historical references in git internals, or no output from tracked files.

- [ ] **Step 5: Commit**

```bash
git add .gitignore AGENTS.md cool-financial-research
git commit -m "chore: rename project folder"
```

## Task 2: Extract Shared Stop-Condition Logic

**Files:**
- Create: `cool-financial-research/src/cool_financial_research/workflow.py`
- Modify: `cool-financial-research/src/cool_financial_research/orchestrator.py`
- Modify: `cool-financial-research/tests/test_loop_stop.py`

- [ ] **Step 1: Write failing tests against shared workflow logic**

Replace the import and assertions in `cool-financial-research/tests/test_loop_stop.py` with:

```python
from cool_financial_research.schemas import (
    Issue,
    IssueSeverity,
    SecurityType,
    ValidationStageOutput,
    ValidationStructuredData,
)
from cool_financial_research.workflow import should_stop_validation


def validation_with_issues(issues, critical=0, moderate=0):
    return ValidationStageOutput(
        symbol="ABC",
        security_type=SecurityType.equity,
        iteration=1,
        markdown_report="# Validation",
        structured_data=ValidationStructuredData(
            symbol="ABC",
            security_type=SecurityType.equity,
            validation_date="2026-05-24",
            overall_verdict="pass_with_revisions",
            recommendation_confidence="medium",
            critical_count=critical,
            moderate_count=moderate,
            minor_count=0,
            issues=issues,
            summary="summary",
        ),
    )


def test_stops_when_no_blocking_issues():
    should_stop, reason = should_stop_validation(validation_with_issues([]))
    assert should_stop is True
    assert reason == "no_blocking_issues"


def test_continues_when_open_moderate_issue_exists():
    validation = validation_with_issues(
        [
            Issue(
                severity=IssueSeverity.moderate,
                section="Valuation",
                issue="DCF arithmetic does not tie out",
                status="open",
            )
        ],
        moderate=1,
    )
    should_stop, reason = should_stop_validation(validation)
    assert should_stop is False
    assert reason == ""


def test_stops_when_blocking_issue_is_unresolved_data_unavailable():
    validation = validation_with_issues(
        [
            Issue(
                severity=IssueSeverity.critical,
                section="SEC Filings",
                issue="Primary source unavailable",
                status="unresolved_data_unavailable",
            )
        ],
        critical=1,
    )
    should_stop, reason = should_stop_validation(validation)
    assert should_stop is True
    assert reason == "only_unresolved_data_unavailable"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd cool-financial-research
pytest tests/test_loop_stop.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'cool_financial_research.workflow'`.

- [ ] **Step 3: Add workflow module**

Create `cool-financial-research/src/cool_financial_research/workflow.py`:

```python
from __future__ import annotations

from cool_financial_research.schemas import IssueSeverity, ValidationStageOutput


def should_stop_validation(validation: ValidationStageOutput) -> tuple[bool, str]:
    data = validation.structured_data
    blocking = [
        issue
        for issue in data.issues
        if issue.severity in {IssueSeverity.critical, IssueSeverity.moderate}
    ]
    open_fixable = [issue for issue in blocking if issue.status == "open"]
    if not blocking and data.blocking_issue_count == 0:
        return True, "no_blocking_issues"
    if not open_fixable:
        return True, "only_unresolved_data_unavailable"
    return False, ""
```

- [ ] **Step 4: Update orchestrator to use workflow module**

In `cool-financial-research/src/cool_financial_research/orchestrator.py`:

```python
from cool_financial_research.workflow import should_stop_validation
```

Replace the body of `_should_stop` with:

```python
    @staticmethod
    def _should_stop(validation: ValidationStageOutput) -> tuple[bool, str]:
        return should_stop_validation(validation)
```

Remove the now-unused `IssueSeverity` import.

- [ ] **Step 5: Run tests**

Run:

```bash
cd cool-financial-research
pytest tests/test_loop_stop.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add cool-financial-research/src/cool_financial_research/workflow.py \
  cool-financial-research/src/cool_financial_research/orchestrator.py \
  cool-financial-research/tests/test_loop_stop.py
git commit -m "refactor: share validation stop logic"
```

## Task 3: Add OpenClaw Helper Read Commands

**Files:**
- Create: `cool-financial-research/src/cool_financial_research/openclaw_helper.py`
- Create: `cool-financial-research/tests/test_openclaw_helper.py`
- Modify: `cool-financial-research/pyproject.toml`

- [ ] **Step 1: Write tests for prompt normalization and JSON output**

Create `cool-financial-research/tests/test_openclaw_helper.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd cool-financial-research
pytest tests/test_openclaw_helper.py -v
```

Expected: FAIL with missing `openclaw_helper`.

- [ ] **Step 3: Implement helper read commands**

Create `cool-financial-research/src/cool_financial_research/openclaw_helper.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import typer
from pydantic import ValidationError

from cool_financial_research.prompt_loader import load_prompt, runtime_contract
from cool_financial_research.schemas import StageOutput, ValidationStageOutput

app = typer.Typer(add_completion=False, help="Deterministic helper commands for the OpenClaw skill.")

StageKind = Literal["research", "fix", "final", "validation"]


def prompt_key(security_type: str, stage: str) -> tuple[str, str]:
    normalized_type = security_type.lower().strip()
    normalized_stage = stage.lower().strip()
    if normalized_type not in {"equity", "adr", "etf"}:
        raise typer.BadParameter("security_type must be equity, adr, or etf")
    if normalized_stage not in {"research", "validation", "fix"}:
        raise typer.BadParameter("stage must be research, validation, or fix")
    return normalized_type, normalized_stage


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_stage(kind: StageKind, payload: dict) -> StageOutput | ValidationStageOutput:
    if kind == "validation":
        return ValidationStageOutput.model_validate(payload)
    return StageOutput.model_validate(payload)


@app.command()
def prompt(security_type: str, stage: str) -> None:
    """Print a prompt template plus the shared runtime contract."""

    prompt_type, prompt_stage = prompt_key(security_type, stage)
    typer.echo(load_prompt(prompt_type, prompt_stage) + runtime_contract())


@app.command("validate-stage")
def validate_stage(kind: StageKind, payload_file: Path) -> None:
    """Validate a stage JSON file against the expected Pydantic schema."""

    try:
        output = _validate_stage(kind, _read_json(payload_file))
    except (json.JSONDecodeError, ValidationError) as exc:
        typer.echo(f"Invalid {kind} stage JSON: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(output.model_dump_json(indent=2))


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Add helper console script**

In `cool-financial-research/pyproject.toml`, add under `[project.scripts]`:

```toml
cool-financial-research-helper = "cool_financial_research.openclaw_helper:app"
```

Keep the existing `cool-financial-research` script for legacy compatibility.

- [ ] **Step 5: Run tests**

Run:

```bash
cd cool-financial-research
pytest tests/test_openclaw_helper.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add cool-financial-research/src/cool_financial_research/openclaw_helper.py \
  cool-financial-research/tests/test_openclaw_helper.py \
  cool-financial-research/pyproject.toml
git commit -m "feat: add OpenClaw helper read commands"
```

## Task 4: Add Helper Classification And Artifact Commands

**Files:**
- Modify: `cool-financial-research/src/cool_financial_research/openclaw_helper.py`
- Modify: `cool-financial-research/tests/test_openclaw_helper.py`

- [ ] **Step 1: Add tests for save-stage and should-stop**

Append to `cool-financial-research/tests/test_openclaw_helper.py`:

```python

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
    payload_file.write_text(json.dumps(validation_payload_without_blocking_issues()), encoding="utf-8")
    result = runner.invoke(app, ["should-stop", str(payload_file)])
    assert result.exit_code == 0
    assert json.loads(result.output) == {"should_stop": True, "reason": "no_blocking_issues"}
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd cool-financial-research
pytest tests/test_openclaw_helper.py -v
```

Expected: FAIL because `save-stage` and `should-stop` are not implemented.

- [ ] **Step 3: Implement artifact and stop commands**

Add imports in `openclaw_helper.py`:

```python
from cool_financial_research.config import RunMode
from cool_financial_research.io import RunPaths
from cool_financial_research.providers import ClassificationError, EdgarClassifier
from cool_financial_research.schemas import SecurityType
from cool_financial_research.workflow import should_stop_validation
```

Add commands:

```python
@app.command()
def classify(
    symbol: str,
    security_type: RunMode = typer.Option("auto", "--security-type", "--type"),
    sec_user_agent: str = typer.Option(
        "cool-financial-research/0.1 local-openclaw-skill",
        "--sec-user-agent",
    ),
) -> None:
    """Classify a ticker using SEC metadata and print JSON."""

    classifier = EdgarClassifier(user_agent=sec_user_agent)
    try:
        classification = classifier.classify(symbol)
    except ClassificationError as exc:
        typer.echo(f"Classification failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    if security_type != "auto":
        classification.security_type = SecurityType(security_type)
        classification.is_adr = security_type == "adr"
        classification.notes.append(f"Security type overridden by OpenClaw input: {security_type}")
    typer.echo(classification.model_dump_json(indent=2))


@app.command("init-run")
def init_run(symbol: str, output_root: Path = typer.Option(Path("./cool-financial-research"))) -> None:
    """Create a symbol output directory and print its location."""

    paths = RunPaths(output_root, symbol)
    typer.echo(json.dumps({"symbol": paths.symbol, "output_dir": str(paths.symbol_dir)}, indent=2))


@app.command("save-stage")
def save_stage(
    symbol: str,
    label: str,
    kind: StageKind,
    payload_file: Path,
    output_root: Path = typer.Option(Path("./cool-financial-research")),
) -> None:
    """Validate and save one markdown/JSON stage artifact."""

    try:
        output = _validate_stage(kind, _read_json(payload_file))
    except (json.JSONDecodeError, ValidationError) as exc:
        typer.echo(f"Invalid {kind} stage JSON: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    paths = RunPaths(output_root, symbol)
    written = paths.write_stage(label, output, output.markdown_report)
    typer.echo(json.dumps({"markdown": str(written[0]), "json": str(written[1])}, indent=2))


@app.command("should-stop")
def should_stop(validation_file: Path) -> None:
    """Evaluate validation-loop stop conditions."""

    try:
        validation = ValidationStageOutput.model_validate(_read_json(validation_file))
    except (json.JSONDecodeError, ValidationError) as exc:
        typer.echo(f"Invalid validation stage JSON: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    stop, reason = should_stop_validation(validation)
    typer.echo(json.dumps({"should_stop": stop, "reason": reason}, indent=2))
```

- [ ] **Step 4: Run tests**

Run:

```bash
cd cool-financial-research
pytest tests/test_openclaw_helper.py tests/test_loop_stop.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add cool-financial-research/src/cool_financial_research/openclaw_helper.py \
  cool-financial-research/tests/test_openclaw_helper.py
git commit -m "feat: add OpenClaw helper artifact commands"
```

## Task 5: Add Manifest Command

**Files:**
- Modify: `cool-financial-research/src/cool_financial_research/openclaw_helper.py`
- Modify: `cool-financial-research/tests/test_openclaw_helper.py`

- [ ] **Step 1: Write manifest command test**

Append to `cool-financial-research/tests/test_openclaw_helper.py`:

```python

def test_write_manifest_creates_run_manifest(tmp_path):
    files_file = tmp_path / "files.json"
    files_file.write_text(json.dumps(["ABC-first_run.md", "ABC-final.md"]), encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "write-manifest",
            "ABC",
            "equity",
            "--output-root",
            str(tmp_path / "out"),
            "--max-iterations",
            "5",
            "--iterations-completed",
            "1",
            "--stopped-reason",
            "no_blocking_issues",
            "--files-file",
            str(files_file),
        ],
    )
    assert result.exit_code == 0
    manifest_path = Path(json.loads(result.output)["manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["symbol"] == "ABC"
    assert manifest["stopped_reason"] == "no_blocking_issues"
    assert manifest["models"] == {"runtime": "openclaw"}
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
cd cool-financial-research
pytest tests/test_openclaw_helper.py::test_write_manifest_creates_run_manifest -v
```

Expected: FAIL because `write-manifest` is not implemented.

- [ ] **Step 3: Implement manifest command**

Add `RunManifest` import:

```python
from cool_financial_research.schemas import RunManifest
```

Add command:

```python
@app.command("write-manifest")
def write_manifest(
    symbol: str,
    security_type: SecurityType,
    output_root: Path = typer.Option(Path("./cool-financial-research")),
    max_iterations: int = typer.Option(...),
    iterations_completed: int = typer.Option(...),
    stopped_reason: str = typer.Option(...),
    files_file: Path = typer.Option(...),
    name: str | None = typer.Option(None),
    exchange: str | None = typer.Option(None),
    cik: str | None = typer.Option(None),
) -> None:
    """Write the final run manifest for an OpenClaw-driven run."""

    files = json.loads(files_file.read_text(encoding="utf-8"))
    manifest = RunManifest(
        symbol=symbol.upper(),
        security_type=security_type,
        name=name,
        exchange=exchange,
        cik=cik,
        max_iterations=max_iterations,
        iterations_completed=iterations_completed,
        stopped_reason=stopped_reason,
        files=files,
        models={"runtime": "openclaw"},
    )
    paths = RunPaths(output_root, symbol)
    path = paths.write_json("run_manifest.json", manifest)
    typer.echo(json.dumps({"manifest": str(path)}, indent=2))
```

- [ ] **Step 4: Run tests**

Run:

```bash
cd cool-financial-research
pytest tests/test_openclaw_helper.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add cool-financial-research/src/cool_financial_research/openclaw_helper.py \
  cool-financial-research/tests/test_openclaw_helper.py
git commit -m "feat: write OpenClaw run manifests"
```

## Task 6: Rewrite SKILL.md For OpenClaw-Native Workflow

**Files:**
- Modify: `cool-financial-research/SKILL.md`

- [ ] **Step 1: Replace SKILL.md content**

Replace `cool-financial-research/SKILL.md` with:

```markdown
---
name: cool-financial-research
description: Research US-listed stocks, ADRs, and ETFs with a validation and revision feedback loop.
---

# Cool Financial Research

Use this skill when the user asks for market, stock, ADR, or ETF research and wants a report with validation, revisions, and saved audit artifacts.

## Runtime Rule

Use OpenClaw's existing model connection and tools for all reasoning. Do not require `OPENAI_API_KEY` and do not run the legacy direct-OpenAI workflow for this skill path.

Python helper commands are deterministic support only. Run them through:

```bash
cd {baseDir}
.venv/bin/python -m cool_financial_research.openclaw_helper --help
```

If `.venv` does not exist, tell the user to run:

```bash
cd {baseDir}
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

## Inputs

- `symbol`: required ticker unless the user has already provided it.
- `security_type`: optional `auto`, `equity`, `adr`, or `etf`; default to `auto`.
- `max_iterations`: default `5`, maximum `10`.
- `horizon`: default `3-5 years` unless the user specifies another horizon.
- `risk_tolerance`: default `moderate` unless the user specifies another profile.

## Workflow

1. Normalize the symbol to uppercase.
2. Run classification:

```bash
cd {baseDir}
.venv/bin/python -m cool_financial_research.openclaw_helper classify SYMBOL --security-type auto
```

3. If classification fails or conflicts with the user's explicit security type, stop and ask for clarification.
4. Initialize the output directory:

```bash
cd {baseDir}
.venv/bin/python -m cool_financial_research.openclaw_helper init-run SYMBOL
```

5. Load the research prompt:

```bash
cd {baseDir}
.venv/bin/python -m cool_financial_research.openclaw_helper prompt SECURITY_TYPE research
```

6. Use OpenClaw reasoning and available browsing/tools to produce a JSON object matching the research stage schema. Include `markdown_report` and `structured_data`.
7. Save the first run:

```bash
cd {baseDir}
.venv/bin/python -m cool_financial_research.openclaw_helper save-stage SYMBOL first_run research /path/to/research.json
```

8. Load the validation prompt and validate the latest report:

```bash
cd {baseDir}
.venv/bin/python -m cool_financial_research.openclaw_helper prompt SECURITY_TYPE validation
```

9. Save validation as `validation<N>`, then check stop conditions:

```bash
cd {baseDir}
.venv/bin/python -m cool_financial_research.openclaw_helper save-stage SYMBOL validation1 validation /path/to/validation.json
.venv/bin/python -m cool_financial_research.openclaw_helper should-stop /path/to/SYMBOL-validation1.json
```

10. If open Critical or Moderate issues remain, load the fix prompt, revise the report, and save `validation-fix<N>`.
11. Repeat validation and fix until a stop condition is met or `max_iterations` is reached.
12. Save the final report as `final` and write `run_manifest.json`.

## Stop Conditions

Stop when:

- no Critical or Moderate validation issues remain;
- all remaining Critical or Moderate issues are marked `unresolved_data_unavailable`;
- `max_iterations` is reached.

## Correctness Rules

- Prefer primary sources: SEC filings, issuer investor relations pages, ETF prospectuses, ETF fact sheets, index methodology documents, and official exchange or regulator data.
- Cite or mark as `unverified` every material quantitative claim.
- Include source dates and confidence levels for material claims.
- Flag stale or fast-changing data instead of inventing precision.
- Keep FACTS separate from INTERPRETATION.
- Validation issue counts must match the issue list.
- Each fix pass must resolve every open Critical or Moderate issue or explicitly mark it `unresolved_data_unavailable`.
- Carry unresolved issues into the final report and manifest.
- Preserve intermediate files for audit.

## Output

Default output location:

```text
{baseDir}/cool-financial-research/SYMBOL/
```

Summarize the final report for the user and include the final markdown path, final JSON path, manifest path, stop reason, and unresolved Critical/Moderate issues.
```

- [ ] **Step 2: Verify OpenClaw frontmatter shape**

Run:

```bash
cd cool-financial-research
python - <<'PY'
from pathlib import Path
text = Path("SKILL.md").read_text()
assert text.startswith("---\n")
assert "\nname: cool-financial-research\n" in text
assert "\ndescription: " in text
assert "{baseDir}" in text
assert "OPENAI_API_KEY" in text
PY
```

Expected: command exits with status 0.

- [ ] **Step 3: Commit**

```bash
git add cool-financial-research/SKILL.md
git commit -m "docs: rewrite skill for OpenClaw runtime"
```

## Task 7: Update README And Local Check Script

**Files:**
- Modify: `cool-financial-research/README.md`
- Create: `cool-financial-research/scripts/check-openclaw-skill.sh`

- [ ] **Step 1: Add check script**

Create `cool-financial-research/scripts/check-openclaw-skill.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

test -f SKILL.md
test -f pyproject.toml

if ! grep -q '^name: cool-financial-research$' SKILL.md; then
  echo "SKILL.md is missing the expected OpenClaw skill name" >&2
  exit 1
fi

if grep -q 'OPENAI_API_KEY.*Required' SKILL.md README.md; then
  echo "OpenClaw path must not require OPENAI_API_KEY" >&2
  exit 1
fi

if [ ! -x .venv/bin/python ]; then
  echo "Missing .venv. Run: python -m venv .venv && source .venv/bin/activate && pip install -e '.[dev]'" >&2
  exit 1
fi

.venv/bin/python -m cool_financial_research.openclaw_helper --help >/dev/null
.venv/bin/python -m cool_financial_research.openclaw_helper prompt equity research >/dev/null

echo "OpenClaw skill check passed."
```

Run:

```bash
chmod +x cool-financial-research/scripts/check-openclaw-skill.sh
```

- [ ] **Step 2: Rewrite README opening and setup**

Update `cool-financial-research/README.md` so the first sections are:

```markdown
# cool-financial-research

Local OpenClaw skill for US-listed stock, ADR, and ETF research with a research → validation → revision feedback loop.

OpenClaw provides the model connection and reasoning. The Python package provides deterministic helpers for ticker classification, prompt loading, schema validation, artifact writing, and manifest generation.

## Local OpenClaw Setup

```bash
cd cool-financial-research
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
scripts/check-openclaw-skill.sh
```

Expose this folder to OpenClaw as a local skill by copying or symlinking it into the active OpenClaw workspace `skills/` directory, or by adding its parent directory to OpenClaw's configured extra skill directories.

This OpenClaw skill path does not require `OPENAI_API_KEY`; it uses the model connection already configured in OpenClaw.
```

Keep a later section named `Legacy Direct CLI Mode` for existing `cool-financial-research run AAPL --no-pdf` behavior and document that mode separately if retained.

- [ ] **Step 3: Run check script expected setup failure or pass**

Run:

```bash
cd cool-financial-research
scripts/check-openclaw-skill.sh
```

Expected if `.venv` is absent: FAIL with the explicit missing `.venv` setup command. Expected if `.venv` exists and dependencies are installed: PASS.

- [ ] **Step 4: Commit**

```bash
git add cool-financial-research/README.md cool-financial-research/scripts/check-openclaw-skill.sh
git commit -m "docs: add local OpenClaw setup"
```

## Task 8: Verify OpenClaw Path Does Not Use Direct OpenAI Runtime

**Files:**
- Modify: `cool-financial-research/tests/test_openclaw_helper.py`

- [ ] **Step 1: Add regression test**

Append:

```python

def test_openclaw_helper_does_not_import_openai_runtime():
    import sys

    sys.modules.pop("openai", None)
    result = runner.invoke(app, ["prompt", "equity", "research"])
    assert result.exit_code == 0
    assert "openai" not in sys.modules
```

- [ ] **Step 2: Run regression test**

Run:

```bash
cd cool-financial-research
pytest tests/test_openclaw_helper.py::test_openclaw_helper_does_not_import_openai_runtime -v
```

Expected: PASS.

- [ ] **Step 3: Run all local checks**

Run:

```bash
cd cool-financial-research
pytest
ruff check .
mypy src
```

Expected: PASS. If `mypy` reports missing imports from optional packages already configured as ignored, fix only project type errors.

- [ ] **Step 4: Commit**

```bash
git add cool-financial-research/tests/test_openclaw_helper.py
git commit -m "test: guard OpenClaw helper runtime"
```

## Task 9: Final Repository Audit

**Files:**
- Modify only files needed to fix verification findings

- [ ] **Step 1: Search for stale project name**

Run:

```bash
grep -R "<old-cli-branded-directory>" -n AGENTS.md docs cool-financial-research || true
```

Expected: no output.

- [ ] **Step 2: Search for misleading OpenAI key requirements**

Run:

```bash
grep -R "OPENAI_API_KEY" -n cool-financial-research/SKILL.md cool-financial-research/README.md
```

Expected: references only say the OpenClaw skill path does not require `OPENAI_API_KEY`, or legacy direct CLI mode requires it.

- [ ] **Step 3: Inspect git status**

Run:

```bash
git status --short
```

Expected: clean working tree.

- [ ] **Step 4: If any documentation or verification fix was required, commit it**

```bash
git add .
git commit -m "chore: finalize OpenClaw skill migration"
```

Skip this commit if the working tree is already clean.
