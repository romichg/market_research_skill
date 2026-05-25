from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional, cast

import typer
from rich.console import Console
from rich.table import Table

from cool_financial_research.config import RunMode, load_config
from cool_financial_research.orchestrator import ResearchOrchestrator, ResearchWorkflowError

app = typer.Typer(add_completion=False, help="Run local multi-agent financial research workflows.")
console = Console()


class RunModeOption(str, Enum):
    auto = "auto"
    equity = "equity"
    adr = "adr"
    etf = "etf"


@app.command()
def run(
    symbol: str = typer.Argument(..., help="US-listed stock, ADR, or ETF ticker."),
    security_type: RunModeOption = typer.Option(
        RunModeOption.auto,
        "--security-type",
        "--type",
        help="auto, equity, adr, or etf. auto uses SEC metadata.",
    ),
    output_root: Path = typer.Option(
        Path("./cool-financial-research"),
        "--output-root",
        help="Root output directory.",
    ),
    max_iterations: int = typer.Option(5, help="Maximum validation/fix iterations."),
    horizon: str = typer.Option("3-5 years", help="Investment horizon used in prompts."),
    risk_tolerance: str = typer.Option("moderate", help="Risk tolerance used in prompts."),
    analysis_date: Optional[str] = typer.Option(None, help="YYYY-MM-DD. Defaults to today's date."),
    pdf: bool = typer.Option(True, "--pdf/--no-pdf", help="Generate a PDF from final markdown."),
    charts: bool = typer.Option(
        True,
        "--charts/--no-charts",
        help="Include charts when reliable chart-ready data is available.",
    ),
) -> None:
    """Run initial research, validation, fix loops, and final report generation."""

    mode = cast(RunMode, security_type.value)
    config = load_config(
        output_root=output_root,
        max_iterations=max_iterations,
        analysis_date=analysis_date,
        horizon=horizon,
        risk_tolerance=risk_tolerance,
        mode=mode,
        create_pdf=pdf,
        include_charts=charts,
    )
    orchestrator = ResearchOrchestrator(config)
    try:
        manifest = orchestrator.run(symbol, mode=mode)
    except ResearchWorkflowError as exc:
        console.print(f"[red]Workflow failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(f"[green]Completed {manifest.symbol} workflow.[/green]")
    console.print(f"Stopped reason: [bold]{manifest.stopped_reason}[/bold]")

    table = Table(title="Generated Files")
    table.add_column("Path", overflow="fold")
    for file_path in manifest.files:
        table.add_row(file_path)
    console.print(table)


@app.command("classify")
def classify(
    symbol: str = typer.Argument(..., help="Ticker to classify."),
    security_type: RunModeOption = typer.Option(
        RunModeOption.auto,
        "--security-type",
        "--type",
    ),
) -> None:
    """Classify a symbol using EDGAR metadata or an optional provider."""

    mode = cast(RunMode, security_type.value)
    config = load_config(mode=mode)
    orchestrator = ResearchOrchestrator(config)
    try:
        classification = orchestrator.classify_symbol(symbol, mode=mode)
    except ResearchWorkflowError as exc:
        console.print(f"[red]Classification failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    console.print_json(classification.model_dump_json(indent=2))


if __name__ == "__main__":
    app()
