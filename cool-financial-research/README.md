# Cool Financial Research — OpenClaw Skill

A local OpenClaw skill for multi-agent financial research on US-listed stocks, ADRs, and ETFs.

This version is OpenClaw-native: the LLM connection is provided by the OpenClaw harness and its configured model/auth profile. The Python helper scripts perform only deterministic work such as EDGAR-first classification, directory setup, JSON validation, stop-condition checks, and PDF rendering. They do **not** call OpenAI, read `.env`, or require an API key.

## Install locally

Unzip or copy this folder somewhere local, then install it into your active OpenClaw workspace:

```bash
# Preferred if your OpenClaw CLI supports local path installs:
openclaw skills install ./cool-financial-research-openclaw
openclaw skills list

# If your CLI treats paths as registry slugs, install manually instead:
mkdir -p ~/.openclaw/skills/cool-financial-research
cp -R ./cool-financial-research-openclaw/* ~/.openclaw/skills/cool-financial-research/
openclaw skills list
```

OpenClaw local installs expect a directory containing `SKILL.md` at the root. Some CLI builds do not support `--as` for local paths; manual install is safe for this skill.


## Optional package install for local development

Manual OpenClaw installation does not require `pip install`; the helper wrapper remains stdlib-only. For local development and schema imports:

```bash
python3 -m pip install -e .[dev,pdf,pdftext,charts]
# deterministic helper entry point
cfr-helper preflight --output-root ./cool-financial-research
```

The package intentionally contains no OpenAI SDK dependency, no `python-dotenv`, no `.env` workflow, and no standalone `cool-financial-research` package CLI. OpenClaw is the only supported orchestration runtime; `scripts/cfr_helper.py` and the packaged `cfr-helper` entry point are deterministic helper surfaces only.

## OpenClaw config requirements

The workflow requires sub-agent tools. If your OpenClaw agent already uses the coding/full tool profile, you may already have them. Otherwise merge the relevant settings from:

```text
examples/openclaw-config.example.json5
```

The important parts are:

```json5
{
  tools: {
    alsoAllow: ["exec", "sessions_spawn", "sessions_yield", "subagents"]
  },
  agents: {
    defaults: {
      model: "gpt-5.5",
      thinking: "high",
      subagents: {
        delegationMode: "prefer",
        maxSpawnDepth: 2,
        maxChildrenPerAgent: 5,
        maxConcurrent: 4,
        runTimeoutSeconds: 1800,
        model: "gpt-5.5-pro",
        thinking: "high"
      }
    }
  }
}
```

Adjust model IDs to match the model names configured in your OpenClaw installation. This skill does not hardcode provider auth.

## Usage

From OpenClaw chat or CLI, ask for the skill explicitly, for example:

```bash
openclaw agent --message "Use the cool-financial-research skill to research AAPL" --thinking high
openclaw agent --message "Use cool-financial-research for SPY as ETF, max 5 iterations, include PDF" --thinking high
openclaw agent --message "Use cool-financial-research for BABA as ADR" --thinking high
```

The parent OpenClaw agent acts as the orchestrator and spawns research, validation, and fix sub-agents.


## Research quality hardening

Version 0.7 narrows the repository to an OpenClaw-only runtime model. The legacy direct workflow stack and developer convenience CLI have been removed. The supported command surface is the deterministic helper wrapper at `scripts/cfr_helper.py`, plus the equivalent packaged `cfr-helper` entry point when the package is installed locally.

Version 0.6 kept the v0.5 research-quality gates and ECH hardening, and added package ergonomics from the superpowers build without adding any direct LLM/API-key path. It includes a proper `src/cool_financial_research/` package, Pydantic developer models that mirror the strict JSON schemas, and importable deterministic helper modules. The stdlib `scripts/cfr_helper.py` path remains available for OpenClaw.

Version 0.5 adds operational hardening from the first ECH ETF run: gzip-safe SEC fetching, ETF/fund ticker fallback, explicit ETF security-type override for source bundling, conservative iShares/BlackRock source discovery, bad CSV/HTML detection, preflight dependency checks, artifact verification/repair workflow, PDF text extraction, optional PDF rendering fallback, and manifest operational issues.

Version 0.4 added explicit quality gates, deterministic data helpers, and a paid-service value ledger on top of the original prompts:

- Primary-source preference is binding across research, validation, and fix agents.
- Every material quantitative claim must be represented in JSON with source id, source date, access date, confidence, verification status, and stale flag.
- Validation counts are checked deterministically against the issue list.
- Fix outputs can be validated against the previous validation JSON to confirm every prior open Critical/Moderate issue id was addressed.
- Validation outputs include `data_gaps` and the helper maintains a cumulative `provider_value_ledger.json`.
- Source bundles, XBRL extracts, ETF holdings CSV/issuer-JSON parsers, citation linting, and verified-data chart generation are available as deterministic helper commands.
- Finalization copies unresolved Critical/Moderate issues into `run_manifest.json`.
- Final manifests scan the output directory recursively so intermediate files and source bundles remain visible for audit.

## Workflow

1. Classify the input ticker as equity, ADR, or ETF.
2. Run preflight and record missing optional PDF/PDF-text dependencies in the manifest.
3. If classification fails but the user supplied a known `security_type`, proceed with a low-confidence override and require validation to verify it.
4. For equity/ADR, use the equity prompts. For ETF, use the ETF prompts.
5. Build a source bundle from EDGAR/fund ticker data, conservative issuer discovery, and any explicit issuer/fact-sheet/methodology URLs supplied by the user. For equities/ADRs, optionally extract common SEC XBRL metrics. For ETFs, parse a user-supplied issuer holdings CSV when available.
6. Launch a research sub-agent and save:
   - `<SYMBOL>-first_run.md`
   - `<SYMBOL>-first_run.json`
7. Verify artifacts with `verify-artifacts`; if missing/malformed, run the artifact-repair prompt once before continuing.
8. Launch a validation sub-agent and save:
   - `<SYMBOL>-validation1.md`
   - `<SYMBOL>-validation1.json`
9. Verify validation artifacts and update the paid-service value ledger from validation `data_gaps`. If the validator finds open critical/moderate issues, launch a fix sub-agent and save:
   - `<SYMBOL>-validation-fix1.md`
   - `<SYMBOL>-validation-fix1.json`
10. Verify fix artifacts against the previous validation JSON so every prior open Critical/Moderate issue ID is addressed. Repeat validation/fix until either:
   - zero critical and zero moderate issues remain; or
   - all remaining critical/moderate issues are marked `unresolved_data_unavailable`; or
   - five validation iterations have completed.
11. Produce final artifacts:
   - `<SYMBOL>-final.md`
   - `<SYMBOL>-final.json`
   - `<SYMBOL>-final.pdf` when PDF rendering is available
   - `run_manifest.json`

## Output directory

Default:

```text
./cool-financial-research/<SYMBOL>/
```

Example:

```text
./cool-financial-research/AAPL/
  AAPL-first_run.md
  AAPL-first_run.json
  AAPL-validation1.md
  AAPL-validation1.json
  AAPL-validation-fix1.md
  AAPL-validation-fix1.json
  AAPL-final.md
  AAPL-final.json
  AAPL-final.pdf
  run_manifest.json
```

## Helper commands

The helper is intentionally deterministic:

```bash
python3 scripts/cfr_helper.py init-run AAPL
python3 scripts/cfr_helper.py preflight --symbol AAPL
python3 scripts/cfr_helper.py classify AAPL --provider edgar
python3 scripts/cfr_helper.py classify ECH --mode etf --provider edgar
python3 scripts/cfr_helper.py prompts equity
python3 scripts/cfr_helper.py build-source-bundle AAPL --output-root ./cool-financial-research
python3 scripts/cfr_helper.py build-source-bundle ECH --output-root ./cool-financial-research --security-type etf --issuer ishares --ishares-product-id 239618
python3 scripts/cfr_helper.py extract-xbrl-metrics ./cool-financial-research/AAPL/source_bundle/sec_companyfacts.json
python3 scripts/cfr_helper.py verify-artifacts AAPL research research ./cool-financial-research/AAPL/AAPL-first_run.md ./cool-financial-research/AAPL/AAPL-first_run.json
python3 scripts/cfr_helper.py validate-json research ./cool-financial-research/AAPL/AAPL-first_run.json
python3 scripts/cfr_helper.py extract-issuer-holdings-json ./cool-financial-research/ECH/source_bundle/issuer_fund.json --output-csv ./cool-financial-research/ECH/source_bundle/holdings_extracted.csv --output-json ./cool-financial-research/ECH/source_bundle/etf_holdings_summary.json
python3 scripts/cfr_helper.py lint-citations ./cool-financial-research/AAPL/AAPL-first_run.md ./cool-financial-research/AAPL/AAPL-first_run.json
python3 scripts/cfr_helper.py validate-json validation ./cool-financial-research/AAPL/AAPL-validation1.json
python3 scripts/cfr_helper.py assess-data-gaps ./cool-financial-research/AAPL/AAPL-validation1.json --symbol AAPL --output-root ./cool-financial-research
python3 scripts/cfr_helper.py check-stop ./cool-financial-research/AAPL/AAPL-validation1.json
python3 scripts/cfr_helper.py validate-json research ./cool-financial-research/AAPL/AAPL-validation-fix1.json --previous-validation ./cool-financial-research/AAPL/AAPL-validation1.json
python3 scripts/cfr_helper.py finalize AAPL current.md current.json --stopped-reason no_blocking_issues --validation-json ./cool-financial-research/AAPL/AAPL-validation1.json
python3 scripts/cfr_helper.py render-pdf ./cool-financial-research/AAPL/AAPL-final.md ./cool-financial-research/AAPL/AAPL-final.pdf --optional
python3 scripts/cfr_helper.py extract-pdf-text ./cool-financial-research/AAPL/source_bundle/prospectus.pdf --optional
python3 scripts/cfr_helper.py provider-summary --output-root ./cool-financial-research --min-runs 20
```

## Learning which paid service is worth buying

Each run records which data gaps most limited research quality. The helper writes:

```text
./cool-financial-research/<SYMBOL>/<SYMBOL>-provider-gap-assessment.json
./cool-financial-research/provider_value_ledger.json
```

After fewer than 20 runs, treat the provider ranking as directional. After 20+ runs, the top one or two services in `provider_value_ledger.json` are the best candidates to evaluate, because they repeatedly addressed actual gaps encountered by this workflow.

The built-in catalog favors retail-accessible services rather than institutional feeds. It includes broad research platforms such as Fiscal.ai, TIKR, Koyfin, Morningstar Investor, Seeking Alpha Premium, TradingView, Unusual Whales, Market Chameleon, Fintel, ORTEX, and ImportGenius. The ledger does not imply the skill accessed those services; it only estimates which service would likely have improved the run if licensed local exports had been available.

## Paid provider option

The default classifier uses EDGAR. For a paid provider, export a local classification JSON and point the helper at it. This keeps provider secrets outside the skill.

Example file:

```text
examples/paid-provider-classifications.example.json
```

Example command:

```bash
python3 scripts/cfr_helper.py classify BABA \
  --provider paid-json \
  --paid-provider-config examples/paid-provider-classifications.example.json
```

## PDF rendering

PDF rendering tries, in order:

1. Python `markdown` + `weasyprint`
2. `pandoc`
3. HTML fallback with an error file

Optional local install:

```bash
python3 -m pip install markdown weasyprint
```

If rendering fails with `--optional`, the command exits successfully after producing HTML fallback and a structured `.pdf-error.txt` JSON status. The skill should not claim a PDF was created; it should link the HTML fallback and error file.

PDF text extraction tries `pdftotext`, `pypdf`, `PyPDF2`, then `pdfplumber`. If all are missing and `--optional` is used, it writes `pdf_extract_manifest.json` and the validator should record the limitation as a data gap when it affects source review.

## Tests

```bash
python3 -m pip install pytest
pytest -q
```

## Files

```text
SKILL.md
README.md
prompts/
  equity-research.md
  equity-validation.md
  equity-research-fix-validation.md
  etf-research.md
  etf-validation.md
  etf-research-fix-validation.md
  artifact-repair.md
schemas/
  research-output.schema.json
  validation-output.schema.json
scripts/
  cfr_helper.py
examples/
  openclaw-config.example.json5
  paid-provider-classifications.example.json
  retail-data-services.example.json
  issuer-product-map.example.json
prompts/
  _quality-gate-addendum.md
tests/
  test_cfr_helper.py
```

## Notes

This skill produces research artifacts only. It should not present output as personalized financial advice.
