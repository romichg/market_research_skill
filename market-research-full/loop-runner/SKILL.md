---
name: market-research-full-loop-runner
description: Use when running supervised market research batches that need fresh Codex contexts for research, validation, remediation, or later skill-improvement feedback collection.
---

# Market Research Loop

Use this skill from a supervised Codex session to orchestrate `market-research-full researcher` and `market-research-full verifier` child sessions. The loop owns subprocess execution, pass/fail gating, remediation retries, logs, summaries, and skill-improvement feedback collection.

## Core Rule

Keep research, validation, remediation, and skill improvement separate.

- Research child: runs `$market-research-full researcher SYMBOL`.
- Validation child: runs `$market-research-full verifier RUN_DIR`.
- Remediation child: fixes only open critical/moderate validation issues in the research bundle.
- Supervisor: watches the run, inspects failures, decides whether skill-improvement feedback is ready for a separate manual pass.

## Run A Batch

From the repo root:

```bash
python3 market-research-full/loop-runner/scripts/research_loop.py run-batch SYMBOL ... --run-root runtime/market-research-loop-YYYYMMDD --as-of YYYY-MM-DD --max-remediation-loops 3
```

If `--as-of` is omitted, the harness uses today's date. Runtime prompts, logs, and loop summaries stay under `RUN_ROOT/SYMBOL/AS_OF/`; deterministic data bundles belong under `data/SYMBOL/AS_OF/`; polished research and validation artifacts belong under `reports/SYMBOL/AS_OF/`.

Defaults launch child sessions with:

```bash
codex exec -C {cwd} --dangerously-bypass-approvals-and-sandbox - < {prompt_file}
```

Use `--command-timeout-seconds` to tune the watchdog. If a child times out after producing the expected artifacts, the harness logs the timeout and continues to the next phase. When a producer writes a dated deterministic bundle such as `SYMBOL/AS_OF/YYYY-MM-DD/` inside the runtime tree or a canonical deterministic bundle under `data/SYMBOL/YYYY-MM-DD/`, the harness passes that bundle as validator input and routes validation markdown/JSON to `reports/SYMBOL/YYYY-MM-DD/`. The input path is recorded as `artifact_run_dir` in `research-loop-summary.json`.

Custom validator command templates can use `{run_dir}` for the input artifact path and `{validation_output_dir}` for the reports output path.

## Supervision

While running, periodically inspect:

```bash
find RUN_ROOT -name '*.log' -print
python3 market-research-full/loop-runner/scripts/research_loop.py summarize RUN_ROOT
```

Final pass gate: no open `critical` or `moderate` validation issues. Open `minor` findings are allowed but must be reported.

## Output Contract

Each run root contains:

- `research-loop-summary.json`
- `loop-skill-issues.md`
- `operator-notes.md`
- `SYMBOL/AS_OF/iteration-*/producer.log`
- `SYMBOL/AS_OF/iteration-*/validator.log`
- `SYMBOL/AS_OF/research_input_pack.md` when a producer writes a bundle directly into runtime
- `SYMBOL/AS_OF/manifest.json` when a producer writes a bundle directly into runtime
- `SYMBOL/AS_OF/source_manifest.json` when a producer writes a bundle directly into runtime
- `SYMBOL/AS_OF/gaps.json` when a producer writes a bundle directly into runtime
- `SYMBOL/AS_OF/normalized/` when a producer writes a bundle directly into runtime
- `SYMBOL/AS_OF/YYYY-MM-DD/` when the producer writes a dated bundle inside runtime; this path is reported as `artifact_run_dir`
- canonical deterministic bundles under `data/SYMBOL/YYYY-MM-DD/` when produced outside the runtime tree
- final research and validation artifacts, including validation for deterministic bundles, under `reports/SYMBOL/YYYY-MM-DD/`
- producer and validator skill issue files when observed

Use `operator-notes.md` for future user-requested changes that should not be implemented automatically, such as PDF output, browser/captcha handoff, alternate report formats, or new data providers.

## Feedback Collection

After enough qualified feedback has accumulated:

```bash
python3 market-research-full/loop-runner/scripts/research_loop.py collect-feedback RUN_ROOT
```

This writes `skill-improvement-feedback.md` and `.json`. Review those manually, then start a separate explicit skill-improvement task. Do not silently rewrite skills at the end of a normal research run.

## Failure Handling

- `producer_failed`: inspect `producer.log`; if report artifacts exist, check whether the artifact-complete fallback should have applied.
- `validator_failed`: inspect `validator.log`; check for partial validation JSON.
- `failed_blocking_issues`: inspect the latest validation JSON, then either let the loop run another remediation if budget remains or report unresolved blocking IDs.
- Repeated harness failures: append concrete details to `loop-skill-issues.md`.
