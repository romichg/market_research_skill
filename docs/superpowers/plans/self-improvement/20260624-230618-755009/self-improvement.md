$superpowers

Run a self-improvement review for completed market-research batches in this Codex session.

Goal: analyze the listed runs, their reports, validation artifacts, skill issue notes, prior plans/specs, and recent code changes. Write improvement ideas and an implementation plan. Do not edit production skill files in this pass.

Inputs to inspect:
- Run root: `runtime/market-research-batch-20260624`
  - Summary: `runtime/market-research-batch-20260624/research-loop-summary.json`
  - Loop notes: `runtime/market-research-batch-20260624/loop-skill-issues.md`
  - Operator notes: `runtime/market-research-batch-20260624/operator-notes.md`
- Run root: `runtime/market-research-batch-20260625`
  - Summary: `runtime/market-research-batch-20260625/research-loop-summary.json`
  - Loop notes: `runtime/market-research-batch-20260625/loop-skill-issues.md`
  - Operator notes: `runtime/market-research-batch-20260625/operator-notes.md`
- Existing plans/specs: `docs/superpowers/plans`, `docs/`, `AGENTS.md`, and `README.md`
- Recent repository changes: `git status --short` and relevant `git diff`/`git log` output

Review questions:
- Did the researcher use all useful deterministic data, especially fields marked required or review in `deterministic_data_usage.json`?
- Did reports omit material investor-relevant facts, risks, source limits, or data gaps?
- Evaluate investor-grade reporting/memo quality. Does the report read like an investor memo rather than a deterministic-data recital or citation-heavy audit trail?
- Evaluate the `Bottom Line` as an executive summary: it should introduce the company/security, what it does, market value or valuation range, core upside, main risks, and monitoring questions before judging valuation.
- Check whether routine data-vendor names, provider mechanics, local paths, deterministic artifacts, manifests, raw/normalized paths, or cache details leaked into the main investment narrative. The main body should state the data, range, conflict, and investment implication; vendor attribution belongs in `Data Issues And Discrepancies`, `Sources And Evidence`, sidecars, or validation artifacts.
- Check whether `Key Facts` is an at-a-glance table or similarly consumable snapshot without internal provenance references.
- Evaluate `Business Profile` and business-model depth. The report should explain the product, technology, customers, who pays, revenue model, acquisition contribution, and demand drivers in plain language; require targeted procedural research when deterministic data leaves these unclear.
- Evaluate `Market Snapshot And Technical Analysis`: market data should be presented as a snapshot plus actual analysis, including trend, moving averages, volume, volatility, drawdown, support/resistance, and technical interpretation when price history exists.
- Confirm financials and valuation are organized for investor consumption with tables or concise snapshots plus analysis, not citation-heavy paragraphs or provider-conflict narration.
- Confirm company/security risks stay in `Risks And Invalidation Points`; research/data-quality issues should be moved to `Data Issues And Discrepancies` near the bottom.
- Did deterministic coverage support synthesis and judgment, or did it crowd out thesis, materiality, variant view, risks, and monitoring triggers?
- Preserve `reports/` as final product and `runtime/` as intermediate work product. Do not recommend bundling runtime artifacts into reports unless the final investor deliverable itself needs a specific appendix or reference artifact.
- Evaluate field-level freshness: which fields required a fresh/latest-available query, which durable filed/source-dated evidence could be reused, and whether missing or stale data changed investor interpretation.
- Do not recommend main-body cache mechanics disclosure unless stale or unavailable data changes investor interpretation. Cache/provider mechanics belong in references, appendices, sidecars, or validation artifacts.
- Did validator/remediation behavior surface the right problems with enough specificity?
- Which recurring failures should become deterministic checks, prompt requirements, helper scripts, or tests?

Write outputs under:
- `docs/superpowers/plans/self-improvement/20260624-230618-755009/self-improvement-ideas.md`
- `docs/superpowers/plans/self-improvement/20260624-230618-755009/self-improvement-plan.md`
- `docs/superpowers/plans/self-improvement/20260624-230618-755009/self-improvement.json`

The plan should use superpowers planning style: concrete phases, files to change, tests to add, verification commands, and explicit risks. Keep recommendations evidence-based and cite local artifact paths.
