---
name: market-research
description: Research US-listed equities, ADRs, and ETFs from a ticker symbol using public/free sources; create cited markdown and JSON artifacts; use deterministic helper scripts when useful but gracefully fall back to procedural research when helpers fail or are sparse. Use when Codex is asked for investment, equity, stock, ADR, ETF, fund, issuer, holdings, valuation, risk, or market research on a symbol.
---

# Market Research

Use this skill to produce a research bundle for one public equity, ADR, or ETF symbol. This is research support, not personalized financial advice.

## Core Rule

Use helper output as evidence, not authority.

```text
helper succeeds -> use structured context
helper partially succeeds -> use reliable helper output, try targeted procedural gap filling, disclose remaining gaps
helper fails -> research procedurally, disclose helper failure
helper gets bloated/flaky -> split, cap outputs, or demote to optional
```

Do not abandon the report solely because a helper failed unless no credible public source can be accessed and no user-provided files exist.

## Resources

- Use `scripts/market_research_helper.py` for deterministic run setup, manual classification, source recording, context preparation, procedural gap-fill recording, and BlackRock/iShares JSON promotion.
- Read `references/source-policy.md` before source gathering and citation work.
- Read `references/equity-research.md` for equities and ADRs.
- Read `references/etf-research.md` for ETFs.
- Read `references/report-template.md` before writing final artifacts.
- Use `schemas/research-output.schema.json` for the report sidecar.
- Use `schemas/validation-output.schema.json` as the shared validation contract.

## Workflow

1. Normalize the symbol to uppercase and create the run:

```bash
python3 {baseDir}/scripts/market_research_helper.py init-run SYMBOL --output-root ./market-research-runs
```

2. Classify the security. If the helper cannot classify from public data, use clear procedural evidence or ask the user to choose `equity`, `adr`, or `etf`; then record it:

```bash
python3 {baseDir}/scripts/market_research_helper.py classify SYMBOL --output-root ./market-research-runs --security-type etf --name "Fund or company name"
```

3. Gather public/free sources. Prefer primary sources. Record each material source:

```bash
python3 {baseDir}/scripts/market_research_helper.py record-source SYMBOL --output-root ./market-research-runs --id source_id --title "Source title" --url "https://example.com/source" --kind issuer_fact_sheet --confidence high
```

4. Prepare compact context:

```bash
python3 {baseDir}/scripts/market_research_helper.py prepare-research-context SYMBOL --output-root ./market-research-runs
```

5. Inspect `market-research-runs/SYMBOL/research_context.json`. If material fields are missing, fill only targeted gaps procedurally from public sources. Record fills:

```bash
python3 {baseDir}/scripts/market_research_helper.py record-gap-fill SYMBOL --output-root ./market-research-runs --field expense_ratio --value "0.59%" --source-id issuer_fact_sheet --confidence high --note "Filled from issuer fact sheet."
```

6. For BlackRock/iShares ETF payloads already downloaded or user-supplied, promote the useful structured data:

```bash
python3 {baseDir}/scripts/market_research_helper.py extract-blackrock SYMBOL --output-root ./market-research-runs --json-file ./market-research-runs/SYMBOL/source_bundle/blackrock_product_api.json --source-id blackrock_product_api
```

7. Write:

```text
market-research-runs/SYMBOL/
  SYMBOL-research.md
  SYMBOL-research.json
  research_context.json
  research_context.md
  sources.json
  run_manifest.json
  source_bundle/
```

8. Same-session self-check the artifacts for missing citations, stale dates, unsupported claims, and gaps. Label this as a self-check, not independent validation.

9. Tell the user the artifact paths and recommend running `validate-market-research` in a fresh Codex context against the run directory.

## Source Discipline

Every material quantitative claim must be cited or marked `Data not available` / `unverified`. Include source date, accessed date, and confidence when possible.

Keep facts separate from interpretation in major sections. Do not let procedural gap filling become open-ended browsing; search for named missing fields only.

## Paid Data

Do not require subscriptions or API keys. You may record exploratory notes about data that would have improved quality, but do not recommend purchasing a paid service from a single run.
