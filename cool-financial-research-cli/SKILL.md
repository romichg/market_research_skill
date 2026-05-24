# Skill: cool-financial-research

## Purpose

Run a local multi-agent financial research workflow for US-listed stocks, ADRs, and ETFs.

## Inputs

- `symbol`: required ticker symbol.
- `security_type`: `auto`, `equity`, `adr`, or `etf`. Default `auto`.
- `max_iterations`: default `5`.
- `analysis_date`, `horizon`, `risk_tolerance`: optional prompt parameters.

## Workflow

1. Orchestrator classifies symbol using EDGAR by default.
2. If classification fails or is ambiguous, stop with an error.
3. Equity and ADR symbols use the equity prompt set.
4. ETF symbols use the ETF prompt set.
5. Research agent writes first-run markdown and strict JSON.
6. Validation agent receives the latest report and writes validation markdown and JSON.
7. Fix agent receives the report plus validation and writes a revised report.
8. Repeat validation/fix until no open Critical or Moderate issues remain, all remaining blocking issues are marked unresolved because primary data is unavailable, or max iterations is reached.
9. Write final markdown, final JSON, run manifest, and optional PDF.

## Output Location

```text
./cool-financial-research/<SYMBOL>/
```

## Important Constraints

- Do not guess when classification fails.
- Do not fabricate unavailable data.
- Preserve FACTS vs. INTERPRETATION distinctions.
- Treat Critical and Moderate validation findings as blocking unless explicitly unresolved due to unavailable primary-source data.
- Keep generated intermediate files for later audit.
- Generate charts only when reliable data is available.
