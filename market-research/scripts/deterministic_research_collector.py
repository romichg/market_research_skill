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
DEFAULT_PROVIDERS = ["sec", "tiingo", "eodhd", "alphavantage", "twelve_data", "marketaux"]
SYMBOL_RE = re.compile(r"^[A-Z0-9.\-]{1,12}$")


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
    for key in set(PROVIDER_ENV["sec"] + list(SECRET_NAMES) + ["RESEARCH_REPORTS_DIR", "RESEARCH_DATA_DIR", "RESEARCH_CACHE_DIR"]):
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
            if config.values.get("SEC_USER_AGENT"):
                found.append(provider)
        elif any(config.values.get(key) for key in keys):
            found.append(provider)
    return found


def write_env_example(repo_root: Path | str, config: ProviderConfig | None = None) -> Path:
    path = Path(repo_root) / ".env.example"
    keys = [
        "SEC_USER_AGENT",
        "TWELVE_DATA_API_KEY",
        "MARKETAUX_API_TOKEN",
        "ALPHAVANTAGE_API_KEY",
        "TIINGO_API_TOKEN",
        "EODHD_API_KEY",
        "FMP_API_KEY",
        "RESEARCH_REPORTS_DIR",
        "RESEARCH_CACHE_DIR",
    ]
    lines = []
    for key in keys:
        default = "./reports" if key == "RESEARCH_REPORTS_DIR" else "./.cache/market-research" if key == "RESEARCH_CACHE_DIR" else ""
        lines.append(f"{key}={default}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def resolve_storage_paths(repo_root: Path | str, config: ProviderConfig, data_dir: str | None = None, cache_dir: str | None = None, reports_dir: str | None = None) -> dict[str, Path]:
    root = Path(repo_root)
    resolved_reports = Path(reports_dir or config.values.get("RESEARCH_REPORTS_DIR", data_dir or root / "reports"))
    resolved_cache = Path(cache_dir or config.values.get("RESEARCH_CACHE_DIR", root / ".cache" / "market-research"))
    return {"reports_dir": resolved_reports, "cache_dir": resolved_cache}


def cache_key(provider: str, endpoint: str, params: dict[str, Any]) -> str:
    clean = {str(k): params[k] for k in sorted(params)}
    digest = hashlib.sha256(json.dumps(clean, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:16]
    safe_endpoint = re.sub(r"[^A-Za-z0-9_.-]+", "_", endpoint).strip("_")
    return f"{provider}_{safe_endpoint}_{digest}"


def raw_path(cache_root: Path, symbol: str, provider: str, endpoint: str, params: dict[str, Any]) -> Path:
    return cache_root / normalize_symbol(symbol) / provider / f"{cache_key(provider, endpoint, params)}.json"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_raw(cache_root: Path, symbol: str, provider: str, endpoint: str, params: dict[str, Any], data: Any, source_url: str, status: str = "ok", error: str | None = None) -> Path:
    path = raw_path(cache_root, symbol, provider, endpoint, params)
    payload = {
        "provider_result": {
            "provider": provider,
            "endpoint": endpoint,
            "url": source_url,
            "params_hash": cache_key(provider, endpoint, params).split("_")[-1],
            "fetched_at_utc": utc_now(),
            "source_as_of": None,
            "raw_path": str(path),
            "status": status,
            "error": error,
        },
        "data": data,
    }
    write_json(path, payload)
    return path


def read_raw_latest(cache_root: Path, symbol: str, provider: str, endpoint: str) -> tuple[Path, dict[str, Any]] | None:
    root = cache_root / normalize_symbol(symbol) / provider
    files = sorted(root.glob(f"{provider}_{endpoint}_*.json"))
    if not files:
        return None
    path = files[-1]
    return path, read_json(path)


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


def should_retry(exc: BaseException, policy: RetryPolicy) -> bool:
    if isinstance(exc, HTTPError):
        return exc.code in policy.retry_http_statuses
    if isinstance(exc, (URLError, TimeoutError)):
        return policy.retry_url_errors
    return False


def http_json(url: str, headers: dict[str, str] | None = None, timeout: int = 20, retry_policy: RetryPolicy | None = None) -> Any:
    policy = retry_policy or RetryPolicy(max_attempts=1)
    request = Request(url, headers=headers or {})
    backoff = policy.initial_backoff_seconds
    for attempt in range(1, policy.max_attempts + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                body = response.read()
            return json.loads(body.decode("utf-8"))
        except (HTTPError, URLError, TimeoutError) as exc:
            if attempt >= policy.max_attempts or not should_retry(exc, policy):
                raise
            time.sleep(backoff)
            backoff *= policy.backoff_multiplier


def fetch_with_cache(cache_root: Path, symbol: str, provider: str, endpoint: str, params: dict[str, Any], url: str, source_url: str, config: ProviderConfig, headers: dict[str, str] | None = None, refresh: bool = False) -> Path:
    path = raw_path(cache_root, symbol, provider, endpoint, params)
    if path.exists() and not refresh:
        return path
    try:
        data = http_json(url, headers=headers, retry_policy=retry_policy_for_provider(provider))
        return write_raw(cache_root, symbol, provider, endpoint, params, data, source_url=source_url)
    except HTTPError as exc:
        status = "rate_limited" if exc.code == 429 else "unauthorized" if exc.code in {401, 403} else "error"
        return write_raw(cache_root, symbol, provider, endpoint, params, {}, source_url=redact(source_url, config), status=status, error=f"HTTP {exc.code}")
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        return write_raw(cache_root, symbol, provider, endpoint, params, {}, source_url=redact(source_url, config), status="error", error=str(exc))


def fetch_provider(symbol: str, provider: str, as_of: str, cache_root: Path, config: ProviderConfig, refresh: bool = False) -> list[Path]:
    symbol = normalize_symbol(symbol)
    paths: list[Path] = []
    if provider == "sec":
        ua = config.values.get("SEC_USER_AGENT")
        if not ua:
            return paths
        headers = {"User-Agent": ua}
        tickers_url = "https://www.sec.gov/files/company_tickers.json"
        paths.append(fetch_with_cache(cache_root, symbol, "sec", "company_tickers", {}, tickers_url, tickers_url, config, headers, refresh))
        cik = cik_from_cached_tickers(cache_root, symbol)
        if cik:
            padded = f"{int(cik):010d}"
            for endpoint, url in {
                "submissions": f"https://data.sec.gov/submissions/CIK{padded}.json",
                "companyfacts": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{padded}.json",
            }.items():
                paths.append(fetch_with_cache(cache_root, symbol, "sec", endpoint, {"cik": padded}, url, url, config, headers, refresh))
    elif provider == "tiingo" and config.values.get("TIINGO_API_TOKEN"):
        token = config.values["TIINGO_API_TOKEN"]
        params = {"startDate": "2021-01-01", "endDate": as_of}
        query = urlencode({**params, "token": token})
        safe_query = urlencode(params)
        url = f"https://api.tiingo.com/tiingo/daily/{symbol}/prices?{query}"
        source = f"https://api.tiingo.com/tiingo/daily/{symbol}/prices?{safe_query}"
        paths.append(fetch_with_cache(cache_root, symbol, "tiingo", "prices", params, url, source, config, refresh=refresh))
    elif provider == "eodhd" and config.values.get("EODHD_API_KEY"):
        token = config.values["EODHD_API_KEY"]
        for endpoint, base in {
            "fundamentals": f"https://eodhd.com/api/fundamentals/{symbol}.US",
            "prices": f"https://eodhd.com/api/eod/{symbol}.US",
        }.items():
            params = {"fmt": "json"} if endpoint == "fundamentals" else {"fmt": "json", "from": "2021-01-01", "to": as_of}
            url = f"{base}?{urlencode({**params, 'api_token': token})}"
            source = f"{base}?{urlencode(params)}"
            paths.append(fetch_with_cache(cache_root, symbol, "eodhd", endpoint, params, url, source, config, refresh=refresh))
    elif provider == "alphavantage" and config.values.get("ALPHAVANTAGE_API_KEY"):
        token = config.values["ALPHAVANTAGE_API_KEY"]
        for endpoint, function in {"overview": "OVERVIEW", "prices": "TIME_SERIES_DAILY_ADJUSTED"}.items():
            params = {"function": function, "symbol": symbol}
            url = f"https://www.alphavantage.co/query?{urlencode({**params, 'apikey': token})}"
            source = f"https://www.alphavantage.co/query?{urlencode(params)}"
            paths.append(fetch_with_cache(cache_root, symbol, "alphavantage", endpoint, params, url, source, config, refresh=refresh))
            time.sleep(0.2)
    elif provider == "twelve_data" and config.values.get("TWELVE_DATA_API_KEY"):
        token = config.values["TWELVE_DATA_API_KEY"]
        params = {"symbol": symbol, "interval": "1day", "outputsize": "5000", "end_date": as_of}
        url = f"https://api.twelvedata.com/time_series?{urlencode({**params, 'apikey': token})}"
        source = f"https://api.twelvedata.com/time_series?{urlencode(params)}"
        paths.append(fetch_with_cache(cache_root, symbol, "twelve_data", "prices", params, url, source, config, refresh=refresh))
    elif provider == "marketaux" and config.values.get("MARKETAUX_API_TOKEN"):
        token = config.values["MARKETAUX_API_TOKEN"]
        params = {"symbols": symbol, "language": "en", "limit": "10"}
        url = f"https://api.marketaux.com/v1/news/all?{urlencode({**params, 'api_token': token})}"
        source = f"https://api.marketaux.com/v1/news/all?{urlencode(params)}"
        paths.append(fetch_with_cache(cache_root, symbol, "marketaux", "news", params, url, source, config, refresh=refresh))
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
    return budgets.get(provider, 10 if provider == "sec" else 2)


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


def collect_provider_status(cache_root: Path, symbol: str, providers: list[str]) -> list[dict[str, Any]]:
    statuses = []
    for provider in providers:
        root = cache_root / symbol / provider
        files = sorted(root.glob("*.json")) if root.exists() else []
        raw_statuses = []
        for path in files:
            payload = read_json(path)
            raw_statuses.append(payload.get("provider_result", {}).get("status", "ok"))
        errors = [status for status in raw_statuses if status != "ok"]
        status = errors[-1] if errors else "ok" if files else "missing"
        item = {"provider": provider, "raw_files": len(files), "status": status}
        if errors:
            item["errors"] = len(errors)
        statuses.append(item)
    return statuses


def normalize_identity(cache_root: Path, symbol: str) -> dict[str, Any]:
    identity: dict[str, Any] = {"input_symbol": provenance(symbol, "input", "", "symbol", Path("")), "normalized_symbol": provenance(symbol, "input", "", "symbol", Path(""))}
    submissions = read_raw_latest(cache_root, symbol, "sec", "submissions")
    if submissions:
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
    eod = read_raw_latest(cache_root, symbol, "eodhd", "fundamentals")
    if eod and "company_name" not in identity:
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
    if "asset_type" not in identity:
        identity["asset_type"] = provenance("unknown", "deterministic_classifier", "", "classification", Path(""), status="gap")
    return identity


def normalize_prices(cache_root: Path, symbol: str) -> tuple[list[dict[str, Any]], Path | None, str, str]:
    sources = [
        ("tiingo", "prices"),
        ("eodhd", "prices"),
        ("alphavantage", "prices"),
        ("twelve_data", "prices"),
    ]
    for provider, endpoint in sources:
        raw = read_raw_latest(cache_root, symbol, provider, endpoint)
        if not raw:
            continue
        path, payload = raw
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


def technicals_from_prices(rows: list[dict[str, Any]], provider: str, raw_path_value: Path | None, source_url: str) -> dict[str, Any]:
    raw = raw_path_value or Path("")
    closes = [float(row["adjusted_close"]) for row in rows if row.get("adjusted_close") is not None]
    volumes = [float(row["volume"]) for row in rows if row.get("volume") is not None]
    latest_date = rows[-1]["date"] if rows else None

    def point(name: str, value: Any, status: str = "ok") -> dict[str, Any]:
        return provenance(value, provider or "unavailable", source_url, "prices", raw, as_of=latest_date, status=status)

    result: dict[str, Any] = {}
    for window in [20, 50, 100, 200]:
        if len(closes) >= window:
            result[f"sma_{window}"] = point(f"sma_{window}", round(average(closes[-window:]) or 0, 6))
        else:
            result[f"sma_{window}"] = point(None, None, "insufficient_data")
    if closes:
        result["latest_close"] = point("latest_close", closes[-1])
        result["fifty_two_week_high"] = point("fifty_two_week_high", max(closes[-252:]))
        result["fifty_two_week_low"] = point("fifty_two_week_low", min(closes[-252:]))
        result["max_drawdown_available"] = point("max_drawdown_available", round(max_drawdown(closes) or 0, 6))
    if volumes:
        result["average_volume_30"] = point("average_volume_30", round(average(volumes[-30:]) or 0, 6))
        result["average_volume_90"] = point("average_volume_90", round(average(volumes[-90:]) or 0, 6))
    for name, periods in {"return_1m": 21, "return_3m": 63, "return_6m": 126, "return_1y": 252}.items():
        if len(closes) > periods:
            result[name] = point(name, round(pct_return(closes[-periods - 1], closes[-1]) or 0, 6))
        else:
            result[name] = point(None, None, "insufficient_data")
    return result


def normalize_market_snapshot(cache_root: Path, symbol: str, prices: list[dict[str, Any]], price_raw: Path | None, price_provider: str, price_url: str) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    if prices:
        latest = prices[-1]
        snapshot["latest_close"] = provenance(latest["adjusted_close"], price_provider, price_url, "prices", price_raw or Path(""), as_of=latest["date"])
        closes = [row["adjusted_close"] for row in prices if row.get("adjusted_close") is not None]
        snapshot["fifty_two_week_high"] = provenance(max(closes[-252:]), price_provider, price_url, "prices", price_raw or Path(""), as_of=latest["date"])
        snapshot["fifty_two_week_low"] = provenance(min(closes[-252:]), price_provider, price_url, "prices", price_raw or Path(""), as_of=latest["date"])
    market_cap_candidates: list[dict[str, Any]] = []
    pe_candidates: list[dict[str, Any]] = []
    attempted = []
    eod = read_raw_latest(cache_root, symbol, "eodhd", "fundamentals")
    attempted.append("eodhd")
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
    av = read_raw_latest(cache_root, symbol, "alphavantage", "overview")
    attempted.append("alphavantage")
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
    chosen_market_cap = choose_candidate(market_cap_candidates, attempted)
    if chosen_market_cap:
        snapshot["market_capitalization"] = chosen_market_cap
    chosen_pe = choose_candidate(pe_candidates, attempted)
    if chosen_pe:
        snapshot["pe_ratio"] = chosen_pe
    return snapshot


def default_gaps(identity: dict[str, Any], snapshot: dict[str, Any]) -> list[dict[str, Any]]:
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
        if field not in snapshot and field not in identity:
            gaps.append({"field": field, "status": "unavailable_free_source", "attempted_sources": DEFAULT_PROVIDERS, "notes": notes})
    return gaps


def copy_raw_files(cache_root: Path, symbol: str, bundle_dir: Path) -> list[dict[str, Any]]:
    entries = []
    for path in sorted((cache_root / symbol).glob("*/*.json")) if (cache_root / symbol).exists() else []:
        payload = read_json(path)
        provider = payload.get("provider_result", {}).get("provider", path.parent.name)
        target = bundle_dir / "raw" / provider / path.name
        write_json(target, payload)
        entries.append({
            "provider": provider,
            "endpoint": payload.get("provider_result", {}).get("endpoint"),
            "url": payload.get("provider_result", {}).get("url"),
            "raw_path": str(target),
            "status": payload.get("provider_result", {}).get("status"),
            "sha256": sha256_file(target),
        })
    return entries


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


def build_research_markdown(symbol: str, as_of: str, identity: dict[str, Any], snapshot: dict[str, Any], technicals: dict[str, Any], gaps: list[dict[str, Any]]) -> str:
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
    lines.extend(["", "## Data Gaps and Cautions"])
    for gap in gaps:
        lines.append(f"- {gap['field']}: {gap['notes']}")
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


def build_bundle(symbol: str, as_of: str, cache_root: Path, output_root: Path, providers: list[str] | None = None, offline: bool = False, config: ProviderConfig | None = None, command: str | None = None, asset_type: str = "auto") -> dict[str, Any]:
    symbol = normalize_symbol(symbol)
    providers = providers or DEFAULT_PROVIDERS
    bundle_dir = output_root / symbol / as_of
    normalized = bundle_dir / "normalized"
    normalized.mkdir(parents=True, exist_ok=True)
    raw_entries = copy_raw_files(cache_root, symbol, bundle_dir)
    identity = normalize_identity(cache_root, symbol)
    if asset_type != "auto":
        identity["asset_type"] = provenance(asset_type, "cli", "", "asset_type", Path(""))
    prices, price_raw, price_provider, price_url = normalize_prices(cache_root, symbol)
    snapshot = normalize_market_snapshot(cache_root, symbol, prices, price_raw, price_provider, price_url)
    technicals = technicals_from_prices(prices, price_provider, price_raw, price_url)
    gaps = default_gaps(identity, snapshot)
    write_json(normalized / "identity.json", identity)
    write_json(normalized / "market_snapshot.json", snapshot)
    write_json(normalized / "prices_daily.json", {"prices": prices, "provider": price_provider, "raw_path": str(price_raw) if price_raw else None})
    write_json(normalized / "technical_signals.json", technicals)
    write_json(normalized / "news.json", normalize_news(cache_root, symbol))
    for filename in ["sec_filings_index", "sec_filing_sections", "equity_fundamentals", "equity_events", "equity_insiders", "etf_profile", "etf_holdings", "etf_distributions", "etf_performance"]:
        write_json(normalized / f"{filename}.json", {"status": "not_implemented_in_core_pass", "gaps_recorded": True})
    write_json(bundle_dir / "source_manifest.json", {"sources": raw_entries})
    write_json(bundle_dir / "gaps.json", {"gaps": gaps})
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
        "provider_status": collect_provider_status(cache_root, symbol, providers),
        "cache": {"raw_entries": len(raw_entries)},
        "api_limits": config.limits if config else {},
        "warnings": [],
        "errors": [],
    }
    if config:
        manifest = json.loads(redact(json.dumps(manifest), config))
    write_json(bundle_dir / "manifest.json", manifest)
    (bundle_dir / "research_input_pack.md").write_text(build_research_markdown(symbol, as_of, identity, snapshot, technicals, gaps), encoding="utf-8")
    assert_no_secrets_in_tree(bundle_dir, config)
    return {"symbol": symbol, "bundle_dir": str(bundle_dir), "manifest": str(bundle_dir / "manifest.json")}


def normalize_news(cache_root: Path, symbol: str) -> dict[str, Any]:
    raw = read_raw_latest(cache_root, symbol, "marketaux", "news")
    if not raw:
        return {"items": [], "status": "unavailable"}
    path, payload = raw
    items = []
    for item in payload.get("data", {}).get("data", []):
        if isinstance(item, dict):
            items.append({"headline": item.get("title"), "source": item.get("source"), "url": item.get("url"), "published_at": item.get("published_at"), "sentiment": item.get("sentiment_score"), "raw_path": str(path), "provider": "marketaux"})
    return {"items": items, "status": "ok" if items else "empty"}


def cmd_doctor(args: argparse.Namespace) -> None:
    root = Path(args.repo_root)
    config = load_env_files(root)
    write_env_example(root, config)
    paths = resolve_storage_paths(root, config, reports_dir=getattr(args, "reports_dir", None), cache_dir=getattr(args, "cache_dir", None))
    reports_dir = paths["reports_dir"]
    cache_dir = paths["cache_dir"]
    reports_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    providers = configured_providers(config)
    payload = {
        "python": sys.version.split()[0],
        "repo_root": str(root),
        "loaded_files": [Path(item).name for item in config.loaded_files],
        "reports_dir_writable": os.access(reports_dir, os.W_OK),
        "cache_dir_writable": os.access(cache_dir, os.W_OK),
        "providers": providers,
        "docs": config.docs,
        "limits": config.limits,
        "network_checks": "skipped" if args.no_network else "not_implemented_for_doctor_core",
    }
    print(redact(json.dumps(payload, indent=2, sort_keys=True), config))


def cmd_fetch(args: argparse.Namespace) -> None:
    root = Path(args.repo_root)
    config = load_env_files(root)
    symbol = normalize_symbol(args.symbol)
    as_of = args.as_of or date.today().isoformat()
    paths = resolve_storage_paths(root, config, data_dir=getattr(args, "data_dir", None), cache_dir=getattr(args, "cache_dir", None), reports_dir=getattr(args, "reports_dir", None))
    cache_root = paths["cache_dir"]
    output_root = paths["reports_dir"]
    providers = parse_provider_list(args.providers, config)
    budgets = parse_budgets(args.max_provider_calls)
    if not args.offline:
        for provider in providers:
            budget = provider_call_budget(provider, budgets)
            if budget <= 0:
                continue
            before = len(list((cache_root / symbol / provider).glob("*.json"))) if (cache_root / symbol / provider).exists() else 0
            fetch_provider(symbol, provider, as_of, cache_root, config, refresh=args.refresh)
            after = len(list((cache_root / symbol / provider).glob("*.json"))) if (cache_root / symbol / provider).exists() else 0
            if after - before > budget:
                die(f"Provider {provider} exceeded call budget {budget}")
    result = build_bundle(symbol, as_of, cache_root, output_root, providers=providers, offline=args.offline, config=config, command=" ".join(sys.argv), asset_type=getattr(args, "asset_type", "auto"))
    print(redact(json.dumps(result, indent=2, sort_keys=True), config))


def cmd_list_cache(args: argparse.Namespace) -> None:
    root = Path(args.repo_root)
    config = load_env_files(root)
    paths = resolve_storage_paths(root, config, data_dir=getattr(args, "data_dir", None), cache_dir=getattr(args, "cache_dir", None), reports_dir=getattr(args, "reports_dir", None))
    cache_root = paths["cache_dir"]
    symbol = normalize_symbol(args.symbol)
    files = [str(path) for path in sorted((cache_root / symbol).glob("*/*.json"))] if (cache_root / symbol).exists() else []
    print(json.dumps({"symbol": symbol, "files": files}, indent=2))


def cmd_clear_cache(args: argparse.Namespace) -> None:
    root = Path(args.repo_root)
    config = load_env_files(root)
    paths = resolve_storage_paths(root, config, data_dir=getattr(args, "data_dir", None), cache_dir=getattr(args, "cache_dir", None), reports_dir=getattr(args, "reports_dir", None))
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
    parser.add_argument("--cache-dir")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic cache-first research data collector.")
    sub = parser.add_subparsers(dest="command", required=True)
    doctor = sub.add_parser("doctor")
    doctor.add_argument("--repo-root", default=".")
    doctor.add_argument("--reports-dir")
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
    add_common_paths(fetch)
    fetch.set_defaults(func=cmd_fetch)
    normalize = sub.add_parser("normalize")
    normalize.add_argument("symbol")
    normalize.add_argument("--as-of")
    normalize.add_argument("--providers")
    normalize.add_argument("--offline", action="store_true", default=True)
    normalize.add_argument("--refresh", action="store_true")
    normalize.add_argument("--max-provider-calls", action="append")
    add_common_paths(normalize)
    normalize.set_defaults(func=cmd_fetch)
    build_pack = sub.add_parser("build-pack")
    build_pack.add_argument("symbol")
    build_pack.add_argument("--as-of")
    build_pack.add_argument("--providers")
    build_pack.add_argument("--offline", action="store_true", default=True)
    build_pack.add_argument("--refresh", action="store_true")
    build_pack.add_argument("--max-provider-calls", action="append")
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
    args.func(args)


if __name__ == "__main__":
    main()
