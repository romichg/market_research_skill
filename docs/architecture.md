# Market Research Architecture

The active skill tree lives under `market-research/` and follows the Agent Skills directory contract: Markdown `SKILL.md` instructions, optional `references/`, executable `scripts/`, schemas, and agent config files.

## Skill Modes

- `market-research/researcher/`: produces a single-symbol research bundle for US-listed equities, ADRs, and ETFs.
- `market-research/verifier/`: validates frozen report artifacts and evidence without editing producer output.
- `market-research/batch-supervisor/`: orchestrates fresh researcher, verifier, remediation, and self-improvement prompt sessions.
- `market-research/shared/`: shared scripts, schemas, provider docs, and agent config.

The top-level `market-research/SKILL.md` routes users to the mode-specific skill files. Keep mode-specific guidance in the smallest relevant file or reference so agents do not load unnecessary policy.

## Artifact Roots

- `data/SYMBOL/YYYY-MM-DD/`: deterministic evidence, raw provider cache copies, normalized values, manifests, gaps, and deterministic-data-usage requirements.
- `reports/SYMBOL/YYYY-MM-DD/`: polished research Markdown, JSON sidecar, best-effort PDF, validation scaffold, completed validation, and validator issue files.
- `runtime/SYMBOL/YYYY-MM-DD/`: procedural source workspaces, prompts, logs, run manifests, notes, source bundles, remediation notes, and transient working files.

Generated `data/`, `reports/`, and `runtime/` outputs are not committed.

## Evidence Roles

Deterministic helper output is evidence, not authority. Researchers should use it aggressively, but final reports must synthesize material facts into an investor-readable memo. Procedural source bundles fill targeted gaps and preserve source dates, URLs, local artifact metadata, and confidence notes.

Validators inspect frozen artifacts, cited sources, deterministic bundles, source registries, schemas, and report claims. They do not create competing investment theses or rewrite producer reports.

## Historical Material

Historical plans and generated self-improvement artifacts live under `OLD/docs-archive/`. They can explain why a decision was made, but active docs and skill files define current behavior.
