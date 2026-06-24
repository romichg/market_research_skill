# Market Research Skill Rename And Report Quality Design

Date: 2026-06-21

## Goal

Make the market research skill easier to invoke, clarify supervised batch operation, improve report readability and analytical depth, and strengthen protected-source handling without weakening reproducibility.

## Problems

The current skill names are confusing because four visible skills share the `market-research-full` prefix. The distinction between the parent skill, researcher, verifier, and loop runner is understandable to a maintainer but not obvious to a user trying to run a report.

The README also makes supervised batch operation look like a Python-only workflow. The Python harness is useful for direct operation and debugging, but users should be able to ask the agent to run the supervised batch mode from inside the harness.

Report output currently exposes internal methodology terms such as "frozen sources" to readers. The internal concept is valid: the workflow saves source artifacts and validates against that evidence. The human-facing report should instead use plain language such as "saved source copies," "locally captured source artifacts," or "source evidence used for this report."

The generated DPC report preserved evidence discipline but was too shallow compared with the user's procedural example. The stronger example led with a clear bottom line, explained the business model, demand story, financials, balance sheet, valuation context, positives, worries, and an explicit take. That quality bar should apply to all reports, not only IPO reports.

Protected-source failures are currently too easy to demote into data gaps. If a material source is blocked by bot protection, CAPTCHA, JavaScript challenge, WAF, or similar access control, the workflow should treat headed-browser human assistance as a first-class quality-preserving path rather than a late fallback after relying on stale or weaker substitutes.

## Naming Design

Rename the active skill tree and skill metadata:

- `market-research-full/` becomes `market-research/`.
- `market-research-full` becomes `market-research`.
- `market-research-full-researcher` becomes `market-research-researcher`.
- `market-research-full-verifier` becomes `market-research-verifier`.
- `market-research-full-loop-runner` becomes `market-research-batch-supervisor`.

User-facing invocation should emphasize modes on the primary skill:

```text
$market-research researcher AAPL
$market-research verifier reports/AAPL/YYYY-MM-DD
$market-research batch-supervisor AAPL MSFT
```

The batch supervisor remains backed by the Python loop harness, but the README should present the agent skill invocation first and the Python command as the underlying helper/direct CLI path.

Internal prompts, tests, script paths, documentation, and examples should be updated to the new directory and skill names. Historical generated artifacts do not need to be rewritten unless tests rely on them.

## README Design

The README should explain:

- There is one primary installed skill: `market-research`.
- The researcher mode creates one report bundle.
- The verifier mode validates one report or deterministic bundle in a fresh context.
- The batch-supervisor mode orchestrates research, validation, remediation retries, logs, summaries, and skill issue collection.
- The supervised batch can be started from the agent by asking for `$market-research batch-supervisor SYMBOL ...`.
- The Python harness remains available for direct CLI operation, debugging, dry runs, and custom command templates.

The README should include a migration note from the old `market-research-full` names to the new names.

## Report Language Design

The final human-facing Markdown report should avoid internal workflow jargon unless the methodology itself is being explained. In particular:

- Prefer "saved source copies," "locally captured source artifacts," or "source evidence used for this report."
- Avoid "frozen sources" and "frozen artifacts" in investor-facing prose.
- Keep "frozen" terminology only in internal verifier/developer instructions where it denotes immutable evidence used for validation.

The `Source Base And Data Quality` section should describe what was saved, which sources are primary versus secondary, source dates, access dates, confidence, and material limitations in plain reader-facing language.

## Global Report Quality Design

The report template should define a stronger baseline for every equity, ADR, and ETF report:

- Lead with a clear investment-research conclusion or bottom line, not an artifact inventory.
- Explain what the company or fund does in practical business terms.
- Discuss the business model, demand drivers, financial quality, balance sheet or fund structure, valuation or performance context, catalysts, and risks when applicable and supported by sources.
- Separate facts from interpretation, but write the interpretation in a form useful to an investor.
- Include analytical sections such as "What Looks Attractive," "What Worries Me," and "My Take" or equivalent sections when they improve readability.
- Avoid mechanically filling a technical-analysis section when the security lacks trading history. Substitute the most relevant lifecycle context instead, such as IPO terms, implied valuation, listing timeline, post-listing monitoring items, or explicit absence of market history.
- For ETFs, adapt the same quality bar to fund objective, index methodology, holdings, exposures, fees, liquidity, tracking/performance context, distribution profile, portfolio role, risks, and monitoring triggers.

The DPC procedural example should inform the template's tone and depth, but the template should remain general enough for non-IPO operating companies, ADRs, ETFs, and thin-data situations.

## Protected-Source Access Design

Protected-source handling should apply to any source, not only SEC.

When a material source is blocked by bot protection, CAPTCHA, WAF, JavaScript challenge, suspicious automated-access response, or similar access control, the workflow should:

1. Classify it as a protected-source access issue.
2. Decide whether the source is material to report quality.
3. If material, move promptly to headed-browser human assistance unless an alternative source is clearly equivalent or better quality, current, and authoritative enough for the claim.
4. Ask the human to solve the challenge in the headed browser when required.
5. Continue capture after access is restored and save the source artifact through the normal source registry path.
6. If access cannot be completed, record a workflow extraction/access gap and explain the analytical limitation.

Lower-quality or stale substitutes should not be used merely to avoid headed-browser escalation. Alternatives are acceptable only when they preserve or improve evidence quality.

## Testing Design

Update tests for:

- New directory names.
- New skill metadata names.
- New prompt strings using `$market-research`.
- New batch supervisor wording.
- README references to the renamed paths.

Run the full test suite:

```bash
python3 -m pytest tests
```

## Out Of Scope

Do not rewrite historical generated reports unless a test or documentation example requires it. Do not add new paid data-provider requirements. Do not implement a full browser automation framework unless existing agent/browser tooling makes that practical in the implementation pass; the key requirement is to document and prompt for headed-browser human assistance as a first-class workflow path.
