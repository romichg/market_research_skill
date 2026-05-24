from __future__ import annotations

from abc import ABC, abstractmethod

from cool_financial_research.schemas import SecurityClassification


class ClassificationError(RuntimeError):
    pass


class SecurityClassifier(ABC):
    @abstractmethod
    def classify(self, symbol: str) -> SecurityClassification:
        raise NotImplementedError
