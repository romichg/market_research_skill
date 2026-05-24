from __future__ import annotations

from pathlib import Path



def markdown_to_pdf(markdown_text: str, output_path: Path, title: str | None = None) -> Path:
    """Render markdown to PDF.

    Requires the optional `weasyprint` dependency. The function raises a RuntimeError with an
    actionable installation hint if WeasyPrint is unavailable or system libraries are missing.
    """

    try:
        import markdown as markdown_lib  # type: ignore
        from weasyprint import HTML  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "PDF generation requires the optional PDF stack. Install with: "
            "pip install 'cool-financial-research[pdf]' and ensure WeasyPrint system "
            "dependencies are present."
        ) from exc

    html_body = markdown_lib.markdown(
        markdown_text,
        extensions=["tables", "fenced_code", "toc", "sane_lists"],
        output_format="html5",
    )
    html = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>{title or 'Financial Research Report'}</title>
  <style>
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; line-height: 1.45; color: #111; }}
    h1, h2, h3 {{ page-break-after: avoid; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; font-size: 0.9rem; }}
    th, td {{ border: 1px solid #ddd; padding: 6px 8px; vertical-align: top; }}
    th {{ background: #f5f5f5; }}
    code, pre {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
    pre {{ white-space: pre-wrap; background: #f7f7f7; padding: 12px; border-radius: 8px; }}
    img {{ max-width: 100%; }}
  </style>
</head>
<body>{html_body}</body>
</html>
"""
    HTML(string=html, base_url=str(output_path.parent)).write_pdf(str(output_path))
    return output_path
