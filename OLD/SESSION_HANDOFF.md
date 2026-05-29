# Session Handoff

## Repository Context

Repo: `/home/rom/src/market_research_skill`

This repo contains two Codex skills and a new research-loop harness:

- `market-research/`: producer skill for public equity/ETF research bundles.
- `validate-market-research/`: validator skill for fresh-context validation of frozen bundles.
- `research-loop/`: harness that supervises producer, validator, and remediation runs through child `codex exec` sessions.

## Important Recent Work

1. Created EWW research artifacts under `market-research-runs/EWW/`.
2. Validator found one moderate issue: product-page snapshot values were stale/mismatched.
3. Fixed EWW product-page snapshot values across:
   - `EWW-research.md`
   - `EWW-research.json`
   - `research_context.json`
   - `research_context.md`
   - `run_manifest.json`
   - `sources.json`
   - `latest-product-page-gap-fill.json`
4. Added `skill-issues.md` entries for:
   - missing post-validator remediation flow
   - dynamic product-page source-date ambiguity
   - BlackRock/iShares extraction issues
5. Built `research-loop/scripts/research_loop.py`.
6. Added `research-loop/README.md`.
7. Added `tests/test_research_loop.py`.
8. Added `research_loop_instructions.md` for a fresh Codex terminal session to run the harness.

## Harness Commands

Fresh-session operator guide:

```bash
cat research_loop_instructions.md
```

Smoke run:

```bash
python3 research-loop/scripts/research_loop.py run-batch EWW AAPL \
  --run-root experiments/market-research-loop-smoke \
  --producer-command 'codex exec -C /home/rom/src/market_research_skill --sandbox danger-full-access --ask-for-approval never - < {prompt_file}' \
  --validator-command 'codex exec -C /home/rom/src/market_research_skill --sandbox danger-full-access --ask-for-approval never - < {prompt_file}' \
  --remediation-command 'codex exec -C /home/rom/src/market_research_skill --sandbox danger-full-access --ask-for-approval never - < {prompt_file}' \
  --max-remediation-loops 3
```

Summarize:

```bash
python3 research-loop/scripts/research_loop.py summarize experiments/market-research-loop-smoke
```

## Verification Already Run

The harness was smoke-tested with fake producer/validator/remediation subprocess commands:

- Help command passed.
- Dry-run prompt/command generation passed.
- Real execution path passed with a fake validation that already had no blocking issues.
- Real remediation path passed with a fake open moderate issue that was resolved on the remediation iteration.

`pytest` is not installed in this environment:

```text
/usr/bin/python3: No module named pytest
```

So the new test file exists but was not run through pytest here.

## Known Working Tree State

At the time this handoff was written, these paths were untracked:

- `market-research-runs/`
- `research-loop/`
- `tests/test_research_loop.py`
- `research_loop_instructions.md`
- `SESSION_HANDOFF.md`

Do not assume these are committed.

## Recommended Next Steps

1. Start a fresh Codex terminal session.
2. Read `research_loop_instructions.md`.
3. Run the smoke batch on `EWW AAPL`.
4. If it passes, run a small discovery batch such as `EWW ECH AAPL MSFT`.
5. Aggregate producer and validator skill issues.
6. Patch both skills in a separate pass, then re-run the same discovery symbols from clean output directories.

## Design Intent

The harness should stay small. It owns orchestration, logs, prompts, validation gating, and summaries. It should not directly perform research or validation judgment. The producer and validator skills should remain responsible for domain work and skill-improvement notes.
