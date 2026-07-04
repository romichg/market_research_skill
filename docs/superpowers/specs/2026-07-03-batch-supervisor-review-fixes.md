# Spec: Fixes for review findings on `improve/market-research-batch-supervisor-ech-20260703`

Status: proposed
Date: 2026-07-03
Branch under review: `improve/market-research-batch-supervisor-ech-20260703` (commits `27444cb`, `2ddda1c`, `9f64f3a`)
Implementation branch: same branch (follow-up commits)

## Background

A full code review of the three commits on this branch surfaced two confirmed defects, one dead-code cleanup, and one robustness gap. Both defects were reproduced empirically before writing this spec. Verified non-issues (no action): the now-non-null `report_json` in data-bundle scaffolds affects no consumer (`producer_self_check.run_self_check` only calls `discover()` on report dirs where a final report exists; `inspect-validation` reads issues only), the reuse guard correctly ignores `init-batch`'s `prompts/` control dir, and the `--resume` real→real path works.

## Findings

### F1 (moderate, regression): `--dry-run` poisons the run-root for the subsequent real run

Introduced in `9f64f3a`. `existing_iteration_conflict()` in
`market-research/batch-supervisor/scripts/research_loop.py` treats
`iteration-01/commands.json` as evidence of a prior run:

```python
if (iteration_dir / "producer.log").exists() or (iteration_dir / "commands.json").exists():
```

But the dry-run path in `execute_symbol_loop` writes exactly that file
(`write_json(iteration_dir / "commands.json", commands)`). Reproduction:

```bash
research_loop.py run-batch EWW --run-root runtime/batch --as-of 2026-07-03 ... --dry-run   # ok
research_loop.py run-batch EWW --run-root runtime/batch --as-of 2026-07-03 ...             # dies: "Refusing to overwrite existing run"
```

This breaks the documented workflow: `supervisor-workflow.md` recommends
`run-batch --dry-run` for inspecting prompts and command plans before a real
run on the same run-root. The die() message is also inaccurate ("already has
iteration-01 logs") when only a plan file exists. The existing test
`test_run_batch_dry_run_does_not_trigger_reuse_guard` only covers dry→dry,
missing the dry→real case.

### F2 (minor, bug): wrong `--output-root` guidance for non-dated run dirs

Introduced in `2ddda1c`. When `runtime_dir_for_prompt` falls back to the
literal placeholder path `runtime/SYMBOL/YYYY-MM-DD` (any non-dated
`--run-dir`, e.g. `write-prompts AAPL --run-dir reports/AAPL`),
`procedural_output_root_for_prompt` fails the `\d{4}-\d{2}-\d{2}` regex on the
literal `YYYY-MM-DD` name, falls through to the generic `path.parent` branch,
and returns `runtime/AAPL`. A child following the generated prompt would run
`procedural_source_helper.py --output-root runtime/AAPL --as-of ...`, and the
helper appends `SYMBOL/AS_OF`, producing a doubled-symbol path
`runtime/AAPL/AAPL/AS_OF`. Reproduced via direct module call. Batch runs
(dated run dirs) are unaffected, which is why existing tests pass.

### F3 (cleanup): dead conditional in `procedural_output_root_for_prompt`

Branches 2 and 3 both `return str(path.parent)`; the second `if` is
meaningless as written. Fold into the F2 fix.

### F4 (minor, robustness): sibling report lookup drops on-disk casing

Introduced in `27444cb`. `sibling_report_json_for_data_bundle` in
`market-research/shared/scripts/validate_market_research.py` builds the
sibling path from the uppercased manifest symbol:

```python
report_dir = repo_root / "reports" / symbol / run_dir.name
```

`ensure_canonical_data_bundle_path` compares case-insensitively
(`path.parent.name.upper() == symbol.upper()`), so a lowercase on-disk layout
(`data/ech/2026-07-03` with manifest symbol `ECH`) is accepted — but the
sibling lookup then probes `reports/ECH/...` while a producer that created the
lowercase data dir would plausibly have written `reports/ech/...`. On a
case-sensitive filesystem the lookup silently misses and the
usage-disposition comparison regresses to the pre-`27444cb` false-positive
behavior for that run.

## Implementation

### Phase 1 — F1: guard only on execution evidence

File: `market-research/batch-supervisor/scripts/research_loop.py`

Replace `existing_iteration_conflict` so only child-execution logs count as a
conflict, and reword the refusal message in `cmd_run_batch` to match:

```python
def existing_iteration_conflict(root: Path, symbol: str, as_of: str) -> Path | None:
    iteration_dir = root / symbol / as_of / "iteration-01"
    if (iteration_dir / "producer.log").exists() or (iteration_dir / "validator.log").exists():
        return iteration_dir
    return None
```

Message change: "...already has iteration-01 producer/validator logs from a
prior run-batch invocation..." (rest unchanged: suggest a fresh timestamped
`--run-root` or `--resume`).

Rationale for the trigger set:
- `producer.log` / `validator.log` are created only by `run_shell_command`,
  i.e. only when a child was actually launched. They are exactly the
  artifacts whose silent overwrite the guard exists to prevent.
- `commands.json` and `*.prompt.md` are plans; dry-run writes them, and a real
  run regenerates them anyway before launching children. Overwriting a plan
  loses nothing.
- A real run interrupted after `write_json(commands.json)` but before
  `run_shell_command` opens the log leaves no logs — allowing a clean re-run
  in that window is correct, not a hole.

Tests (`tests/test_research_loop.py`):
- Add `test_run_batch_dry_run_then_real_run_does_not_trigger_reuse_guard`:
  dry-run with stub `--producer-command`/`--validator-command` templates, then
  a real run with the same run-root using the stub-writer commands from
  `test_run_batch_refuses_to_reuse_run_root_with_existing_iteration_logs`;
  assert the real run exits 0.
- Keep `test_run_batch_refuses_to_reuse_run_root_with_existing_iteration_logs`
  as-is (its first real run writes `producer.log`, so it still exercises the
  refusal and the `--resume` escape). Update its stderr assertion if the
  message rewording changes asserted substrings ("Refusing to overwrite
  existing run" and "--resume" both survive).
- Keep `test_run_batch_dry_run_does_not_trigger_reuse_guard` (dry→dry).

### Phase 2 — F2 + F3: fix placeholder handling, collapse dead branch

File: `market-research/batch-supervisor/scripts/research_loop.py`

```python
def procedural_output_root_for_prompt(symbol: str, runtime_dir: str) -> str:
    path = Path(runtime_dir)
    dated_name = re.fullmatch(r"\d{4}-\d{2}-\d{2}", path.name) or path.name == "YYYY-MM-DD"
    if dated_name and path.parent.name.upper() == symbol.upper():
        return str(path.parent.parent)
    return str(path.parent)
```

- Treat the literal `YYYY-MM-DD` placeholder (produced by
  `dated_layout_dir` for non-dated inputs) the same as a real date, so
  `runtime/AAPL/YYYY-MM-DD` → `runtime`, matching the helper's
  `output_root/SYMBOL/AS_OF` layout.
- The former branches 2 and 3 collapse into the single trailing `return`;
  behavior for `runtime/loop/AAPL`-shaped dirs (symbol-named leaf) is
  unchanged (`path.parent`).
- The `dated_name and not symbol-parent` corner (e.g. a hand-passed
  `--skill-issue-dir` ending in a date under a non-symbol parent) keeps the
  `path.parent` fallback; no known caller produces it.

Tests (`tests/test_research_loop.py`):
- Add `test_producer_prompt_procedural_output_root_for_non_dated_run_dir`:
  `write-prompts AAPL --run-dir reports/AAPL`, assert the producer prompt
  contains ``pass `--output-root runtime --as-of YYYY-MM-DD` `` and does NOT
  contain `--output-root runtime/AAPL `.
- Existing tests `test_producer_prompt_points_procedural_helper_output_root_at_plain_runtime_dir`
  and `..._at_batch_run_root` continue to pin the dated cases.

### Phase 3 — F4: preserve on-disk casing in sibling lookup

File: `market-research/shared/scripts/validate_market_research.py`

```python
def sibling_report_json_for_data_bundle(run_dir: Path, symbol: str) -> Path | None:
    repo_root = run_dir.parent.parent.parent
    report_dir = repo_root / "reports" / run_dir.parent.name / run_dir.name
    ...
```

Drop the now-unused `symbol` parameter (single call site in
`deterministic_bundle_result`) or keep it if a casing-normalized fallback
probe is desired; preferred: drop it and use only `run_dir.parent.name`,
since the producer that wrote `data/<name>/<date>` writes
`reports/<name>/<date>` with the same casing (both come from the same
normalized symbol), and a mixed-casing layout has no known producer.

Tests (`tests/test_validate_market_research.py`):
- Add `test_validator_data_bundle_sibling_report_lookup_preserves_dir_casing`:
  same fixture as
  `test_validator_data_bundle_uses_existing_sibling_report_json_for_usage_dispositions`
  but with `data/ech/2026-06-01` + `reports/ech/2026-06-01` (lowercase dirs,
  manifest symbol `ECH`); assert `missing_required == []` and
  `validation["report_json"]` points at the lowercase report path.
  Note: `ensure_canonical_report_dir_path` is not invoked on this code path
  (bundle branch), so lowercase report dirs do not trip the canonical-path
  check; the scaffold `--output-prefix` in the test must still satisfy
  `ensure_validation_output_prefix` (use the lowercase reports dir, which
  passes its case-insensitive comparison).

## Verification

```bash
python3 -m pytest tests/ -q                     # expect 296 existing + 3 new = 299 passed
```

Manual reproductions that must flip:

```bash
# F1: dry-run then real run on the same root (stub commands) — must succeed
research_loop.py run-batch EWW --run-root /tmp/rr --as-of 2026-07-03 --producer-command "..." --validator-command "..." --dry-run
research_loop.py run-batch EWW --run-root /tmp/rr --as-of 2026-07-03 --producer-command "..." --validator-command "..."

# F2: non-dated run dir — prompt must say `--output-root runtime`, not `runtime/AAPL`
research_loop.py write-prompts AAPL --run-dir reports/AAPL --output-dir /tmp/p && grep output-root /tmp/p/AAPL-producer-initial.md
```

And the guard must still refuse after a real (logged) run without `--resume`.

## Risks

- Phase 1 loosens a guard added on this same branch; the loosened trigger
  still covers every case where child work would be silently destroyed. No
  release has shipped the stricter behavior.
- Phase 2 changes generated prompt text only; no execution-path changes.
- Phase 3 changes a fallback lookup path only; the uppercase layout used by
  every current producer resolves identically before and after.
- All three phases are prompt/guard/lookup adjustments with no schema or
  artifact-contract changes; no batch re-run is required to merge, though a
  smoke `run-batch --dry-run` + real run on a scratch root exercises F1
  end-to-end.
