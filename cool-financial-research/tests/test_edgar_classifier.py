import requests
import pytest

from cool_financial_research.providers import ClassificationError
from cool_financial_research.providers.edgar import EdgarClassifier


def test_classification_fails_when_recent_submissions_fetch_fails(monkeypatch):
    classifier = EdgarClassifier(user_agent="test-agent")

    monkeypatch.setattr(
        classifier,
        "_find_ticker",
        lambda symbol: {
            "cik": "320193",
            "name": "Apple Inc.",
            "ticker": symbol,
            "exchange": "Nasdaq",
        },
    )

    def raise_request_error(cik: str):
        raise requests.RequestException("SEC unavailable")

    monkeypatch.setattr(classifier, "_recent_forms", raise_request_error)

    with pytest.raises(ClassificationError, match="Could not fetch recent SEC submissions"):
        classifier.classify("AAPL")
