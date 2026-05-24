from __future__ import annotations

from pathlib import Path

from cool_financial_research.schemas import StageOutput


def create_reliable_charts(report: StageOutput, output_dir: Path) -> list[Path]:
    """Create charts only when the structured report contains enough reliable data.

    This version intentionally returns no charts unless a data-provider adapter enriches the
    structured output with chart-ready time series. Add adapters here for price history,
    revenue/margin trend, FCF trend, ETF allocation, premium/discount, etc.
    """

    _ = report
    _ = output_dir
    return []


def append_chart_links(markdown_report: str, chart_paths: list[Path]) -> str:
    if not chart_paths:
        return markdown_report
    lines = [markdown_report.rstrip(), "", "## Appendix: Charts & Figures"]
    for path in chart_paths:
        lines.append(f"![{path.stem}]({path.name})")
    return "\n".join(lines) + "\n"
