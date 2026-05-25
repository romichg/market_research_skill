from __future__ import annotations

from datetime import date

from cool_financial_research.agents.base import OpenAIJsonAgent
from cool_financial_research.config import AppConfig
from cool_financial_research.prompt_loader import load_prompt, runtime_contract
from cool_financial_research.schemas import SecurityClassification, StageOutput


class ResearchAgent:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.agent = OpenAIJsonAgent(model=config.model.research, output_model=StageOutput)

    def run(self, classification: SecurityClassification) -> StageOutput:
        stage_type = "etf" if classification.security_type.value == "etf" else classification.security_type.value
        instructions = load_prompt(stage_type, "research") + runtime_contract()
        today = self.config.analysis_date or date.today().isoformat()
        user_input = f"""
Run the initial research stage.

SYMBOL: {classification.symbol}
SECURITY_TYPE: {classification.security_type.value}
NAME: {classification.name or 'Data not available'}
EXCHANGE: {classification.exchange or 'Data not available'}
CIK: {classification.cik or 'Data not available'}
ANALYSIS_DATE: {today}
INVESTMENT_HORIZON: {self.config.horizon}
RISK_TOLERANCE: {self.config.risk_tolerance}

Use current public-source data and EDGAR/issuer/filing sources wherever possible.
"""
        result: StageOutput = self.agent.run(instructions=instructions, user_input=user_input)
        result.stage = "research"
        result.iteration = 0
        return result
