# Changelog

## 0.6.0 — Package ergonomics merge while preserving v0.5 quality gates

- Reorganized the deterministic helper into an importable `src/cool_financial_research/` package.
- Kept `scripts/cfr_helper.py` as a stable stdlib compatibility wrapper for OpenClaw skill instructions.
- Added Pydantic developer models mirroring the strict research and validation JSON schemas, including structured quantitative claims, source confidence/date fields, issue count consistency, unresolved issue carry-forward, and artifact/operational manifest fields.
- Added importable modules for source bundling, ETF holdings, XBRL extraction, PDF/render fallback, verified-data charts, and paid-provider ledger logic.
- Added optional Typer/Rich developer CLI for creating ready-to-copy OpenClaw run messages and forwarding helper commands.
- Updated `pyproject.toml` with package metadata and console entry points while intentionally avoiding OpenAI SDK, dotenv, and direct LLM-provider dependencies.
- Added package layout tests and Pydantic model tests; the full helper/test suite passes.

## 0.5.0 — ECH run reliability fixes

- Hardened HTTP fetching with gzip magic-byte handling, declared gzip, deflate, and detailed safe error snippets.
- Added SEC fund ticker fallback for ETF/mutual-fund classification and explicit `--security-type` override support in source bundling.
- Added conservative iShares/BlackRock ETF source discovery, including ECH product hints and auditable issuer source manifests.
- Added content sniffing so HTML returned from CSV/JSON endpoints is marked `wrong_content_type` instead of treated as usable data.
- Added official issuer/API holdings JSON extraction into `holdings_extracted.csv` and `etf_holdings_summary.json`.
- Added `preflight` command to record optional PDF text/render dependencies and write capabilities to the run manifest.
- Added `verify-artifacts` and `prompts/artifact-repair.md` so sub-agent completion is not accepted unless expected files exist and validate.
- Added artifact discipline addendum to research, validation, and fix prompts.
- Added `extract-pdf-text` command with `pdftotext`, `pypdf`, `PyPDF2`, and `pdfplumber` fallback order.
- Changed `render-pdf --optional` to return HTML fallback and structured status without failing the whole workflow.
- Added manifest operational issues and artifact-compliance audit fields.
- Expanded tests to cover gzip decoding, ETF override bundling, HTML/CSV detection, preflight, optional PDF fallback, and operational issue recording.

## 0.4.0 — Quality automation and provider-value ledger

- Added deterministic source-bundle builder for EDGAR submissions/companyfacts and explicit user-supplied URLs.
- Added SEC companyfacts metric extractor for common auditable financial metrics.
- Added ETF holdings CSV parser for holdings count, top-10 concentration, sector weights, and country weights.
- Added citation linter for markdown + JSON quantitative-claim discipline.
- Added verified-local-data chart generator for price and ETF sector-weight charts.
- Added validation `data_gaps` schema and prompt requirements.
- Added retail paid-service usefulness assessment and cumulative `provider_value_ledger.json`.
- Added provider summary command for deciding after 20+ runs which one or two retail services are most likely to improve quality.
- Final manifests now scan recursively so source bundles and intermediate artifacts remain visible.

## 0.3.0 — OpenClaw quality gates

- Added primary-source quality addendum.
- Added structured quantitative claim schema.
- Added deterministic validation-count checks.
- Added fix-coverage checks for prior Critical/Moderate issue IDs.
- Carried unresolved data-unavailable issues into final manifest.
