#!/usr/bin/env python3
"""Deterministic helpers for the Cool Financial Research OpenClaw skill.

This script intentionally performs no LLM calls and reads no API key from .env.
OpenClaw remains the LLM harness; this helper only handles classification,
filesystem layout, JSON validation/stop logic, and PDF rendering fallbacks.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import urllib.error
import urllib.request
import zlib
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, Literal

BASE_DIR = Path(__file__).resolve().parents[2]  # package root when imported from src/cool_financial_research
DEFAULT_OUTPUT_ROOT = Path("./cool-financial-research")
SEC_COMPANY_TICKERS_EXCHANGE = "https://www.sec.gov/files/company_tickers_exchange.json"
SEC_FUND_TICKERS = "https://www.sec.gov/files/company_tickers_mf.json"
SEC_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_COMPANYFACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

SecurityType = Literal["equity", "adr", "etf"]

ETF_NAME_MARKERS = (
    " ETF",
    "EXCHANGE TRADED FUND",
    "ISHARES",
    "VANGUARD ",
    "SPDR ",
    "SELECT SECTOR SPDR",
    "INVESCO ",
    "DIREXION ",
    "PROSHARES ",
    "GLOBAL X ",
    "FIRST TRUST ",
    "WISDOMTREE ",
    "SCHWAB ",
    "ARK ",
    "JANUS HENDERSON",
    "FRANKLIN ",
    "FIDELITY ",
    "BITWISE ",
    "GRAYSCALE ",
    "ETF TRUST",
    "INDEX FUND",
    "TRUST SERIES",
    "EXCHANGE-TRADED FUND",
    "ETF SERIES",
)
ADR_NAME_MARKERS = (
    " ADR",
    " ADS",
    " AMERICAN DEPOSITARY",
    " DEPOSITARY SHARES",
    " SPONSORED ADR",
    " SPONSORED ADS",
)
FOREIGN_ISSUER_FORMS = {"20-F", "40-F", "6-K", "F-1", "F-3", "F-4", "F-6"}
SYMBOL_RE = re.compile(r"^[A-Za-z0-9.\-]{1,12}$")

# Conservative issuer/product hints for ETF source discovery. Keep this small and
# auditable; users can pass --ishares-product-id or --issuer-product-map for more.
ISHARES_PRODUCT_HINTS: dict[str, dict[str, str]] = {
    "ECH": {
        "issuer": "ishares",
        "product_id": "239618",
        "slug": "ishares-msci-chile-capped-etf",
        "fund_name": "iShares MSCI Chile ETF",
    }
}

OPERATIONAL_CATEGORIES = {
    "helper_error",
    "missing_dependency",
    "subagent_no_artifact",
    "source_wrong_content_type",
    "pdf_render_fallback",
    "pdf_extract_unavailable",
    "data_unavailable",
    "classification_fallback",
}


@dataclass
class Classification:
    symbol: str
    security_type: SecurityType
    name: str | None
    exchange: str | None
    cik: str | None
    is_adr: bool
    confidence: Literal["high", "medium", "low"]
    source: str
    notes: list[str]


def _json_dump(obj: Any) -> None:
    print(json.dumps(obj, indent=2, sort_keys=True))


def _die(message: str, code: int = 2) -> None:
    print(json.dumps({"error": message}, indent=2), file=sys.stderr)
    raise SystemExit(code)


def normalize_symbol(symbol: str) -> str:
    symbol = symbol.strip().upper()
    if not SYMBOL_RE.match(symbol):
        _die(f"Invalid symbol format: {symbol!r}. Expected 1-12 ticker characters.")
    return symbol


def safe_snippet(data: bytes, limit: int = 500) -> str:
    return data[:limit].decode("utf-8", errors="replace").replace("\x00", "")


def decode_http_body(data: bytes, *, content_encoding: str | None = None) -> bytes:
    """Decode common HTTP encodings, including servers that forget headers."""
    enc = (content_encoding or "").lower()
    if "gzip" in enc or data.startswith(b"\x1f\x8b"):
        return gzip.decompress(data)
    if "deflate" in enc:
        try:
            return zlib.decompress(data)
        except zlib.error:
            return zlib.decompress(data, -zlib.MAX_WBITS)
    return data


def fetch_bytes(url: str, *, user_agent: str, timeout: int = 30, accept: str = "*/*") -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Accept": accept,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed SEC/configured/explicit URL input
            raw = resp.read()
            headers = dict(resp.headers.items())
            body = decode_http_body(raw, content_encoding=headers.get("Content-Encoding"))
            return {
                "url": url,
                "status": getattr(resp, "status", None),
                "content_type": headers.get("Content-Type", ""),
                "content_encoding": headers.get("Content-Encoding", ""),
                "bytes": len(body),
                "body": body,
                "headers": headers,
            }
    except urllib.error.HTTPError as exc:
        raw = exc.read() if hasattr(exc, "read") else b""
        try:
            body = decode_http_body(raw, content_encoding=exc.headers.get("Content-Encoding") if exc.headers else None)
        except Exception:
            body = raw
        _die(
            f"Could not fetch {url}: HTTP {exc.code}; content-type={exc.headers.get('Content-Type') if exc.headers else 'unknown'}; snippet={safe_snippet(body)}"
        )
    except (urllib.error.URLError, TimeoutError) as exc:
        _die(f"Could not fetch {url}: {exc}")


def fetch_json(url: str, *, user_agent: str, timeout: int = 30) -> Any:
    meta = fetch_bytes(url, user_agent=user_agent, timeout=timeout, accept="application/json,text/plain,*/*")
    body = meta["body"]
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        _die(
            f"Could not parse JSON from {url}: {exc}; status={meta.get('status')}; content-type={meta.get('content_type')}; bytes={meta.get('bytes')}; snippet={safe_snippet(body)}"
        )


def looks_like_html(data: bytes, content_type: str = "") -> bool:
    head = data[:1024].lstrip().lower()
    return "html" in (content_type or "").lower() or head.startswith(b"<!doctype html") or head.startswith(b"<html") or b"<body" in head[:300]


def looks_like_csv(data: bytes, content_type: str = "") -> bool:
    if looks_like_html(data, content_type):
        return False
    text = safe_snippet(data, 2000)
    first = text.splitlines()[0] if text.splitlines() else ""
    return "," in first or "text/csv" in (content_type or "").lower() or "application/vnd.ms-excel" in (content_type or "").lower()


def load_paid_mapping(path: Path, symbol: str) -> Classification:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        _die(f"Could not read paid-provider config JSON {path}: {exc}")
    record = payload.get(symbol) or payload.get(symbol.upper())
    if not record:
        _die(f"Paid-provider config had no classification for {symbol}")
    security_type = record.get("security_type")
    if security_type not in {"equity", "adr", "etf"}:
        _die(f"Paid-provider classification for {symbol} must be equity, adr, or etf")
    return Classification(
        symbol=symbol,
        security_type=security_type,
        name=record.get("name"),
        exchange=record.get("exchange"),
        cik=str(record.get("cik")).zfill(10) if record.get("cik") is not None else None,
        is_adr=bool(record.get("is_adr", security_type == "adr")),
        confidence=record.get("confidence", "high"),
        source=f"paid-json:{path}",
        notes=list(record.get("notes", [])),
    )


def fetch_recent_forms(cik: str, *, user_agent: str) -> list[str]:
    payload = fetch_json(SEC_SUBMISSIONS.format(cik=cik), user_agent=user_agent)
    recent = payload.get("filings", {}).get("recent", {})
    forms = recent.get("form") or []
    return [str(f).upper() for f in forms[:200]]


def _record_to_classification(symbol: str, record: dict[str, Any], *, source: str, security_type: SecurityType = "etf", confidence: Literal["high", "medium", "low"] = "medium", notes: list[str] | None = None) -> Classification:
    cik = record.get("cik") or record.get("cik_str") or record.get("cik_str")
    return Classification(
        symbol=symbol,
        security_type=security_type,
        name=record.get("name") or record.get("companyName") or record.get("seriesName") or record.get("className") or record.get("fund_name"),
        exchange=record.get("exchange") or record.get("exchangeName"),
        cik=str(cik).zfill(10) if cik is not None else None,
        is_adr=security_type == "adr",
        confidence=confidence,
        source=source,
        notes=notes or [],
    )


def classify_with_fund_tickers(symbol: str, *, user_agent: str) -> Classification | None:
    """Try SEC mutual fund / ETF ticker dataset when company ticker map misses ETFs."""
    try:
        payload = fetch_json(SEC_FUND_TICKERS, user_agent=user_agent)
    except SystemExit:
        return None
    rows: list[dict[str, Any]] = []
    if isinstance(payload, dict) and "data" in payload and "fields" in payload:
        fields = payload.get("fields") or []
        for row in payload.get("data") or []:
            if len(row) >= len(fields):
                rows.append({str(k): v for k, v in zip(fields, row)})
    elif isinstance(payload, dict):
        # SEC has changed shapes over time. Accept dict-of-records too.
        for value in payload.values():
            if isinstance(value, dict):
                rows.append(value)
    elif isinstance(payload, list):
        rows = [r for r in payload if isinstance(r, dict)]
    matches = []
    for row in rows:
        ticker_values = [row.get(k) for k in ("ticker", "Ticker", "classTicker", "class_ticker", "symbol")]
        if any(str(v).upper() == symbol for v in ticker_values if v is not None):
            matches.append(row)
    if not matches:
        return None
    if len(matches) > 1:
        names = [str(m.get("seriesName") or m.get("name") or m.get("className") or m)[:120] for m in matches]
        _die(f"Fund/ETF classification ambiguous: {symbol} matched multiple SEC fund records: {names}")
    rec = matches[0]
    return _record_to_classification(
        symbol,
        rec,
        source="SEC company_tickers_mf.json",
        security_type="etf",
        confidence="medium",
        notes=[
            "Classified using SEC fund ticker dataset after company_tickers_exchange lookup missed or did not apply.",
            "ETF/fund status must be verified against issuer prospectus/fact sheet during research.",
        ],
    )


def override_classification(symbol: str, security_type: SecurityType, *, reason: str) -> Classification:
    return Classification(
        symbol=symbol,
        security_type=security_type,
        name=None,
        exchange=None,
        cik=None,
        is_adr=security_type == "adr",
        confidence="low",
        source="user_override",
        notes=[reason, "Override permits source bundling to proceed, but report must verify classification from primary/issuer/exchange data."],
    )


def classify_with_edgar(symbol: str, *, user_agent: str, enrich_submissions: bool = True) -> Classification:
    payload = fetch_json(SEC_COMPANY_TICKERS_EXCHANGE, user_agent=user_agent)
    fields = payload.get("fields") or []
    data = payload.get("data") or []
    if not fields or not data:
        _die("SEC company_tickers_exchange.json did not contain fields/data")
    try:
        ticker_idx = fields.index("ticker")
        name_idx = fields.index("name")
        cik_idx = fields.index("cik")
        exchange_idx = fields.index("exchange")
    except ValueError as exc:
        _die(f"SEC ticker payload missing required field: {exc}")

    matches = [row for row in data if str(row[ticker_idx]).upper() == symbol]
    if not matches:
        fund_result = classify_with_fund_tickers(symbol, user_agent=user_agent)
        if fund_result is not None:
            fund_result.notes.insert(0, f"{symbol} was not found in SEC company_tickers_exchange.json; used ETF/fund fallback.")
            return fund_result
        _die(
            f"Classification failed: {symbol} was not found in SEC company ticker or fund ticker datasets. "
            "If the user already knows the security type, rerun with --mode/--security-type equity|adr|etf; otherwise stop with an ambiguity error."
        )
    if len(matches) > 1:
        names = [str(row[name_idx]) for row in matches]
        _die(f"Classification ambiguous: {symbol} matched multiple SEC records: {names}")

    row = matches[0]
    name = str(row[name_idx])
    exchange = str(row[exchange_idx]) if row[exchange_idx] is not None else None
    cik = str(row[cik_idx]).zfill(10) if row[cik_idx] is not None else None
    upper_name = f" {name.upper()} "
    notes = ["Classified using SEC company_tickers_exchange.json."]

    if any(marker in upper_name for marker in ETF_NAME_MARKERS):
        security_type: SecurityType = "etf"
        is_adr = False
        confidence: Literal["high", "medium", "low"] = "medium"
        notes.append("ETF classification uses name-marker heuristic; verify against issuer/prospectus during research.")
    elif any(marker in upper_name for marker in ADR_NAME_MARKERS):
        security_type = "adr"
        is_adr = True
        confidence = "high"
    else:
        security_type = "equity"
        is_adr = False
        confidence = "medium"
        notes.append("Defaulted to equity because SEC record did not match ETF/ADR markers.")

    # ADR names often omit ADS/ADR in the SEC ticker map. If recent filings are foreign-issuer
    # forms, classify as ADR for this skill but require the research agent to verify depositary receipt status.
    if enrich_submissions and cik and security_type == "equity":
        try:
            forms = set(fetch_recent_forms(cik, user_agent=user_agent))
        except SystemExit:
            raise
        except Exception:  # pragma: no cover - defensive; fetch_json exits on most errors
            forms = set()
        if forms.intersection(FOREIGN_ISSUER_FORMS):
            security_type = "adr"
            is_adr = True
            confidence = "medium"
            notes.append(
                "Recent SEC submissions include foreign-issuer forms; classified as ADR/foreign listing for routing. Research must verify ADS/ADR status from filings or exchange data."
            )

    return Classification(symbol, security_type, name, exchange, cik, is_adr, confidence, "SEC", notes)


def cmd_classify(args: argparse.Namespace) -> None:
    symbol = normalize_symbol(args.symbol)
    mode = args.mode
    if args.provider == "paid-json":
        if not args.paid_provider_config:
            _die("--provider paid-json requires --paid-provider-config")
        result = load_paid_mapping(Path(args.paid_provider_config), symbol)
        if mode != "auto":
            result.security_type = mode
            result.is_adr = mode == "adr"
            result.confidence = "high"
            result.notes.append(f"Security type overridden by requested mode: {mode}")
    else:
        if mode != "auto":
            # Explicit user/skill security-type overrides must never be blocked by public classifier gaps.
            # Research and validation must verify the classification from issuer/exchange/filing sources.
            result = override_classification(symbol, mode, reason=f"Security type explicitly overridden by user/skill: {mode}.")
            result.confidence = "low"
        else:
            result = classify_with_edgar(symbol, user_agent=args.sec_user_agent, enrich_submissions=not args.no_edgar_enrich)

    _json_dump(asdict(result))


def symbol_dir(output_root: Path, symbol: str) -> Path:
    return output_root / normalize_symbol(symbol)


def cmd_init_run(args: argparse.Namespace) -> None:
    symbol = normalize_symbol(args.symbol)
    root = Path(args.output_root)
    out = symbol_dir(root, symbol)
    out.mkdir(parents=True, exist_ok=True)
    manifest = {
        "symbol": symbol,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(out),
        "max_iterations": min(args.max_iterations, 5),
        "files": sorted(str(p) for p in out.rglob("*") if p.is_file()),
        "stopped_reason": None,
        "unresolved_issues": [],
        "data_gap_assessment": None,
        "provider_recommendation_snapshot": None,
        "preflight": None,
        "operational_issues": [],
        "artifact_compliance": {
            "research_artifacts_written_by_child": None,
            "validation_artifacts_written_by_child": None,
            "fix_artifacts_written_by_child": None,
            "repair_attempts": 0,
            "artifact_sources": {}
        },
        "quality_gates": {
            "intermediate_files_preserved": True,
            "validation_counts_checked": True,
            "fix_coverage_checked": True,
            "artifact_files_checked": True,
            "preflight_recorded": False,
        },
    }
    (out / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _json_dump(manifest)


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        _die(f"Could not read JSON from {path}: {exc}")


def blocking_issue_ids(validation_payload: dict[str, Any]) -> set[str]:
    issues = validation_payload.get("structured_data", {}).get("issues", []) or []
    return {
        str(i.get("id"))
        for i in issues
        if i.get("severity") in {"critical", "moderate"} and i.get("status") == "open" and i.get("id")
    }


def validate_fix_coverage(research_payload: dict[str, Any], previous_validation_payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    stage = research_payload.get("stage")
    if stage != "fix":
        return errors
    required_ids = blocking_issue_ids(previous_validation_payload)
    fix_response = (research_payload.get("structured_data") or {}).get("fix_response") or {}
    addressed = fix_response.get("addressed_issues") or []
    addressed_by_id = {str(i.get("issue_id")): i for i in addressed if i.get("issue_id")}
    missing = sorted(required_ids - set(addressed_by_id))
    if missing:
        errors.append(f"fix_response missing prior open critical/moderate issue ids: {missing}")
    for issue_id in required_ids.intersection(addressed_by_id):
        status = addressed_by_id[issue_id].get("status")
        if status not in {"fixed", "unresolved_data_unavailable"}:
            errors.append(f"fix_response issue {issue_id} has invalid status: {status}")
    return errors


def validate_validation_counts(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    sd = payload.get("structured_data") or {}
    issues = sd.get("issues") or []
    if not isinstance(issues, list):
        return ["structured_data.issues must be a list"]
    counts = Counter(i.get("severity") for i in issues)
    expected = {
        "critical": int(sd.get("critical_count", 0)),
        "moderate": int(sd.get("moderate_count", 0)),
        "minor": int(sd.get("minor_count", 0)),
    }
    for sev, count in expected.items():
        if counts.get(sev, 0) != count:
            errors.append(f"{sev}_count={count} does not match issues list count={counts.get(sev, 0)}")
    ids = [i.get("id") for i in issues]
    if any(not x for x in ids):
        errors.append("every validation issue must include a stable non-empty id")
    dupes = sorted({x for x in ids if x and ids.count(x) > 1})
    if dupes:
        errors.append(f"duplicate validation issue ids: {dupes}")
    unresolved = sd.get("unresolved_due_to_data_unavailable") or []
    unresolved_ids = {i.get("id") for i in unresolved if i.get("id")}
    issue_unresolved_ids = {i.get("id") for i in issues if i.get("status") == "unresolved_data_unavailable"}
    if unresolved_ids != issue_unresolved_ids:
        errors.append(
            "unresolved_due_to_data_unavailable ids must exactly match issues with status unresolved_data_unavailable"
        )
    for issue in issues:
        if issue.get("severity") in {"critical", "moderate"} and issue.get("status") == "deferred":
            errors.append(f"critical/moderate issue cannot be deferred: {issue.get('id')}")
        if issue.get("status") == "unresolved_data_unavailable" and not issue.get("unresolved_reason"):
            errors.append(f"unresolved issue missing unresolved_reason: {issue.get('id')}")
    return errors


def validate_research_quality(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    sd = payload.get("structured_data") or {}
    qc = sd.get("quality_control") or {}
    for flag in [
        "primary_sources_preferred",
        "facts_interpretation_separated",
        "quant_claims_sourced_or_marked_unverified",
        "stale_data_flagged",
    ]:
        if qc.get(flag) is not True:
            errors.append(f"quality_control.{flag} must be true")
    sections = sd.get("sections") or []
    source_ids = {s.get("id") for s in sd.get("sources", []) if isinstance(s, dict)}
    for section in sections if isinstance(sections, list) else []:
        if not isinstance(section.get("quantitative_claims", []), list):
            errors.append(f"section {section.get('number')} quantitative_claims must be a list")
            continue
        for idx, claim in enumerate(section.get("quantitative_claims", [])):
            if not isinstance(claim, dict):
                errors.append(f"section {section.get('number')} quantitative_claims[{idx}] must be an object")
                continue
            status = claim.get("verification_status")
            source_id = claim.get("source_id")
            confidence = claim.get("confidence")
            if status in {"verified_primary", "verified_secondary"} and not source_id:
                errors.append(f"verified claim missing source_id in section {section.get('number')}: {claim.get('claim_text')}")
            if source_id and source_ids and source_id not in source_ids:
                errors.append(f"claim source_id not found in top-level sources: {source_id}")
            if status in {"unverified", "not_available"} and confidence != "unverified":
                errors.append(f"unverified/not_available claim must use confidence=unverified: {claim.get('claim_text')}")
            if claim.get("stale") is True and not claim.get("staleness_reason"):
                errors.append(f"stale claim missing staleness_reason: {claim.get('claim_text')}")
    return errors


def minimal_validate(schema_name: str, payload: Any, previous_validation: Any | None = None) -> list[str]:
    """Small stdlib validator for fields the OpenClaw loop relies on.

    OpenClaw/sub-agents can use the full JSON Schema files for generation; this
    helper keeps runtime dependencies low and validates required loop fields plus
    quality gates that JSON Schema cannot easily express.
    """
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["payload is not a JSON object"]
    for field in ["symbol", "security_type", "stage", "iteration", "markdown_report", "structured_data"]:
        if field not in payload:
            errors.append(f"missing required field: {field}")
    if errors:
        return errors

    if schema_name == "validation":
        if payload.get("stage") != "validation":
            errors.append("stage must be validation")
        sd = payload.get("structured_data", {})
        for field in [
            "critical_count",
            "moderate_count",
            "minor_count",
            "issues",
            "unresolved_due_to_data_unavailable",
            "sources_checked",
            "data_freshness_audit",
            "data_gaps",
        ]:
            if field not in sd:
                errors.append(f"structured_data missing required field: {field}")
        for issue in sd.get("issues", []) if isinstance(sd.get("issues", []), list) else []:
            if issue.get("severity") not in {"critical", "moderate", "minor"}:
                errors.append(f"invalid issue severity: {issue.get('severity')}")
            if issue.get("status") not in {"open", "unresolved_data_unavailable", "deferred"}:
                errors.append(f"invalid issue status: {issue.get('status')}")
        errors.extend(validate_validation_counts(payload))
        valid_gap_categories = set(GAP_CATEGORIES) | {"other"}
        for gap in sd.get("data_gaps", []) if isinstance(sd.get("data_gaps", []), list) else []:
            if gap.get("category") not in valid_gap_categories:
                errors.append(f"invalid data_gap category: {gap.get('category')}")
            if not gap.get("why_free_sources_were_insufficient"):
                errors.append("data_gap missing why_free_sources_were_insufficient")
            if not isinstance(gap.get("potential_paid_services", []), list):
                errors.append("data_gap.potential_paid_services must be a list")
    elif schema_name == "research":
        if payload.get("stage") not in {"research", "fix", "final"}:
            errors.append("stage must be research, fix, or final")
        sd = payload.get("structured_data", {})
        for field in ["quality_control", "sections", "sources", "open_questions", "unresolved_issues"]:
            if field not in sd:
                errors.append(f"structured_data missing required field: {field}")
        sections = sd.get("sections", [])
        if not isinstance(sections, list) or len(sections) < 16:
            errors.append("structured_data.sections must contain at least 16 sections")
        errors.extend(validate_research_quality(payload))
        if previous_validation is not None:
            errors.extend(validate_fix_coverage(payload, previous_validation))
    else:
        errors.append(f"unknown schema name: {schema_name}")
    return errors


def cmd_validate_json(args: argparse.Namespace) -> None:
    payload = read_json(Path(args.json_file))
    previous_validation = read_json(Path(args.previous_validation)) if args.previous_validation else None
    errors = minimal_validate(args.schema, payload, previous_validation)
    result = {"valid": not errors, "errors": errors, "file": args.json_file, "schema": args.schema}
    _json_dump(result)
    if errors:
        raise SystemExit(1)


def validation_stop_result(payload: dict[str, Any]) -> dict[str, Any]:
    sd = payload.get("structured_data") or {}
    issues = sd.get("issues") or []
    blocking = [i for i in issues if i.get("severity") in {"critical", "moderate"}]
    open_fixable = [i for i in blocking if i.get("status", "open") == "open"]
    unresolved_only = bool(blocking) and not open_fixable and all(
        i.get("status") == "unresolved_data_unavailable" for i in blocking
    )
    counts_zero = int(sd.get("critical_count", 0)) == 0 and int(sd.get("moderate_count", 0)) == 0
    if not blocking and counts_zero:
        return {"should_stop": True, "reason": "no_blocking_issues", "open_fixable_blocking_issues": 0}
    if unresolved_only:
        return {"should_stop": True, "reason": "only_unresolved_data_unavailable", "open_fixable_blocking_issues": 0}
    return {
        "should_stop": False,
        "reason": "fixable_blocking_issues_remain",
        "open_fixable_blocking_issues": len(open_fixable),
    }


def cmd_check_stop(args: argparse.Namespace) -> None:
    payload = read_json(Path(args.validation_json))
    count_errors = validate_validation_counts(payload)
    if count_errors:
        _json_dump({"should_stop": False, "reason": "invalid_validation_json", "errors": count_errors})
        raise SystemExit(1)
    result = validation_stop_result(payload)
    _json_dump(result)
    if result["should_stop"]:
        return
    raise SystemExit(1)


def cmd_prompts(args: argparse.Namespace) -> None:
    security_type = args.security_type
    if security_type in {"equity", "adr"}:
        names = ["equity-research.md", "equity-validation.md", "equity-research-fix-validation.md"]
    elif security_type == "etf":
        names = ["etf-research.md", "etf-validation.md", "etf-research-fix-validation.md"]
    else:
        _die(f"unknown security type: {security_type}")
    _json_dump({"security_type": security_type, "prompts": [str(BASE_DIR / "prompts" / n) for n in names]})


def simple_markdown_to_html(markdown: str, title: str) -> str:
    html_lines = [
        "<!doctype html>",
        "<html><head><meta charset='utf-8'>",
        f"<title>{escape(title)}</title>",
        "<style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;line-height:1.45;max-width:960px;margin:40px auto;padding:0 24px;} table{border-collapse:collapse;width:100%;} th,td{border:1px solid #ccc;padding:6px;vertical-align:top;} code,pre{background:#f6f8fa;} pre{padding:12px;overflow:auto;} h1,h2,h3{page-break-after:avoid;} img{max-width:100%;}</style>",
        "</head><body>",
    ]
    in_code = False
    for raw in markdown.splitlines():
        line = raw.rstrip("\n")
        if line.startswith("```"):
            html_lines.append("</code></pre>" if in_code else "<pre><code>")
            in_code = not in_code
            continue
        if in_code:
            html_lines.append(escape(line))
            continue
        if line.startswith("# "):
            html_lines.append(f"<h1>{escape(line[2:].strip())}</h1>")
        elif line.startswith("## "):
            html_lines.append(f"<h2>{escape(line[3:].strip())}</h2>")
        elif line.startswith("### "):
            html_lines.append(f"<h3>{escape(line[4:].strip())}</h3>")
        elif line.startswith("- "):
            html_lines.append(f"<p>• {escape(line[2:].strip())}</p>")
        elif not line.strip():
            html_lines.append("<br>")
        else:
            html_lines.append(f"<p>{escape(line)}</p>")
    if in_code:
        html_lines.append("</code></pre>")
    html_lines.append("</body></html>")
    return "\n".join(html_lines)


def cmd_render_pdf(args: argparse.Namespace) -> None:
    md_path = Path(args.markdown_file)
    pdf_path = Path(args.pdf_file)
    markdown = md_path.read_text(encoding="utf-8")
    title = args.title or md_path.stem
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    status: dict[str, Any] = {
        "pdf_created": False,
        "html_created": False,
        "pdf": str(pdf_path),
        "html": None,
        "method": None,
        "missing_dependencies": [],
        "errors": [],
    }

    try:
        from markdown import markdown as markdown_to_html  # type: ignore
        from weasyprint import HTML  # type: ignore

        html = markdown_to_html(markdown, extensions=["tables", "fenced_code", "toc"])
        HTML(string=f"<html><body>{html}</body></html>", base_url=str(md_path.parent)).write_pdf(str(pdf_path))
        status.update({"pdf_created": True, "method": "weasyprint"})
        _json_dump(status)
        return
    except Exception as exc:  # noqa: BLE001
        status["errors"].append(f"weasyprint: {exc}")
        if not module_available("markdown"):
            status["missing_dependencies"].append("python package: markdown")
        if not module_available("weasyprint"):
            status["missing_dependencies"].append("python package: weasyprint")

    if shutil.which("pandoc"):
        try:
            subprocess.run(["pandoc", str(md_path), "-o", str(pdf_path)], check=True, capture_output=True, text=True)
            status.update({"pdf_created": True, "method": "pandoc"})
            _json_dump(status)
            return
        except subprocess.CalledProcessError as exc:
            status["errors"].append(f"pandoc: {exc.stderr[-1000:]}")
    else:
        status["missing_dependencies"].append("binary: pandoc")

    html_path = pdf_path.with_suffix(".html")
    html_path.write_text(simple_markdown_to_html(markdown, title), encoding="utf-8")
    err_path = pdf_path.with_suffix(".pdf-error.txt")
    status.update({"html_created": True, "html": str(html_path), "method": "html-fallback", "error_file": str(err_path)})
    err_path.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    _json_dump(status)
    if not args.optional:
        raise SystemExit(3)


def unresolved_from_validation(validation_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not validation_payload:
        return []
    issues = validation_payload.get("structured_data", {}).get("issues") or []
    return [
        {
            "id": i.get("id"),
            "severity": i.get("severity"),
            "section": i.get("section"),
            "issue": i.get("issue"),
            "status": i.get("status"),
            "unresolved_reason": i.get("unresolved_reason"),
            "required_fix": i.get("required_fix"),
        }
        for i in issues
        if i.get("severity") in {"critical", "moderate"} and i.get("status") == "unresolved_data_unavailable"
    ]


def scan_files(out: Path) -> list[str]:
    if not out.exists():
        return []
    return sorted(str(p) for p in out.rglob("*") if p.is_file())



def append_operational_issue(output_root: Path, symbol: str, issue: dict[str, Any]) -> dict[str, Any]:
    out = symbol_dir(output_root, symbol)
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "run_manifest.json"
    manifest = read_json(manifest_path) if manifest_path.exists() else {"symbol": symbol, "files": []}
    issue = dict(issue)
    issue.setdefault("created_at", datetime.now(timezone.utc).isoformat())
    issue.setdefault("severity", "warning")
    issue.setdefault("category", "helper_error")
    if issue.get("category") not in OPERATIONAL_CATEGORIES:
        issue["category"] = "helper_error"
    manifest.setdefault("operational_issues", []).append(issue)
    manifest["files"] = scan_files(out)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def cmd_record_operational_issue(args: argparse.Namespace) -> None:
    symbol = normalize_symbol(args.symbol)
    issue = {
        "stage": args.stage,
        "severity": args.severity,
        "category": args.category,
        "issue": args.issue,
        "resolution": args.resolution,
    }
    manifest = append_operational_issue(Path(args.output_root), symbol, issue)
    _json_dump({"manifest": str(symbol_dir(Path(args.output_root), symbol) / "run_manifest.json"), "operational_issue_count": len(manifest.get("operational_issues", []))})


def set_artifact_compliance(output_root: Path, symbol: str, *, stage: str, ok: bool, source: str, repair_attempts: int = 0, notes: list[str] | None = None) -> dict[str, Any]:
    out = symbol_dir(output_root, symbol)
    manifest_path = out / "run_manifest.json"
    manifest = read_json(manifest_path) if manifest_path.exists() else {"symbol": symbol, "files": []}
    comp = manifest.setdefault("artifact_compliance", {})
    key = f"{stage}_artifacts_written_by_child"
    if stage in {"research", "validation", "fix"}:
        comp[key] = bool(ok) and source == "child"
    comp.setdefault("artifact_sources", {})[stage] = source
    comp["repair_attempts"] = int(comp.get("repair_attempts", 0)) + int(repair_attempts)
    if notes:
        comp.setdefault("notes", []).extend(notes)
    manifest["files"] = scan_files(out)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def cmd_verify_artifacts(args: argparse.Namespace) -> None:
    symbol = normalize_symbol(args.symbol)
    md_path = Path(args.markdown_file)
    json_path = Path(args.json_file)
    errors: list[str] = []
    if not md_path.exists() or md_path.stat().st_size == 0:
        errors.append(f"missing or empty markdown artifact: {md_path}")
    if not json_path.exists() or json_path.stat().st_size == 0:
        errors.append(f"missing or empty json artifact: {json_path}")
        payload = None
    else:
        payload = read_json(json_path)
        prev = read_json(Path(args.previous_validation)) if args.previous_validation else None
        errors.extend(minimal_validate(args.schema, payload, prev))
    ok = not errors
    source = args.artifact_source if ok else "missing_or_invalid"
    set_artifact_compliance(Path(args.output_root), symbol, stage=args.stage, ok=ok, source=source, repair_attempts=args.repair_attempts, notes=errors if errors else None)
    if errors:
        append_operational_issue(Path(args.output_root), symbol, {
            "stage": args.stage,
            "severity": "error",
            "category": "subagent_no_artifact",
            "issue": "; ".join(errors),
            "resolution": "Spawn artifact-repair sub-agent with exact expected paths and prior child output.",
        })
    _json_dump({"valid": ok, "errors": errors, "stage": args.stage, "markdown": str(md_path), "json": str(json_path)})
    if errors:
        raise SystemExit(1)


def module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def preflight_status(output_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    write_ok = False
    try:
        probe = output_root / ".cfr_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        write_ok = True
    except Exception:
        write_ok = False
    pdf_text = {
        "pdftotext": shutil.which("pdftotext") is not None,
        "pypdf": module_available("pypdf"),
        "PyPDF2": module_available("PyPDF2"),
        "pdfplumber": module_available("pdfplumber"),
    }
    pdf_render = {
        "markdown": module_available("markdown"),
        "weasyprint": module_available("weasyprint"),
        "pandoc": shutil.which("pandoc") is not None,
        "latex": any(shutil.which(x) for x in ["xelatex", "pdflatex", "lualatex"]),
    }
    capabilities = {
        "pdf_text_extraction_available": any(pdf_text.values()),
        "pdf_render_available": (pdf_render["markdown"] and pdf_render["weasyprint"]) or pdf_render["pandoc"],
        "html_fallback_available": True,
        "write_output_root": write_ok,
    }
    issues = []
    if not capabilities["pdf_text_extraction_available"]:
        issues.append({"category": "missing_dependency", "severity": "warning", "stage": "preflight", "issue": "PDF text extraction unavailable; prospectus/shareholder-report extraction may be quality-impacting.", "resolution": "Install pdftotext or one of pypdf/PyPDF2/pdfplumber, or provide extracted text manually."})
    if not capabilities["pdf_render_available"]:
        issues.append({"category": "missing_dependency", "severity": "warning", "stage": "preflight", "issue": "PDF rendering unavailable; HTML fallback will be produced.", "resolution": "Install markdown+weasyprint or pandoc+LaTeX to enable final PDF."})
    if not write_ok:
        issues.append({"category": "helper_error", "severity": "error", "stage": "preflight", "issue": f"Output root is not writable: {output_root}", "resolution": "Choose a writable --output-root."})
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version.split()[0],
        "output_root": str(output_root),
        "required": {"python3": True, "stdlib": True, "write_output_root": write_ok},
        "optional_pdf_text_tools": pdf_text,
        "optional_pdf_render_tools": pdf_render,
        "capabilities": capabilities,
        "operational_issues": issues,
    }


def cmd_preflight(args: argparse.Namespace) -> None:
    output_root = Path(args.output_root)
    status = preflight_status(output_root)
    if args.symbol:
        symbol = normalize_symbol(args.symbol)
        out = symbol_dir(output_root, symbol)
        out.mkdir(parents=True, exist_ok=True)
        (out / "preflight.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
        manifest_path = out / "run_manifest.json"
        manifest = read_json(manifest_path) if manifest_path.exists() else {"symbol": symbol, "files": []}
        manifest["preflight"] = str(out / "preflight.json")
        manifest.setdefault("operational_issues", []).extend(status["operational_issues"])
        manifest.setdefault("quality_gates", {})["preflight_recorded"] = True
        manifest["files"] = scan_files(out)
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _json_dump(status)
    if not status["required"]["write_output_root"]:
        raise SystemExit(1)



# ---------------------------------------------------------------------------
# Deterministic research-quality helpers
# ---------------------------------------------------------------------------

GAP_CATEGORIES: dict[str, dict[str, Any]] = {
    "fundamentals_valuation": {
        "label": "fundamentals, valuation, segments, and point-in-time financials",
        "patterns": [r"financial statement", r"fundamental", r"segment", r"revenue", r"margin", r"eps", r"fcf", r"cash flow", r"dcf", r"valuation", r"multiple", r"xbrl", r"10-k", r"10-q", r"guidance"],
    },
    "consensus_estimates": {
        "label": "analyst estimates, ratings, and price targets",
        "patterns": [r"analyst", r"consensus", r"estimate", r"price target", r"rating", r"upgrade", r"downgrade", r"revision"],
    },
    "transcripts_kpis": {
        "label": "earnings-call transcripts, investor events, slides, and operating KPIs",
        "patterns": [r"transcript", r"earnings call", r"conference call", r"q&a", r"management tone", r"kpi", r"slides", r"investor day"],
    },
    "etf_fund_analytics": {
        "label": "ETF holdings, AUM, NAV, premium/discount, tracking, distributions, and fund analytics",
        "patterns": [r"etf", r"holdings", r"aum", r"nav", r"premium", r"discount", r"tracking", r"expense ratio", r"distribution", r"yield", r"n-port", r"prospectus", r"fact sheet", r"index methodology"],
    },
    "options_derivatives": {
        "label": "options flow, volatility surface, put/call skew, and gamma positioning",
        "patterns": [r"option", r"put/call", r"gamma", r"implied vol", r"iv", r"skew", r"sweep", r"open interest", r"derivative"],
    },
    "short_interest_borrow": {
        "label": "short interest, securities lending, borrow cost, and utilization",
        "patterns": [r"short interest", r"days-to-cover", r"borrow", r"utilization", r"securities lending", r"lendable", r"rebate"],
    },
    "market_data_technicals": {
        "label": "market data, technical indicators, spreads, and intraday/near-real-time pricing",
        "patterns": [r"price", r"volume", r"technical", r"rsi", r"macd", r"moving average", r"spread", r"intraday", r"52-week", r"support", r"resistance"],
    },
    "ownership_insider": {
        "label": "insider transactions, 13F/13D/13G ownership, and institutional flows",
        "patterns": [r"insider", r"form 4", r"13f", r"13d", r"13g", r"ownership", r"institutional", r"activist"],
    },
    "supply_chain_tariff": {
        "label": "tariff, trade, supply-chain, customs, and import/export exposure",
        "patterns": [r"tariff", r"trade", r"supply chain", r"import", r"export", r"shipment", r"customs", r"country of origin"],
    },
    "news_sentiment": {
        "label": "news, events, sentiment, and controversy monitoring",
        "patterns": [r"news", r"sentiment", r"controversy", r"litigation", r"headline", r"regulatory action", r"enforcement"],
    },
}

# The scores below are intentionally heuristic. They are designed to help a retail
# user decide which one or two paid services would have improved the most runs,
# not to imply that any service is complete or endorsed.
RETAIL_SERVICE_CATALOG: dict[str, dict[str, Any]] = {
    "Fiscal.ai": {
        "retail_fit": "high",
        "approx_cost_tier": "medium",
        "categories": ["fundamentals_valuation", "consensus_estimates", "transcripts_kpis", "news_sentiment"],
        "notes": "Good candidate for public-company financials, KPIs, transcripts/events, estimates, and auditability to filings.",
    },
    "TIKR": {
        "retail_fit": "high",
        "approx_cost_tier": "medium",
        "categories": ["fundamentals_valuation", "consensus_estimates", "ownership_insider", "market_data_technicals"],
        "notes": "Good candidate for retail fundamental research, long financial histories, estimates, screeners, and ownership/13F-style workflows.",
    },
    "Koyfin": {
        "retail_fit": "high",
        "approx_cost_tier": "medium",
        "categories": ["market_data_technicals", "fundamentals_valuation", "etf_fund_analytics", "news_sentiment", "consensus_estimates"],
        "notes": "Good broad-market dashboard candidate across equities, ETFs, macro, charting, screens, and news workflows.",
    },
    "Morningstar Investor": {
        "retail_fit": "high",
        "approx_cost_tier": "low_medium",
        "categories": ["etf_fund_analytics", "fundamentals_valuation"],
        "notes": "Good retail ETF/fund research candidate; less suitable for deep options, supply-chain, or point-in-time model exports.",
    },
    "Seeking Alpha Premium": {
        "retail_fit": "high",
        "approx_cost_tier": "low_medium",
        "categories": ["transcripts_kpis", "news_sentiment", "consensus_estimates", "fundamentals_valuation"],
        "notes": "Good for transcripts, news/context, author debates, and retail-accessible estimates; treat community analysis as secondary.",
    },
    "TradingView": {
        "retail_fit": "high",
        "approx_cost_tier": "low_medium",
        "categories": ["market_data_technicals", "news_sentiment"],
        "notes": "Good for charting, market data visualization, and technical workflows; not a substitute for filing-backed fundamentals.",
    },
    "Unusual Whales": {
        "retail_fit": "medium_high",
        "approx_cost_tier": "medium",
        "categories": ["options_derivatives", "market_data_technicals", "news_sentiment"],
        "notes": "Good candidate when options flow, unusual activity, and positioning are recurring quality gaps.",
    },
    "Market Chameleon": {
        "retail_fit": "medium_high",
        "approx_cost_tier": "medium",
        "categories": ["options_derivatives", "market_data_technicals", "short_interest_borrow"],
        "notes": "Good candidate for options analytics, earnings moves, implied volatility, and some short-interest workflows.",
    },
    "Fintel": {
        "retail_fit": "medium_high",
        "approx_cost_tier": "medium",
        "categories": ["short_interest_borrow", "ownership_insider", "fundamentals_valuation"],
        "notes": "Good candidate for ownership, short-interest style dashboards, and screening; verify source lineage before treating as primary.",
    },
    "ORTEX": {
        "retail_fit": "medium",
        "approx_cost_tier": "high",
        "categories": ["short_interest_borrow", "options_derivatives"],
        "notes": "Good candidate when borrow/short-interest dynamics repeatedly affect conclusions; cost may be higher than basic retail tools.",
    },
    "ImportGenius": {
        "retail_fit": "medium",
        "approx_cost_tier": "high",
        "categories": ["supply_chain_tariff"],
        "notes": "Good candidate if tariff/supply-chain exposure is the recurring blocker; not usually the first broad-market subscription.",
    },
}

AFFORDABILITY_WEIGHT = {"low": 1.25, "low_medium": 1.15, "medium": 1.0, "high": 0.7, "enterprise": 0.35}
SEVERITY_WEIGHT = {"critical": 5, "moderate": 3, "minor": 1}
STATUS_WEIGHT = {"open": 1.0, "unresolved_data_unavailable": 1.25, "deferred": 0.35}
CONFIDENCE_WEIGHT = {"unverified": 1.0, "low": 0.65, "medium": 0.25, "high": 0.0}


def issue_text(issue: dict[str, Any]) -> str:
    return " ".join(str(issue.get(k) or "") for k in ["section", "issue", "required_fix", "source_or_evidence", "unresolved_reason"]).lower()


def categorize_issue(issue: dict[str, Any]) -> list[str]:
    text = issue_text(issue)
    categories: list[str] = []
    for category, meta in GAP_CATEGORIES.items():
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in meta["patterns"]):
            categories.append(category)
    return categories or ["fundamentals_valuation"]


def issue_gap_weight(issue: dict[str, Any]) -> float:
    severity = str(issue.get("severity") or "minor")
    status = str(issue.get("status") or "open")
    confidence = str(issue.get("source_confidence") or "medium")
    weight = SEVERITY_WEIGHT.get(severity, 1) * STATUS_WEIGHT.get(status, 1.0)
    weight *= 1 + CONFIDENCE_WEIGHT.get(confidence, 0.25)
    return round(weight, 3)


def assessment_from_validation(validation_payload: dict[str, Any], *, symbol: str | None = None) -> dict[str, Any]:
    sd = validation_payload.get("structured_data") or {}
    issues = sd.get("issues") or []
    symbol = symbol or validation_payload.get("symbol") or sd.get("symbol")
    category_totals: dict[str, dict[str, Any]] = {}
    issue_assessments: list[dict[str, Any]] = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        # Focus the paid-service recommendation on material unresolved/low-confidence gaps.
        status = issue.get("status")
        conf = issue.get("source_confidence")
        severity = issue.get("severity")
        if severity not in {"critical", "moderate", "minor"}:
            continue
        if status not in {"open", "unresolved_data_unavailable"} and conf not in {"unverified", "low"}:
            continue
        cats = categorize_issue(issue)
        weight = issue_gap_weight(issue)
        entry = {
            "issue_id": issue.get("id"),
            "severity": severity,
            "status": status,
            "source_confidence": conf,
            "categories": cats,
            "gap_weight": weight,
            "issue": issue.get("issue"),
            "required_fix": issue.get("required_fix"),
        }
        issue_assessments.append(entry)
        split_weight = weight / max(len(cats), 1)
        for cat in cats:
            meta = category_totals.setdefault(
                cat,
                {
                    "label": GAP_CATEGORIES.get(cat, {}).get("label", cat),
                    "weighted_gap_score": 0.0,
                    "issue_count": 0,
                    "critical_count": 0,
                    "moderate_count": 0,
                    "minor_count": 0,
                },
            )
            meta["weighted_gap_score"] = round(meta["weighted_gap_score"] + split_weight, 3)
            meta["issue_count"] += 1
            meta[f"{severity}_count"] = meta.get(f"{severity}_count", 0) + 1
    services = rank_services(category_totals)
    return {
        "symbol": symbol,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "validation_iteration": validation_payload.get("iteration"),
        "issue_count_considered": len(issue_assessments),
        "issues": issue_assessments,
        "category_totals": dict(sorted(category_totals.items(), key=lambda kv: kv[1]["weighted_gap_score"], reverse=True)),
        "service_rankings": services,
        "recommendation_note": "Use this as an evidence tally over many runs, not as a standalone purchase recommendation.",
    }


def rank_services(category_totals: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for service, meta in RETAIL_SERVICE_CATALOG.items():
        raw = 0.0
        covered = []
        for cat in meta["categories"]:
            if cat in category_totals:
                raw += float(category_totals[cat].get("weighted_gap_score", 0.0))
                covered.append(cat)
        if raw <= 0:
            continue
        affordability = AFFORDABILITY_WEIGHT.get(str(meta.get("approx_cost_tier")), 1.0)
        score = round(raw * affordability, 3)
        ranked.append(
            {
                "service": service,
                "bang_for_buck_score": score,
                "raw_gap_coverage_score": round(raw, 3),
                "retail_fit": meta["retail_fit"],
                "approx_cost_tier": meta["approx_cost_tier"],
                "covered_categories": covered,
                "notes": meta["notes"],
            }
        )
    return sorted(ranked, key=lambda x: (x["bang_for_buck_score"], x["raw_gap_coverage_score"]), reverse=True)


def content_hash(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()[:16]


def load_ledger(path: Path) -> dict[str, Any]:
    if path.exists():
        return read_json(path)
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": None,
        "run_count": 0,
        "runs": [],
        "category_totals": {},
        "service_scores": {},
        "recommendation_ready_after_runs": 20,
        "recommendation_ready": False,
    }


def merge_assessment_into_ledger(ledger: dict[str, Any], assessment: dict[str, Any], *, run_id: str) -> tuple[dict[str, Any], bool]:
    existing = {r.get("run_id") for r in ledger.get("runs", []) if isinstance(r, dict)}
    if run_id in existing:
        return ledger, False
    ledger.setdefault("runs", []).append(
        {
            "run_id": run_id,
            "symbol": assessment.get("symbol"),
            "created_at": assessment.get("created_at"),
            "top_categories": list((assessment.get("category_totals") or {}).keys())[:5],
            "top_services": [s.get("service") for s in (assessment.get("service_rankings") or [])[:5]],
        }
    )
    ledger["run_count"] = len(ledger["runs"])
    ledger["updated_at"] = datetime.now(timezone.utc).isoformat()
    # Merge category scores.
    for cat, meta in (assessment.get("category_totals") or {}).items():
        tgt = ledger.setdefault("category_totals", {}).setdefault(
            cat,
            {
                "label": GAP_CATEGORIES.get(cat, {}).get("label", cat),
                "weighted_gap_score": 0.0,
                "issue_count": 0,
                "critical_count": 0,
                "moderate_count": 0,
                "minor_count": 0,
                "symbols": [],
            },
        )
        tgt["weighted_gap_score"] = round(float(tgt.get("weighted_gap_score", 0.0)) + float(meta.get("weighted_gap_score", 0.0)), 3)
        for key in ["issue_count", "critical_count", "moderate_count", "minor_count"]:
            tgt[key] = int(tgt.get(key, 0)) + int(meta.get(key, 0))
        sym = assessment.get("symbol")
        if sym and sym not in tgt["symbols"]:
            tgt["symbols"].append(sym)
    ledger["service_scores"] = {s["service"]: s for s in rank_services(ledger.get("category_totals", {}))}
    ledger["recommendation_ready"] = int(ledger.get("run_count", 0)) >= int(ledger.get("recommendation_ready_after_runs", 20))
    ledger["top_services"] = list(ledger["service_scores"].values())[:10]
    return ledger, True


def cmd_assess_data_gaps(args: argparse.Namespace) -> None:
    validation_path = Path(args.validation_json)
    validation_payload = read_json(validation_path)
    symbol = normalize_symbol(args.symbol or validation_payload.get("symbol") or validation_payload.get("structured_data", {}).get("symbol"))
    assessment = assessment_from_validation(validation_payload, symbol=symbol)
    out = symbol_dir(Path(args.output_root), symbol)
    out.mkdir(parents=True, exist_ok=True)
    assessment_path = out / f"{symbol}-provider-gap-assessment.json"
    assessment_path.write_text(json.dumps(assessment, indent=2), encoding="utf-8")

    ledger_path = Path(args.output_root) / "provider_value_ledger.json"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger = load_ledger(ledger_path)
    run_id = args.run_id or f"{symbol}-{content_hash(validation_path)}"
    ledger, added = merge_assessment_into_ledger(ledger, assessment, run_id=run_id)
    ledger_path.write_text(json.dumps(ledger, indent=2), encoding="utf-8")

    # Attach the assessment snapshot to this symbol's manifest when available.
    manifest_path = out / "run_manifest.json"
    if manifest_path.exists():
        manifest = read_json(manifest_path)
        manifest["data_gap_assessment"] = str(assessment_path)
        manifest["provider_recommendation_snapshot"] = {
            "ledger": str(ledger_path),
            "run_count": ledger.get("run_count"),
            "recommendation_ready": ledger.get("recommendation_ready"),
            "top_services": ledger.get("top_services", [])[:5],
        }
        manifest["files"] = scan_files(out)
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    _json_dump({"assessment": str(assessment_path), "ledger": str(ledger_path), "added_to_ledger": added, "run_count": ledger.get("run_count"), "recommendation_ready": ledger.get("recommendation_ready"), "top_services": ledger.get("top_services", [])[:5]})


def cmd_provider_summary(args: argparse.Namespace) -> None:
    ledger_path = Path(args.output_root) / "provider_value_ledger.json"
    ledger = load_ledger(ledger_path)
    min_runs = args.min_runs
    summary = {
        "ledger": str(ledger_path),
        "run_count": ledger.get("run_count", 0),
        "recommendation_ready": int(ledger.get("run_count", 0)) >= min_runs,
        "min_runs": min_runs,
        "top_categories": sorted((ledger.get("category_totals") or {}).items(), key=lambda kv: kv[1].get("weighted_gap_score", 0), reverse=True)[:10],
        "top_services": list((ledger.get("service_scores") or {}).values())[:10],
        "note": "Before the minimum run count, treat this as directional. After the threshold, focus on the top one or two services whose categories match your actual recurring data gaps.",
    }
    _json_dump(summary)


def load_product_hints(path: Path | None) -> dict[str, dict[str, str]]:
    hints = {k: dict(v) for k, v in ISHARES_PRODUCT_HINTS.items()}
    if path and path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            for sym, meta in payload.items():
                if isinstance(meta, dict):
                    hints[normalize_symbol(sym)] = {str(k): str(v) for k, v in meta.items()}
        except Exception as exc:  # noqa: BLE001
            _die(f"Could not parse issuer product map {path}: {exc}")
    return hints


def iShares_sources_for(symbol: str, *, product_id: str | None = None, slug: str | None = None, product_map: Path | None = None) -> list[dict[str, str]]:
    hints = load_product_hints(product_map).get(symbol, {})
    product_id = product_id or hints.get("product_id")
    slug = slug or hints.get("slug")
    sources: list[dict[str, str]] = []
    if product_id and slug:
        sources.append({"name": "ishares_product_page.html", "url": f"https://www.ishares.com/us/products/{product_id}/{slug}", "kind": "product_page"})
        sources.append({"name": "blackrock_product_page.html", "url": f"https://www.blackrock.com/us/individual/products/{product_id}/{slug}", "kind": "product_page"})
    # Ticker-based literature URLs are stable enough to try, but are treated as candidates.
    lower = symbol.lower()
    if symbol == "ECH":
        sources.extend([
            {"name": "ishares_fact_sheet.pdf", "url": "https://www.blackrock.com/us/individual/literature/fact-sheet/ech-ishares-msci-chile-etf-fund-fact-sheet-en-us.pdf", "kind": "fact_sheet"},
            {"name": "ishares_summary_prospectus.pdf", "url": "https://www.ishares.com/us/literature/summary-prospectus/sp-ishares-msci-chile-capped-etf-8-31.pdf", "kind": "summary_prospectus"},
        ])
    if product_id:
        # Candidate machine-readable/ajax endpoints. Some locales require cookies and may return HTML; downloader marks those as wrong_content_type rather than silently saving as CSV/JSON.
        sources.extend([
            {"name": "ishares_holdings_candidate.csv", "url": f"https://www.ishares.com/us/products/{product_id}/1467271812596.ajax?fileType=csv&fileName={symbol}_holdings&dataType=fund", "kind": "holdings_csv"},
            {"name": "ishares_fund_candidate.json", "url": f"https://www.ishares.com/us/products/{product_id}/1467271812596.ajax?fileType=json&dataType=fund", "kind": "fund_json"},
        ])
    return sources


def save_downloaded_source(out: Path, desc: dict[str, str], *, user_agent: str) -> dict[str, Any]:
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", desc.get("name", "download"))[:100] or "download"
    url = desc["url"]
    kind = desc.get("kind", "source")
    record: dict[str, Any] = {"name": name, "url": url, "kind": kind, "status": "pending", "content_type": None, "bytes": 0, "path": None, "accessed_at": datetime.now(timezone.utc).isoformat(), "issues": []}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate", "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=45) as resp:  # noqa: S310 - explicit/issuer URL download
            raw = resp.read()
            headers = dict(resp.headers.items())
        data = decode_http_body(raw, content_encoding=headers.get("Content-Encoding"))
        content_type = headers.get("Content-Type", "")
        record.update({"status": "downloaded", "content_type": content_type, "bytes": len(data)})
        if kind in {"holdings_csv", "csv"} and not looks_like_csv(data, content_type):
            record["status"] = "wrong_content_type"
            record["issues"].append("Expected CSV but response looked like HTML or non-CSV content; not saved as usable holdings CSV.")
            diag = out / (name + ".diagnostic.txt")
            diag.write_text(safe_snippet(data, 4000), encoding="utf-8")
            record["diagnostic_path"] = str(diag)
            return record
        if kind in {"fund_json", "json"}:
            try:
                json.loads(data.decode("utf-8"))
            except Exception:
                if looks_like_html(data, content_type):
                    record["status"] = "wrong_content_type"
                    record["issues"].append("Expected JSON but response looked like HTML; saved diagnostic only.")
                    diag = out / (name + ".diagnostic.txt")
                    diag.write_text(safe_snippet(data, 4000), encoding="utf-8")
                    record["diagnostic_path"] = str(diag)
                    return record
        path = out / name
        path.write_bytes(data)
        record["path"] = str(path)
        return record
    except urllib.error.HTTPError as exc:
        body = exc.read() if hasattr(exc, "read") else b""
        record.update({"status": "failed", "issues": [f"HTTP {exc.code}; content-type={exc.headers.get('Content-Type') if exc.headers else 'unknown'}; snippet={safe_snippet(body)}"]})
        return record
    except Exception as exc:  # noqa: BLE001
        record.update({"status": "failed", "issues": [str(exc)]})
        return record


def maybe_parse_downloaded_holdings(out: Path, records: list[dict[str, Any]]) -> list[str]:
    created: list[str] = []
    for rec in records:
        if rec.get("kind") == "holdings_csv" and rec.get("status") == "downloaded" and rec.get("path"):
            try:
                class A: pass
                a = A(); a.holdings_csv = rec["path"]; a.output_json = str(out / "etf_holdings_summary.json"); a.weight_column = "weight"; a.name_column = "name"; a.ticker_column = "ticker"; a.sector_column = "sector"; a.country_column = "country"
                cmd_parse_etf_holdings(a)
                created.append(str(out / "etf_holdings_summary.json"))
            except (SystemExit, Exception):
                pass
        if rec.get("kind") == "fund_json" and rec.get("status") == "downloaded" and rec.get("path"):
            try:
                class A: pass
                a = A(); a.json_file = rec["path"]; a.output_csv = str(out / "holdings_extracted.csv"); a.output_json = str(out / "etf_holdings_summary.json")
                cmd_extract_issuer_holdings_json(a)
                created.extend([str(out / "holdings_extracted.csv"), str(out / "etf_holdings_summary.json")])
            except (SystemExit, Exception):
                pass
    return created


def cmd_build_source_bundle(args: argparse.Namespace) -> None:
    symbol = normalize_symbol(args.symbol)
    out = symbol_dir(Path(args.output_root), symbol) / "source_bundle"
    out.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    operational_issues: list[dict[str, Any]] = []

    requested_type = args.security_type
    try:
        if requested_type and requested_type != "auto":
            classification = override_classification(symbol, requested_type, reason=f"Source bundle security type override used: {requested_type}.")
            operational_issues.append({"stage": "classification", "severity": "warning", "category": "classification_fallback", "issue": "--security-type override was supplied; public classifier enrichment was not required for source bundling.", "resolution": f"Proceeding as {requested_type}; research/validation must verify classification."})
        else:
            classification = classify_with_edgar(symbol, user_agent=args.sec_user_agent, enrich_submissions=not args.no_edgar_enrich)
    except SystemExit:
        raise

    classification_path = out / "classification.json"
    classification_path.write_text(json.dumps(asdict(classification), indent=2), encoding="utf-8")
    files = [str(classification_path)]
    download_records: list[dict[str, Any]] = []

    if classification.cik and classification.security_type in {"equity", "adr"}:
        cik = classification.cik
        for name, url in {
            "sec_submissions.json": SEC_SUBMISSIONS.format(cik=cik),
            "sec_companyfacts.json": SEC_COMPANYFACTS.format(cik=cik),
        }.items():
            try:
                payload = fetch_json(url, user_agent=args.sec_user_agent)
                p = out / name
                p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                files.append(str(p))
            except SystemExit as exc:
                errors.append(f"{name}: {exc}")

    # ETF issuer discovery. Conservative and auditable.
    issuer = (args.issuer or "").lower()
    if classification.security_type == "etf" and (issuer in {"ishares", "blackrock"} or symbol in ISHARES_PRODUCT_HINTS or args.ishares_product_id):
        for desc in iShares_sources_for(symbol, product_id=args.ishares_product_id, product_map=Path(args.issuer_product_map) if args.issuer_product_map else None):
            rec = save_downloaded_source(out, desc, user_agent=args.sec_user_agent)
            download_records.append(rec)
            if rec.get("path"):
                files.append(str(rec["path"]))
            if rec.get("status") == "wrong_content_type":
                operational_issues.append({"stage": "source_bundle", "severity": "warning", "category": "source_wrong_content_type", "issue": f"{rec.get('name')} returned wrong content type", "resolution": "Diagnostic saved; use other issuer files/API/explicit URL or manual CSV export."})

    for item in args.url or []:
        if "=" not in item:
            errors.append(f"--url value must be name=url, got {item}")
            continue
        name, url = item.split("=", 1)
        rec = save_downloaded_source(out, {"name": name.strip(), "url": url.strip(), "kind": "source"}, user_agent=args.sec_user_agent)
        download_records.append(rec)
        if rec.get("path"):
            files.append(str(rec["path"]))
        if rec.get("status") in {"wrong_content_type", "failed"}:
            operational_issues.append({"stage": "source_bundle", "severity": "warning", "category": "source_wrong_content_type" if rec.get("status") == "wrong_content_type" else "helper_error", "issue": f"Explicit source {name} status={rec.get('status')}", "resolution": "; ".join(rec.get("issues") or [])})

    files.extend(maybe_parse_downloaded_holdings(out, download_records))
    source_manifest = {
        "symbol": symbol,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "classification": asdict(classification),
        "files": files,
        "downloads": download_records,
        "errors": errors,
        "operational_issues": operational_issues,
        "instructions": "Provide this source_bundle directory to OpenClaw sub-agents as the preferred citation source. If material data is missing, mark it unverified or Data not available.",
    }
    (out / "manifest.json").write_text(json.dumps(source_manifest, indent=2), encoding="utf-8")
    # Mirror operational issues to run_manifest if present.
    for issue in operational_issues:
        append_operational_issue(Path(args.output_root), symbol, issue)
    _json_dump(source_manifest)


def latest_fact_by_tag(companyfacts: dict[str, Any], tags: list[str], *, units: tuple[str, ...] = ("USD", "shares", "USD/shares")) -> dict[str, Any] | None:
    facts = companyfacts.get("facts", {}).get("us-gaap", {})
    candidates: list[dict[str, Any]] = []
    for tag in tags:
        item = facts.get(tag)
        if not item:
            continue
        unit_map = item.get("units") or {}
        for unit in units:
            for fact in unit_map.get(unit, []) or []:
                if "val" in fact and fact.get("end"):
                    candidates.append({"tag": tag, "unit": unit, **fact})
    if not candidates:
        return None
    # Prefer recent filed data, then end date. This does not decide FY vs TTM; it surfaces auditable raw facts.
    candidates.sort(key=lambda x: (str(x.get("filed") or ""), str(x.get("end") or "")), reverse=True)
    return candidates[0]


def cmd_extract_xbrl_metrics(args: argparse.Namespace) -> None:
    payload = read_json(Path(args.companyfacts_json))
    tag_map = {
        "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"],
        "gross_profit": ["GrossProfit"],
        "operating_income": ["OperatingIncomeLoss"],
        "net_income": ["NetIncomeLoss", "ProfitLoss"],
        "diluted_eps": ["EarningsPerShareDiluted"],
        "assets": ["Assets"],
        "liabilities": ["Liabilities"],
        "equity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
        "cash": ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
        "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
        "capex": ["PaymentsToAcquirePropertyPlantAndEquipment"],
        "shares": ["CommonStocksIncludingAdditionalPaidInCapital", "EntityCommonStockSharesOutstanding"],
        "short_term_debt": ["ShortTermBorrowings", "ShortTermDebtCurrent", "DebtCurrent"],
        "long_term_debt": ["LongTermDebtNoncurrent", "LongTermDebt"],
    }
    metrics: dict[str, Any] = {}
    for metric, tags in tag_map.items():
        units = ("USD", "shares", "USD/shares") if metric != "diluted_eps" else ("USD/shares",)
        metrics[metric] = latest_fact_by_tag(payload, tags, units=units)
    ocf = metrics.get("operating_cash_flow") or {}
    capex = metrics.get("capex") or {}
    fcf = None
    if isinstance(ocf, dict) and isinstance(capex, dict) and ocf.get("val") is not None and capex.get("val") is not None:
        fcf = {
            "val": float(ocf["val"]) - abs(float(capex["val"])),
            "formula": "operating_cash_flow - abs(capex)",
            "source_tags": [ocf.get("tag"), capex.get("tag")],
            "end": ocf.get("end"),
            "filed": ocf.get("filed"),
            "confidence": "medium",
            "note": "Computed from latest available SEC companyfacts concepts; verify period alignment before using in valuation.",
        }
    result = {"created_at": datetime.now(timezone.utc).isoformat(), "source": str(args.companyfacts_json), "metrics": metrics, "computed": {"free_cash_flow": fcf}, "caveats": ["SEC companyfacts tags vary by filer; treat this as an auditable extraction aid, not a replacement for filing review."]}
    out = Path(args.output_json) if args.output_json else Path(args.companyfacts_json).with_name("xbrl_metrics.json")
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    _json_dump({"output": str(out), "metrics": result})


def parse_percent(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace("%", "").replace(",", "")
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def extract_holdings_rows_from_json(payload: Any) -> list[dict[str, Any]]:
    """Best-effort extractor for issuer API JSON that contains holdings arrays.

    It intentionally does not infer missing weights. It only returns rows where a
    numeric weight-like field is present. This is used for deterministic recovery
    from official issuer API JSON, not for broad web scraping.
    """
    candidate_lists: list[list[dict[str, Any]]] = []

    def walk(obj: Any) -> None:
        if isinstance(obj, list) and obj and all(isinstance(x, dict) for x in obj):
            candidate_lists.append(obj)
            for x in obj[:3]:
                walk(x)
        elif isinstance(obj, dict):
            for v in obj.values():
                walk(v)

    walk(payload)
    weight_keys = {"weight", "weight_", "market_value_weight", "marketvalueweight", "weight_percent", "weightpercent", "fund_weight", "fundweight", "percentage", "percent"}
    name_keys = {"name", "holding_name", "security_name", "issuer_name", "description"}
    ticker_keys = {"ticker", "symbol", "local_ticker", "holding_ticker"}
    sector_keys = {"sector", "gics_sector", "industry"}
    country_keys = {"country", "location", "country_of_risk", "market"}
    best: list[dict[str, Any]] = []
    for rows in candidate_lists:
        extracted: list[dict[str, Any]] = []
        for row in rows:
            key_map = {normalize_key(str(k)): k for k in row.keys()}
            wkey = next((key_map[k] for k in key_map if k in weight_keys or k.endswith("_weight")), None)
            if not wkey:
                continue
            weight = parse_percent(row.get(wkey))
            if weight is None:
                continue
            def first(keys: set[str]) -> Any:
                for nk, orig in key_map.items():
                    if nk in keys:
                        return row.get(orig)
                return None
            extracted.append({
                "ticker": first(ticker_keys),
                "name": first(name_keys),
                "weight": weight,
                "sector": first(sector_keys),
                "country": first(country_keys),
            })
        if len(extracted) > len(best):
            best = extracted
    return sorted(best, key=lambda r: r.get("weight") or 0, reverse=True)


def write_holdings_csv(rows: list[dict[str, Any]], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["ticker", "name", "weight", "sector", "country"])
        writer.writeheader()
        writer.writerows(rows)


def summarize_holdings_rows(rows: list[dict[str, Any]], *, source: str) -> dict[str, Any]:
    rows = sorted(rows, key=lambda r: float(r.get("weight") or 0), reverse=True)
    top10 = rows[:10]
    def aggregate(key: str) -> dict[str, float]:
        agg: dict[str, float] = {}
        for r in rows:
            label = r.get(key) or "Unclassified"
            agg[str(label)] = round(agg.get(str(label), 0.0) + float(r.get("weight") or 0), 4)
        return dict(sorted(agg.items(), key=lambda kv: kv[1], reverse=True))
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "holdings_count": len(rows),
        "total_weight": round(sum(float(r.get("weight") or 0) for r in rows), 4),
        "top10_weight": round(sum(float(r.get("weight") or 0) for r in top10), 4),
        "top10": top10,
        "sector_weights": aggregate("sector"),
        "country_weights": aggregate("country"),
        "caveats": ["Weights are parsed from official/local issuer data. Verify whether cash, derivatives, and pending trades are included by the issuer."],
    }


def cmd_extract_issuer_holdings_json(args: argparse.Namespace) -> None:
    source = Path(args.json_file)
    payload = read_json(source)
    rows = extract_holdings_rows_from_json(payload)
    if not rows:
        _die(f"No holdings array with numeric weights found in {source}")
    csv_out = Path(args.output_csv) if args.output_csv else source.with_name("holdings_extracted.csv")
    json_out = Path(args.output_json) if args.output_json else source.with_name("etf_holdings_summary.json")
    write_holdings_csv(rows, csv_out)
    summary = summarize_holdings_rows(rows, source=str(source))
    json_out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    _json_dump({"output_csv": str(csv_out), "output_json": str(json_out), "summary": summary})


def cmd_parse_etf_holdings(args: argparse.Namespace) -> None:
    path = Path(args.holdings_csv)
    if looks_like_html(path.read_bytes()[:2048], ""):
        _die(f"{path} looks like HTML, not a holdings CSV. Use source bundle diagnostics or issuer JSON fallback.")
    rows: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        raw_fields = reader.fieldnames or []
        fields = {normalize_key(name): name for name in raw_fields}
        weight_col = fields.get(normalize_key(args.weight_column)) or fields.get("weight") or fields.get("weight_") or fields.get("market_value_weight") or fields.get("holding_weight")
        name_col = fields.get(normalize_key(args.name_column)) or fields.get("name") or fields.get("holding_name") or fields.get("security_name")
        ticker_col = fields.get(normalize_key(args.ticker_column)) or fields.get("ticker") or fields.get("symbol")
        sector_col = fields.get(normalize_key(args.sector_column)) or fields.get("sector")
        country_col = fields.get(normalize_key(args.country_column)) or fields.get("country") or fields.get("location")
        if not weight_col:
            _die(f"Could not find a holdings weight column in {path}; pass --weight-column")
        for row in reader:
            weight = parse_percent(row.get(weight_col))
            if weight is None:
                continue
            rows.append({"ticker": row.get(ticker_col) if ticker_col else None, "name": row.get(name_col) if name_col else None, "weight": weight, "sector": row.get(sector_col) if sector_col else None, "country": row.get(country_col) if country_col else None})
    result = summarize_holdings_rows(rows, source=str(path))
    out = Path(args.output_json) if args.output_json else path.with_name("etf_holdings_summary.json")
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    _json_dump({"output": str(out), "summary": result})


def cmd_lint_citations(args: argparse.Namespace) -> None:
    md = Path(args.markdown_file).read_text(encoding="utf-8")
    js = read_json(Path(args.json_file))
    sd = js.get("structured_data") or {}
    claims = []
    for section in sd.get("sections", []) or []:
        claims.extend(section.get("quantitative_claims", []) or [])
    errors: list[str] = []
    warnings: list[str] = []
    for idx, claim in enumerate(claims):
        status = claim.get("verification_status")
        source_id = claim.get("source_id")
        if status in {"verified_primary", "verified_secondary"} and not source_id:
            errors.append(f"claim {idx} verified but missing source_id: {claim.get('claim_text')}")
        if status in {"unverified", "not_available"} and str(claim.get("confidence")) != "unverified":
            errors.append(f"claim {idx} unverified/not_available but confidence is not unverified")
    numberish = re.findall(r"(?<![A-Za-z0-9])(?:\$)?\d+(?:\.\d+)?%?(?:\s?(?:bn|billion|mm|million|x|bps))?", md, flags=re.IGNORECASE)
    material_count_estimate = len([n for n in numberish if len(n.strip()) > 1])
    if material_count_estimate > 20 and len(claims) < max(5, material_count_estimate // 6):
        warnings.append("markdown contains many numeric tokens relative to JSON quantitative_claims; review for uncaptured material claims")
    result = {"valid": not errors, "errors": errors, "warnings": warnings, "numeric_token_count": material_count_estimate, "json_quantitative_claim_count": len(claims)}
    _json_dump(result)
    if errors:
        raise SystemExit(1)


def cmd_generate_charts(args: argparse.Namespace) -> None:
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    errors: list[str] = []
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception as exc:  # noqa: BLE001
        _die(f"matplotlib is required for generate-charts: {exc}")
    if args.prices_csv:
        try:
            dates, closes = [], []
            with Path(args.prices_csv).open(newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    date = row.get("date") or row.get("Date")
                    close = parse_percent(row.get("close") or row.get("Close") or row.get("adj_close") or row.get("Adj Close"))
                    if date and close is not None:
                        dates.append(date); closes.append(close)
            if dates and closes:
                plt.figure(figsize=(10, 5))
                plt.plot(dates, closes)
                plt.title("Verified local price history")
                plt.xlabel("Date")
                plt.ylabel("Close")
                plt.xticks(rotation=45, ha="right")
                plt.tight_layout()
                p = out / "price_history.png"
                plt.savefig(p, dpi=160); plt.close(); created.append(str(p))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"prices_csv: {exc}")
    if args.holdings_summary_json:
        try:
            payload = read_json(Path(args.holdings_summary_json))
            sectors = payload.get("sector_weights") or {}
            top = list(sectors.items())[:12]
            if top:
                labels, values = zip(*top)
                plt.figure(figsize=(10, 6))
                plt.bar(labels, values)
                plt.title("Verified local ETF sector weights")
                plt.ylabel("Weight (%)")
                plt.xticks(rotation=45, ha="right")
                plt.tight_layout()
                p = out / "etf_sector_weights.png"
                plt.savefig(p, dpi=160); plt.close(); created.append(str(p))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"holdings_summary_json: {exc}")
    _json_dump({"created": created, "errors": errors})


def cmd_extract_pdf_text(args: argparse.Namespace) -> None:
    pdf = Path(args.pdf_file)
    output = Path(args.output) if args.output else pdf.with_suffix(".txt")
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest_path = Path(args.manifest) if args.manifest else output.with_name("pdf_extract_manifest.json")
    status: dict[str, Any] = {
        "source_pdf": str(pdf),
        "output_text": str(output),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "text_created": False,
        "method": None,
        "errors": [],
        "missing_dependencies": [],
    }
    # 1. poppler pdftotext
    if shutil.which("pdftotext"):
        try:
            subprocess.run(["pdftotext", str(pdf), str(output)], check=True, capture_output=True, text=True)
            status.update({"text_created": output.exists(), "method": "pdftotext"})
        except subprocess.CalledProcessError as exc:
            status["errors"].append(f"pdftotext: {exc.stderr[-1000:]}")
    else:
        status["missing_dependencies"].append("binary: pdftotext")
    # 2. Python libraries
    if not status["text_created"] and module_available("pypdf"):
        try:
            from pypdf import PdfReader  # type: ignore
            reader = PdfReader(str(pdf))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            output.write_text(text, encoding="utf-8")
            status.update({"text_created": True, "method": "pypdf"})
        except Exception as exc:  # noqa: BLE001
            status["errors"].append(f"pypdf: {exc}")
    elif not module_available("pypdf"):
        status["missing_dependencies"].append("python package: pypdf")
    if not status["text_created"] and module_available("PyPDF2"):
        try:
            from PyPDF2 import PdfReader  # type: ignore
            reader = PdfReader(str(pdf))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            output.write_text(text, encoding="utf-8")
            status.update({"text_created": True, "method": "PyPDF2"})
        except Exception as exc:  # noqa: BLE001
            status["errors"].append(f"PyPDF2: {exc}")
    elif not module_available("PyPDF2"):
        status["missing_dependencies"].append("python package: PyPDF2")
    if not status["text_created"] and module_available("pdfplumber"):
        try:
            import pdfplumber  # type: ignore
            with pdfplumber.open(str(pdf)) as doc:
                text = "\n".join(page.extract_text() or "" for page in doc.pages)
            output.write_text(text, encoding="utf-8")
            status.update({"text_created": True, "method": "pdfplumber"})
        except Exception as exc:  # noqa: BLE001
            status["errors"].append(f"pdfplumber: {exc}")
    elif not module_available("pdfplumber"):
        status["missing_dependencies"].append("python package: pdfplumber")
    manifest_path.write_text(json.dumps(status, indent=2), encoding="utf-8")
    _json_dump(status)
    if not status["text_created"]:
        if args.optional:
            return
        raise SystemExit(3)


def cmd_finalize(args: argparse.Namespace) -> None:
    symbol = normalize_symbol(args.symbol)
    out = symbol_dir(Path(args.output_root), symbol)
    out.mkdir(parents=True, exist_ok=True)
    src_md = Path(args.current_markdown)
    src_json = Path(args.current_json)
    final_md = out / f"{symbol}-final.md"
    final_json = out / f"{symbol}-final.json"
    shutil.copyfile(src_md, final_md)
    shutil.copyfile(src_json, final_json)

    latest_validation = read_json(Path(args.validation_json)) if args.validation_json else None
    unresolved = unresolved_from_validation(latest_validation)
    manifest_path = out / "run_manifest.json"
    manifest = read_json(manifest_path) if manifest_path.exists() else {"symbol": symbol, "files": []}
    manifest.update(
        {
            "symbol": symbol,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "stopped_reason": args.stopped_reason,
            "final_markdown": str(final_md),
            "final_json": str(final_json),
            "latest_validation_json": args.validation_json,
            "unresolved_issues": unresolved,
            "intermediate_files_preserved": True,
        }
    )
    pdf_error = out / f"{symbol}-final.pdf-error.txt"
    if pdf_error.exists():
        try:
            manifest["pdf_render_status"] = json.loads(pdf_error.read_text(encoding="utf-8"))
        except Exception:
            manifest["pdf_render_status"] = {"error_file": str(pdf_error)}
        manifest.setdefault("operational_issues", []).append({
            "created_at": datetime.now(timezone.utc).isoformat(),
            "stage": "finalize",
            "severity": "warning",
            "category": "pdf_render_fallback",
            "issue": "Final PDF was not created; HTML fallback/error status exists.",
            "resolution": "Install PDF rendering dependencies and rerun render-pdf if a PDF is required.",
        })
    assessment_path = out / f"{symbol}-provider-gap-assessment.json"
    if assessment_path.exists():
        manifest["data_gap_assessment"] = str(assessment_path)
    manifest["files"] = scan_files(out)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _json_dump({"final_markdown": str(final_md), "final_json": str(final_json), "manifest": str(manifest_path), "unresolved_issues": unresolved})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic helpers for the OpenClaw financial research skill")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("classify", help="Classify a US stock/ADR/ETF ticker using EDGAR by default")
    p.add_argument("symbol")
    p.add_argument("--mode", choices=["auto", "equity", "adr", "etf"], default="auto")
    p.add_argument("--provider", choices=["edgar", "paid-json"], default="edgar")
    p.add_argument("--paid-provider-config")
    p.add_argument("--sec-user-agent", default=os.environ.get("SEC_USER_AGENT", "cool-financial-research-openclaw/0.3 local-skill set-SEC_USER_AGENT"))
    p.add_argument("--no-edgar-enrich", action="store_true", help="Disable SEC submissions enrichment used to detect foreign issuer/ADR routing")
    p.set_defaults(func=cmd_classify)

    p = sub.add_parser("init-run", help="Create the output directory and initial manifest")
    p.add_argument("symbol")
    p.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    p.add_argument("--max-iterations", type=int, default=5)
    p.set_defaults(func=cmd_init_run)

    p = sub.add_parser("prompts", help="Return prompt paths for a security type")
    p.add_argument("security_type", choices=["equity", "adr", "etf"])
    p.set_defaults(func=cmd_prompts)

    p = sub.add_parser("validate-json", help="Validate required loop fields and quality gates in generated JSON")
    p.add_argument("schema", choices=["research", "validation"])
    p.add_argument("json_file")
    p.add_argument("--previous-validation", help="For fix-stage research JSON, verify all prior open critical/moderate issue ids are addressed")
    p.set_defaults(func=cmd_validate_json)

    p = sub.add_parser("check-stop", help="Check whether validation/fix loop should stop")
    p.add_argument("validation_json")
    p.set_defaults(func=cmd_check_stop)

    p = sub.add_parser("finalize", help="Copy current report/json to final filenames and update manifest")
    p.add_argument("symbol")
    p.add_argument("current_markdown")
    p.add_argument("current_json")
    p.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    p.add_argument("--stopped-reason", required=True)
    p.add_argument("--validation-json", help="Latest validation JSON; unresolved critical/moderate issues are copied into run_manifest.json")
    p.set_defaults(func=cmd_finalize)


    p = sub.add_parser("build-source-bundle", help="Build a local source bundle from EDGAR/fund ticker data and optional issuer URLs")
    p.add_argument("symbol")
    p.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    p.add_argument("--security-type", choices=["auto", "equity", "adr", "etf"], default="auto", help="Override/route source bundling when public classifier misses a known security type")
    p.add_argument("--issuer", choices=["ishares", "blackrock", "none"], default="none", help="Enable conservative provider-specific ETF discovery")
    p.add_argument("--ishares-product-id", help="Optional BlackRock/iShares product ID, e.g. ECH is 239618")
    p.add_argument("--issuer-product-map", help="Optional JSON map of ticker to issuer/product_id/slug")
    p.add_argument("--url", action="append", help="Additional source to download as name=url; use explicit issuer/fact-sheet/methodology URLs only")
    p.add_argument("--sec-user-agent", default=os.environ.get("SEC_USER_AGENT", "cool-financial-research-openclaw/0.5 local-skill set-SEC_USER_AGENT"))
    p.add_argument("--no-edgar-enrich", action="store_true")
    p.set_defaults(func=cmd_build_source_bundle)

    p = sub.add_parser("extract-xbrl-metrics", help="Extract common auditable metrics from SEC companyfacts JSON")
    p.add_argument("companyfacts_json")
    p.add_argument("--output-json")
    p.set_defaults(func=cmd_extract_xbrl_metrics)

    p = sub.add_parser("parse-etf-holdings", help="Parse an issuer ETF holdings CSV into concentration/sector/country summaries")
    p.add_argument("holdings_csv")
    p.add_argument("--output-json")
    p.add_argument("--weight-column", default="weight")
    p.add_argument("--name-column", default="name")
    p.add_argument("--ticker-column", default="ticker")
    p.add_argument("--sector-column", default="sector")
    p.add_argument("--country-column", default="country")
    p.set_defaults(func=cmd_parse_etf_holdings)

    p = sub.add_parser("extract-issuer-holdings-json", help="Extract ETF holdings from official issuer/API JSON into CSV plus summary JSON")
    p.add_argument("json_file")
    p.add_argument("--output-csv")
    p.add_argument("--output-json")
    p.set_defaults(func=cmd_extract_issuer_holdings_json)

    p = sub.add_parser("lint-citations", help="Check that JSON quantitative claims have source/confidence discipline")
    p.add_argument("markdown_file")
    p.add_argument("json_file")
    p.set_defaults(func=cmd_lint_citations)

    p = sub.add_parser("generate-charts", help="Generate charts only from verified local CSV/JSON data")
    p.add_argument("--output-dir", required=True)
    p.add_argument("--prices-csv")
    p.add_argument("--holdings-summary-json")
    p.set_defaults(func=cmd_generate_charts)

    p = sub.add_parser("assess-data-gaps", help="Analyze validation gaps and update the paid-provider value ledger")
    p.add_argument("validation_json")
    p.add_argument("--symbol")
    p.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    p.add_argument("--run-id")
    p.set_defaults(func=cmd_assess_data_gaps)

    p = sub.add_parser("provider-summary", help="Summarize cumulative paid-provider value after multiple runs")
    p.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    p.add_argument("--min-runs", type=int, default=20)
    p.set_defaults(func=cmd_provider_summary)

    p = sub.add_parser("preflight", help="Check local deterministic helper capabilities and optional PDF dependencies")
    p.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    p.add_argument("--symbol", help="If provided, write preflight.json and record results in the run manifest")
    p.set_defaults(func=cmd_preflight)

    p = sub.add_parser("verify-artifacts", help="Verify expected markdown/json artifacts after a sub-agent stage and update manifest compliance")
    p.add_argument("symbol")
    p.add_argument("stage", choices=["research", "validation", "fix"])
    p.add_argument("schema", choices=["research", "validation"])
    p.add_argument("markdown_file")
    p.add_argument("json_file")
    p.add_argument("--previous-validation")
    p.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    p.add_argument("--artifact-source", choices=["child", "repair-child", "parent-recovered"], default="child")
    p.add_argument("--repair-attempts", type=int, default=0)
    p.set_defaults(func=cmd_verify_artifacts)

    p = sub.add_parser("record-operational-issue", help="Append an operational issue to a run manifest")
    p.add_argument("symbol")
    p.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    p.add_argument("--stage", required=True)
    p.add_argument("--severity", choices=["info", "warning", "error"], default="warning")
    p.add_argument("--category", choices=sorted(OPERATIONAL_CATEGORIES), default="helper_error")
    p.add_argument("--issue", required=True)
    p.add_argument("--resolution", default="")
    p.set_defaults(func=cmd_record_operational_issue)

    p = sub.add_parser("extract-pdf-text", help="Extract PDF text using pdftotext, pypdf, PyPDF2, or pdfplumber")
    p.add_argument("pdf_file")
    p.add_argument("--output")
    p.add_argument("--manifest")
    p.add_argument("--optional", action="store_true", help="Exit 0 even if no extractor is available; status JSON records the gap")
    p.set_defaults(func=cmd_extract_pdf_text)

    p = sub.add_parser("render-pdf", help="Render markdown to PDF with WeasyPrint/pandoc; write HTML fallback on failure")
    p.add_argument("markdown_file")
    p.add_argument("pdf_file")
    p.add_argument("--title")
    p.add_argument("--optional", action="store_true", help="Exit 0 when HTML fallback is created but PDF dependencies are missing")
    p.set_defaults(func=cmd_render_pdf)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
