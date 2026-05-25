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
        output = ValidationStageOutput.model_validate(payload)
    else:
        output = StageOutput.model_validate(payload)
    if output.stage != kind:
        raise ValueError(f"Expected {kind} stage JSON but found {output.stage}")
    return output


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


if __name__ == "__main__":
    app()
