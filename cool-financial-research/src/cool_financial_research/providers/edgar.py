from __future__ import annotations

import re
from typing import Any

import requests

from cool_financial_research.schemas import SecurityClassification, SecurityType
from cool_financial_research.providers.base import ClassificationError, SecurityClassifier

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

ETF_FORMS = {
    "N-1A",
    "485BPOS",
    "485APOS",
    "N-CSR",
    "N-CSRS",
    "NPORT-P",
    "N-CEN",
    "497",
    "497K",
}
ADR_FORMS = {"F-6", "F-6EF", "20-F", "6-K", "F-1", "F-3"}
EQUITY_FORMS = {"10-K", "10-Q", "8-K", "DEF 14A", "S-1"}
ADR_NAME_RE = re.compile(r"\b(ADR|ADS|AMERICAN DEPOSITARY|DEPOSITARY SHARES|SPONSORED)\b", re.I)


class EdgarClassifier(SecurityClassifier):
    """Classify US-listed equities, ADRs, and ETFs using public SEC metadata.

    The SEC ticker file gives symbol/name/exchange/CIK. The filings feed is then used as a
    heuristic to split operating companies from registered funds and ADR issuers. If the
    evidence is ambiguous, this class raises ClassificationError rather than guessing.
    """

    def __init__(self, user_agent: str, timeout: int = 30) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"})
        self.timeout = timeout

    def classify(self, symbol: str) -> SecurityClassification:
        symbol = symbol.upper().strip().replace(".", "-")
        row = self._find_ticker(symbol)
        cik = str(row["cik"]).zfill(10)
        try:
            forms = self._recent_forms(cik)
        except requests.RequestException as exc:
            raise ClassificationError(
                f"Could not fetch recent SEC submissions for {symbol}; classification is unavailable."
            ) from exc
        name = row.get("name")
        exchange = row.get("exchange")

        is_etf = len(forms & ETF_FORMS) >= 2 and not (forms & EQUITY_FORMS)
        is_adr = bool(ADR_NAME_RE.search(name or "")) or bool(forms & ADR_FORMS)

        if is_etf:
            return SecurityClassification(
                symbol=symbol,
                security_type=SecurityType.etf,
                name=name,
                exchange=exchange,
                cik=cik,
                is_adr=False,
                confidence="medium",
                source="SEC company_tickers_exchange.json + submissions forms heuristic",
                notes=["Classified as ETF/fund because recent SEC forms include registered-fund forms."],
            )
        if is_adr:
            return SecurityClassification(
                symbol=symbol,
                security_type=SecurityType.adr,
                name=name,
                exchange=exchange,
                cik=cik,
                is_adr=True,
                confidence="medium",
                source="SEC company_tickers_exchange.json + submissions forms/name heuristic",
                notes=["Classified as ADR because filings/name indicate depositary or foreign issuer forms."],
            )
        if forms & EQUITY_FORMS or not forms & ETF_FORMS:
            return SecurityClassification(
                symbol=symbol,
                security_type=SecurityType.equity,
                name=name,
                exchange=exchange,
                cik=cik,
                is_adr=False,
                confidence="medium" if forms else "low",
                source="SEC company_tickers_exchange.json + submissions forms heuristic",
                notes=["Classified as equity/operating company. Override with --security-type if needed."],
            )

        raise ClassificationError(
            f"Could not reliably classify {symbol} as equity, ADR, or ETF from SEC metadata."
        )

    def _find_ticker(self, symbol: str) -> dict[str, Any]:
        response = self.session.get(SEC_TICKERS_URL, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        fields = payload.get("fields", [])
        for entry in payload.get("data", []):
            row = dict(zip(fields, entry))
            if str(row.get("ticker", "")).upper() == symbol:
                return {
                    "cik": row.get("cik"),
                    "name": row.get("name"),
                    "ticker": row.get("ticker"),
                    "exchange": row.get("exchange"),
                }
        raise ClassificationError(f"{symbol} was not found in the SEC ticker/exchange mapping.")

    def _recent_forms(self, cik: str) -> set[str]:
        response = self.session.get(SEC_SUBMISSIONS_URL.format(cik=cik), timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        forms = data.get("filings", {}).get("recent", {}).get("form", [])
        return {str(form).upper() for form in forms[:80]}
