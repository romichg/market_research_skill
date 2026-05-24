from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class RunPaths:
    def __init__(self, root: Path, symbol: str) -> None:
        self.root = root
        self.symbol = symbol.upper()
        self.symbol_dir = root / self.symbol
        self.symbol_dir.mkdir(parents=True, exist_ok=True)

    def stage_base(self, label: str) -> Path:
        return self.symbol_dir / f"{self.symbol}-{label}"

    def write_stage(self, label: str, output: BaseModel, markdown: str) -> list[Path]:
        base = self.stage_base(label)
        md = base.with_suffix(".md")
        js = base.with_suffix(".json")
        md.write_text(markdown, encoding="utf-8")
        js.write_text(output.model_dump_json(indent=2), encoding="utf-8")
        return [md, js]

    def write_json(self, filename: str, data: BaseModel | dict[str, Any]) -> Path:
        path = self.symbol_dir / filename
        if isinstance(data, BaseModel):
            text = data.model_dump_json(indent=2)
        else:
            text = json.dumps(data, indent=2, default=str)
        path.write_text(text, encoding="utf-8")
        return path

    def write_markdown(self, filename: str, text: str) -> Path:
        path = self.symbol_dir / filename
        path.write_text(text, encoding="utf-8")
        return path
