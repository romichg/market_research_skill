# Supervisor Workflow

## Run A Batch

From the repo root:

```bash
python3 market-research/batch-supervisor/scripts/research_loop.py run-batch SYMBOL ... --run-root runtime/market-research-batch-YYYYMMDD-HHMMSS --as-of YYYY-MM-DD --max-remediation-loops 3
```

Use a time-of-day suffix (`HHMMSS`) in `--run-root`, not just the date, so a second same-day invocation for the same symbols gets its own run-root instead of colliding with an earlier run's iteration logs. `run-batch` refuses to run (non-`--dry-run`) if `RUN_ROOT/SYMBOL/AS_OF/iteration-01` already has producer/validator logs from a prior invocation, to avoid silently overwriting them; pass `--resume` to intentionally continue writing into an existing run-root.

If `--as-of` is omitted, the harness uses today's date. Runtime prompts, logs, skill issue files, intermediate validation scaffold snapshots, self-improvement feedback packages, and loop summaries stay under `runtime/SYMBOL/AS_OF/` or the configured runtime `RUN_ROOT/SYMBOL/AS_OF/`; deterministic data bundles belong under `data/SYMBOL/AS_OF/`; polished research and validation artifacts plus the canonical `SYMBOL-validation-scaffold.md/json` belong under `reports/SYMBOL/AS_OF/`.

Defaults launch child sessions with:

```bash
codex exec -C {cwd} --dangerously-bypass-approvals-and-sandbox - < {prompt_file}
```

This default is conditional on `codex` being available on PATH. If the current agent runtime does not provide a local `codex` CLI, do not assume the shell harness can launch children directly. Use the current agent's native fresh-child/subagent mechanism with the generated producer, verifier, and remediation prompts, or pass explicit `--producer-command`, `--validator-command`, and `--remediation-command` templates. `run-batch --dry-run` remains useful for writing prompt files and command plans without launching children.

Use `--command-timeout-seconds` to tune the watchdog. If a child times out after producing expected artifacts, the harness logs the timeout and continues. When a producer writes a canonical deterministic bundle under `data/SYMBOL/YYYY-MM-DD/`, the harness passes that bundle as validator input and routes validation markdown/JSON to `reports/SYMBOL/YYYY-MM-DD/`. The input path is recorded as `artifact_run_dir` in `research-loop-summary.json`.

Custom validator command templates can use `{run_dir}` for the input artifact path and `{validation_output_dir}` for the reports output path.

CLI paths are authoritative. When defaults are used, the supervisor recognizes `RESEARCH_DATA_DIR`, `RESEARCH_REPORTS_DIR`, and `RESEARCH_RUNTIME_DIR` as artifact-root fallbacks, while `RESEARCH_CACHE_DIR` controls deterministic raw/cache behavior. Prefer explicit CLI roots for reproducible batch runs.

Before launching a verifier for a completed report bundle, the harness runs the producer self-check with safe deterministic source-registry fixes enabled. If the self-check finds open critical or moderate issues, the harness skips the verifier for that iteration and sends the producer into remediation. This moves repeat mechanical findings such as missing deterministic usage dispositions or missing deterministic source records left into the producer loop.

## Supervision

Periodically inspect:

```bash
find RUN_ROOT -name '*.log' -print
python3 market-research/batch-supervisor/scripts/research_loop.py summarize RUN_ROOT
```

Summary uses `research-loop-config.json` symbols when available and ignores scaffold/control directories such as `prompts/`.

If manual post-loop remediation and fresh validation change current pass/fail state, refresh the persisted summary:

```bash
python3 market-research/batch-supervisor/scripts/research_loop.py refresh-summary RUN_ROOT
```

This preserves historical loop facts while updating current status and the final validation path.

Failure handling:

- `producer_failed`: inspect `producer.log`; if canonical `reports/SYMBOL/YYYY-MM-DD/` or `data/SYMBOL/YYYY-MM-DD/` artifacts exist, check whether the artifact-complete fallback should have applied.
- `validator_failed`: inspect `validator.log`; check for partial validation JSON.
- `failed_blocking_issues`: inspect the latest validation JSON, then either let the loop run another remediation if budget remains or report unresolved blocking IDs.
- Repeated harness failures: append concrete details to `loop-skill-issues.md`.

## Feedback Collection

Self-improvement is not automatic. To create a central prompt over one or more completed batch roots, prefer:

```text
$market-research batch-supervisor self-improve RUN_ROOT [RUN_ROOT ...]
```

The helper can also be run directly:

```bash
python3 market-research/batch-supervisor/scripts/research_loop.py self-improve RUN_ROOT [RUN_ROOT ...]
```

This first refreshes each run root's runtime `skill-improvement-feedback.md` and `.json` package, collecting loop notes, operator notes, report-side skill issue files, inline report comments such as `<@researcher: ...>`, and supporting intermediate validation scaffold paths under `validation_scaffolds/`. It then writes `docs/superpowers/plans/self-improvement/TIMESTAMP/self-improvement.md` by default so durable prompts, ideas, plans, and JSON survive `runtime/` cleanup. Open that prompt in Codex and run the review in the current session. The prompt asks for `self-improvement-ideas.md`, `self-improvement-plan.md`, and `self-improvement.json` under the same central output directory.

The generated prompt should evaluate deterministic data usage, investor-grade memo quality, omitted risks or data gaps, validator specificity, and recurring failures that should become checks, prompt requirements, helper scripts, or tests.

Treat the finished investor report as the product: preserve `reports/` for polished deliverables, `runtime/` for intermediate work, and `data/` for deterministic evidence. Prefer field-level freshness guidance over cache-mechanics disclosure; only surface cache/provider mechanics in the main report when stale, missing, or conflicting data changes investor interpretation.

To collect existing issue notes and inline report comments without starting a review:

```bash
python3 market-research/batch-supervisor/scripts/research_loop.py collect-feedback RUN_ROOT
```

This writes `skill-improvement-feedback.md` and `.json`. Review those manually, then start a separate explicit skill-improvement task.
