from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

SecurityType = Literal["equity", "adr", "etf"]
RunMode = Literal["auto", "equity", "adr", "etf"]


class ModelConfig(BaseModel):
    """Configurable model map with agreed defaults."""

    orchestrator: str = Field(default_factory=lambda: os.getenv("CFR_ORCHESTRATOR_MODEL", "gpt-5.5"))
    research: str = Field(default_factory=lambda: os.getenv("CFR_RESEARCH_MODEL", "gpt-5.5-pro"))
    validation: str = Field(default_factory=lambda: os.getenv("CFR_VALIDATION_MODEL", "gpt-5.5-pro"))
    fix: str = Field(default_factory=lambda: os.getenv("CFR_FIX_MODEL", "gpt-5.5-pro"))
    json_repair: str = Field(default_factory=lambda: os.getenv("CFR_JSON_REPAIR_MODEL", "gpt-5.5"))


class AppConfig(BaseModel):
    output_root: Path = Path("./cool-financial-research")
    max_iterations: int = 5
    analysis_date: str | None = None
    horizon: str = "3-5 years"
    risk_tolerance: str = "moderate"
    mode: RunMode = "auto"
    create_pdf: bool = True
    include_charts: bool = True
    model: ModelConfig = Field(default_factory=ModelConfig)
    paid_provider: str = Field(default_factory=lambda: os.getenv("CFR_PAID_PROVIDER", "none"))
    sec_user_agent: str = Field(
        default_factory=lambda: os.getenv(
            "SEC_USER_AGENT",
            "cool-financial-research/0.1 contact@example.com",
        )
    )

    @field_validator("max_iterations")
    @classmethod
    def check_max_iterations(cls, value: int) -> int:
        if value < 1 or value > 10:
            raise ValueError("max_iterations must be between 1 and 10")
        return value


def load_config(**overrides: object) -> AppConfig:
    load_dotenv()
    raw = {k: v for k, v in overrides.items() if v is not None}
    return AppConfig(**raw)
