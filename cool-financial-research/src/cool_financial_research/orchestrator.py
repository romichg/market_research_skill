from __future__ import annotations

from pathlib import Path

from cool_financial_research.agents import FixAgent, ResearchAgent, ValidationAgent
from cool_financial_research.charts import append_chart_links, create_reliable_charts
from cool_financial_research.config import AppConfig, RunMode
from cool_financial_research.io import RunPaths
from cool_financial_research.pdf import markdown_to_pdf
from cool_financial_research.providers import ClassificationError, EdgarClassifier, PaidProviderClassifier
from cool_financial_research.providers.base import SecurityClassifier
from cool_financial_research.schemas import (
    RunManifest,
    SecurityClassification,
    SecurityType,
    StageOutput,
    ValidationStageOutput,
)
from cool_financial_research.workflow import should_stop_validation


class ResearchWorkflowError(RuntimeError):
    pass


class ResearchOrchestrator:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def classify_symbol(self, symbol: str, mode: RunMode = "auto") -> SecurityClassification:
        symbol = symbol.upper().strip()
        if self.config.paid_provider and self.config.paid_provider.lower() != "none":
            # Extension point: use a paid provider when a concrete adapter is implemented.
            classifier: SecurityClassifier = PaidProviderClassifier(self.config.paid_provider)
        else:
            classifier = EdgarClassifier(user_agent=self.config.sec_user_agent)

        try:
            classification = classifier.classify(symbol)
        except ClassificationError as exc:
            raise ResearchWorkflowError(str(exc)) from exc

        if mode != "auto":
            classification.security_type = SecurityType(mode)
            classification.is_adr = mode == "adr"
            classification.notes.append(f"Security type overridden by CLI mode: {mode}")
        return classification

    def run(self, symbol: str, mode: RunMode = "auto") -> RunManifest:
        classification = self.classify_symbol(symbol, mode)
        paths = RunPaths(self.config.output_root, classification.symbol)
        files: list[Path] = []
        stopped_reason = "runtime_error"
        iterations_completed = 0

        research_agent = ResearchAgent(self.config)
        validation_agent = ValidationAgent(self.config)
        fix_agent = FixAgent(self.config)

        current = research_agent.run(classification)
        files += paths.write_stage("first_run", current, current.markdown_report)

        for iteration in range(1, self.config.max_iterations + 1):
            iterations_completed = iteration
            validation = validation_agent.run(
                classification=classification,
                report=current,
                iteration=iteration,
            )
            files += paths.write_stage(
                f"validation{iteration}",
                validation,
                validation.markdown_report,
            )

            stop, reason = self._should_stop(validation)
            if stop:
                stopped_reason = reason
                break

            fixed = fix_agent.run(
                classification=classification,
                report=current,
                validation=validation,
                iteration=iteration,
            )
            files += paths.write_stage(
                f"validation-fix{iteration}",
                fixed,
                fixed.markdown_report,
            )
            current = fixed
        else:
            stopped_reason = "max_iterations_reached"

        final_markdown = current.markdown_report
        chart_paths: list[Path] = []
        if self.config.include_charts:
            chart_paths = create_reliable_charts(current, paths.symbol_dir)
            final_markdown = append_chart_links(final_markdown, chart_paths)
            files += chart_paths

        files.append(paths.write_markdown(f"{classification.symbol}-final.md", final_markdown))
        final_as_stage = StageOutput(
            symbol=current.symbol,
            security_type=current.security_type,
            stage="final",
            iteration=current.iteration,
            markdown_report=final_markdown,
            structured_data=current.structured_data,
        )
        files += paths.write_stage("final", final_as_stage, final_markdown)[1:]

        if self.config.create_pdf:
            pdf_path = paths.symbol_dir / f"{classification.symbol}-final.pdf"
            try:
                files.append(markdown_to_pdf(final_markdown, pdf_path, title=f"{classification.symbol} Research"))
            except RuntimeError as exc:
                error_path = paths.symbol_dir / f"{classification.symbol}-final-pdf-error.txt"
                error_path.write_text(str(exc), encoding="utf-8")
                files.append(error_path)

        manifest = RunManifest(
            symbol=classification.symbol,
            security_type=classification.security_type,
            name=classification.name,
            exchange=classification.exchange,
            cik=classification.cik,
            max_iterations=self.config.max_iterations,
            iterations_completed=iterations_completed,
            stopped_reason=stopped_reason,  # type: ignore[arg-type]
            files=[str(path) for path in files],
            models={
                "orchestrator": self.config.model.orchestrator,
                "research": self.config.model.research,
                "validation": self.config.model.validation,
                "fix": self.config.model.fix,
                "json_repair": self.config.model.json_repair,
            },
        )
        files.append(paths.write_json("run_manifest.json", manifest))
        return manifest

    @staticmethod
    def _should_stop(validation: ValidationStageOutput) -> tuple[bool, str]:
        return should_stop_validation(validation)
