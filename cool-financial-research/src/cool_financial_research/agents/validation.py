from __future__ import annotations

from datetime import date

from cool_financial_research.agents.base import OpenAIJsonAgent
from cool_financial_research.config import AppConfig
from cool_financial_research.prompt_loader import load_prompt, runtime_contract
from cool_financial_research.schemas import SecurityClassification, StageOutput, ValidationStageOutput


class ValidationAgent:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.agent = OpenAIJsonAgent(model=config.model.validation, output_model=ValidationStageOutput)

    def run(
        self,
        *,
        classification: SecurityClassification,
        report: StageOutput,
        iteration: int,
    ) -> ValidationStageOutput:
        stage_type = "etf" if classification.security_type.value == "etf" else classification.security_type.value
        instructions = load_prompt(stage_type, "validation") + runtime_contract()
        today = self.config.analysis_date or date.today().isoformat()
        user_input = f"""
Run validation iteration {iteration}.

SYMBOL: {classification.symbol}
SECURITY_TYPE: {classification.security_type.value}
NAME: {classification.name or 'Data not available'}
EXCHANGE: {classification.exchange or 'Data not available'}
CIK: {classification.cik or 'Data not available'}
REPORT_DATE: {report.structured_data.analysis_date}
VALIDATION_DATE: {today}

REPORT UNDER REVIEW BELOW:

{report.markdown_report}
"""
        result: ValidationStageOutput = self.agent.run(
            instructions=instructions,
            user_input=user_input,
        )
        result.iteration = iteration
        return result
