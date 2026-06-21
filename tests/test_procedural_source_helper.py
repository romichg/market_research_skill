import json
import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "market-research" / "shared" / "scripts" / "procedural_source_helper.py"


def run_helper(*args, cwd=None):
    return subprocess.run(
        [sys.executable, str(HELPER), *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def test_init_run_creates_manifest(tmp_path):
    result = run_helper("init-run", "aapl", "--output-root", str(tmp_path))
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    run_dir = tmp_path / "AAPL"
    assert payload["symbol"] == "AAPL"
    assert Path(payload["run_dir"]) == run_dir
    manifest = json.loads((run_dir / "run_manifest.json").read_text())
    assert manifest["symbol"] == "AAPL"
    assert manifest["helper_errors"] == []
    assert manifest["procedural_gap_fills"] == []


def test_default_output_root_is_runtime_symbol_date(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = run_helper("init-run", "aapl", "--as-of", "2026-06-16")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert Path(payload["run_dir"]) == tmp_path / "runtime" / "AAPL" / "2026-06-16"
    assert (tmp_path / "runtime" / "AAPL" / "2026-06-16" / "run_manifest.json").exists()


def test_init_run_rejects_traversal_as_of(tmp_path):
    result = run_helper("init-run", "AAPL", "--output-root", str(tmp_path), "--as-of", "../outside")

    assert result.returncode != 0
    assert "Invalid as-of" in result.stderr
    assert not (tmp_path / "outside" / "run_manifest.json").exists()


def test_init_run_rejects_invalid_calendar_as_of(tmp_path):
    result = run_helper("init-run", "AAPL", "--output-root", str(tmp_path), "--as-of", "2026-99-99")

    assert result.returncode != 0
    assert "Invalid as-of" in result.stderr
    assert not (tmp_path / "AAPL" / "2026-99-99" / "run_manifest.json").exists()


def test_init_run_refuses_to_overwrite_existing_manifest_without_force(tmp_path):
    run_helper("init-run", "aapl", "--output-root", str(tmp_path))
    manifest_path = tmp_path / "AAPL" / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["procedural_gap_fills"] = [{"field": "expense_ratio", "value": "0.03%"}]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = run_helper("init-run", "AAPL", "--output-root", str(tmp_path))

    assert result.returncode != 0
    assert "already initialized" in result.stderr
    persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert persisted["procedural_gap_fills"] == [{"field": "expense_ratio", "value": "0.03%"}]


def test_init_run_force_overwrites_existing_manifest(tmp_path):
    run_helper("init-run", "aapl", "--output-root", str(tmp_path))

    result = run_helper("init-run", "AAPL", "--output-root", str(tmp_path), "--force")

    assert result.returncode == 0, result.stderr
    manifest = json.loads((tmp_path / "AAPL" / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["procedural_gap_fills"] == []


def test_invalid_symbol_rejected(tmp_path):
    result = run_helper("init-run", "../AAPL", "--output-root", str(tmp_path))
    assert result.returncode != 0
    assert "Invalid symbol" in result.stderr


@pytest.mark.parametrize(
    ("symbol", "artifact_path"),
    [
        (".", Path("runs/run_manifest.json")),
        ("..", Path("run_manifest.json")),
    ],
)
def test_dot_symbol_path_components_rejected(tmp_path, symbol, artifact_path):
    output_root = tmp_path / "runs"
    result = run_helper("init-run", symbol, "--output-root", str(output_root))

    assert result.returncode != 0
    assert "Invalid symbol" in result.stderr
    assert not (tmp_path / artifact_path).exists()


def test_classify_manual_updates_manifest(tmp_path):
    run_helper("init-run", "vti", "--output-root", str(tmp_path))
    result = run_helper("classify", "VTI", "--output-root", str(tmp_path), "--security-type", "etf", "--name", "Vanguard Total Stock Market ETF")
    assert result.returncode == 0, result.stderr
    classification = json.loads((tmp_path / "VTI" / "source_bundle" / "classification.json").read_text())
    assert classification["security_type"] == "etf"
    assert classification["source"] == "manual"
    manifest = json.loads((tmp_path / "VTI" / "run_manifest.json").read_text())
    assert manifest["security_type"] == "etf"


def test_record_source_and_prepare_sparse_context(tmp_path):
    run_helper("init-run", "ECH", "--output-root", str(tmp_path))
    run_helper("classify", "ECH", "--output-root", str(tmp_path), "--security-type", "etf", "--name", "iShares MSCI Chile ETF")
    result = run_helper(
        "record-source",
        "ECH",
        "--output-root",
        str(tmp_path),
        "--id",
        "issuer_page",
        "--title",
        "iShares ECH product page",
        "--url",
        "https://www.ishares.com/us/products/239618/",
        "--kind",
        "issuer_product_page",
    )
    assert result.returncode == 0, result.stderr
    result = run_helper("prepare-research-context", "ECH", "--output-root", str(tmp_path))
    assert result.returncode == 0, result.stderr
    context = json.loads((tmp_path / "ECH" / "research_context.json").read_text())
    assert context["symbol"] == "ECH"
    assert context["context_quality"]["is_sparse"] is True
    assert "expense_ratio" in context["context_quality"]["missing_material_fields"]
    assert (tmp_path / "ECH" / "research_context.md").exists()


def test_record_source_preserves_source_date_and_copies_artifact(tmp_path):
    artifact = tmp_path / "fact-sheet.pdf"
    artifact.write_bytes(b"%PDF-1.7\n")
    run_helper("init-run", "ECH", "--output-root", str(tmp_path))
    result = run_helper(
        "record-source",
        "ECH",
        "--output-root",
        str(tmp_path),
        "--id",
        "issuer_fact_sheet",
        "--title",
        "iShares ECH fact sheet",
        "--url",
        "https://example.com/fact-sheet.pdf",
        "--kind",
        "issuer_fact_sheet",
        "--source-date",
        "2026-03-31",
        "--artifact",
        str(artifact),
    )
    assert result.returncode == 0, result.stderr
    source = json.loads(result.stdout)
    assert source["source_date"] == "2026-03-31"
    copied = Path(source["local_artifact"])
    assert copied.exists()
    assert copied.parent == tmp_path / "ECH" / "source_bundle"
    sources = json.loads((tmp_path / "ECH" / "sources.json").read_text())
    assert sources["sources"][0]["local_artifact"] == str(copied)


def test_record_source_records_artifact_checksum(tmp_path):
    artifact = tmp_path / "fact-sheet.pdf"
    content = b"%PDF-1.7\nchecksum me\n"
    artifact.write_bytes(content)
    run_helper("init-run", "ECH", "--output-root", str(tmp_path))
    result = run_helper(
        "record-source",
        "ECH",
        "--output-root",
        str(tmp_path),
        "--id",
        "issuer_fact_sheet",
        "--title",
        "iShares ECH fact sheet",
        "--url",
        "https://example.com/fact-sheet.pdf",
        "--kind",
        "issuer_fact_sheet",
        "--artifact",
        str(artifact),
    )
    assert result.returncode == 0, result.stderr
    source = json.loads(result.stdout)
    assert source["artifact_sha256"] == hashlib.sha256(content).hexdigest()
    assert source["artifact_size_bytes"] == len(content)


def test_record_source_rejects_csv_artifact_that_contains_html(tmp_path):
    artifact = tmp_path / "holdings.csv"
    artifact.write_text("<!doctype html><html><body>not csv</body></html>", encoding="utf-8")
    run_helper("init-run", "ECH", "--output-root", str(tmp_path))
    result = run_helper(
        "record-source",
        "ECH",
        "--output-root",
        str(tmp_path),
        "--id",
        "holdings_csv",
        "--title",
        "Holdings CSV",
        "--url",
        "https://example.com/holdings.csv",
        "--kind",
        "holdings",
        "--artifact",
        str(artifact),
    )
    assert result.returncode != 0
    assert "looks like HTML" in result.stderr


def test_record_gap_fill_updates_context_and_manifest(tmp_path):
    run_helper("init-run", "ECH", "--output-root", str(tmp_path))
    run_helper("classify", "ECH", "--output-root", str(tmp_path), "--security-type", "etf")
    result = run_helper(
        "record-gap-fill",
        "ECH",
        "--output-root",
        str(tmp_path),
        "--field",
        "expense_ratio",
        "--value",
        "0.59%",
        "--source-id",
        "issuer_fact_sheet",
        "--confidence",
        "high",
        "--note",
        "Procedurally filled from issuer fact sheet.",
    )
    assert result.returncode == 0, result.stderr
    context = json.loads((tmp_path / "ECH" / "research_context.json").read_text())
    assert context["data_points"][0]["key"] == "expense_ratio"
    manifest = json.loads((tmp_path / "ECH" / "run_manifest.json").read_text())
    assert manifest["procedural_gap_fills"][0]["field"] == "expense_ratio"


def test_record_gap_fill_from_json_file_preserves_dollar_values(tmp_path):
    fill = tmp_path / "fill.json"
    fill.write_text(
        json.dumps(
            {
                "field": "net_assets",
                "value": "$994.36 million and $1.227029 billion",
                "source_id": "issuer_fact_sheet",
                "confidence": "high",
                "note": "Structured input avoids shell expansion.",
            }
        ),
        encoding="utf-8",
    )
    run_helper("init-run", "ECH", "--output-root", str(tmp_path))
    run_helper("classify", "ECH", "--output-root", str(tmp_path), "--security-type", "etf")
    result = run_helper("record-gap-fill", "ECH", "--output-root", str(tmp_path), "--json-file", str(fill))
    assert result.returncode == 0, result.stderr
    context = json.loads((tmp_path / "ECH" / "research_context.json").read_text())
    by_key = {point["key"]: point for point in context["data_points"]}
    assert by_key["net_assets"]["value"] == "$994.36 million and $1.227029 billion"


def test_record_gap_fill_accepts_json_array(tmp_path):
    fill = tmp_path / "fills.json"
    fill.write_text(
        json.dumps(
            [
                {"field": "expense_ratio", "value": "0.59%", "source_id": "issuer_fact_sheet", "confidence": "high"},
                {"field": "benchmark", "value": "MSCI Chile IMI 25/50 Index", "source_id": "msci_factsheet", "confidence": "high"},
            ]
        ),
        encoding="utf-8",
    )
    run_helper("init-run", "ECH", "--output-root", str(tmp_path))
    run_helper("classify", "ECH", "--output-root", str(tmp_path), "--security-type", "etf")
    result = run_helper("record-gap-fill", "ECH", "--output-root", str(tmp_path), "--json-file", str(fill))
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["recorded_fields"] == ["expense_ratio", "benchmark"]
    context = json.loads((tmp_path / "ECH" / "research_context.json").read_text())
    by_key = {point["key"]: point for point in context["data_points"]}
    assert by_key["expense_ratio"]["value"] == "0.59%"
    assert by_key["benchmark"]["value"] == "MSCI Chile IMI 25/50 Index"


def test_parallel_gap_fills_do_not_corrupt_manifest(tmp_path):
    run_helper("init-run", "MSFT", "--output-root", str(tmp_path))
    run_helper("classify", "MSFT", "--output-root", str(tmp_path), "--security-type", "equity")
    processes = []
    for index in range(6):
        processes.append(
            subprocess.Popen(
                [
                    sys.executable,
                    str(HELPER),
                    "record-gap-fill",
                    "MSFT",
                    "--output-root",
                    str(tmp_path),
                    "--field",
                    f"field_{index}",
                    "--value",
                    f"value {index}",
                    "--source-id",
                    "sec_companyfacts",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        )
    failures = []
    for process in processes:
        stdout, stderr = process.communicate(timeout=10)
        if process.returncode != 0:
            failures.append((process.returncode, stdout, stderr))
    assert failures == []
    manifest = json.loads((tmp_path / "MSFT" / "run_manifest.json").read_text())
    fields = {item["field"] for item in manifest["procedural_gap_fills"]}
    assert {f"field_{index}" for index in range(6)} <= fields


def test_parallel_record_source_preserves_all_sources(tmp_path):
    run_helper("init-run", "ECH", "--output-root", str(tmp_path))
    processes = []
    for index in range(6):
        artifact = tmp_path / f"source-{index}.html"
        artifact.write_text(f"<html><body>{index}</body></html>", encoding="utf-8")
        processes.append(
            subprocess.Popen(
                [
                    sys.executable,
                    str(HELPER),
                    "record-source",
                    "ECH",
                    "--output-root",
                    str(tmp_path),
                    "--id",
                    f"source_{index}",
                    "--title",
                    f"Source {index}",
                    "--url",
                    f"https://example.com/{index}",
                    "--kind",
                    "test_source",
                    "--artifact",
                    str(artifact),
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        )
    failures = []
    for process in processes:
        stdout, stderr = process.communicate(timeout=10)
        if process.returncode != 0:
            failures.append((process.returncode, stdout, stderr))
    assert failures == []
    sources = json.loads((tmp_path / "ECH" / "sources.json").read_text())
    ids = {source["id"] for source in sources["sources"]}
    assert {f"source_{index}" for index in range(6)} <= ids


def test_prepare_context_promotes_basic_equity_companyfacts(tmp_path):
    run_helper("init-run", "MSFT", "--output-root", str(tmp_path))
    run_helper("classify", "MSFT", "--output-root", str(tmp_path), "--security-type", "equity", "--name", "Microsoft Corporation")
    run_helper(
        "record-source",
        "MSFT",
        "--output-root",
        str(tmp_path),
        "--id",
        "sec_2025_10k",
        "--title",
        "Microsoft Form 10-K for fiscal year ended June 30, 2025",
        "--url",
        "https://www.sec.gov/example-10k",
        "--kind",
        "sec_10k",
        "--source-date",
        "2025-06-30",
    )
    companyfacts = {
        "entityName": "Microsoft Corporation",
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {"form": "10-K", "fp": "FY", "fy": 2025, "end": "2025-06-30", "filed": "2025-07-30", "val": 281724000000}
                        ]
                    }
                },
                "NetIncomeLoss": {
                    "units": {
                        "USD": [
                            {"form": "10-K", "fp": "FY", "fy": 2025, "end": "2025-06-30", "filed": "2025-07-30", "val": 101832000000}
                        ]
                    }
                },
            }
        },
    }
    companyfacts_path = tmp_path / "MSFT" / "source_bundle" / "sec_companyfacts.json"
    companyfacts_path.write_text(json.dumps(companyfacts), encoding="utf-8")
    run_helper(
        "record-source",
        "MSFT",
        "--output-root",
        str(tmp_path),
        "--id",
        "sec_companyfacts",
        "--title",
        "SEC Companyfacts for Microsoft Corporation",
        "--url",
        "https://data.sec.gov/api/xbrl/companyfacts/CIK0000789019.json",
        "--kind",
        "sec_companyfacts",
        "--artifact",
        str(companyfacts_path),
    )
    result = run_helper("prepare-research-context", "MSFT", "--output-root", str(tmp_path))
    assert result.returncode == 0, result.stderr
    context = json.loads((tmp_path / "MSFT" / "research_context.json").read_text())
    by_key = {point["key"]: point for point in context["data_points"]}
    assert by_key["company_name"]["value"] == "Microsoft Corporation"
    assert by_key["latest_annual_filing"]["value"] == "Microsoft Form 10-K for fiscal year ended June 30, 2025"
    assert by_key["revenue"]["value"]["value"] == 281724000000
    assert by_key["net_income"]["value"]["value"] == 101832000000
    assert context["context_quality"]["is_sparse"] is False


def test_prepare_context_prefers_latest_revenue_across_companyfacts_tags(tmp_path):
    run_helper("init-run", "MSFT", "--output-root", str(tmp_path))
    run_helper("classify", "MSFT", "--output-root", str(tmp_path), "--security-type", "equity", "--name", "Microsoft Corporation")
    companyfacts = {
        "entityName": "Microsoft Corporation",
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {"form": "10-K", "fp": "FY", "fy": 2010, "end": "2010-06-30", "filed": "2010-07-30", "val": 16039000000}
                        ]
                    }
                },
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {
                        "USD": [
                            {"form": "10-K", "fp": "FY", "fy": 2025, "end": "2025-06-30", "filed": "2025-07-30", "val": 281724000000}
                        ]
                    }
                },
                "NetIncomeLoss": {
                    "units": {
                        "USD": [
                            {"form": "10-K", "fp": "FY", "fy": 2025, "end": "2025-06-30", "filed": "2025-07-30", "val": 101832000000}
                        ]
                    }
                },
            }
        },
    }
    companyfacts_path = tmp_path / "sec_companyfacts.json"
    companyfacts_path.write_text(json.dumps(companyfacts), encoding="utf-8")
    run_helper(
        "record-source",
        "MSFT",
        "--output-root",
        str(tmp_path),
        "--id",
        "sec_companyfacts",
        "--title",
        "SEC Companyfacts for Microsoft Corporation",
        "--url",
        "https://data.sec.gov/api/xbrl/companyfacts/CIK0000789019.json",
        "--kind",
        "sec_companyfacts",
        "--artifact",
        str(companyfacts_path),
    )

    result = run_helper("prepare-research-context", "MSFT", "--output-root", str(tmp_path))

    assert result.returncode == 0, result.stderr
    context = json.loads((tmp_path / "MSFT" / "research_context.json").read_text())
    by_key = {point["key"]: point for point in context["data_points"]}
    assert by_key["revenue"]["value"]["tag"] == "RevenueFromContractWithCustomerExcludingAssessedTax"
    assert by_key["revenue"]["value"]["fy"] == 2025
    assert by_key["revenue"]["value"]["value"] == 281724000000


def test_prepare_context_treats_sec_filing_10k_title_as_latest_annual(tmp_path):
    run_helper("init-run", "AAPL", "--output-root", str(tmp_path))
    run_helper("classify", "AAPL", "--output-root", str(tmp_path), "--security-type", "equity", "--name", "Apple Inc.")
    companyfacts = {
        "entityName": "Apple Inc.",
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {"USD": [{"form": "10-K", "fp": "FY", "fy": 2025, "end": "2025-09-27", "filed": "2025-10-31", "val": 416161000000}]}
                },
                "NetIncomeLoss": {
                    "units": {"USD": [{"form": "10-K", "fp": "FY", "fy": 2025, "end": "2025-09-27", "filed": "2025-10-31", "val": 112010000000}]}
                },
            }
        },
    }
    companyfacts_path = tmp_path / "sec_companyfacts.json"
    companyfacts_path.write_text(json.dumps(companyfacts), encoding="utf-8")
    run_helper(
        "record-source",
        "AAPL",
        "--output-root",
        str(tmp_path),
        "--id",
        "sec_companyfacts",
        "--title",
        "SEC companyfacts XBRL JSON for Apple Inc.",
        "--url",
        "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json",
        "--kind",
        "sec_companyfacts",
        "--artifact",
        str(companyfacts_path),
    )
    run_helper(
        "record-source",
        "AAPL",
        "--output-root",
        str(tmp_path),
        "--id",
        "latest_10k",
        "--title",
        "Apple Form 10-K for fiscal year ended 2025-09-27",
        "--url",
        "https://www.sec.gov/example-10k",
        "--kind",
        "sec_filing",
        "--source-date",
        "2025-10-31",
    )
    result = run_helper("prepare-research-context", "AAPL", "--output-root", str(tmp_path))
    assert result.returncode == 0, result.stderr
    context = json.loads((tmp_path / "AAPL" / "research_context.json").read_text())
    by_key = {point["key"]: point for point in context["data_points"]}
    assert by_key["latest_annual_filing"]["source_id"] == "latest_10k"
    assert by_key["revenue"]["value"]["value"] == 416161000000
    assert context["context_quality"]["is_sparse"] is False


def test_record_source_gap_appends_structured_manifest_entry(tmp_path):
    run_helper("init-run", "ECH", "--output-root", str(tmp_path))

    result = run_helper(
        "record-source-gap",
        "ECH",
        "--output-root",
        str(tmp_path),
        "--source-id",
        "holdings_csv",
        "--attempted-url",
        "https://www.ishares.com/us/products/239618/holdings.csv",
        "--reason",
        "CSV endpoint returned HTML.",
        "--replacement-source-id",
        "issuer_fact_sheet",
        "--severity",
        "medium",
    )

    assert result.returncode == 0, result.stderr
    manifest = json.loads((tmp_path / "ECH" / "run_manifest.json").read_text())
    assert manifest["source_gaps"][0]["source_id"] == "holdings_csv"
    assert manifest["source_gaps"][0]["attempted_url"] == "https://www.ishares.com/us/products/239618/holdings.csv"
    assert manifest["source_gaps"][0]["replacement_source_id"] == "issuer_fact_sheet"


def test_prepare_context_includes_manifest_source_gaps(tmp_path):
    run_helper("init-run", "ECH", "--output-root", str(tmp_path))
    run_helper("classify", "ECH", "--output-root", str(tmp_path), "--security-type", "etf")
    run_helper(
        "record-source-gap",
        "ECH",
        "--output-root",
        str(tmp_path),
        "--source-id",
        "holdings_csv",
        "--attempted-url",
        "https://example.com/holdings.csv",
        "--reason",
        "CSV endpoint returned HTML.",
    )

    result = run_helper("prepare-research-context", "ECH", "--output-root", str(tmp_path))

    assert result.returncode == 0, result.stderr
    context = json.loads((tmp_path / "ECH" / "research_context.json").read_text())
    assert context["source_gaps"][0]["source_id"] == "holdings_csv"


def test_extract_blackrock_payload_promotes_key_fields(tmp_path):
    payload = {
        "fundHeader": {
            "fundName": "iShares MSCI Chile ETF",
            "ticker": "ECH",
            "benchmark": "MSCI Chile IMI 25/50 Index",
        },
        "keyFundFacts": {
            "netExpenseRatio": "0.59%",
            "inceptionDate": "2007-11-12",
        },
        "performance": {
            "asOfDate": "2026-03-31",
            "oneYear": "12.3%",
        },
        "exposureBreakdowns": {
            "country": [{"name": "Chile", "weight": "99.1%"}],
            "sector": [{"name": "Financials", "weight": "28.4%"}],
        },
        "componentsByNameMap": {
            "holdings": {
                "containersByNameMap": {
                    "all": {
                        "dataPointsByNameMap": {
                            "issueName": {"value": ["Banco de Chile"]},
                            "ticker": {"value": ["CHILE"]},
                            "holdingPercent": {"value": ["8.1"]},
                            "sectorName": {"value": ["Financials"]},
                            "countryOfRisk": {"value": ["Chile"]},
                        }
                    }
                }
            }
        },
    }
    source_path = tmp_path / "blackrock_product.json"
    source_path.write_text(json.dumps(payload), encoding="utf-8")
    run_helper("init-run", "ECH", "--output-root", str(tmp_path))
    run_helper("classify", "ECH", "--output-root", str(tmp_path), "--security-type", "etf")
    result = run_helper(
        "extract-blackrock",
        "ECH",
        "--output-root",
        str(tmp_path),
        "--json-file",
        str(source_path),
        "--source-id",
        "blackrock_product_api",
    )
    assert result.returncode == 0, result.stderr
    context = json.loads((tmp_path / "ECH" / "research_context.json").read_text())
    by_key = {point["key"]: point for point in context["data_points"]}
    assert by_key["fund_name"]["value"] == "iShares MSCI Chile ETF"
    assert by_key["expense_ratio"]["value"] == "0.59%"
    assert by_key["benchmark"]["value"] == "MSCI Chile IMI 25/50 Index"
    assert by_key["holdings_summary"]["value"]["top_holdings"][0]["name"] == "Banco de Chile"
    assert context["context_quality"]["is_sparse"] is False


def test_extract_blackrock_component_payload_promotes_key_fields(tmp_path):
    payload = {
        "FundHeaderV3": {"fundName": "iShares MSCI Mexico ETF"},
        "KeyFundFactsV3": {
            "containersByNameMap": {
                "default": {
                    "dataPointsByNameMap": {
                        "indexSeriesName": {"formattedValue": "MSCI Mexico IMI 25/50 Index (Net)", "value": "MSCI Mexico IMI 25/50 Index (Net)"},
                        "totalNetAssetsFundLevel": {"formattedValue": "1,994,787,694", "value": 1994787694.34, "formattedAsOfDate": "May 28, 2026"},
                    }
                }
            }
        },
        "FeeTableV3": {
            "containersByNameMap": {
                "default": {
                    "subContainersByNameMap": {
                        "qeFeesContainer": {
                            "dataPointsByNameMap": {
                                "qgrs": {"label": "Expense Ratio", "formattedValue": "0.50%", "value": 0.5}
                            }
                        }
                    }
                }
            }
        },
        "TopHoldingsV3": {
            "holdingsAsOfDate": "May 27, 2026",
            "topHoldings": [
                {"holdingsName": "GRUPO MEXICO B", "holdingPercent": "14.04"},
                {"holdingsName": "GPO FINANCE BANORTE", "holdingPercent": "10.46"},
            ],
        },
    }
    source_path = tmp_path / "blackrock_components.json"
    source_path.write_text(json.dumps(payload), encoding="utf-8")
    run_helper("init-run", "EWW", "--output-root", str(tmp_path))
    run_helper("classify", "EWW", "--output-root", str(tmp_path), "--security-type", "etf")

    result = run_helper(
        "extract-blackrock",
        "EWW",
        "--output-root",
        str(tmp_path),
        "--json-file",
        str(source_path),
        "--source-id",
        "blackrock_components",
    )

    assert result.returncode == 0, result.stderr
    context = json.loads((tmp_path / "EWW" / "research_context.json").read_text())
    by_key = {point["key"]: point for point in context["data_points"]}
    assert by_key["fund_name"]["value"] == "iShares MSCI Mexico ETF"
    assert by_key["benchmark"]["value"] == "MSCI Mexico IMI 25/50 Index (Net)"
    assert by_key["expense_ratio"]["value"] == "0.50%"
    assert by_key["holdings_summary"]["value"]["as_of"] == "May 27, 2026"
    assert by_key["net_assets"]["value"]["formatted"] == "1,994,787,694"
    assert context["context_quality"]["is_sparse"] is False
