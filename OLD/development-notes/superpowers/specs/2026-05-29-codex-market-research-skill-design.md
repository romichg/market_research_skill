# Codex Market Research Skill Design

Date: 2026-05-29

## Goal

Create a Codex-installable skill set that can take a US-listed equity, ADR, or ETF symbol and produce useful, cited investment research artifacts using public/free sources. The design should reuse the best ideas from the existing `skill1` and `skill2` OpenClaw attempts while avoiding their main failure modes: brittle sub-agent orchestration, sparse context packets, helper hard-failures, and self-referential validation.

The expected end state is two manual Codex skills:

- `market-research`: produces the initial research bundle.
- `validate-market-research`: validates a frozen research bundle in a fresh context.

The skills should be useful in Codex first. Portability back to OpenClaw is optional future work.

## Non-Goals

- Do not build a paid-data workflow or require subscriptions.
- Do not ask for API keys or read `.env` secrets.
- Do not make multi-agent orchestration mandatory.
- Do not promise personalized financial advice or a buy/sell recommendation tailored to the user.
- Do not make helper success a prerequisite for a useful report.

## Design Summary

Use a helper-assisted workflow with procedural fallback.

The deterministic helper should gather, normalize, extract, scaffold, and validate structure. Codex should perform source judgment, procedural gap filling, interpretation, report writing, and independent validation.

The producer skill should attempt deterministic helpers first because they improve repeatability. If helpers partially succeed, Codex uses reliable helper output, tries to fill material gaps procedurally from public sources, and discloses remaining gaps. If helpers fail, Codex continues procedurally unless no credible source can be accessed and no user-provided files exist.

Validation should be a separate skill invoked manually in a new Codex context against the frozen run directory. Same-session self-checks are allowed as fast linting, but they are not independent validation.

## Package Layout

```text
market-research/
  SKILL.md
  agents/openai.yaml
  scripts/market_research_helper.py
  schemas/research-output.schema.json
  schemas/validation-output.schema.json
  references/equity-research.md
  references/etf-research.md
  references/source-policy.md
  references/report-template.md

validate-market-research/
  SKILL.md
  agents/openai.yaml
  scripts/validate_market_research.py
  references/investment-validation.md
```

The final implementation may copy or adapt proven code from `skill2/cool-financial-research`, but it should remove OpenClaw-specific runtime assumptions and keep the Codex skill surface small.

## Deterministic Responsibilities

The helper should handle tasks where the same inputs should produce the same structured outputs, aside from changes in public source content:

- Normalize ticker symbols and validate safe symbol format.
- Create run directories and artifact paths.
- Classify equities, ADRs, and ETFs using public datasets where possible.
- Fetch SEC company ticker, fund ticker, submissions, and companyfacts data.
- Fetch known issuer endpoints when URLs or product IDs are known.
- Parse known JSON/CSV structures.
- Extract PDF text when local tooling is available.
- Extract structured BlackRock/iShares fund data when payloads are available.
- Extract SEC XBRL metrics for equities and ADRs where feasible.
- Generate `sources.json`, `run_manifest.json`, and scaffold report JSON.
- Validate JSON shape against schemas.
- Lint obvious citation and issue-count consistency problems.
- Record helper failures, stale data, missing dependencies, and source gaps.

The helper must not write the investment thesis, make valuation judgments, or become the report author.

## Judgment Responsibilities

Codex handles the non-deterministic parts:

- Decide whether the source base is sufficient.
- Search for alternate public sources when helper output is missing key data.
- Decide which sources are primary versus secondary in context.
- Interpret business quality, strategy, risks, valuation, ETF exposures, and portfolio fit.
- Select reasonable peer comparisons when not predetermined.
- Decide whether stale data is still usable and how prominently to caveat it.
- Write the human-readable report.
- Assign confidence where source quality is mixed.
- Validate omissions, unsupported conclusions, internal contradictions, and cherry-picked claims.

## Helper Failure Policy

The skill should use this explicit failure ladder:

```text
helper succeeds -> use structured context
helper partially succeeds -> use reliable helper output, try targeted procedural gap filling, disclose remaining gaps
helper fails -> research procedurally, disclose helper failure
helper gets bloated/flaky -> split, cap outputs, or demote to optional
```

Helper failure is a data gap, not a terminal failure, unless no credible public source can be accessed and no user-provided files exist.

Procedural gap filling must be targeted. It is valid to look for a missing expense ratio, benchmark, latest 10-K, or holdings file. It is not valid to keep searching indefinitely until the report feels complete.

## ETF Source Handling

ETF research should prioritize issuer/sponsor data for operating facts:

- Product page.
- Fact sheet.
- Summary prospectus and prospectus.
- SAI when needed.
- Holdings file or holdings API.
- Index methodology.
- Annual and semiannual reports when available.

For BlackRock/iShares, product ID and ticker mapping should be first-class. The helper should support bundled examples and user-provided mappings.

When a BlackRock/iShares product payload is available, `prepare-research-context` must promote high-value fields into `research_context.json`, including:

- Fund identity and benchmark.
- Key fund facts.
- Fee table and expense ratio.
- NAV, market price, AUM, shares outstanding, or related market/fund data when present.
- Performance tables with dates and caveats.
- Holdings summary.
- Sector, country, asset-class, and other exposure breakdowns.
- Source URLs, source dates, accessed dates, and confidence.

Raw issuer payloads should remain in `source_bundle/`, but the working context should contain the material facts needed to write the report. If raw issuer payloads contain useful structured data but `research_context.json` is sparse, the workflow should stop and enrich context before report writing.

## SEC And EDGAR Handling

Equity and ADR research should use SEC filings and companyfacts where available. The helper should prefer a configured `SEC_USER_AGENT` for SEC requests. If absent, it should warn and continue where permitted.

ETF EDGAR discovery should be treated carefully. SEC fund ticker and fund-series mappings can be useful, but issuer data should remain the primary source for ETF operating facts unless EDGAR filings are clearly identified. The skill should not overstate confidence in ETF classification or filing coverage when EDGAR mappings are thin.

## Producer Workflow

Given a symbol:

1. Normalize the symbol and create the run directory.
2. Run helper preflight and classification if available.
3. Build a source bundle from public sources and any user-supplied URLs/files.
4. Prepare `research_context.json` and `research_context.md`.
5. Inspect context quality before writing.
6. If material fields are missing, perform targeted procedural gap filling.
7. Write `<SYMBOL>-research.md` and `<SYMBOL>-research.json`.
8. Run schema and citation lint checks where available.
9. Record remaining gaps and helper failures in `run_manifest.json`.
10. Tell the user where the artifacts are and recommend fresh-context validation.

## Output Contract

For symbol `AAPL`, the producer should write:

```text
market-research-runs/AAPL/
  AAPL-research.md
  AAPL-research.json
  research_context.json
  research_context.md
  sources.json
  run_manifest.json
  source_bundle/
```

The markdown report should separate facts from interpretation in major sections. The JSON sidecar should preserve machine-readable material claims, citations, confidence, source dates, accessed dates, and unresolved data gaps.

Every material quantitative claim must be cited or marked `Data not available` / `unverified`.

## Validation Workflow

The validation skill takes a run directory and validates the frozen artifacts. It must not depend on the producer conversation.

The validator should:

1. Discover the report markdown, report JSON, manifest, source context, and source bundle.
2. Run deterministic schema and structure checks.
3. Inspect cited sources and source context.
4. Identify unsupported claims, stale data, omitted risks, weak thesis support, contradictions, and missing citations.
5. Classify issues as `critical`, `moderate`, or `minor`.
6. Mark unavailable public-data gaps as `unresolved_data_unavailable`.
7. Write `<SYMBOL>-validation.md` and `<SYMBOL>-validation.json`.
8. Return artifact paths and blocking issue counts.

The validator never edits the original report. A later producer pass applies fixes.

## Multi-Agent Strategy

The preferred validation loop is manual and context-separated:

1. Run `market-research` in one Codex context.
2. Start a fresh Codex context and invoke `validate-market-research` on the run directory.
3. Return to a producer context to fix blocking issues.
4. Repeat until no open fixable critical/moderate issues remain or an iteration cap is reached.

Optional sub-agents can be used in environments that support them, but they must be reviewers only. Their failure must not block completion, and parent-owned files remain the source of truth.

## Paid-Service Exploration

The report and validation artifacts may record which unavailable data would have improved quality, such as point-in-time fundamentals, consensus estimates, institutional ownership, analyst history, or deeper ETF flow/liquidity data.

These notes are exploratory. The skill should not recommend purchasing a service from a single run. If a ledger is later added, provider suggestions should remain directional until there are enough completed runs to reveal recurring gaps.

## Testing And Verification

Implementation should include focused tests for:

- Symbol normalization and path safety.
- Graceful helper failure handling.
- Sparse context detection.
- BlackRock/iShares payload extraction into research context.
- SEC user-agent warning behavior.
- Schema validation success and failure cases.
- Validation issue count consistency.

Forward tests should include at least:

- One large-cap equity, such as `AAPL`.
- One broad ETF, such as `VTI` or `SPY`.
- One issuer-specific ETF with known BlackRock/iShares product data, such as `ECH`.

## Implementation Defaults

- Start with simplified Codex-native schemas rather than copying the existing `cool-financial-research` schemas wholesale. Preserve useful concepts such as material claims, citations, confidence, data gaps, and validation issues.
- Use `./market-research-runs/` as the default output root.
- Keep PDF rendering out of the initial implementation. The markdown and JSON artifacts are required; PDF can be added later as an optional helper.

## Acceptance Criteria

- A user can invoke the producer skill with an equity or ETF symbol and receive cited markdown and JSON artifacts.
- The producer skill still produces useful research when helpers partially fail.
- BlackRock/iShares ETF data that is present in raw API payloads is promoted into the compact research context.
- The validation skill can be invoked manually in a fresh context and produce independent validation artifacts.
- Helper failures, sparse source data, and unavailable public data are disclosed instead of hidden.
- No paid subscription is required.
- No OpenClaw-specific sub-agent runtime is required.
