# Deterministic Usage And Self-Improvement Lessons

Date: 2026-06-22

## Lessons

- Keep self-improvement prompt-only and operator-triggered. Do not launch surprise subprocesses after a successful research loop.
- Use `research_loop.py self-improve RUN_ROOT [RUN_ROOT ...]` to create a central review prompt when enough completed runs exist to justify a skill-improvement pass.
- Treat `deterministic_data_usage.json` as the researcher-stage contract for usable deterministic data. Required and review datapoints should be used or explicitly dispositioned in the final report JSON.
- Treat the validator's heuristic referenced/not-referenced audit as secondary. The explicit field-level disposition contract is the stronger enforcement path.
- Missing required deterministic usage dispositions should remain blocking validation issues until the report uses the datapoint or explains why it is not usable or material.
- Watch for boilerplate dispositions added only to satisfy lint. Future verifier work should assess disposition quality, not just existence.
- Future data-usage classifier improvements should consider asset type and lifecycle stage, especially ETFs, pending IPOs, SPACs, and sparse/no-trading-history symbols.
- Self-improvement prompts should judge the finished investor experience before artifact ergonomics. Ask whether the thesis, valuation context, catalysts, risks, data limits, and monitoring triggers are decision-useful to an experienced investor.
- Preserve artifact roles in recommendations: `reports/` is for polished final deliverables, `runtime/` is for prompts/logs/intermediate notes, and `data/` is for deterministic evidence. Moving runtime evidence into reports is not a default quality improvement.
- Treat freshness as a data-field policy rather than a cache disclosure policy. Recommend fresh/latest-available collection for time-sensitive fields, durable cached/source-dated reuse for filed historical evidence, and main-report disclosure only when missing/stale data is material.

## Follow-Up Ideas

- Add verifier guidance or deterministic checks for weak usage-disposition rationales.
- Refine required/review/context materiality rules with examples from real research runs.
- Use self-improvement prompts to compare multiple batch roots and identify recurring missing-data or omitted-risk patterns before changing the skill.
- Include an explicit "investor with 15 years of experience" critique in future self-improvement reviews, focusing on usefulness, actionability, and signal-to-noise rather than internal trace completeness.
