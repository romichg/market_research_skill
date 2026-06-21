import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = ROOT / "market-research" / "shared" / "scripts" / "deterministic_research_collector.py"
VALIDATOR = ROOT / "market-research" / "shared" / "scripts" / "validate_market_research.py"
AS_OF = "2026-06-16"


def run_cli(*args):
    return subprocess.run(
        [sys.executable, *map(str, args)],
        text=True,
        capture_output=True,
        check=False,
    )


def write_research_report(report_dir: Path, symbol: str, security_type: str) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "symbol": symbol,
        "security_type": security_type,
        "as_of_date": AS_OF,
        "material_claims": [],
        "data_gaps": [
            {
                "field": "intraday liquidity",
                "status": "not_required_for_acceptance_fixture",
                "attempted_sources": ["synthetic fixture"],
                "notes": "Offline acceptance fixture uses deterministic collector layout only.",
            }
        ],
        "technical_analysis": {
            "trend": "neutral",
            "price_context": {
                "latest_close": 100.0,
                "sma_50": 101.5,
                "sma_200": 98.25,
            },
        },
        "valuation_or_performance": {
            "primary_metric": "total_return" if security_type == "etf" else "forward_pe",
            "summary": "Synthetic offline acceptance value.",
            "metrics": {
                "price": 100.0,
                "year_to_date_return": 0.08,
            },
        },
        "decision_factors": {
            "bull_case": ["durable demand", "strong balance sheet"],
            "bear_case": ["valuation sensitivity", "macro uncertainty"],
            "watch_items": ["next earnings date", "fund flows" if security_type == "etf" else "services growth"],
        },
        "risks": [
            {"risk": "market drawdown", "severity": "medium", "time_horizon": "12 months"},
            {"risk": "fixture-only data", "severity": "low", "time_horizon": "test runtime"},
        ],
        "catalysts": [
            {"catalyst": "earnings update" if security_type == "equity" else "index rebalance", "expected_window": "next quarter"}
        ],
        "source_coverage": {
            "deterministic_bundle": "present",
            "offline_fixture": True,
            "providers": ["synthetic"],
        },
        "calculation_audit": [
            {
                "calculation": "year_to_date_return",
                "formula": "(current - start) / start",
                "inputs": {"current": 108.0, "start": 100.0},
                "result": 0.08,
            }
        ],
    }
    (report_dir / f"{symbol}-research.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (report_dir / f"{symbol}-research.md").write_text(
        "\n".join(
            [
                f"# {symbol} Research",
                "",
                f"As of: {AS_OF}",
                f"Security type: {security_type}",
                "",
                "Synthetic offline acceptance report.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_market_research_offline_acceptance_for_equity_and_etf(tmp_path):
    data_dir = tmp_path / "data"
    cache_dir = tmp_path / "cache"
    reports_dir = tmp_path / "reports"

    for symbol, security_type in [("AAPL", "equity"), ("SPY", "etf")]:
        collector = run_cli(
            COLLECTOR,
            "fetch",
            symbol,
            "--offline",
            "--asset-type",
            security_type,
            "--as-of",
            AS_OF,
            "--data-dir",
            data_dir,
            "--cache-dir",
            cache_dir,
            "--reports-dir",
            reports_dir,
        )

        assert collector.returncode == 0, collector.stderr
        manifest = data_dir / symbol / AS_OF / "manifest.json"
        assert manifest.exists()

        report_dir = reports_dir / symbol / AS_OF
        write_research_report(report_dir, symbol, security_type)

        validator = run_cli(VALIDATOR, report_dir)

        assert validator.returncode == 0, validator.stderr
        validation_path = report_dir / f"{symbol}-validation-scaffold.json"
        assert validation_path.exists()
        validation = json.loads(validation_path.read_text(encoding="utf-8"))
        assert validation["blocking_issue_count"] == 0
