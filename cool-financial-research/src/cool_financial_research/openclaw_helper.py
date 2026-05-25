from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Literal

import requests
import typer
from pydantic import ValidationError
from typer import Option

from cool_financial_research.config import RunMode
from cool_financial_research.io import RunPaths
from cool_financial_research.providers import ClassificationError, EdgarClassifier
from cool_financial_research.prompt_loader import load_prompt, runtime_contract
from cool_financial_research.schemas import (
    RunManifest,
    SecurityType,
    StageOutput,
    ValidationStageOutput,
)
from cool_financial_research.workflow import should_stop_validation

app = typer.Typer(
    add_completion=False,
    help="Deterministic helper commands for the OpenClaw skill.",
)

StageKind = Literal["research", "fix", "final", "validation"]
DEFAULT_SEC_USER_AGENT = "cool-financial-research/0.1 contact@example.com"


class StoppedReason(str, Enum):
    no_blocking_issues = "no_blocking_issues"
    only_unresolved_data_unavailable = "only_unresolved_data_unavailable"
    max_iterations_reached = "max_iterations_reached"
    classification_error = "classification_error"
    runtime_error = "runtime_error"


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
        validation_output = ValidationStageOutput.model_validate(payload)
        if validation_output.stage != kind:
            raise ValueError(f"Expected {kind} stage JSON but found {validation_output.stage}")
        return validation_output
    stage_output = StageOutput.model_validate(payload)
    if stage_output.stage != kind:
        raise ValueError(f"Expected {kind} stage JSON but found {stage_output.stage}")
    return stage_output


def _validate_validation_stage(payload: dict) -> ValidationStageOutput:
    validation_output = ValidationStageOutput.model_validate(payload)
    if validation_output.stage != "validation":
        raise ValueError(f"Expected validation stage JSON but found {validation_output.stage}")
    return validation_output


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
    except (
        FileNotFoundError,
        PermissionError,
        UnicodeDecodeError,
        OSError,
        json.JSONDecodeError,
        ValidationError,
        ValueError,
    ) as exc:
        typer.echo(f"Invalid {kind} stage JSON: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(output.model_dump_json(indent=2))


@app.command()
def classify(
    symbol: str,
    security_type: RunMode = Option(
        "auto",
        "--security-type",
        "--type",
        help="auto, equity, adr, or etf. auto uses SEC metadata.",
    ),
    sec_user_agent: str = Option(
        DEFAULT_SEC_USER_AGENT,
        "--sec-user-agent",
        help="User-Agent header for SEC EDGAR requests.",
    ),
) -> None:
    """Classify a ticker using EDGAR metadata and optional user override."""

    try:
        classification = EdgarClassifier(user_agent=sec_user_agent).classify(symbol)
    except (ClassificationError, requests.RequestException, OSError, ValueError) as exc:
        typer.echo(f"Classification failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if security_type != "auto":
        classification.security_type = SecurityType(security_type)
        classification.is_adr = security_type == "adr"
        classification.notes.append(f"Security type overridden by helper mode: {security_type}")
    typer.echo(classification.model_dump_json(indent=2))


@app.command("init-run")
def init_run(
    symbol: str,
    output_root: Path = Option(
        Path("./cool-financial-research"),
        "--output-root",
        help="Root output directory.",
    ),
) -> None:
    """Create the output directory for a symbol run."""

    try:
        paths = RunPaths(output_root, symbol)
    except OSError as exc:
        typer.echo(f"Could not initialize run: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps({"symbol": paths.symbol, "output_dir": str(paths.symbol_dir)}))


@app.command("save-stage")
def save_stage(
    symbol: str,
    label: str,
    kind: StageKind,
    payload_file: Path,
    output_root: Path = Option(
        Path("./cool-financial-research"),
        "--output-root",
        help="Root output directory.",
    ),
) -> None:
    """Validate and persist a stage payload as markdown and JSON artifacts."""

    try:
        output = _validate_stage(kind, _read_json(payload_file))
    except (
        FileNotFoundError,
        PermissionError,
        UnicodeDecodeError,
        OSError,
        json.JSONDecodeError,
        ValidationError,
        ValueError,
    ) as exc:
        typer.echo(f"Invalid {kind} stage JSON: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    try:
        markdown_path, json_path = RunPaths(output_root, symbol).write_stage(
            label,
            output,
            output.markdown_report,
        )
    except OSError as exc:
        typer.echo(f"Could not save stage: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps({"markdown": str(markdown_path), "json": str(json_path)}))


@app.command("should-stop")
def should_stop(validation_file: Path) -> None:
    """Print the validation loop stop decision for a validation payload."""

    try:
        validation = _validate_validation_stage(_read_json(validation_file))
    except (
        FileNotFoundError,
        PermissionError,
        UnicodeDecodeError,
        OSError,
        json.JSONDecodeError,
        ValidationError,
        ValueError,
    ) as exc:
        typer.echo(f"Invalid validation stage JSON: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    should_stop_result, reason = should_stop_validation(validation)
    typer.echo(json.dumps({"should_stop": should_stop_result, "reason": reason}))


@app.command("write-manifest")
def write_manifest(
    symbol: str,
    security_type: SecurityType,
    output_root: Path = Option(
        Path("./cool-financial-research"),
        "--output-root",
        help="Root output directory.",
    ),
    max_iterations: int = Option(...),
    iterations_completed: int = Option(...),
    stopped_reason: StoppedReason = typer.Option(...),
    files_file: Path = Option(...),
    name: str | None = Option(None),
    exchange: str | None = Option(None),
    cik: str | None = Option(None),
) -> None:
    """Write the final run manifest for an OpenClaw-driven run."""

    try:
        files = json.loads(files_file.read_text(encoding="utf-8"))
    except (
        FileNotFoundError,
        PermissionError,
        UnicodeDecodeError,
        OSError,
        json.JSONDecodeError,
    ) as exc:
        typer.echo(f"Could not write manifest: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    try:
        manifest = RunManifest(
            symbol=symbol.upper(),
            security_type=security_type,
            name=name,
            exchange=exchange,
            cik=cik,
            max_iterations=max_iterations,
            iterations_completed=iterations_completed,
            stopped_reason=stopped_reason.value,
            files=files,
            models={"runtime": "openclaw"},
        )
    except ValidationError as exc:
        typer.echo(f"Invalid manifest inputs: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    try:
        path = RunPaths(output_root, symbol).write_json("run_manifest.json", manifest)
    except OSError as exc:
        typer.echo(f"Could not write manifest: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps({"manifest": str(path)}, indent=2))


if __name__ == "__main__":
    app()
