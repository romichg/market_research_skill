from __future__ import annotations

from cool_financial_research.providers.base import ClassificationError, SecurityClassifier
from cool_financial_research.schemas import SecurityClassification


class PaidProviderClassifier(SecurityClassifier):
    """Extension point for FMP, Polygon, FactSet, Bloomberg, etc.

    Implement this class by calling a paid provider's reference-data endpoint and returning
    SecurityClassification. The orchestrator will fall back to EDGAR if this provider raises.
    """

    def __init__(self, provider_name: str) -> None:
        self.provider_name = provider_name

    def classify(self, symbol: str) -> SecurityClassification:
        raise ClassificationError(
            f"Paid provider '{self.provider_name}' is configured but no adapter is implemented yet."
        )
