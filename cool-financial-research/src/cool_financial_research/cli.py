"""Optional Typer-based developer CLI.

This is intentionally a convenience layer around deterministic helper commands.
It does not call OpenAI or any other LLM provider; OpenClaw remains the harness
for research/validation/fix sub-agents.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from . import __version__
from .openclaw_helper import main as helper_main

app = typer.Typer(add_completion=False, help="Developer conveniences for the Cool Financial Research OpenClaw skill.")
console = Console()


@app.command()
def version() -> None:
    """Print package version."""
    console.print(__version__)


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def helper(ctx: typer.Context) -> None:
    """Forward arguments to the stdlib OpenClaw helper.

    Example: cool-financial-research-dev helper preflight --output-root ./cool-financial-research
    """
    raise typer.Exit(code=helper_main(list(ctx.args)))


@app.command("openclaw-message")
def openclaw_message(
    symbol: str = typer.Argument(..., help="Ticker to research."),
    security_type: str = typer.Option("auto", "--security-type", "--type", help="auto, equity, adr, or etf."),
    output_root: Path = typer.Option(Path("./cool-financial-research"), help="Output root."),
    max_iterations: int = typer.Option(5, help="Max validation/fix iterations."),
    pdf: bool = typer.Option(True, "--pdf/--no-pdf", help="Ask the skill to render PDF when dependencies allow."),
) -> None:
    """Print a ready-to-copy OpenClaw message for a run."""
    pdf_text = "and render the final PDF if available" if pdf else "and skip final PDF rendering"
    message = (
        f"Use the cool-financial-research skill to research {symbol.upper()} with security_type={security_type}, "
        f"output_root={output_root}, max_iterations={max_iterations}, {pdf_text}."
    )
    console.print(message)


if __name__ == "__main__":
    app()
