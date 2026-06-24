#!/usr/bin/env python3
"""Cache-first deterministic collector for free/public market-research APIs.

Fetches raw provider responses, preserves provenance, normalizes canonical
research fields, computes local price analytics, and writes report bundles.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deterministic_data_usage import build_usage_requirements
from script_metrics import add_metrics_arg, start_timer, write_metrics


SECRET_NAMES = {
    "TWELVE_DATA_API_KEY",
    "MARKETAUX_API_TOKEN",
    "ALPHAVANTAGE_API_KEY",
    "TIINGO_API_TOKEN",
    "EODHD_API_KEY",
    "FMP_API_KEY",
}
PROVIDER_ENV = {
    "sec": ["SEC_USER_AGENT"],
    "twelve_data": ["TWELVE_DATA_API_KEY"],
    "marketaux": ["MARKETAUX_API_TOKEN"],
    "alphavantage": ["ALPHAVANTAGE_API_KEY"],
    "tiingo": ["TIINGO_API_TOKEN"],
    "eodhd": ["EODHD_API_KEY"],
    "fmp": ["FMP_API_KEY"],
}
DEFAULT_PROVIDERS = ["sec", "tiingo", "eodhd", "alphavantage", "marketaux", "fmp", "twelve_data"]
DEFAULT_SEC_USER_AGENT = "market-research-skill/1.0 research@example.com"
DEFAULT_HTTP_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)
BROWSER_USER_AGENT_TOKENS = ("mozilla/", "chrome/", "safari/", "applewebkit", "firefox/")
SYMBOL_RE = re.compile(r"^(?=.*[A-Z0-9])[A-Z0-9][A-Z0-9.\-]{0,11}$")
AS_OF_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PROVIDER_ENDPOINT_COSTS = {
    "sec": {"company_tickers": 1, "submissions": 1, "companyfacts": 1},
    "tiingo": {"metadata": 1, "prices": 1},
    "eodhd": {"fundamentals": 10, "news": 1, "historical_market_cap": 1, "prices": 1},
    "alphavantage": {
        "overview": 10,
        "income_statement": 5,
        "balance_sheet": 5,
        "cash_flow": 5,
        "earnings": 1,
        "etf_profile": 1,
        "news_sentiment": 1,
        "prices": 1,
    },
    "twelve_data": {"quote": 1, "profile": 1, "prices": 1},
    "marketaux": {"news": 1},
    "fmp": {
        "profile": 1,
        "key_metrics_ttm": 1,
        "ratios_ttm": 1,
        "income_statement": 5,
        "balance_sheet": 5,
        "cash_flow": 5,
        "stock_news": 1,
        "press_releases": 1,
        "dividends": 1,
        "earnings": 1,
        "splits": 1,
        "insider_trading": 1,
        "insider_statistics": 1,
        "etf_holdings": 1,
    },
}
UNIQUE_DEFAULT_ENDPOINTS = {
    "sec": {"company_tickers", "submissions", "companyfacts"},
    "tiingo": {"metadata", "prices"},
    "eodhd": {"fundamentals", "news", "historical_market_cap"},
    "alphavantage": {"overview", "income_statement", "balance_sheet", "cash_flow", "earnings", "etf_profile", "news_sentiment"},
    "marketaux": {"news"},
    "fmp": {
        "profile",
        "key_metrics_ttm",
        "ratios_ttm",
        "income_statement",
        "balance_sheet",
        "cash_flow",
        "stock_news",
        "press_releases",
        "dividends",
        "earnings",
        "splits",
        "insider_trading",
        "insider_statistics",
        "etf_holdings",
    },
    "twelve_data": {"quote", "profile"},
}
PRICE_PROVIDER_PRIORITY = ["tiingo", "eodhd", "alphavantage", "twelve_data"]
ENDPOINT_BUDGET_PRIORITY = {
    "tiingo": ["prices", "metadata"],
    "eodhd": ["fundamentals", "news", "historical_market_cap", "prices"],
    "alphavantage": ["prices", "overview", "income_statement", "balance_sheet", "cash_flow", "earnings", "etf_profile", "news_sentiment"],
    "twelve_data": ["prices", "quote", "profile"],
    "marketaux": ["news"],
    "fmp": [
        "profile",
        "key_metrics_ttm",
        "ratios_ttm",
        "income_statement",
        "balance_sheet",
        "cash_flow",
        "stock_news",
        "press_releases",
        "dividends",
        "earnings",
        "splits",
        "insider_trading",
        "insider_statistics",
        "etf_holdings",
    ],
}


class ProviderConfig:
    def __init__(self, values: dict[str, str] | None = None, docs: dict[str, list[str]] | None = None, limits: dict[str, str] | None = None, loaded_files: list[str] | None = None):
        self.values = values or {}
        self.docs = docs or {}
        self.limits = limits or {}
        self.loaded_files = loaded_files or []


class RetryPolicy:
    def __init__(
        self,
        max_attempts: int = 3,
        initial_backoff_seconds: float = 1.0,
        backoff_multiplier: float = 2.0,
        retry_http_statuses: tuple[int, ...] = (429, 503),
        retry_url_errors: bool = True,
    ):
        self.max_attempts = max_attempts
        self.initial_backoff_seconds = initial_backoff_seconds
        self.backoff_multiplier = backoff_multiplier
        self.retry_http_statuses = retry_http_statuses
        self.retry_url_errors = retry_url_errors


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def die(message: str, code: int = 2) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


def normalize_symbol(symbol: str) -> str:
    value = symbol.strip().upper()
    if not SYMBOL_RE.fullmatch(value):
        die(f"Invalid symbol: {symbol!r}")
    return value


def validate_as_of(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    if not AS_OF_RE.fullmatch(value):
        die(f"Invalid as-of {value!r}; expected YYYY-MM-DD.")
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        die(f"Invalid as-of {value!r}; expected a real calendar date.")
    return value


def parse_key_value_line(line: str) -> tuple[str, str] | None:
    if "=" not in line:
        return None
    key, value = line.split("=", 1)
    key = key.strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
        return None
    return key, value.strip().strip('"').strip("'")


def provider_from_heading(line: str) -> str | None:
    normalized = re.sub(r"[^a-z0-9]+", "_", line.strip().lower()).strip("_")
    aliases = {
        "twelve_data": "twelve_data",
        "marketaux": "marketaux",
        "alphavantage": "alphavantage",
        "alpha_vantage": "alphavantage",
        "tiingo": "tiingo",
        "eodhd": "eodhd",
        "fmp": "fmp",
        "financial_modeling_prep": "fmp",
    }
    return aliases.get(normalized)


def token_env_for_provider(provider: str) -> str | None:
    for key in PROVIDER_ENV.get(provider, []):
        if key in SECRET_NAMES:
            return key
    return None


def parse_env_starter(path: Path) -> tuple[dict[str, str], dict[str, list[str]], dict[str, str]]:
    values: dict[str, str] = {}
    docs: dict[str, list[str]] = {}
    limits: dict[str, str] = {}
    current_provider: str | None = None
    section: str | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        pair = parse_key_value_line(line)
        if pair:
            values[pair[0]] = pair[1]
            continue
        heading = provider_from_heading(line)
        if heading:
            current_provider = heading
            section = None
            continue
        if line.lower().startswith("api token") and current_provider:
            token = line.split(":", 1)[1].strip() if ":" in line else ""
            env_name = token_env_for_provider(current_provider)
            if env_name and token:
                values[env_name] = token
            continue
        if line.lower().startswith("docs"):
            section = "docs"
            continue
        if line.lower().startswith("limits"):
            section = "limits"
            continue
        if current_provider and line.startswith("http"):
            docs.setdefault(current_provider, []).append(line)
            continue
        if current_provider and section == "limits":
            limits[current_provider] = f"{limits.get(current_provider, '')}\n{line}".strip()
    return values, docs, limits


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        pair = parse_key_value_line(line)
        if pair:
            values[pair[0]] = pair[1]
    return values


def load_env_files(repo_root: Path | str = ".") -> ProviderConfig:
    root = Path(repo_root)
    values: dict[str, str] = {}
    docs: dict[str, list[str]] = {}
    limits: dict[str, str] = {}
    loaded: list[str] = []
    starter = root / ".env-starter"
    if starter.exists():
        starter_values, docs, limits = parse_env_starter(starter)
        values.update(starter_values)
        loaded.append(str(starter))
    for name in [".env"]:
        path = root / name
        if path.exists():
            values.update(load_env_file(path))
            loaded.append(str(path))
    storage_keys = ["RESEARCH_DATA_DIR", "RESEARCH_REPORTS_DIR", "RESEARCH_RUNTIME_DIR", "RESEARCH_CACHE_DIR"]
    for key in set(PROVIDER_ENV["sec"] + list(SECRET_NAMES) + storage_keys):
        if os.environ.get(key):
            values[key] = os.environ[key]
    return ProviderConfig(values=values, docs=docs, limits=limits, loaded_files=loaded)


def redact(text: str, config: ProviderConfig) -> str:
    redacted = text
    for value in sorted((v for k, v in config.values.items() if k in SECRET_NAMES or "TOKEN" in k or "KEY" in k), key=len, reverse=True):
        if value:
            redacted = redacted.replace(value, "REDACTED")
    return redacted


def configured_providers(config: ProviderConfig) -> list[str]:
    found = []
    for provider, keys in PROVIDER_ENV.items():
        if provider == "sec":
            found.append(provider)
        elif any(config.values.get(key) for key in keys):
            found.append(provider)
    return found


def is_descriptive_sec_user_agent(value: str) -> bool:
    normalized = value.strip().lower()
    if not normalized:
        return False
    if any(token in normalized for token in BROWSER_USER_AGENT_TOKENS):
        return False
    return "@" in normalized or "http://" in normalized or "https://" in normalized


def sec_user_agent(config: ProviderConfig | None = None) -> str:
    if config:
        sec_value = config.values.get("SEC_USER_AGENT", "").strip()
        if is_descriptive_sec_user_agent(sec_value):
            return sec_value
    return DEFAULT_SEC_USER_AGENT


def http_user_agent(config: ProviderConfig | None = None) -> str:
    if config:
        http_value = config.values.get("HTTP_USER_AGENT", "").strip()
        if http_value:
            return http_value
    return DEFAULT_HTTP_USER_AGENT


def write_env_example(repo_root: Path | str, config: ProviderConfig | None = None) -> Path:
    path = Path(repo_root) / ".env.example"
    keys = [
        "SEC_USER_AGENT",
        "HTTP_USER_AGENT",
        "TWELVE_DATA_API_KEY",
        "MARKETAUX_API_TOKEN",
        "ALPHAVANTAGE_API_KEY",
        "TIINGO_API_TOKEN",
        "EODHD_API_KEY",
        "FMP_API_KEY",
        "MARKETAUX_NEWS_LIMIT",
        "RESEARCH_DATA_DIR",
        "RESEARCH_REPORTS_DIR",
        "RESEARCH_RUNTIME_DIR",
        "RESEARCH_CACHE_DIR",
    ]
    lines = []
    for key in keys:
        defaults = {
            "SEC_USER_AGENT": "market-research-skill/1.0 your-email@example.com",
            "RESEARCH_DATA_DIR": "./data",
            "RESEARCH_REPORTS_DIR": "./reports",
            "RESEARCH_RUNTIME_DIR": "./runtime",
            "RESEARCH_CACHE_DIR": "./data/cache",
        }
        default = defaults.get(key, "")
        lines.append(f"{key}={default}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def resolve_storage_paths(
    repo_root: Path | str,
    config: ProviderConfig,
    data_dir: str | None = None,
    cache_dir: str | None = None,
    reports_dir: str | None = None,
    runtime_dir: str | None = None,
) -> dict[str, Path]:
    root = Path(repo_root)
    resolved_data = Path(data_dir or config.values.get("RESEARCH_DATA_DIR", root / "data"))
    resolved_reports = Path(reports_dir or config.values.get("RESEARCH_REPORTS_DIR", root / "reports"))
    resolved_runtime = Path(runtime_dir or config.values.get("RESEARCH_RUNTIME_DIR", root / "runtime"))
    resolved_cache = Path(cache_dir or config.values.get("RESEARCH_CACHE_DIR", resolved_data / "cache"))
    return {
        "data_dir": resolved_data,
        "reports_dir": resolved_reports,
        "runtime_dir": resolved_runtime,
        "cache_dir": resolved_cache,
    }


DETERMINISTIC_OUTPUT_ROOT_MESSAGE = (
    "Deterministic output root must be a directory named data and must not be under runtime or reports."
)


def is_relative_to_path(path: Path, root: Path | None) -> bool:
    if root is None:
        return False
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError:
        return False
    return True


def ensure_deterministic_output_root(output_root: Path, runtime_root: Path | None = None, reports_root: Path | None = None) -> None:
    if output_root.name != "data" or is_relative_to_path(output_root, runtime_root) or is_relative_to_path(output_root, reports_root):
        die(DETERMINISTIC_OUTPUT_ROOT_MESSAGE)


def cache_key(provider: str, endpoint: str, params: dict[str, Any]) -> str:
    clean = {str(k): params[k] for k in sorted(params)}
    digest = hashlib.sha256(json.dumps(clean, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:16]
    safe_endpoint = re.sub(r"[^A-Za-z0-9_.-]+", "_", endpoint).strip("_")
    return f"{provider}_{safe_endpoint}_{digest}"


def cache_symbol_for_endpoint(symbol: str, provider: str, endpoint: str) -> str:
    if provider == "sec" and endpoint == "company_tickers":
        return "_global"
    return normalize_symbol(symbol)


def raw_path(cache_root: Path, symbol: str, provider: str, endpoint: str, params: dict[str, Any]) -> Path:
    return cache_root / cache_symbol_for_endpoint(symbol, provider, endpoint) / provider / f"{cache_key(provider, endpoint, params)}.json"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_raw(
    cache_root: Path,
    symbol: str,
    provider: str,
    endpoint: str,
    params: dict[str, Any],
    data: Any,
    source_url: str,
    status: str = "ok",
    error: str | None = None,
    error_metadata: dict[str, Any] | None = None,
) -> Path:
    path = raw_path(cache_root, symbol, provider, endpoint, params)
    provider_result = {
        "provider": provider,
        "endpoint": endpoint,
        "url": source_url,
        "params_hash": cache_key(provider, endpoint, params).split("_")[-1],
        "fetched_at_utc": utc_now(),
        "source_as_of": None,
        "raw_path": str(path),
        "status": status,
        "error": error,
    }
    if error_metadata:
        provider_result.update(error_metadata)
    payload = {"provider_result": provider_result, "data": data}
    write_json(path, payload)
    return path


def classify_provider_payload(provider: str, data: Any) -> tuple[str, str | None]:
    if provider == "alphavantage" and isinstance(data, dict):
        for key in ["Information", "Note"]:
            if key in data:
                return "rate_limited", f"{key}: {data[key]}"
        if "Error Message" in data:
            return "error", f"Error Message: {data['Error Message']}"
    if provider == "twelve_data" and isinstance(data, dict) and data.get("status") == "error":
        message_text = str(data.get("message") or data.get("code") or "Twelve Data error payload")
        return classify_provider_error_message(message_text), message_text
    if provider in {"fmp", "marketaux", "eodhd"} and isinstance(data, dict):
        message = data.get("Error Message") or data.get("error") or data.get("message") or data.get("Information")
        if message:
            message_text = str(message)
            return classify_provider_error_message(message_text), message_text
    return "ok", None


def classify_provider_error_message(message: str) -> str:
    lowered = message.lower()
    plan_needles = [
        "available exclusively",
        "available starting with",
        "only eod data allowed",
        "payment required",
        "subscription",
        "premium",
        "upgrade",
        " plan",
        "plans",
        "pricing",
        "free users",
    ]
    if any(needle in lowered for needle in plan_needles):
        return "plan_gated"
    if any(needle in lowered for needle in ["unauthorized", "forbidden", "invalid api", "invalid token", "not authorized"]):
        return "unauthorized"
    if any(needle in lowered for needle in ["rate", "limit", "quota", "exceed"]):
        return "rate_limited"
    return "error"


def extract_html_title(body: str) -> str | None:
    match = re.search(r"<title>(.*?)</title>", body, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return re.sub(r"\s+", " ", match.group(1)).strip()


def classify_http_error(provider: str, code: int, body: str) -> tuple[str, str]:
    title = extract_html_title(body)
    if provider == "sec" and code == 403 and title and "Request Rate Threshold Exceeded" in title:
        return "rate_limited", f"HTTP 403: {title}"
    body_text = re.sub(r"\s+", " ", body).strip()
    body_status = classify_provider_error_message(body_text) if body_text else None
    if body_status in {"plan_gated", "rate_limited"}:
        return body_status, body_text or f"HTTP {code}"
    if code == 429:
        return "rate_limited", f"HTTP {code}"
    if code in {401, 403}:
        return "unauthorized", f"HTTP {code}" if not title else f"HTTP {code}: {title}"
    if code == 402:
        return "plan_gated", f"HTTP {code}"
    return "error", f"HTTP {code}" if not title else f"HTTP {code}: {title}"


def read_raw_latest(cache_root: Path, symbol: str, provider: str, endpoint: str) -> tuple[Path, dict[str, Any]] | None:
    root = cache_root / cache_symbol_for_endpoint(symbol, provider, endpoint) / provider
    files = sorted(root.glob(f"{provider}_{endpoint}_*.json"), key=lambda path: (path.stat().st_mtime, path.name))
    if not files:
        return None
    path = files[-1]
    return path, read_json(path)


def reusable_cached_raw(cache_root: Path, symbol: str, provider: str, endpoint: str, refresh: bool = False) -> Path | None:
    if refresh:
        return None
    latest = read_raw_latest(cache_root, symbol, provider, endpoint)
    if not latest:
        return None
    path, payload = latest
    status = payload.get("provider_result", {}).get("status", "ok")
    semantic_status, _ = classify_provider_payload(provider, payload.get("data"))
    if status == "ok" and semantic_status == "ok":
        return path
    return None


def raw_payload_status(provider: str, payload: dict[str, Any]) -> str:
    stored_status = payload.get("provider_result", {}).get("status", "ok")
    semantic_status, _ = classify_provider_payload(provider, payload.get("data"))
    return semantic_status if semantic_status != "ok" else stored_status


def raw_payload_ok(provider: str, payload: dict[str, Any]) -> bool:
    return raw_payload_status(provider, payload) == "ok"


def provenance(value: Any, provider: str, source_url: str, endpoint: str, raw: Path, unit: str | None = None, as_of: str | None = None, status: str = "ok", alternates: list[dict[str, Any]] | None = None, attempted_providers: list[str] | None = None, selection_reason: str | None = None) -> dict[str, Any]:
    point = {
        "value": value,
        "unit": unit,
        "period": None,
        "as_of": as_of,
        "provider": provider,
        "source_url": source_url,
        "endpoint": endpoint,
        "raw_path": str(raw),
        "fetched_at_utc": utc_now(),
        "status": status,
    }
    if alternates:
        point["alternates"] = alternates
    if attempted_providers:
        point["attempted_providers"] = attempted_providers
    if selection_reason:
        point["selection_reason"] = selection_reason
    return point


def data_point_candidate(value: Any, provider: str, source_url: str, endpoint: str, raw: Path, unit: str | None = None, as_of: str | None = None) -> dict[str, Any]:
    return provenance(value, provider, source_url, endpoint, raw, unit=unit, as_of=as_of)


def choose_candidate(candidates: list[dict[str, Any]], attempted_providers: list[str], selection_reason: str = "primary_source_priority") -> dict[str, Any] | None:
    usable = [candidate for candidate in candidates if candidate.get("value") not in (None, "", [], {})]
    if not usable:
        return None
    chosen = dict(usable[0])
    alternates = [dict(candidate) for candidate in usable[1:]]
    if alternates:
        chosen["alternates"] = alternates
    chosen["attempted_providers"] = attempted_providers
    chosen["selection_reason"] = selection_reason
    return chosen


def retry_policy_for_provider(provider: str) -> RetryPolicy:
    if provider == "sec":
        return RetryPolicy(max_attempts=3, initial_backoff_seconds=1.0)
    if provider in {"alphavantage", "twelve_data", "marketaux"}:
        return RetryPolicy(max_attempts=3, initial_backoff_seconds=1.0)
    return RetryPolicy(max_attempts=3, initial_backoff_seconds=0.5)


def should_retry(exc: BaseException, policy: RetryPolicy, provider: str | None = None, headers: dict[str, str] | None = None) -> bool:
    if isinstance(exc, HTTPError):
        if provider == "sec" and exc.code == 403:
            body = exc.read(4096).decode("utf-8", "replace")
            status, _error = classify_http_error("sec", exc.code, body)
            user_agent = (headers or {}).get("User-Agent", "")
            return status == "rate_limited" and is_descriptive_sec_user_agent(user_agent)
        return exc.code in policy.retry_http_statuses
    if isinstance(exc, (URLError, TimeoutError)):
        return policy.retry_url_errors
    return False


def http_json(url: str, headers: dict[str, str] | None = None, timeout: int = 20, retry_policy: RetryPolicy | None = None, provider: str | None = None) -> Any:
    policy = retry_policy or RetryPolicy(max_attempts=1)
    request = Request(url, headers=headers or {})
    backoff = policy.initial_backoff_seconds
    for attempt in range(1, policy.max_attempts + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                body = response.read()
            return json.loads(body.decode("utf-8"))
        except (HTTPError, URLError, TimeoutError) as exc:
            if attempt >= policy.max_attempts or not should_retry(exc, policy, provider=provider, headers=headers):
                raise
            time.sleep(backoff)
            backoff *= policy.backoff_multiplier


def fetch_with_cache(cache_root: Path, symbol: str, provider: str, endpoint: str, params: dict[str, Any], url: str, source_url: str, config: ProviderConfig, headers: dict[str, str] | None = None, refresh: bool = False, reuse_endpoint_cache: bool = False) -> Path:
    path = raw_path(cache_root, symbol, provider, endpoint, params)
    if path.exists() and not refresh:
        return path
    if reuse_endpoint_cache:
        cached = reusable_cached_raw(cache_root, symbol, provider, endpoint, refresh=refresh)
        if cached:
            return cached
    try:
        data = http_json(url, headers=headers, retry_policy=retry_policy_for_provider(provider), provider=provider)
        status, semantic_error = classify_provider_payload(provider, data)
        return write_raw(cache_root, symbol, provider, endpoint, params, data, source_url=source_url, status=status, error=semantic_error)
    except HTTPError as exc:
        body_bytes = exc.read(4096)
        body_text = body_bytes.decode("utf-8", "replace")
        status, error = classify_http_error(provider, exc.code, body_text)
        metadata = {
            "http_status": exc.code,
            "response_headers": {str(k).lower(): str(v) for k, v in dict(exc.headers or {}).items()},
            "error_body_snippet": body_text[:2000],
        }
        return write_raw(cache_root, symbol, provider, endpoint, params, {}, source_url=redact(source_url, config), status=status, error=error, error_metadata=metadata)
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        return write_raw(cache_root, symbol, provider, endpoint, params, {}, source_url=redact(source_url, config), status="error", error=str(exc))


def fetch_provider(symbol: str, provider: str, as_of: str, cache_root: Path, config: ProviderConfig, refresh: bool = False, endpoints: set[str] | None = None) -> list[Path]:
    symbol = normalize_symbol(symbol)
    paths: list[Path] = []
    selected_endpoints = {"prices"} if provider == "tiingo" and endpoints is None else endpoints_for_provider(provider, endpoints)
    if provider == "sec":
        headers = {"User-Agent": sec_user_agent(config)}
        tickers_url = "https://www.sec.gov/files/company_tickers.json"
        if "company_tickers" in selected_endpoints:
            paths.append(fetch_with_cache(cache_root, symbol, "sec", "company_tickers", {}, tickers_url, tickers_url, config, headers, refresh, reuse_endpoint_cache=True))
        cik = cik_from_cached_tickers(cache_root, symbol)
        if cik:
            padded = f"{int(cik):010d}"
            for endpoint, url in {
                "submissions": f"https://data.sec.gov/submissions/CIK{padded}.json",
                "companyfacts": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{padded}.json",
            }.items():
                if endpoint in selected_endpoints:
                    paths.append(fetch_with_cache(cache_root, symbol, "sec", endpoint, {"cik": padded}, url, url, config, headers, refresh, reuse_endpoint_cache=True))
    elif provider == "tiingo" and config.values.get("TIINGO_API_TOKEN"):
        token = config.values["TIINGO_API_TOKEN"]
        if "metadata" in selected_endpoints:
            params = {}
            url = f"https://api.tiingo.com/tiingo/daily/{symbol}?{urlencode({'token': token})}"
            source = f"https://api.tiingo.com/tiingo/daily/{symbol}"
            paths.append(fetch_with_cache(cache_root, symbol, "tiingo", "metadata", params, url, source, config, refresh=refresh, reuse_endpoint_cache=True))
        if "prices" in selected_endpoints:
            params = {"startDate": "2021-01-01", "endDate": as_of}
            query = urlencode({**params, "token": token})
            safe_query = urlencode(params)
            url = f"https://api.tiingo.com/tiingo/daily/{symbol}/prices?{query}"
            source = f"https://api.tiingo.com/tiingo/daily/{symbol}/prices?{safe_query}"
            paths.append(fetch_with_cache(cache_root, symbol, "tiingo", "prices", params, url, source, config, refresh=refresh, reuse_endpoint_cache=True))
    elif provider == "eodhd" and config.values.get("EODHD_API_KEY"):
        token = config.values["EODHD_API_KEY"]
        eodhd_symbol = symbol if "." in symbol else f"{symbol}.US"
        specs = {
            "fundamentals": (f"https://eodhd.com/api/fundamentals/{eodhd_symbol}", {"fmt": "json"}),
            "news": ("https://eodhd.com/api/news", {"s": eodhd_symbol, "limit": "10", "fmt": "json"}),
            "historical_market_cap": (f"https://eodhd.com/api/historical-market-cap/{eodhd_symbol}", {"fmt": "json"}),
            "prices": (f"https://eodhd.com/api/eod/{eodhd_symbol}", {"fmt": "json", "from": "2021-01-01", "to": as_of}),
        }
        for endpoint, (base, params) in specs.items():
            if endpoint not in selected_endpoints:
                continue
            url = f"{base}?{urlencode({**params, 'api_token': token})}"
            source = f"{base}?{urlencode(params)}"
            paths.append(fetch_with_cache(cache_root, symbol, "eodhd", endpoint, params, url, source, config, refresh=refresh, reuse_endpoint_cache=True))
    elif provider == "alphavantage" and config.values.get("ALPHAVANTAGE_API_KEY"):
        token = config.values["ALPHAVANTAGE_API_KEY"]
        functions = {
            "overview": "OVERVIEW",
            "income_statement": "INCOME_STATEMENT",
            "balance_sheet": "BALANCE_SHEET",
            "cash_flow": "CASH_FLOW",
            "earnings": "EARNINGS",
            "etf_profile": "ETF_PROFILE",
            "news_sentiment": "NEWS_SENTIMENT",
            "prices": "TIME_SERIES_DAILY_ADJUSTED",
        }
        for endpoint, function in functions.items():
            if endpoint not in selected_endpoints:
                continue
            params = {"function": function, "tickers": symbol} if endpoint == "news_sentiment" else {"function": function, "symbol": symbol}
            url = f"https://www.alphavantage.co/query?{urlencode({**params, 'apikey': token})}"
            source = f"https://www.alphavantage.co/query?{urlencode(params)}"
            paths.append(fetch_with_cache(cache_root, symbol, "alphavantage", endpoint, params, url, source, config, refresh=refresh, reuse_endpoint_cache=True))
            time.sleep(0.2)
    elif provider == "twelve_data" and config.values.get("TWELVE_DATA_API_KEY"):
        token = config.values["TWELVE_DATA_API_KEY"]
        specs = {
            "quote": ("https://api.twelvedata.com/quote", {"symbol": symbol}),
            "profile": ("https://api.twelvedata.com/profile", {"symbol": symbol}),
            "prices": ("https://api.twelvedata.com/time_series", {"symbol": symbol, "interval": "1day", "outputsize": "5000", "end_date": as_of}),
        }
        for endpoint, (base, params) in specs.items():
            if endpoint not in selected_endpoints:
                continue
            url = f"{base}?{urlencode({**params, 'apikey': token})}"
            source = f"{base}?{urlencode(params)}"
            paths.append(fetch_with_cache(cache_root, symbol, "twelve_data", endpoint, params, url, source, config, refresh=refresh, reuse_endpoint_cache=True))
    elif provider == "marketaux" and config.values.get("MARKETAUX_API_TOKEN") and "news" in selected_endpoints:
        token = config.values["MARKETAUX_API_TOKEN"]
        params = {"symbols": symbol, "language": "en", "limit": config.values.get("MARKETAUX_NEWS_LIMIT", "3")}
        url = f"https://api.marketaux.com/v1/news/all?{urlencode({**params, 'api_token': token})}"
        source = f"https://api.marketaux.com/v1/news/all?{urlencode(params)}"
        headers = {"User-Agent": http_user_agent(config), "Accept": "application/json"}
        paths.append(fetch_with_cache(cache_root, symbol, "marketaux", "news", params, url, source, config, headers=headers, refresh=refresh, reuse_endpoint_cache=True))
    elif provider == "fmp" and config.values.get("FMP_API_KEY"):
        token = config.values["FMP_API_KEY"]
        specs = {
            "profile": ("https://financialmodelingprep.com/stable/profile", {"symbol": symbol}),
            "key_metrics_ttm": ("https://financialmodelingprep.com/stable/key-metrics-ttm", {"symbol": symbol}),
            "ratios_ttm": ("https://financialmodelingprep.com/stable/ratios-ttm", {"symbol": symbol}),
            "income_statement": ("https://financialmodelingprep.com/stable/income-statement", {"symbol": symbol, "limit": "5"}),
            "balance_sheet": ("https://financialmodelingprep.com/stable/balance-sheet-statement", {"symbol": symbol, "limit": "5"}),
            "cash_flow": ("https://financialmodelingprep.com/stable/cash-flow-statement", {"symbol": symbol, "limit": "5"}),
            "stock_news": ("https://financialmodelingprep.com/stable/news/stock", {"symbols": symbol, "limit": "10"}),
            "press_releases": ("https://financialmodelingprep.com/stable/news/press-releases", {"symbols": symbol, "limit": "10"}),
            "dividends": ("https://financialmodelingprep.com/stable/dividends", {"symbol": symbol, "limit": "10"}),
            "earnings": ("https://financialmodelingprep.com/stable/earnings", {"symbol": symbol, "limit": "10"}),
            "splits": ("https://financialmodelingprep.com/stable/splits", {"symbol": symbol, "limit": "10"}),
            "insider_trading": ("https://financialmodelingprep.com/stable/insider-trading", {"symbol": symbol, "limit": "10"}),
            "insider_statistics": ("https://financialmodelingprep.com/stable/insider-trading/statistics", {"symbol": symbol}),
            "etf_holdings": ("https://financialmodelingprep.com/stable/etf/holdings", {"symbol": symbol}),
        }
        for endpoint, (base, params) in specs.items():
            if endpoint not in selected_endpoints:
                continue
            url = f"{base}?{urlencode({**params, 'apikey': token})}"
            source = f"{base}?{urlencode(params)}"
            paths.append(fetch_with_cache(cache_root, symbol, "fmp", endpoint, params, url, source, config, refresh=refresh, reuse_endpoint_cache=True))
            time.sleep(0.05)
    return paths


def cik_from_cached_tickers(cache_root: Path, symbol: str) -> str | None:
    raw = read_raw_latest(cache_root, symbol, "sec", "company_tickers")
    if not raw:
        return None
    data = raw[1].get("data", {})
    for item in data.values() if isinstance(data, dict) else []:
        if isinstance(item, dict) and str(item.get("ticker", "")).upper() == symbol:
            return str(item.get("cik_str"))
    return None


def provider_call_budget(provider: str, budgets: dict[str, int]) -> int:
    if provider in budgets:
        return budgets[provider]
    if provider == "sec":
        return 10
    if provider in PROVIDER_ENDPOINT_COSTS:
        return sum(PROVIDER_ENDPOINT_COSTS[provider].values())
    return 2


def endpoints_for_provider(provider: str, endpoints: set[str] | None = None) -> set[str]:
    available = set(PROVIDER_ENDPOINT_COSTS.get(provider, {}))
    if endpoints is None:
        return available
    return {endpoint for endpoint in endpoints if endpoint in available}


def default_endpoint_plan(providers: list[str]) -> dict[str, set[str]]:
    plan = {provider: set(UNIQUE_DEFAULT_ENDPOINTS.get(provider, set(PROVIDER_ENDPOINT_COSTS.get(provider, {})))) for provider in providers}
    for provider in PRICE_PROVIDER_PRIORITY:
        if provider in providers:
            plan.setdefault(provider, set()).add("prices")
    return plan


def parse_provider_endpoints(items: list[str] | None, providers: list[str]) -> dict[str, set[str]]:
    plan = default_endpoint_plan(providers)
    for item in items or []:
        if "=" not in item:
            die(f"Invalid provider endpoint filter {item!r}; expected PROVIDER=ENDPOINT[,ENDPOINT]")
        provider, value = item.split("=", 1)
        provider = provider.strip()
        requested = {part.strip() for part in value.split(",") if part.strip()}
        unknown = requested - set(PROVIDER_ENDPOINT_COSTS.get(provider, {}))
        if unknown:
            die(f"Unknown endpoint(s) for {provider}: {', '.join(sorted(unknown))}")
        plan[provider] = requested
    return plan


def provider_endpoint_enabled(endpoint_plan: dict[str, set[str]] | None, provider: str, endpoint: str) -> bool:
    if endpoint_plan is None:
        return True
    return endpoint in endpoint_plan.get(provider, set())


def estimated_provider_call_cost(cache_root: Path, symbol: str, provider: str, refresh: bool = False, endpoints: set[str] | None = None) -> int:
    endpoint_costs = PROVIDER_ENDPOINT_COSTS.get(provider, {})
    cost = 0
    for endpoint in endpoints_for_provider(provider, endpoints):
        endpoint_cost = endpoint_costs[endpoint]
        if reusable_cached_raw(cache_root, symbol, provider, endpoint, refresh=refresh):
            continue
        cost += endpoint_cost
    return cost


def endpoints_within_budget(cache_root: Path, symbol: str, provider: str, budget: int, refresh: bool = False, endpoints: set[str] | None = None) -> set[str]:
    selected = endpoints_for_provider(provider, endpoints)
    endpoint_costs = PROVIDER_ENDPOINT_COSTS.get(provider, {})
    ordered = [endpoint for endpoint in ENDPOINT_BUDGET_PRIORITY.get(provider, []) if endpoint in selected]
    ordered.extend(sorted(selected - set(ordered)))
    allowed: set[str] = set()
    remaining = budget
    for endpoint in ordered:
        endpoint_cost = endpoint_costs[endpoint]
        if endpoint_cost > remaining:
            continue
        allowed.add(endpoint)
        remaining -= endpoint_cost
    return allowed


def parse_provider_list(value: str | None, config: ProviderConfig) -> list[str]:
    if value:
        return [p.strip() for p in value.split(",") if p.strip()]
    found = configured_providers(config)
    return [p for p in DEFAULT_PROVIDERS if p in found]


def parse_budgets(items: list[str] | None) -> dict[str, int]:
    budgets: dict[str, int] = {}
    for item in items or []:
        if "=" not in item:
            die(f"Invalid budget {item!r}; expected PROVIDER=N")
        provider, value = item.split("=", 1)
        budgets[provider.strip()] = int(value)
    return budgets


def collect_provider_status(cache_root: Path, symbol: str, providers: list[str], endpoint_plan: dict[str, set[str]] | None = None) -> list[dict[str, Any]]:
    statuses = []
    for provider in providers:
        roots = [cache_root / symbol / provider]
        if provider == "sec":
            roots.insert(0, cache_root / "_global" / provider)
        files = []
        for root in roots:
            if root.exists():
                files.extend(root.glob("*.json"))
        files = sorted(set(files))
        raw_statuses = []
        for path in files:
            payload = read_json(path)
            endpoint = payload.get("provider_result", {}).get("endpoint")
            if endpoint and not provider_endpoint_enabled(endpoint_plan, provider, endpoint):
                continue
            semantic_status, _ = classify_provider_payload(provider, payload.get("data"))
            raw_statuses.append(semantic_status if semantic_status != "ok" else payload.get("provider_result", {}).get("status", "ok"))
        errors = [status for status in raw_statuses if status != "ok"]
        ok_files = sum(1 for status in raw_statuses if status == "ok")
        status = errors[-1] if errors else "ok" if raw_statuses else "missing"
        item = {"provider": provider, "raw_files": len(raw_statuses), "ok_files": ok_files, "status": status}
        if errors:
            item["errors"] = len(errors)
        statuses.append(item)
    return statuses


def provider_enabled(providers: list[str], provider: str) -> bool:
    return provider in providers


def provider_status_warnings(statuses: list[dict[str, Any]]) -> list[str]:
    warnings = []
    for item in statuses:
        status = item.get("status")
        if status in {"rate_limited", "quota_exhausted"}:
            warnings.append(f"Provider {item.get('provider')} reported {status}; cached raw response records the exhausted quota location.")
        elif status == "plan_gated":
            warnings.append(f"Provider {item.get('provider')} reported plan_gated; cached raw response records the gated endpoint.")
        elif status == "unauthorized":
            warnings.append(f"Provider {item.get('provider')} reported unauthorized for one or more endpoints; usable endpoint data was preserved when available.")
        elif status == "error":
            warnings.append(f"Provider {item.get('provider')} reported error; inspect source_manifest.json and raw provider_result.error for the failing endpoint.")
    return warnings


def raise_for_auth_failures(statuses: list[dict[str, Any]]) -> None:
    failed = [item for item in statuses if item.get("status") == "unauthorized" and not item.get("ok_files")]
    if failed:
        providers = ", ".join(str(item.get("provider")) for item in failed)
        die(f"Authentication failed for provider(s): {providers}. Check API token or account permissions.")


def normalize_identity(cache_root: Path, symbol: str, providers: list[str] | None = None, endpoint_plan: dict[str, set[str]] | None = None) -> dict[str, Any]:
    providers = providers or DEFAULT_PROVIDERS
    identity: dict[str, Any] = {"input_symbol": provenance(symbol, "input", "", "symbol", Path("")), "normalized_symbol": provenance(symbol, "input", "", "symbol", Path(""))}
    submissions = read_raw_latest(cache_root, symbol, "sec", "submissions") if provider_enabled(providers, "sec") and provider_endpoint_enabled(endpoint_plan, "sec", "submissions") else None
    if submissions and raw_payload_ok("sec", submissions[1]):
        raw, payload = submissions
        data = payload.get("data", {})
        url = payload.get("provider_result", {}).get("url", "")
        if data.get("name"):
            identity["company_name"] = provenance(data["name"], "sec", url, "submissions", raw)
        if data.get("sic"):
            identity["sic"] = provenance(data["sic"], "sec", url, "submissions", raw)
        if data.get("exchanges"):
            identity["exchange"] = provenance(data["exchanges"][0], "sec", url, "submissions", raw)
        recent_forms = data.get("filings", {}).get("recent", {}).get("form", []) if isinstance(data.get("filings"), dict) else []
        asset_type = "adr" if any(form in {"20-F", "40-F", "6-K"} for form in recent_forms) else "equity"
        identity["asset_type"] = provenance(asset_type, "sec", url, "submissions", raw)
    eod = read_raw_latest(cache_root, symbol, "eodhd", "fundamentals") if provider_enabled(providers, "eodhd") and provider_endpoint_enabled(endpoint_plan, "eodhd", "fundamentals") else None
    if eod and raw_payload_ok("eodhd", eod[1]) and "company_name" not in identity:
        raw, payload = eod
        general = payload.get("data", {}).get("General", {})
        url = payload.get("provider_result", {}).get("url", "")
        if general.get("Name"):
            identity["company_name"] = provenance(general["Name"], "eodhd", url, "fundamentals", raw)
        if general.get("Exchange"):
            identity["exchange"] = provenance(general["Exchange"], "eodhd", url, "fundamentals", raw)
        if "asset_type" not in identity:
            category = f"{general.get('Type', '')} {general.get('Category', '')}".lower()
            asset_type = "etf" if "etf" in category or "fund" in category else "equity"
            identity["asset_type"] = provenance(asset_type, "eodhd", url, "fundamentals", raw)
    fmp = read_raw_latest(cache_root, symbol, "fmp", "profile") if provider_enabled(providers, "fmp") and provider_endpoint_enabled(endpoint_plan, "fmp", "profile") else None
    if fmp and raw_payload_ok("fmp", fmp[1]):
        raw, payload = fmp
        data = first_dict(payload.get("data"))
        url = payload.get("provider_result", {}).get("url", "")
        if data:
            if data.get("companyName") and "company_name" not in identity:
                identity["company_name"] = provenance(data["companyName"], "fmp", url, "profile", raw)
            if data.get("exchangeShortName") and "exchange" not in identity:
                identity["exchange"] = provenance(data["exchangeShortName"], "fmp", url, "profile", raw)
            if data.get("industry"):
                identity["industry"] = provenance(data["industry"], "fmp", url, "profile", raw)
            if "asset_type" not in identity:
                identity["asset_type"] = provenance("equity", "fmp", url, "profile", raw)
    twelve = read_raw_latest(cache_root, symbol, "twelve_data", "profile") if provider_enabled(providers, "twelve_data") and provider_endpoint_enabled(endpoint_plan, "twelve_data", "profile") else None
    if twelve and raw_payload_ok("twelve_data", twelve[1]):
        raw, payload = twelve
        data = first_dict(payload.get("data"))
        url = payload.get("provider_result", {}).get("url", "")
        if data:
            name = data.get("name") or data.get("company_name") or data.get("instrument_name")
            if name and "company_name" not in identity:
                identity["company_name"] = provenance(name, "twelve_data", url, "profile", raw)
            exchange = data.get("exchange") or data.get("exchange_name") or data.get("mic_code")
            if exchange and "exchange" not in identity:
                identity["exchange"] = provenance(exchange, "twelve_data", url, "profile", raw)
            currency = data.get("currency") or data.get("currency_base")
            if currency:
                identity["currency"] = provenance(currency, "twelve_data", url, "profile", raw)
            if "asset_type" not in identity:
                type_text = str(data.get("type") or data.get("instrument_type") or "").lower()
                if "etf" in type_text:
                    asset_type = "etf"
                elif "fund" in type_text:
                    asset_type = "fund"
                elif any(value in type_text for value in ["stock", "common", "equity"]):
                    asset_type = "equity"
                else:
                    asset_type = "unknown"
                identity["asset_type"] = provenance(asset_type, "twelve_data", url, "profile", raw, status="ok" if asset_type != "unknown" else "gap")
    if "asset_type" not in identity:
        identity["asset_type"] = provenance("unknown", "deterministic_classifier", "", "classification", Path(""), status="gap")
    return identity


def normalize_prices(cache_root: Path, symbol: str, providers: list[str] | None = None, endpoint_plan: dict[str, set[str]] | None = None) -> tuple[list[dict[str, Any]], Path | None, str, str]:
    providers = providers or DEFAULT_PROVIDERS
    sources = [
        ("tiingo", "prices"),
        ("eodhd", "prices"),
        ("alphavantage", "prices"),
        ("twelve_data", "prices"),
    ]
    for provider, endpoint in sources:
        if not provider_enabled(providers, provider) or not provider_endpoint_enabled(endpoint_plan, provider, endpoint):
            continue
        raw = read_raw_latest(cache_root, symbol, provider, endpoint)
        if not raw:
            continue
        path, payload = raw
        if not raw_payload_ok(provider, payload):
            continue
        data = payload.get("data")
        rows = parse_price_rows(provider, data)
        if rows:
            rows = sorted(rows, key=lambda row: row["date"])
            return rows, path, provider, payload.get("provider_result", {}).get("url", "")
    return [], None, "", ""


def parse_price_rows(provider: str, data: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if provider in {"tiingo", "eodhd"} and isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                date_value = str(item.get("date", ""))[:10]
                close = item.get("adjClose", item.get("adjusted_close", item.get("close")))
                if date_value and close is not None:
                    rows.append({"date": date_value, "open": number(item.get("open")), "high": number(item.get("high")), "low": number(item.get("low")), "close": number(item.get("close", close)), "adjusted_close": number(close), "volume": number(item.get("volume"))})
    elif provider == "alphavantage" and isinstance(data, dict):
        series = data.get("Time Series (Daily)", {})
        for date_value, item in series.items():
            rows.append({"date": date_value, "open": number(item.get("1. open")), "high": number(item.get("2. high")), "low": number(item.get("3. low")), "close": number(item.get("4. close")), "adjusted_close": number(item.get("5. adjusted close", item.get("4. close"))), "volume": number(item.get("6. volume"))})
    elif provider == "twelve_data" and isinstance(data, dict):
        for item in data.get("values", []):
            rows.append({"date": str(item.get("datetime", ""))[:10], "open": number(item.get("open")), "high": number(item.get("high")), "low": number(item.get("low")), "close": number(item.get("close")), "adjusted_close": number(item.get("close")), "volume": number(item.get("volume"))})
    return [row for row in rows if row["date"] and row["adjusted_close"] is not None]


def number(value: Any) -> float | int | None:
    if value in (None, ""):
        return None
    try:
        result = float(str(value).replace(",", ""))
    except ValueError:
        return None
    return int(result) if result.is_integer() else result


def average(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def pct_return(start: float, end: float) -> float | None:
    if not start:
        return None
    return (end / start) - 1


def max_drawdown(closes: list[float]) -> float | None:
    peak = -math.inf
    worst = 0.0
    for close in closes:
        peak = max(peak, close)
        if peak:
            worst = min(worst, close / peak - 1)
    return worst


def rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) <= period:
        return None
    changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    window = changes[-period:]
    gains = [max(change, 0.0) for change in window]
    losses = [abs(min(change, 0.0)) for change in window]
    avg_gain = average(gains) or 0.0
    avg_loss = average(losses) or 0.0
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    relative_strength = avg_gain / avg_loss
    return 100 - (100 / (1 + relative_strength))


def ema_series(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    multiplier = 2 / (period + 1)
    ema_values = [values[0]]
    for value in values[1:]:
        ema_values.append((value - ema_values[-1]) * multiplier + ema_values[-1])
    return ema_values


def macd(closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> dict[str, float] | None:
    if len(closes) < slow + signal:
        return None
    fast_ema = ema_series(closes, fast)
    slow_ema = ema_series(closes, slow)
    macd_line = [fast_value - slow_value for fast_value, slow_value in zip(fast_ema, slow_ema)]
    signal_line = ema_series(macd_line, signal)
    if not macd_line or not signal_line:
        return None
    return {
        "macd": round(macd_line[-1], 6),
        "signal": round(signal_line[-1], 6),
        "histogram": round(macd_line[-1] - signal_line[-1], 6),
    }


def realized_volatility(closes: list[float], period: int = 30) -> float | None:
    if len(closes) <= period:
        return None
    returns = [pct_return(closes[i - 1], closes[i]) for i in range(len(closes) - period, len(closes))]
    usable = [float(value) for value in returns if value is not None]
    if len(usable) < 2:
        return None
    mean = average(usable) or 0.0
    variance = sum((value - mean) ** 2 for value in usable) / (len(usable) - 1)
    return math.sqrt(variance) * math.sqrt(252)


def trend_classification(latest_close: float, sma_20: float | None, sma_50: float | None, sma_200: float | None) -> str:
    if sma_20 is None or sma_50 is None or sma_200 is None:
        return "insufficient_data"
    if latest_close > sma_20 > sma_50 > sma_200:
        return "strong_uptrend"
    if latest_close > sma_50 and sma_50 > sma_200:
        return "uptrend"
    if latest_close < sma_20 < sma_50 < sma_200:
        return "strong_downtrend"
    if latest_close < sma_50 and sma_50 < sma_200:
        return "downtrend"
    return "mixed"


def technicals_from_prices(rows: list[dict[str, Any]], provider: str, raw_path_value: Path | None, source_url: str) -> dict[str, Any]:
    raw = raw_path_value or Path("")
    closes = [float(row["adjusted_close"]) for row in rows if row.get("adjusted_close") is not None]
    volumes = [float(row["volume"]) for row in rows if row.get("volume") is not None]
    latest_date = rows[-1]["date"] if rows else None

    def point(name: str, value: Any, status: str = "ok") -> dict[str, Any]:
        return provenance(value, provider or "unavailable", source_url, "prices", raw, as_of=latest_date, status=status)

    result: dict[str, Any] = {}
    sma_values: dict[int, float | None] = {}
    for window in [20, 50, 100, 200]:
        if len(closes) >= window:
            sma_value = round(average(closes[-window:]) or 0, 6)
            sma_values[window] = sma_value
            result[f"sma_{window}"] = point(f"sma_{window}", sma_value)
        else:
            sma_values[window] = None
            result[f"sma_{window}"] = point(None, None, "insufficient_data")
    if closes:
        result["latest_close"] = point("latest_close", closes[-1])
        result["fifty_two_week_high"] = point("fifty_two_week_high", max(closes[-252:]))
        result["fifty_two_week_low"] = point("fifty_two_week_low", min(closes[-252:]))
        result["max_drawdown_available"] = point("max_drawdown_available", round(max_drawdown(closes) or 0, 6))
        rsi_value = rsi(closes, 14)
        result["rsi_14"] = point("rsi_14", round(rsi_value, 6) if rsi_value is not None else None, "ok" if rsi_value is not None else "insufficient_data")
        macd_value = macd(closes, 12, 26, 9)
        result["macd_12_26_9"] = point("macd_12_26_9", macd_value, "ok" if macd_value is not None else "insufficient_data")
        volatility_value = realized_volatility(closes, 30)
        result["realized_volatility_30"] = point("realized_volatility_30", round(volatility_value, 6) if volatility_value is not None else None, "ok" if volatility_value is not None else "insufficient_data")
        trend_value = trend_classification(closes[-1], sma_values.get(20), sma_values.get(50), sma_values.get(200))
        result["trend_classification"] = point("trend_classification", trend_value, "ok" if trend_value != "insufficient_data" else "insufficient_data")
    if volumes:
        result["average_volume_30"] = point("average_volume_30", round(average(volumes[-30:]) or 0, 6))
        result["average_volume_90"] = point("average_volume_90", round(average(volumes[-90:]) or 0, 6))
        if len(volumes) >= 90:
            avg_30 = average(volumes[-30:]) or 0
            avg_90 = average(volumes[-90:]) or 0
            relative_volume = avg_30 / avg_90 if avg_90 else None
            result["relative_volume_30_vs_90"] = point("relative_volume_30_vs_90", round(relative_volume, 6) if relative_volume is not None else None, "ok" if relative_volume is not None else "insufficient_data")
        else:
            result["relative_volume_30_vs_90"] = point(None, None, "insufficient_data")
    for name, periods in {"return_1m": 21, "return_3m": 63, "return_6m": 126, "return_1y": 252}.items():
        if len(closes) > periods:
            result[name] = point(name, round(pct_return(closes[-periods - 1], closes[-1]) or 0, 6))
        else:
            result[name] = point(None, None, "insufficient_data")
    return result


def normalize_market_snapshot(cache_root: Path, symbol: str, prices: list[dict[str, Any]], price_raw: Path | None, price_provider: str, price_url: str, providers: list[str] | None = None, endpoint_plan: dict[str, set[str]] | None = None) -> dict[str, Any]:
    providers = providers or DEFAULT_PROVIDERS
    snapshot: dict[str, Any] = {}
    if prices:
        latest = prices[-1]
        snapshot["latest_close"] = provenance(latest["adjusted_close"], price_provider, price_url, "prices", price_raw or Path(""), as_of=latest["date"])
        closes = [row["adjusted_close"] for row in prices if row.get("adjusted_close") is not None]
        snapshot["fifty_two_week_high"] = provenance(max(closes[-252:]), price_provider, price_url, "prices", price_raw or Path(""), as_of=latest["date"])
        snapshot["fifty_two_week_low"] = provenance(min(closes[-252:]), price_provider, price_url, "prices", price_raw or Path(""), as_of=latest["date"])
    quote = read_raw_latest(cache_root, symbol, "twelve_data", "quote") if provider_enabled(providers, "twelve_data") and provider_endpoint_enabled(endpoint_plan, "twelve_data", "quote") else None
    if quote:
        raw, payload = quote
        if raw_payload_ok("twelve_data", payload):
            data = payload.get("data", {})
            if isinstance(data, dict):
                url = payload.get("provider_result", {}).get("url", "")
                close = number(data.get("close") or data.get("previous_close"))
                volume = number(data.get("volume"))
                if close is not None and "latest_close" not in snapshot:
                    snapshot["latest_close"] = provenance(close, "twelve_data", url, "quote", raw)
                if volume is not None and "latest_volume" not in snapshot:
                    snapshot["latest_volume"] = provenance(volume, "twelve_data", url, "quote", raw)
    market_cap_candidates: list[dict[str, Any]] = []
    pe_candidates: list[dict[str, Any]] = []
    attempted = []
    eod = read_raw_latest(cache_root, symbol, "eodhd", "fundamentals") if provider_enabled(providers, "eodhd") and provider_endpoint_enabled(endpoint_plan, "eodhd", "fundamentals") else None
    if provider_enabled(providers, "eodhd") and provider_endpoint_enabled(endpoint_plan, "eodhd", "fundamentals"):
        attempted.append("eodhd")
    if eod:
        raw, payload = eod
        if not raw_payload_ok("eodhd", payload):
            eod = None
    if eod:
        raw, payload = eod
        data = payload.get("data", {})
        general = data.get("General", {})
        highlights = data.get("Highlights", {})
        url = payload.get("provider_result", {}).get("url", "")
        if general.get("MarketCapitalization") is not None:
            market_cap_candidates.append(data_point_candidate(general["MarketCapitalization"], "eodhd", url, "fundamentals", raw))
        if highlights.get("PERatio") is not None:
            pe_candidates.append(data_point_candidate(highlights["PERatio"], "eodhd", url, "fundamentals", raw))
    av = read_raw_latest(cache_root, symbol, "alphavantage", "overview") if provider_enabled(providers, "alphavantage") and provider_endpoint_enabled(endpoint_plan, "alphavantage", "overview") else None
    if provider_enabled(providers, "alphavantage") and provider_endpoint_enabled(endpoint_plan, "alphavantage", "overview"):
        attempted.append("alphavantage")
    if av:
        raw, payload = av
        if not raw_payload_ok("alphavantage", payload):
            av = None
    if av:
        raw, payload = av
        data = payload.get("data", {})
        url = payload.get("provider_result", {}).get("url", "")
        market_cap = number(data.get("MarketCapitalization"))
        pe_ratio = number(data.get("PERatio") or data.get("TrailingPE"))
        if market_cap is not None:
            market_cap_candidates.append(data_point_candidate(market_cap, "alphavantage", url, "overview", raw))
        if pe_ratio is not None:
            pe_candidates.append(data_point_candidate(pe_ratio, "alphavantage", url, "overview", raw))
        beta = number(data.get("Beta"))
        if beta is not None:
            snapshot["beta"] = provenance(beta, "alphavantage", url, "overview", raw)
    fmp = read_raw_latest(cache_root, symbol, "fmp", "profile") if provider_enabled(providers, "fmp") and provider_endpoint_enabled(endpoint_plan, "fmp", "profile") else None
    if provider_enabled(providers, "fmp") and provider_endpoint_enabled(endpoint_plan, "fmp", "profile"):
        attempted.append("fmp")
    if fmp:
        raw, payload = fmp
        if not raw_payload_ok("fmp", payload):
            fmp = None
    if fmp:
        raw, payload = fmp
        data = first_dict(payload.get("data"))
        url = payload.get("provider_result", {}).get("url", "")
        if data:
            market_cap = number(data.get("mktCap") or data.get("marketCap"))
            if market_cap is not None:
                market_cap_candidates.append(data_point_candidate(market_cap, "fmp", url, "profile", raw))
            beta = number(data.get("beta"))
            if beta is not None and "beta" not in snapshot:
                snapshot["beta"] = provenance(beta, "fmp", url, "profile", raw)
    chosen_market_cap = choose_candidate(market_cap_candidates, attempted)
    if chosen_market_cap:
        snapshot["market_capitalization"] = chosen_market_cap
    chosen_pe = choose_candidate(pe_candidates, attempted)
    if chosen_pe:
        snapshot["pe_ratio"] = chosen_pe
    return snapshot


def normalize_equity_fundamentals(cache_root: Path, symbol: str, providers: list[str] | None = None, endpoint_plan: dict[str, set[str]] | None = None) -> dict[str, Any]:
    providers = providers or DEFAULT_PROVIDERS
    fundamentals: dict[str, Any] = {}
    sec = read_raw_latest(cache_root, symbol, "sec", "companyfacts") if provider_enabled(providers, "sec") and provider_endpoint_enabled(endpoint_plan, "sec", "companyfacts") else None
    if sec and raw_payload_ok("sec", sec[1]):
        raw, payload = sec
        data = payload.get("data", {})
        url = payload.get("provider_result", {}).get("url", "")
        revenue = latest_companyfacts_usd_fact(data, ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"])
        if revenue:
            fundamentals["revenue"] = provenance(revenue, "sec", url, "companyfacts", raw, unit="USD", as_of=revenue.get("period_end"))
        net_income = latest_companyfacts_usd_fact(data, ["NetIncomeLoss", "ProfitLoss"])
        if net_income:
            fundamentals["net_income"] = provenance(net_income, "sec", url, "companyfacts", raw, unit="USD", as_of=net_income.get("period_end"))
    av = read_raw_latest(cache_root, symbol, "alphavantage", "overview") if provider_enabled(providers, "alphavantage") and provider_endpoint_enabled(endpoint_plan, "alphavantage", "overview") else None
    if av and raw_payload_ok("alphavantage", av[1]):
        raw, payload = av
        data = payload.get("data", {})
        url = payload.get("provider_result", {}).get("url", "")
        fields = {
            "revenue_ttm": ("RevenueTTM", None),
            "gross_profit_ttm": ("GrossProfitTTM", None),
            "ebitda": ("EBITDA", None),
            "eps": ("EPS", None),
            "diluted_eps_ttm": ("DilutedEPSTTM", None),
            "book_value": ("BookValue", None),
            "dividend_yield": ("DividendYield", None),
            "shares_outstanding": ("SharesOutstanding", None),
            "profit_margin": ("ProfitMargin", None),
            "operating_margin_ttm": ("OperatingMarginTTM", None),
            "return_on_assets_ttm": ("ReturnOnAssetsTTM", None),
            "return_on_equity_ttm": ("ReturnOnEquityTTM", None),
            "quarterly_revenue_growth_yoy": ("QuarterlyRevenueGrowthYOY", None),
            "quarterly_earnings_growth_yoy": ("QuarterlyEarningsGrowthYOY", None),
            "analyst_target_price": ("AnalystTargetPrice", None),
            "analyst_rating_strong_buy": ("AnalystRatingStrongBuy", None),
            "analyst_rating_buy": ("AnalystRatingBuy", None),
            "analyst_rating_hold": ("AnalystRatingHold", None),
            "analyst_rating_sell": ("AnalystRatingSell", None),
            "analyst_rating_strong_sell": ("AnalystRatingStrongSell", None),
        }
        for out_key, (provider_key, unit) in fields.items():
            value = number(data.get(provider_key))
            if value is not None:
                fundamentals[out_key] = provenance(value, "alphavantage", url, "overview", raw, unit=unit, as_of=data.get("LatestQuarter"))
    if provider_enabled(providers, "fmp"):
        fmp_fundamentals = normalize_fmp_fundamentals(cache_root, symbol, endpoint_plan)
        fundamentals.update({key: value for key, value in fmp_fundamentals.items() if key not in fundamentals})
    return fundamentals


def first_dict(data: Any) -> dict[str, Any] | None:
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                return item
    if isinstance(data, dict):
        return data
    return None


def fmp_first(cache_root: Path, symbol: str, endpoint: str, endpoint_plan: dict[str, set[str]] | None = None) -> tuple[Path, dict[str, Any], str] | None:
    if not provider_endpoint_enabled(endpoint_plan, "fmp", endpoint):
        return None
    raw = read_raw_latest(cache_root, symbol, "fmp", endpoint)
    if not raw:
        return None
    path, payload = raw
    if not raw_payload_ok("fmp", payload):
        return None
    item = first_dict(payload.get("data"))
    if not item:
        return None
    return path, item, payload.get("provider_result", {}).get("url", "")


def normalize_fmp_fundamentals(cache_root: Path, symbol: str, endpoint_plan: dict[str, set[str]] | None = None) -> dict[str, Any]:
    fundamentals: dict[str, Any] = {}

    latest_income = fmp_first(cache_root, symbol, "income_statement", endpoint_plan)
    if latest_income:
        raw, data, url = latest_income
        for out_key, provider_key, unit in [
            ("latest_revenue", "revenue", "USD"),
            ("latest_net_income", "netIncome", "USD"),
            ("eps", "eps", None),
        ]:
            value = number(data.get(provider_key))
            if value is not None:
                fundamentals[out_key] = provenance(value, "fmp", url, "income_statement", raw, unit=unit, as_of=data.get("date"))

    latest_balance = fmp_first(cache_root, symbol, "balance_sheet", endpoint_plan)
    if latest_balance:
        raw, data, url = latest_balance
        for out_key, provider_key in [("total_assets", "totalAssets"), ("total_debt", "totalDebt"), ("cash_and_short_term_investments", "cashAndShortTermInvestments")]:
            value = number(data.get(provider_key))
            if value is not None:
                fundamentals[out_key] = provenance(value, "fmp", url, "balance_sheet", raw, unit="USD", as_of=data.get("date"))

    latest_cash_flow = fmp_first(cache_root, symbol, "cash_flow", endpoint_plan)
    if latest_cash_flow:
        raw, data, url = latest_cash_flow
        for out_key, provider_key in [("operating_cash_flow", "operatingCashFlow"), ("free_cash_flow", "freeCashFlow"), ("capital_expenditure", "capitalExpenditure")]:
            value = number(data.get(provider_key))
            if value is not None:
                fundamentals[out_key] = provenance(value, "fmp", url, "cash_flow", raw, unit="USD", as_of=data.get("date"))

    latest_metrics = fmp_first(cache_root, symbol, "key_metrics_ttm", endpoint_plan)
    if latest_metrics:
        raw, data, url = latest_metrics
        for out_key, provider_key in [
            ("revenue_per_share_ttm", "revenuePerShareTTM"),
            ("net_income_per_share_ttm", "netIncomePerShareTTM"),
            ("enterprise_value_ttm", "enterpriseValueTTM"),
            ("ev_to_sales_ttm", "evToSalesTTM"),
        ]:
            value = number(data.get(provider_key))
            if value is not None:
                fundamentals[out_key] = provenance(value, "fmp", url, "key_metrics_ttm", raw)

    latest_ratios = fmp_first(cache_root, symbol, "ratios_ttm", endpoint_plan)
    if latest_ratios:
        raw, data, url = latest_ratios
        for out_key, provider_key in [
            ("gross_profit_margin_ttm", "grossProfitMarginTTM"),
            ("net_profit_margin_ttm", "netProfitMarginTTM"),
            ("current_ratio_ttm", "currentRatioTTM"),
            ("debt_to_equity_ttm", "debtToEquityRatioTTM"),
            ("return_on_equity_ttm", "returnOnEquityTTM"),
        ]:
            value = number(data.get(provider_key))
            if value is not None:
                fundamentals[out_key] = provenance(value, "fmp", url, "ratios_ttm", raw)
    return fundamentals


def nested_get(payload: dict[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def latest_companyfacts_usd_fact(companyfacts: dict[str, Any], names: list[str]) -> dict[str, Any] | None:
    facts = nested_get(companyfacts, "facts", "us-gaap")
    if not isinstance(facts, dict):
        return None
    candidates: list[dict[str, Any]] = []
    for name in names:
        values = nested_get(facts, name, "units", "USD")
        if not isinstance(values, list):
            continue
        annual = [item for item in values if isinstance(item, dict) and item.get("form") == "10-K" and item.get("fp") == "FY" and "val" in item]
        candidates.extend({**item, "_tag": name} for item in annual)
    if not candidates:
        return None
    item = sorted(candidates, key=lambda row: (int(row.get("fy") or 0), str(row.get("end") or ""), str(row.get("filed") or "")))[-1]
    return {
        "tag": item.get("_tag"),
        "value": item.get("val"),
        "fy": item.get("fy"),
        "period_end": item.get("end"),
        "filed": item.get("filed"),
        "form": item.get("form"),
    }


def default_gaps(identity: dict[str, Any], snapshot: dict[str, Any], fundamentals: dict[str, Any], attempted_providers: list[str]) -> list[dict[str, Any]]:
    requested = {
        "short_interest": "No configured free provider returned reproducible short-interest data.",
        "forward_estimates": "Forward estimates are unavailable from cached configured providers.",
        "analyst_context": "Analyst context is unavailable from cached configured providers.",
    }
    if identity.get("asset_type", {}).get("value") in {"etf", "fund", "unknown"}:
        requested.update({
            "etf_holdings": "Full ETF holdings are unavailable from configured official/public APIs in this run.",
            "nav": "ETF NAV is unavailable from cached configured providers.",
        })
    gaps = []
    for field, notes in requested.items():
        if field == "analyst_context":
            analyst_keys = {
                "analyst_target_price",
                "analyst_rating_strong_buy",
                "analyst_rating_buy",
                "analyst_rating_hold",
                "analyst_rating_sell",
                "analyst_rating_strong_sell",
            }
            if analyst_keys & fundamentals.keys():
                continue
        if field not in snapshot and field not in identity and field not in fundamentals:
            gaps.append({"field": field, "status": "unavailable_free_source", "attempted_sources": attempted_providers, "notes": notes})
    return gaps


def normalized_value(payload: dict[str, Any], key: str) -> Any:
    item = payload.get(key)
    if isinstance(item, dict):
        return item.get("value")
    return None


def infer_lifecycle_hints(asset_type: str | None, fundamentals: dict[str, Any], technicals: dict[str, Any]) -> dict[str, Any]:
    eps = number(normalized_value(fundamentals, "eps"))
    ebitda = number(normalized_value(fundamentals, "ebitda"))
    revenue_ttm = number(normalized_value(fundamentals, "revenue_ttm"))
    quarterly_revenue_growth = number(normalized_value(fundamentals, "quarterly_revenue_growth_yoy"))
    realized_volatility = number(normalized_value(technicals, "realized_volatility_30"))
    return {
        "asset_type": asset_type,
        "negative_eps": eps is not None and eps < 0,
        "negative_ebitda": ebitda is not None and ebitda < 0,
        "high_realized_volatility": realized_volatility is not None and realized_volatility >= 0.8,
        "micro_or_early_revenue": revenue_ttm is not None and revenue_ttm < 50_000_000,
        "recent_revenue_step_up": quarterly_revenue_growth is not None and quarterly_revenue_growth >= 0.5,
    }


def copy_raw_files(cache_root: Path, symbol: str, bundle_dir: Path, providers: list[str], endpoint_plan: dict[str, set[str]] | None = None) -> tuple[list[dict[str, Any]], dict[str, str]]:
    entries = []
    path_map: dict[str, str] = {}
    referenced_global_targets: dict[tuple[str, str], str] = {}
    roots = []
    if provider_enabled(providers, "sec"):
        roots.append(cache_root / "_global" / "sec")
    roots.extend(cache_root / symbol / provider for provider in providers)
    files = []
    for root in roots:
        if root.exists():
            files.extend(root.glob("*.json"))
    seen_targets: set[Path] = set()
    for path in sorted(files):
        payload = read_json(path)
        provider = payload.get("provider_result", {}).get("provider", path.parent.name)
        endpoint = payload.get("provider_result", {}).get("endpoint")
        if endpoint and not provider_endpoint_enabled(endpoint_plan, provider, endpoint):
            continue
        if provider == "sec" and endpoint == "company_tickers":
            key = (provider, endpoint)
            if key in referenced_global_targets:
                path_map[str(path)] = referenced_global_targets[key]
                continue
            referenced_global_targets[key] = str(path)
            path_map[str(path)] = str(path)
            entries.append({
                "provider": provider,
                "endpoint": endpoint,
                "url": payload.get("provider_result", {}).get("url"),
                "raw_path": str(path),
                "cache_raw_path": str(path),
                "status": payload.get("provider_result", {}).get("status"),
                "error": payload.get("provider_result", {}).get("error"),
                "sha256": sha256_file(path),
            })
            continue
        target = bundle_dir / "raw" / provider / path.name
        if target in seen_targets:
            path_map[str(path)] = str(target)
            continue
        seen_targets.add(target)
        semantic_status, semantic_error = classify_provider_payload(provider, payload.get("data"))
        if isinstance(payload.get("provider_result"), dict):
            payload["provider_result"]["raw_path"] = str(target)
            if semantic_status != "ok":
                payload["provider_result"]["status"] = semantic_status
                payload["provider_result"]["error"] = semantic_error
        write_json(target, payload)
        path_map[str(path)] = str(target)
        entries.append({
            "provider": provider,
            "endpoint": payload.get("provider_result", {}).get("endpoint"),
            "url": payload.get("provider_result", {}).get("url"),
            "raw_path": str(target),
            "cache_raw_path": str(path),
            "status": payload.get("provider_result", {}).get("status"),
            "error": payload.get("provider_result", {}).get("error"),
            "sha256": sha256_file(target),
        })
    return entries, path_map


def endpoint_status_from_raw_entries(raw_entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    statuses = []
    for entry in raw_entries:
        item = {
            "provider": entry.get("provider"),
            "endpoint": entry.get("endpoint"),
            "status": entry.get("status") or "missing",
            "raw_path": entry.get("raw_path"),
        }
        if entry.get("error"):
            item["error"] = entry.get("error")
        statuses.append(item)
    return statuses


def unwrap_provider_data(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data") if isinstance(payload, dict) else None
    return data if isinstance(data, dict) else payload


def emit_sec_filings_index(bundle_dir: Path, submissions_raw: Path, cik: str) -> None:
    payload = read_json(submissions_raw)
    data = unwrap_provider_data(payload)
    recent = data.get("filings", {}).get("recent", {}) if isinstance(data, dict) else {}
    if not isinstance(recent, dict):
        return
    accession_numbers = recent.get("accessionNumber", [])
    if not isinstance(accession_numbers, list):
        return
    normalized_dir = bundle_dir / "normalized"
    normalized_dir.mkdir(parents=True, exist_ok=True)
    cik_for_url = str(cik).lstrip("0") or str(cik)
    filings = []
    for index, accession in enumerate(accession_numbers):
        if not accession:
            continue
        primary_document = list_value(recent.get("primaryDocument"), index)
        accession_compact = str(accession).replace("-", "")
        primary_document_url = None
        if primary_document:
            primary_document_url = f"https://www.sec.gov/Archives/edgar/data/{cik_for_url}/{accession_compact}/{primary_document}"
        filings.append(
            {
                "accession_number": accession,
                "form": list_value(recent.get("form"), index),
                "filing_date": list_value(recent.get("filingDate"), index),
                "report_date": list_value(recent.get("reportDate"), index),
                "primary_document": primary_document,
                "primary_document_url": primary_document_url,
                "raw_path": str(submissions_raw),
                "status": "ok",
            }
        )
    write_json(normalized_dir / "sec_filings_index.json", {"filings": filings, "raw_path": str(submissions_raw), "status": "ok"})


def list_value(values: Any, index: int) -> Any:
    if isinstance(values, list) and index < len(values):
        return values[index]
    return None


ANALYSIS_LIMITATION_MAP = {
    ("fmp", "insider_statistics"): ("insider_activity", "dilution_and_governance_analysis_limited"),
    ("fmp", "insider_trading"): ("insider_activity", "dilution_and_governance_analysis_limited"),
    ("fmp", "key_metrics_ttm"): ("forward_valuation", "forward_valuation_analysis_limited"),
    ("fmp", "ratios_ttm"): ("forward_valuation", "forward_valuation_analysis_limited"),
    ("eodhd", "historical_market_cap"): ("market_cap_history", "historical_valuation_context_limited"),
}


def analysis_limitations_from_endpoint_status(endpoint_status: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for item in endpoint_status:
        if item.get("status") == "ok":
            continue
        key = (str(item.get("provider")), str(item.get("endpoint")))
        mapping = ANALYSIS_LIMITATION_MAP.get(key)
        if not mapping:
            continue
        area, impact = mapping
        group_key = (area, impact)
        entry = grouped.setdefault(
            group_key,
            {
                "area": area,
                "impact": impact,
                "status": "unavailable",
                "attempted_providers": [],
                "endpoints": [],
                "raw_paths": [],
            },
        )
        provider = item.get("provider")
        endpoint = item.get("endpoint")
        raw_path_value = item.get("raw_path")
        if provider and provider not in entry["attempted_providers"]:
            entry["attempted_providers"].append(provider)
        if endpoint and endpoint not in entry["endpoints"]:
            entry["endpoints"].append(endpoint)
        if raw_path_value and raw_path_value not in entry["raw_paths"]:
            entry["raw_paths"].append(raw_path_value)
    for entry in grouped.values():
        entry["attempted_providers"].sort()
        entry["endpoints"].sort()
        entry["raw_paths"].sort()
    return [grouped[key] for key in sorted(grouped)]


def discrepancies_from_snapshot(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    market_cap = snapshot.get("market_capitalization")
    if not isinstance(market_cap, dict):
        return []
    return market_cap_discrepancies(market_cap)


def market_cap_discrepancies(point: dict[str, Any], threshold: float = 0.2) -> list[dict[str, Any]]:
    primary_value = number(point.get("value"))
    if primary_value in (None, 0):
        return []
    discrepancies = []
    for alternate in point.get("alternates", []):
        if not isinstance(alternate, dict):
            continue
        alternate_value = number(alternate.get("value"))
        if alternate_value is None:
            continue
        relative_difference = abs(primary_value - alternate_value) / abs(primary_value)
        if relative_difference < threshold:
            continue
        discrepancies.append(
            {
                "field_path": "market_snapshot.market_capitalization",
                "severity": "material",
                "primary_provider": point.get("provider"),
                "primary_value": primary_value,
                "alternate_provider": alternate.get("provider"),
                "alternate_value": alternate_value,
                "relative_difference": round(relative_difference, 6),
                "impact": "valuation_multiples_require_range_or_caveat",
                "primary_raw_path": point.get("raw_path"),
                "alternate_raw_path": alternate.get("raw_path"),
            }
        )
    return discrepancies


def rewrite_raw_paths(payload: Any, path_map: dict[str, str]) -> Any:
    if isinstance(payload, dict):
        rewritten = {}
        for key, value in payload.items():
            if key == "raw_path" and isinstance(value, str) and value in path_map:
                rewritten[key] = path_map[value]
            else:
                rewritten[key] = rewrite_raw_paths(value, path_map)
        return rewritten
    if isinstance(payload, list):
        return [rewrite_raw_paths(item, path_map) for item in payload]
    return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit(repo_root: Path | None = None) -> str | None:
    try:
        result = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=repo_root or Path.cwd(), text=True, capture_output=True, check=False)
    except FileNotFoundError:
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def build_research_markdown(symbol: str, as_of: str, identity: dict[str, Any], snapshot: dict[str, Any], technicals: dict[str, Any], fundamentals: dict[str, Any], gaps: list[dict[str, Any]], usage_requirements: dict[str, Any] | None = None) -> str:
    lines = [f"# {symbol} Deterministic Research Input Pack", "", f"As of: {as_of}", "", "This is a deterministic data package, not investment advice.", "", "## Executive Summary Facts"]
    for key in ["company_name", "asset_type", "exchange", "sic"]:
        point = identity.get(key)
        if point:
            lines.append(f"- {key.replace('_', ' ').title()}: {point.get('value')}. Source: {point.get('provider')}, `{point.get('raw_path')}`.")
    lines.extend(["", "## Market Snapshot"])
    latest = snapshot.get("latest_close")
    if latest:
        lines.append(f"- Latest close: {latest.get('value')} as of {latest.get('as_of')}. Source: {latest.get('provider')}, `{latest.get('raw_path')}`.")
    for key in ["fifty_two_week_high", "fifty_two_week_low", "market_capitalization", "pe_ratio"]:
        point = snapshot.get(key)
        if point:
            lines.append(f"- {key.replace('_', ' ').title()}: {point.get('value')}. Source: {point.get('provider')}, `{point.get('raw_path')}`.")
    lines.extend(["", "## Technical Signals"])
    for key in ["sma_20", "sma_50", "sma_200", "return_1m", "return_1y", "average_volume_30"]:
        point = technicals.get(key)
        if point:
            value = point.get("value") if point.get("status") == "ok" else point.get("status")
            lines.append(f"- {key.upper()}: {value}. Source: {point.get('provider')}, `{point.get('raw_path')}`.")
    if fundamentals:
        lines.extend(["", "## Equity Fundamentals"])
        for key in ["revenue", "net_income", "revenue_ttm", "gross_profit_ttm", "ebitda", "eps", "profit_margin", "shares_outstanding"]:
            point = fundamentals.get(key)
            if point:
                lines.append(f"- {key.replace('_', ' ').title()}: {point.get('value')}. Source: {point.get('provider')}, `{point.get('raw_path')}`.")
    lines.extend(["", "## Data Gaps and Cautions"])
    for gap in gaps:
        lines.append(f"- {gap['field']}: {gap['notes']}")
    if usage_requirements:
        summary = usage_requirements.get("summary", {})
        lines.extend(
            [
                "",
                "## Deterministic Data Usage Requirements",
                f"- Total usable deterministic datapoints: {summary.get('total_ok_datapoints', 0)}.",
                f"- Required datapoints needing report use or disposition: {summary.get('required', 0)}.",
                f"- Review datapoints needing report use or disposition when material: {summary.get('review', 0)}.",
            ]
        )
        required_or_review = [
            item
            for item in usage_requirements.get("datapoints", [])
            if item.get("materiality") in {"required", "review"}
        ]
        for item in required_or_review[:40]:
            lines.append(
                f"- {item.get('field_path')}: {item.get('materiality')}; source {item.get('provider')}, `{item.get('raw_path')}`."
            )
    return "\n".join(lines) + "\n"


def assert_no_secrets_in_tree(root: Path, config: ProviderConfig | None) -> None:
    if not config:
        return
    secrets = [value for key, value in config.values.items() if value and (key in SECRET_NAMES or "TOKEN" in key or "KEY" in key)]
    for path in root.rglob("*"):
        if path.is_file() and path.suffix in {".json", ".md", ".txt"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for secret in secrets:
                if secret in text:
                    die(f"Secret value leaked into output file: {path}")


def build_bundle(symbol: str, as_of: str, cache_root: Path, output_root: Path, providers: list[str] | None = None, offline: bool = False, config: ProviderConfig | None = None, command: str | None = None, asset_type: str = "auto", warnings: list[str] | None = None, endpoint_plan: dict[str, set[str]] | None = None) -> dict[str, Any]:
    symbol = normalize_symbol(symbol)
    as_of = validate_as_of(as_of) or date.today().isoformat()
    ensure_deterministic_output_root(output_root)
    providers = providers or DEFAULT_PROVIDERS
    endpoint_plan = endpoint_plan or default_endpoint_plan(providers)
    bundle_dir = output_root / symbol / as_of
    normalized = bundle_dir / "normalized"
    normalized.mkdir(parents=True, exist_ok=True)
    for stale_json in normalized.glob("*.json"):
        stale_json.unlink()
    raw_entries, raw_path_map = copy_raw_files(cache_root, symbol, bundle_dir, providers, endpoint_plan)
    identity = normalize_identity(cache_root, symbol, providers, endpoint_plan)
    if asset_type != "auto":
        identity["asset_type"] = provenance(asset_type, "cli", "", "asset_type", Path(""))
    prices, price_raw, price_provider, price_url = normalize_prices(cache_root, symbol, providers, endpoint_plan)
    snapshot = normalize_market_snapshot(cache_root, symbol, prices, price_raw, price_provider, price_url, providers, endpoint_plan)
    technicals = technicals_from_prices(prices, price_provider, price_raw, price_url)
    fundamentals = normalize_equity_fundamentals(cache_root, symbol, providers, endpoint_plan)
    identity = rewrite_raw_paths(identity, raw_path_map)
    snapshot = rewrite_raw_paths(snapshot, raw_path_map)
    technicals = rewrite_raw_paths(technicals, raw_path_map)
    fundamentals = rewrite_raw_paths(fundamentals, raw_path_map)
    news = rewrite_raw_paths(normalize_news(cache_root, symbol, providers, endpoint_plan), raw_path_map)
    equity_events = rewrite_raw_paths(normalize_equity_events(cache_root, symbol, providers, endpoint_plan), raw_path_map)
    equity_insiders = rewrite_raw_paths(normalize_equity_insiders(cache_root, symbol, providers, endpoint_plan), raw_path_map)
    etf_holdings = rewrite_raw_paths(normalize_etf_holdings(cache_root, symbol, providers, endpoint_plan), raw_path_map)
    price_raw_path = raw_path_map.get(str(price_raw), str(price_raw) if price_raw else None)
    gaps = default_gaps(identity, snapshot, fundamentals, providers)
    write_json(normalized / "identity.json", identity)
    write_json(normalized / "market_snapshot.json", snapshot)
    write_json(normalized / "prices_daily.json", {"prices": prices, "provider": price_provider, "raw_path": price_raw_path})
    write_json(normalized / "technical_signals.json", technicals)
    write_json(normalized / "news.json", news)
    asset_type_value = identity.get("asset_type", {}).get("value")
    if asset_type_value in {"equity", "adr", "unknown"}:
        write_json(normalized / "equity_fundamentals.json", fundamentals if fundamentals else {"status": "unavailable", "gaps_recorded": True})
        write_json(normalized / "equity_events.json", equity_events)
        write_json(normalized / "equity_insiders.json", equity_insiders)
    if asset_type_value in {"etf", "fund"}:
        write_json(normalized / "etf_holdings.json", etf_holdings)
    sec_submissions_entry = next((entry for entry in raw_entries if entry.get("provider") == "sec" and entry.get("endpoint") == "submissions" and entry.get("status") == "ok"), None)
    cik_value = identity.get("cik", {}).get("value") if isinstance(identity.get("cik"), dict) else None
    if sec_submissions_entry and cik_value:
        emit_sec_filings_index(bundle_dir, Path(str(sec_submissions_entry["raw_path"])), str(cik_value))
    lifecycle_hints = infer_lifecycle_hints(asset_type_value, fundamentals, technicals)
    usage_requirements = build_usage_requirements(normalized, asset_type_value, lifecycle_hints)
    write_json(bundle_dir / "deterministic_data_usage.json", usage_requirements)
    write_json(bundle_dir / "source_manifest.json", {"sources": raw_entries})
    write_json(bundle_dir / "gaps.json", {"gaps": gaps})
    endpoint_status = endpoint_status_from_raw_entries(raw_entries)
    manifest = {
        "command": command,
        "tool_version": "deterministic-core-1",
        "git_commit": git_commit(Path.cwd()),
        "symbol": symbol,
        "normalized_symbol": symbol,
        "asset_type": identity.get("asset_type", {}).get("value"),
        "as_of": as_of,
        "created_at_utc": utc_now(),
        "offline": offline,
        "provider_status": collect_provider_status(cache_root, symbol, providers, endpoint_plan),
        "endpoint_status": endpoint_status,
        "analysis_limitations": analysis_limitations_from_endpoint_status(endpoint_status),
        "discrepancies": discrepancies_from_snapshot(snapshot),
        "endpoint_plan": {provider: sorted(endpoints) for provider, endpoints in endpoint_plan.items()},
        "cache": {"raw_entries": len(raw_entries)},
        "api_limits": config.limits if config else {},
        "warnings": warnings or [],
        "errors": [],
    }
    if config:
        manifest = json.loads(redact(json.dumps(manifest), config))
    write_json(bundle_dir / "manifest.json", manifest)
    (bundle_dir / "research_input_pack.md").write_text(build_research_markdown(symbol, as_of, identity, snapshot, technicals, fundamentals, gaps, usage_requirements), encoding="utf-8")
    assert_no_secrets_in_tree(bundle_dir, config)
    return {"symbol": symbol, "bundle_dir": str(bundle_dir), "manifest": str(bundle_dir / "manifest.json")}


def normalize_news(cache_root: Path, symbol: str, providers: list[str] | None = None, endpoint_plan: dict[str, set[str]] | None = None) -> dict[str, Any]:
    providers = providers or DEFAULT_PROVIDERS
    items = []

    def news_item(provider: str, endpoint: str, path: Path, payload: dict[str, Any], item: dict[str, Any], headline: Any, source: Any, url_value: Any, published_at: Any) -> dict[str, Any]:
        result = {
            "headline": headline,
            "source": source,
            "url": url_value,
            "published_at": published_at,
            "raw_path": str(path),
            "provider": provider,
            "endpoint": endpoint,
            "source_url": payload.get("provider_result", {}).get("url", ""),
            "status": "ok",
        }
        for out_key, provider_key in [
            ("sentiment", "sentiment_score"),
            ("sentiment", "overall_sentiment_score"),
            ("summary", "summary"),
            ("text", "text"),
            ("text", "content"),
        ]:
            if out_key not in result and item.get(provider_key) is not None:
                result[out_key] = item.get(provider_key)
        return result

    if provider_enabled(providers, "marketaux") and provider_endpoint_enabled(endpoint_plan, "marketaux", "news"):
        raw = read_raw_latest(cache_root, symbol, "marketaux", "news")
        if raw:
            path, payload = raw
            if raw_payload_ok("marketaux", payload):
                data = payload.get("data", {})
                feed = data.get("data", []) if isinstance(data, dict) else []
                for item in feed:
                    if isinstance(item, dict):
                        items.append(news_item("marketaux", "news", path, payload, item, item.get("title"), item.get("source"), item.get("url"), item.get("published_at")))
    if provider_enabled(providers, "alphavantage") and provider_endpoint_enabled(endpoint_plan, "alphavantage", "news_sentiment"):
        raw = read_raw_latest(cache_root, symbol, "alphavantage", "news_sentiment")
        if raw:
            path, payload = raw
            if raw_payload_ok("alphavantage", payload):
                data = payload.get("data", {})
                feed = data.get("feed", []) if isinstance(data, dict) else []
                for item in feed:
                    if isinstance(item, dict) and (item.get("title") or item.get("url")):
                        items.append(news_item("alphavantage", "news_sentiment", path, payload, item, item.get("title"), item.get("source"), item.get("url"), item.get("time_published")))
    if provider_enabled(providers, "fmp"):
        for endpoint in ["stock_news", "press_releases"]:
            if not provider_endpoint_enabled(endpoint_plan, "fmp", endpoint):
                continue
            raw = read_raw_latest(cache_root, symbol, "fmp", endpoint)
            if not raw:
                continue
            path, payload = raw
            if not raw_payload_ok("fmp", payload):
                continue
            data = payload.get("data", [])
            if isinstance(data, dict):
                data = [data]
            for item in data if isinstance(data, list) else []:
                if isinstance(item, dict) and (item.get("title") or item.get("url")):
                    items.append(news_item("fmp", endpoint, path, payload, item, item.get("title"), item.get("site") or item.get("publisher"), item.get("url"), item.get("publishedDate") or item.get("date")))
    if provider_enabled(providers, "eodhd") and provider_endpoint_enabled(endpoint_plan, "eodhd", "news"):
        raw = read_raw_latest(cache_root, symbol, "eodhd", "news")
        if raw:
            path, payload = raw
            if raw_payload_ok("eodhd", payload):
                data = payload.get("data", [])
                if isinstance(data, dict):
                    data = data.get("data") or data.get("news") or [data]
                for item in data if isinstance(data, list) else []:
                    if isinstance(item, dict) and (item.get("title") or item.get("link") or item.get("url")):
                        items.append(news_item("eodhd", "news", path, payload, item, item.get("title"), item.get("source"), item.get("link") or item.get("url"), item.get("date") or item.get("published_at")))
    return {"items": items, "status": "ok" if items else "empty"}


def normalize_etf_holdings(cache_root: Path, symbol: str, providers: list[str] | None = None, endpoint_plan: dict[str, set[str]] | None = None) -> dict[str, Any]:
    providers = providers or DEFAULT_PROVIDERS
    if not provider_enabled(providers, "fmp") or not provider_endpoint_enabled(endpoint_plan, "fmp", "etf_holdings"):
        return {"status": "unavailable", "top_holdings": []}
    raw = read_raw_latest(cache_root, symbol, "fmp", "etf_holdings")
    if not raw:
        return {"status": "empty", "top_holdings": []}
    path, payload = raw
    status = raw_payload_status("fmp", payload)
    if status != "ok":
        return {"status": status, "top_holdings": []}
    data = payload.get("data", [])
    if isinstance(data, dict):
        data = [data]
    url = payload.get("provider_result", {}).get("url", "")
    holdings = []
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        ticker = item.get("asset") or item.get("symbol") or item.get("ticker")
        weight = number(item.get("weightPercentage") or item.get("weight") or item.get("percentage"))
        if ticker in (None, "") and weight is None:
            continue
        holding: dict[str, Any] = {}
        if ticker not in (None, ""):
            holding["ticker"] = provenance(str(ticker).upper(), "fmp", url, "etf_holdings", path)
        if weight is not None:
            holding["weight"] = provenance(weight, "fmp", url, "etf_holdings", path, unit="percent")
        name = item.get("name") or item.get("companyName")
        if name:
            holding["name"] = provenance(name, "fmp", url, "etf_holdings", path)
        holdings.append(holding)
    return {"status": "ok" if holdings else "empty", "top_holdings": holdings}


def normalize_equity_events(cache_root: Path, symbol: str, providers: list[str] | None = None, endpoint_plan: dict[str, set[str]] | None = None) -> dict[str, Any]:
    providers = providers or DEFAULT_PROVIDERS
    if not provider_enabled(providers, "fmp"):
        return {"status": "unavailable", "items": []}
    events: dict[str, Any] = {"status": "empty", "items": []}
    for endpoint in ["dividends", "earnings", "splits"]:
        if not provider_endpoint_enabled(endpoint_plan, "fmp", endpoint):
            continue
        raw = read_raw_latest(cache_root, symbol, "fmp", endpoint)
        if not raw:
            continue
        path, payload = raw
        if not raw_payload_ok("fmp", payload):
            continue
        data = payload.get("data", [])
        if isinstance(data, dict):
            data = [data]
        endpoint_items = []
        url = payload.get("provider_result", {}).get("url", "")
        for item in data if isinstance(data, list) else []:
            if isinstance(item, dict) and item:
                endpoint_items.append({**item, "provider": "fmp", "endpoint": endpoint, "source_url": url, "raw_path": str(path), "status": "ok"})
        events[endpoint] = endpoint_items
        events["items"].extend(endpoint_items)
    events["status"] = "ok" if events["items"] else "empty"
    return events


def normalize_equity_insiders(cache_root: Path, symbol: str, providers: list[str] | None = None, endpoint_plan: dict[str, set[str]] | None = None) -> dict[str, Any]:
    providers = providers or DEFAULT_PROVIDERS
    if not provider_enabled(providers, "fmp"):
        return {"status": "unavailable", "items": []}
    result: dict[str, Any] = {"status": "empty", "items": []}
    if provider_endpoint_enabled(endpoint_plan, "fmp", "insider_trading"):
        raw = read_raw_latest(cache_root, symbol, "fmp", "insider_trading")
        if raw:
            path, payload = raw
            if raw_payload_ok("fmp", payload):
                data = payload.get("data", [])
                if isinstance(data, dict):
                    data = [data]
                url = payload.get("provider_result", {}).get("url", "")
                items = [{**item, "provider": "fmp", "endpoint": "insider_trading", "source_url": url, "raw_path": str(path), "status": "ok"} for item in data if isinstance(item, dict) and item]
                result["items"] = items
    if provider_endpoint_enabled(endpoint_plan, "fmp", "insider_statistics"):
        raw = read_raw_latest(cache_root, symbol, "fmp", "insider_statistics")
        if raw:
            path, payload = raw
            if raw_payload_ok("fmp", payload):
                data = first_dict(payload.get("data"))
                if data:
                    result["statistics"] = provenance(data, "fmp", payload.get("provider_result", {}).get("url", ""), "insider_statistics", path)
    result["status"] = "ok" if result.get("items") or result.get("statistics") else "empty"
    return result


def cmd_doctor(args: argparse.Namespace) -> None:
    root = Path(args.repo_root)
    config = load_env_files(root)
    write_env_example(root, config)
    paths = resolve_storage_paths(
        root,
        config,
        data_dir=getattr(args, "data_dir", None),
        cache_dir=getattr(args, "cache_dir", None),
        reports_dir=getattr(args, "reports_dir", None),
        runtime_dir=getattr(args, "runtime_dir", None),
    )
    data_dir = paths["data_dir"]
    reports_dir = paths["reports_dir"]
    runtime_dir = paths["runtime_dir"]
    cache_dir = paths["cache_dir"]
    data_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    providers = configured_providers(config)
    payload = {
        "python": sys.version.split()[0],
        "repo_root": str(root),
        "loaded_files": [Path(item).name for item in config.loaded_files],
        "data_dir_writable": os.access(data_dir, os.W_OK),
        "reports_dir_writable": os.access(reports_dir, os.W_OK),
        "runtime_dir_writable": os.access(runtime_dir, os.W_OK),
        "cache_dir_writable": os.access(cache_dir, os.W_OK),
        "providers": providers,
        "docs": config.docs,
        "limits": config.limits,
        "network_checks": "skipped" if args.no_network else "not_implemented_for_doctor_core",
    }
    print(redact(json.dumps(payload, indent=2, sort_keys=True), config))


def cmd_fetch(args: argparse.Namespace) -> None:
    metrics_start = getattr(args, "_metrics_start", start_timer())
    root = Path(args.repo_root)
    config = load_env_files(root)
    symbol = normalize_symbol(args.symbol)
    as_of = validate_as_of(args.as_of or date.today().isoformat())
    paths = resolve_storage_paths(
        root,
        config,
        data_dir=getattr(args, "data_dir", None),
        cache_dir=getattr(args, "cache_dir", None),
        reports_dir=getattr(args, "reports_dir", None),
        runtime_dir=getattr(args, "runtime_dir", None),
    )
    cache_root = paths["cache_dir"]
    output_root = paths["data_dir"]
    ensure_deterministic_output_root(output_root, runtime_root=paths["runtime_dir"], reports_root=paths["reports_dir"])
    providers = parse_provider_list(args.providers, config)
    endpoint_plan = parse_provider_endpoints(getattr(args, "provider_endpoints", None), providers)
    effective_endpoint_plan = {provider: set(endpoints) for provider, endpoints in endpoint_plan.items()}
    budgets = parse_budgets(args.max_provider_calls)
    warnings: list[str] = []
    provider_metrics: list[dict[str, Any]] = []
    if not args.offline:
        for provider in providers:
            budget = provider_call_budget(provider, budgets)
            provider_root = cache_root / symbol / provider
            before = len(list(provider_root.glob("*.json"))) if provider_root.exists() else 0
            if budget <= 0:
                warnings.append(f"Skipped {provider}: provider call budget is {budget}.")
                effective_endpoint_plan[provider] = set()
                provider_metrics.append(
                    {
                        "provider": provider,
                        "budget": budget,
                        "estimated_call_cost": 0,
                        "endpoints": [],
                        "fetch_attempted": False,
                        "cache_files_before": before,
                        "cache_files_after": before,
                        "new_cache_files": 0,
                    }
                )
                continue
            endpoints = endpoint_plan.get(provider, set())
            estimated_cost = estimated_provider_call_cost(cache_root, symbol, provider, refresh=args.refresh, endpoints=endpoints)
            if estimated_cost > budget:
                budgeted_endpoints = endpoints_within_budget(cache_root, symbol, provider, budget, refresh=args.refresh, endpoints=endpoints)
                if not budgeted_endpoints:
                    warnings.append(f"Skipped {provider}: estimated call cost {estimated_cost} exceeds budget {budget}.")
                    effective_endpoint_plan[provider] = set()
                    continue
                warnings.append(f"Limited {provider}: estimated call cost {estimated_cost} exceeds budget {budget}; fetching {', '.join(sorted(budgeted_endpoints))}.")
                endpoints = budgeted_endpoints
            effective_endpoint_plan[provider] = set(endpoints)
            fetch_provider(symbol, provider, as_of, cache_root, config, refresh=args.refresh, endpoints=endpoints)
            after = len(list(provider_root.glob("*.json"))) if provider_root.exists() else 0
            provider_metrics.append(
                {
                    "provider": provider,
                    "budget": budget,
                    "estimated_call_cost": estimated_cost,
                    "endpoints": sorted(endpoints),
                    "fetch_attempted": True,
                    "cache_files_before": before,
                    "cache_files_after": after,
                    "new_cache_files": max(0, after - before),
                }
            )
            if after - before > budget:
                die(f"Provider {provider} exceeded call budget {budget}")
    else:
        for provider in providers:
            provider_root = cache_root / symbol / provider
            before = len(list(provider_root.glob("*.json"))) if provider_root.exists() else 0
            provider_metrics.append(
                {
                    "provider": provider,
                    "budget": provider_call_budget(provider, budgets),
                    "estimated_call_cost": 0,
                    "endpoints": sorted(endpoint_plan.get(provider, set())),
                    "fetch_attempted": False,
                    "cache_files_before": before,
                    "cache_files_after": before,
                    "new_cache_files": 0,
                }
            )
    statuses = collect_provider_status(cache_root, symbol, providers, effective_endpoint_plan)
    raise_for_auth_failures(statuses)
    warnings.extend(provider_status_warnings(statuses))
    result = build_bundle(symbol, as_of, cache_root, output_root, providers=providers, offline=args.offline, config=config, command=" ".join(sys.argv), asset_type=getattr(args, "asset_type", "auto"), warnings=warnings, endpoint_plan=effective_endpoint_plan)
    write_metrics(
        getattr(args, "metrics_json", None),
        start=metrics_start,
        script="deterministic_research_collector.py",
        command=getattr(args, "command", "fetch"),
        symbol=symbol,
        as_of=as_of,
        offline=args.offline,
        providers_requested=providers,
        provider_fetches_attempted=sum(1 for item in provider_metrics if item["fetch_attempted"]),
        provider_call_estimate=sum(item["estimated_call_cost"] for item in provider_metrics),
        provider_metrics=provider_metrics,
        bundle_dir=result.get("bundle_dir"),
    )
    print(redact(json.dumps(result, indent=2, sort_keys=True), config))


def cmd_list_cache(args: argparse.Namespace) -> None:
    root = Path(args.repo_root)
    config = load_env_files(root)
    paths = resolve_storage_paths(
        root,
        config,
        data_dir=getattr(args, "data_dir", None),
        cache_dir=getattr(args, "cache_dir", None),
        reports_dir=getattr(args, "reports_dir", None),
        runtime_dir=getattr(args, "runtime_dir", None),
    )
    cache_root = paths["cache_dir"]
    symbol = normalize_symbol(args.symbol)
    files = [str(path) for path in sorted((cache_root / symbol).glob("*/*.json"))] if (cache_root / symbol).exists() else []
    print(json.dumps({"symbol": symbol, "files": files}, indent=2))


def cmd_clear_cache(args: argparse.Namespace) -> None:
    root = Path(args.repo_root)
    config = load_env_files(root)
    paths = resolve_storage_paths(
        root,
        config,
        data_dir=getattr(args, "data_dir", None),
        cache_dir=getattr(args, "cache_dir", None),
        reports_dir=getattr(args, "reports_dir", None),
        runtime_dir=getattr(args, "runtime_dir", None),
    )
    cache_root = paths["cache_dir"]
    symbol = normalize_symbol(args.symbol)
    provider_root = cache_root / symbol / args.provider
    removed = 0
    if provider_root.exists():
        for path in provider_root.glob("*.json"):
            path.unlink()
            removed += 1
    print(json.dumps({"symbol": symbol, "provider": args.provider, "removed": removed}, indent=2))


def add_common_paths(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--data-dir", help=argparse.SUPPRESS)
    parser.add_argument("--reports-dir")
    parser.add_argument("--runtime-dir")
    parser.add_argument("--cache-dir")
    add_metrics_arg(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic cache-first research data collector.")
    sub = parser.add_subparsers(dest="command", required=True)
    doctor = sub.add_parser("doctor")
    doctor.add_argument("--repo-root", default=".")
    doctor.add_argument("--data-dir", help=argparse.SUPPRESS)
    doctor.add_argument("--reports-dir")
    doctor.add_argument("--runtime-dir")
    doctor.add_argument("--cache-dir")
    doctor.add_argument("--no-network", action="store_true")
    doctor.set_defaults(func=cmd_doctor)
    fetch = sub.add_parser("fetch")
    fetch.add_argument("symbol")
    fetch.add_argument("--asset-type", default="auto", choices=["auto", "equity", "adr", "etf", "fund"])
    fetch.add_argument("--as-of")
    fetch.add_argument("--providers")
    fetch.add_argument("--offline", action="store_true")
    fetch.add_argument("--refresh", action="store_true")
    fetch.add_argument("--max-provider-calls", action="append")
    fetch.add_argument("--provider-endpoints", action="append", help="Restrict endpoints for a provider, e.g. eodhd=fundamentals or fmp=profile,ratios_ttm.")
    add_common_paths(fetch)
    fetch.set_defaults(func=cmd_fetch)
    normalize = sub.add_parser("normalize")
    normalize.add_argument("symbol")
    normalize.add_argument("--as-of")
    normalize.add_argument("--providers")
    normalize.add_argument("--offline", action="store_true", default=True)
    normalize.add_argument("--refresh", action="store_true")
    normalize.add_argument("--max-provider-calls", action="append")
    normalize.add_argument("--provider-endpoints", action="append", help="Restrict endpoints for a provider, e.g. eodhd=fundamentals or fmp=profile,ratios_ttm.")
    add_common_paths(normalize)
    normalize.set_defaults(func=cmd_fetch)
    build_pack = sub.add_parser("build-pack")
    build_pack.add_argument("symbol")
    build_pack.add_argument("--as-of")
    build_pack.add_argument("--providers")
    build_pack.add_argument("--offline", action="store_true", default=True)
    build_pack.add_argument("--refresh", action="store_true")
    build_pack.add_argument("--max-provider-calls", action="append")
    build_pack.add_argument("--provider-endpoints", action="append", help="Restrict endpoints for a provider, e.g. eodhd=fundamentals or fmp=profile,ratios_ttm.")
    add_common_paths(build_pack)
    build_pack.set_defaults(func=cmd_fetch)
    list_cache = sub.add_parser("list-cache")
    list_cache.add_argument("symbol")
    add_common_paths(list_cache)
    list_cache.set_defaults(func=cmd_list_cache)
    clear = sub.add_parser("clear-cache")
    clear.add_argument("symbol")
    clear.add_argument("--provider", required=True)
    add_common_paths(clear)
    clear.set_defaults(func=cmd_clear_cache)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args._metrics_start = start_timer()
    args.func(args)


if __name__ == "__main__":
    main()
