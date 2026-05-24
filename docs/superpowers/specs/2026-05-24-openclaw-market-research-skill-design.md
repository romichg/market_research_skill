# OpenClaw Market Research Skill Design

## Goal

Build a local-only OpenClaw skill for stock, ADR, and ETF research that uses OpenClaw's existing model connection for all reasoning. The skill should run a structured research, validation, and revision loop, preserve auditable artifacts, and avoid requiring a separate `OPENAI_API_KEY`.

The project identity should be `cool-financial-research`, not `cool-financial-research-cli`. A command-line interface may remain as a helper or compatibility surface, but the repository and skill should no longer present themselves as primarily a CLI.

## Package Shape

The installable OpenClaw skill folder will be the renamed project directory:

```text
cool-financial-research/
  SKILL.md
  README.md
  pyproject.toml
  src/cool_financial_research/
    openclaw_helper.py
    schemas.py
    providers/
    prompts/
  scripts/check-openclaw-skill.sh
  tests/
```

OpenClaw loads the skill from `SKILL.md`. The Python package name remains `cool_financial_research` to preserve normal Python naming and minimize code churn.

## Runtime Model

OpenClaw is the analyst. Python is the clerk.

OpenClaw performs research, validation, and revision using its configured model, browsing, and tool permissions. Python helpers perform deterministic work only:

- Normalize and classify tickers through SEC/EDGAR metadata.
- Load the correct prompt template for equity, ADR, or ETF workflows.
- Create run directories and stage filenames.
- Save markdown and JSON artifacts.
- Validate structured JSON against Pydantic schemas.
- Compute validation-loop stop conditions.
- Write `run_manifest.json`.

The OpenClaw execution path must not call the OpenAI SDK directly and must not require `OPENAI_API_KEY`.

## Workflow

For each requested symbol, the skill will:

1. Ask for a ticker if one was not provided.
2. Normalize the ticker and classify it as `equity`, `adr`, or `etf`.
3. Stop and ask for clarification if classification fails or conflicts with the user's stated security type.
4. Load the appropriate research, validation, and fix prompts.
5. Produce the initial research report using OpenClaw's model connection.
6. Save `<SYMBOL>-first_run.md` and `<SYMBOL>-first_run.json`.
7. Run forensic validation against the latest report.
8. Save `<SYMBOL>-validation<N>.md` and `<SYMBOL>-validation<N>.json`.
9. If open Critical or Moderate issues exist, revise the report.
10. Save `<SYMBOL>-validation-fix<N>.md` and `<SYMBOL>-validation-fix<N>.json`.
11. Repeat until a stop condition is met.
12. Save `<SYMBOL>-final.md`, `<SYMBOL>-final.json`, and `run_manifest.json`.

Outputs should default to:

```text
./cool-financial-research/<SYMBOL>/
```

## Stop Conditions

The loop stops when one of these is true:

- No Critical or Moderate validation issues remain.
- All remaining Critical or Moderate issues are explicitly marked `unresolved_data_unavailable`.
- The configured maximum iteration count is reached.

The manifest records the stop reason, iteration count, classification, generated files, and unresolved issues summary.

## Correctness Requirements

The skill should improve on the current workflow rather than merely repackage it:

- Prefer primary sources: SEC filings, issuer investor relations pages, ETF prospectuses, ETF fact sheets, index methodology documents, and official exchange or regulator data.
- Cite or mark as `unverified` every material quantitative claim.
- Include source dates and confidence levels for material claims.
- Flag stale or fast-changing data rather than forcing false precision.
- Keep FACTS separate from INTERPRETATION in research outputs.
- Ensure validation issue counts match the issue list.
- Require each fix stage to address every open Critical or Moderate issue or explicitly mark it unresolved due to unavailable data.
- Carry unresolved issues into the final report and manifest.
- Keep generated intermediate files for audit.

Disclaimers should be minimal. The skill may state that outputs are research, not personalized financial advice, but should not overemphasize that point in a local-only workflow.

## OpenClaw Skill Instructions

`SKILL.md` should include OpenClaw-compatible frontmatter with single-line YAML keys and a concise description. The body should explain when to use the skill, required inputs, helper commands, workflow stages, stop conditions, and failure handling.

The instructions should use `{baseDir}` when referencing local files so the skill remains relocatable inside an OpenClaw workspace or extra skill directory.

## Helper Interface

Add a helper module, likely `src/cool_financial_research/openclaw_helper.py`, with subcommands for deterministic operations. Candidate commands:

```bash
python -m cool_financial_research.openclaw_helper classify AAPL
python -m cool_financial_research.openclaw_helper init-run AAPL
python -m cool_financial_research.openclaw_helper prompt equity research
python -m cool_financial_research.openclaw_helper save-stage ...
python -m cool_financial_research.openclaw_helper validate-stage ...
python -m cool_financial_research.openclaw_helper should-stop ...
python -m cool_financial_research.openclaw_helper finalize-run ...
```

The exact command surface can be simplified during implementation, but it must keep model reasoning outside Python.

## Setup And Validation

Local setup should install Python dependencies but not model credentials:

```bash
cd cool-financial-research
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

Add `scripts/check-openclaw-skill.sh` to verify:

- `SKILL.md` exists and has valid frontmatter.
- `.venv` exists or setup instructions are clear.
- helper commands can import the package.
- classification helper can run or fails with an actionable SEC/network error.
- no OpenClaw path requires `OPENAI_API_KEY`.

## Testing

Unit tests should cover:

- EDGAR classification success and failure behavior with mocked responses.
- JSON schema validation for stage outputs.
- stop-condition logic.
- helper command behavior.
- checks that the OpenClaw path does not instantiate the direct OpenAI runtime.

Existing tests for loop stopping should be retained and adapted as needed.

## Migration Notes

The current `OpenAIJsonAgent` and standalone CLI workflow can remain temporarily for reference or compatibility, but they must not be the OpenClaw execution path. Documentation should clearly distinguish any legacy direct-LLM mode from the OpenClaw-native skill mode.

Rename user-facing references from `cool-financial-research-cli` to `cool-financial-research`.
