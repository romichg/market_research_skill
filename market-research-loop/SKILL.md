---
name: market-research-loop
description: Use when running supervised market research batches that need fresh Codex contexts for research, validation, remediation, or later skill-improvement feedback collection.
---

# Market Research Loop

Use this skill from a supervised Codex session to orchestrate `market-research` and `validate-market-research` child sessions. The loop owns subprocess execution, pass/fail gating, remediation retries, logs, summaries, and skill-improvement feedback collection.

## Core Rule

Keep research, validation, remediation, and skill improvement separate.

- Research child: runs `$market-research SYMBOL`.
- Validation child: runs `$validate-market-research RUN_DIR`.
- Remediation child: fixes only open critical/moderate validation issues in the research bundle.
- Supervisor: watches the run, inspects failures, decides whether skill-improvement feedback is ready for a separate manual pass.

## Run A Batch

From the repo root:

```bash
python3 market-research-loop/scripts/research_loop.py run-batch SYMBOL ... --run-root reports/market-research-loop-YYYYMMDD --max-remediation-loops 3
```

Defaults launch child sessions with:

```bash
codex exec -C {cwd} --dangerously-bypass-approvals-and-sandbox - < {prompt_file}
```

Use `--command-timeout-seconds` to tune the watchdog. If a child times out after producing the expected artifacts, the harness logs the timeout and continues to the next phase.

## Supervision

While running, periodically inspect:

```bash
find RUN_ROOT -name '*.log' -print
python3 market-research-loop/scripts/research_loop.py summarize RUN_ROOT
```

Final pass gate: no open `critical` or `moderate` validation issues. Open `minor` findings are allowed but must be reported.

## Output Contract

Each run root contains:

- `research-loop-summary.json`
- `loop-skill-issues.md`
- `operator-notes.md`
- `SYMBOL/iteration-*/producer.log`
- `SYMBOL/iteration-*/validator.log`
- `SYMBOL/research_input_pack.md`
- `SYMBOL/manifest.json`
- `SYMBOL/source_manifest.json`
- `SYMBOL/gaps.json`
- `SYMBOL/normalized/`
- `SYMBOL/SYMBOL-research.md`
- `SYMBOL/SYMBOL-research.json`
- `SYMBOL/SYMBOL-validation.md`
- `SYMBOL/SYMBOL-validation.json`
- producer and validator skill issue files when observed

Use `operator-notes.md` for future user-requested changes that should not be implemented automatically, such as PDF output, browser/captcha handoff, alternate report formats, or new data providers.

## Feedback Collection

After enough qualified feedback has accumulated:

```bash
python3 market-research-loop/scripts/research_loop.py collect-feedback RUN_ROOT
```

This writes `skill-improvement-feedback.md` and `.json`. Review those manually, then start a separate explicit skill-improvement task. Do not silently rewrite skills at the end of a normal research run.

## Failure Handling

- `producer_failed`: inspect `producer.log`; if report artifacts exist, check whether the artifact-complete fallback should have applied.
- `validator_failed`: inspect `validator.log`; check for partial validation JSON.
- `failed_blocking_issues`: inspect the latest validation JSON, then either let the loop run another remediation if budget remains or report unresolved blocking IDs.
- Repeated harness failures: append concrete details to `loop-skill-issues.md`.
