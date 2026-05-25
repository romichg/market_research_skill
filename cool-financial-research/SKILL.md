---
name: cool-financial-research
description: Research US-listed stocks, ADRs, and ETFs with a validation and revision feedback loop.
---

# Cool Financial Research

Use this skill when the user asks for market, stock, ADR, or ETF research and wants a report with validation, revisions, and saved audit artifacts.

## Runtime Rule

Use OpenClaw's existing model connection and tools for all reasoning. Do not require `OPENAI_API_KEY` and do not run the legacy direct-OpenAI workflow for this skill path.

Python helper commands are deterministic support only. Run them through:

```bash
cd {baseDir}
.venv/bin/python -m cool_financial_research.openclaw_helper --help
```

If `.venv` does not exist, tell the user to run:

```bash
cd {baseDir}
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

## Inputs

- `symbol`: required ticker unless the user has already provided it.
- `security_type`: optional `auto`, `equity`, `adr`, or `etf`; default to `auto`.
- `max_iterations`: default `5`, maximum `10`.
- `horizon`: default `3-5 years` unless the user specifies another horizon.
- `risk_tolerance`: default `moderate` unless the user specifies another profile.

## Workflow

1. Normalize the symbol to uppercase.
2. Run classification:

```bash
cd {baseDir}
.venv/bin/python -m cool_financial_research.openclaw_helper classify SYMBOL --security-type auto
```

3. If classification fails or conflicts with the user's explicit security type, stop and ask for clarification.
4. Initialize the output directory:

```bash
cd {baseDir}
.venv/bin/python -m cool_financial_research.openclaw_helper init-run SYMBOL
```

5. Load the research prompt:

```bash
cd {baseDir}
.venv/bin/python -m cool_financial_research.openclaw_helper prompt SECURITY_TYPE research
```

6. Use OpenClaw reasoning and available browsing/tools to produce a JSON object matching the research stage schema. Include `markdown_report` and `structured_data`.
7. Save the first run:

```bash
cd {baseDir}
.venv/bin/python -m cool_financial_research.openclaw_helper save-stage SYMBOL first_run research /path/to/research.json
```

8. Load the validation prompt and validate the latest report:

```bash
cd {baseDir}
.venv/bin/python -m cool_financial_research.openclaw_helper prompt SECURITY_TYPE validation
```

9. Save validation as `validation<N>`, then check stop conditions:

```bash
cd {baseDir}
.venv/bin/python -m cool_financial_research.openclaw_helper save-stage SYMBOL validation1 validation /path/to/validation.json
.venv/bin/python -m cool_financial_research.openclaw_helper should-stop /path/to/SYMBOL-validation1.json
```

10. If open Critical or Moderate issues remain, load the fix prompt, revise the report, and save `validation-fix<N>`.

```bash
cd {baseDir}
.venv/bin/python -m cool_financial_research.openclaw_helper prompt SECURITY_TYPE fix
.venv/bin/python -m cool_financial_research.openclaw_helper save-stage SYMBOL validation-fix1 fix /path/to/fix.json
```

Increment `validation-fix<N>` for each fix iteration.

11. Repeat validation and fix until a stop condition is met or `max_iterations` is reached.
12. Save the final report as `final` and write `run_manifest.json`.

```bash
cd {baseDir}
.venv/bin/python -m cool_financial_research.openclaw_helper save-stage SYMBOL final final /path/to/final.json
.venv/bin/python -m cool_financial_research.openclaw_helper write-manifest SYMBOL SECURITY_TYPE \
  --max-iterations 5 \
  --iterations-completed N \
  --stopped-reason STOP_REASON \
  --files-file /path/to/files.json \
  --unresolved-issues-file /path/to/unresolved-issues.json
```

`STOP_REASON` must be one of the stop condition values emitted or derived by the loop. If there are no unresolved issues, omit `--unresolved-issues-file` or provide an empty JSON list.

## Stop Conditions

Stop when:

- no Critical or Moderate validation issues remain;
- all remaining Critical or Moderate issues are marked `unresolved_data_unavailable`;
- `max_iterations` is reached.

## Correctness Rules

- Prefer primary sources: SEC filings, issuer investor relations pages, ETF prospectuses, ETF fact sheets, index methodology documents, and official exchange or regulator data.
- Cite or mark as `unverified` every material quantitative claim.
- Include source dates and confidence levels for material claims.
- Flag stale or fast-changing data instead of inventing precision.
- Keep FACTS separate from INTERPRETATION.
- Validation issue counts must match the issue list.
- Each fix pass must resolve every open Critical or Moderate issue or explicitly mark it `unresolved_data_unavailable`.
- Carry unresolved issues into the final report and manifest.
- Preserve intermediate files for audit.

## Output

Default output location:

```text
{baseDir}/cool-financial-research/SYMBOL/
```

Summarize the final report for the user and include the final markdown path, final JSON path, manifest path, stop reason, and unresolved Critical/Moderate issues.
