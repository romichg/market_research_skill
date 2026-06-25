# Report Language And ETF Holdings Design

## Goal

Improve final market-research reports in two investor-facing ways:

- Remove internal workflow language from the main narrative.
- Add useful company-level context to ETF reports without turning ETF research into separate full reports for each holding.

## Main-Report Language Boundary

The final Markdown report should read like an investor memo. Main sections should not use implementation vocabulary such as `deterministic`, `bundle`, `artifact`, `normalized`, `raw`, `runtime`, `cache`, `provider`, `source_manifest`, local paths, or file names.

Preferred main-report phrasing:

- `latest available close` instead of `deterministic close`
- `calculated price signals` instead of `deterministic technical signals`
- `available market data` instead of `provider data`
- `source evidence set` only in `Sources And Evidence`, not in thesis sections
- `source limitation` or `unavailable field` instead of `provider gap`

Allowed locations for internal vocabulary:

- JSON sidecars
- validation artifacts
- helper logs
- implementation plans
- `Sources And Evidence`, when the purpose is auditability
- `Data Issues And Discrepancies`, only when mechanics directly affect confidence or interpretation

The report language lint should check the main body and allow evidence/provenance sections. The lint should be stricter for sections before `Data Issues And Discrepancies`.

## ETF Portfolio Companies Snapshot

ETF reports should include a `Portfolio Companies Snapshot` section when holdings are available.

Selection rule:

- If the ETF has 25 or fewer holdings, cover all holdings.
- If the ETF has more than 25 holdings, cover the top 25 by portfolio weight.

The section should be compact and decision-useful. Each row should include:

- Holding name and ticker when available
- Portfolio weight
- Sector or industry
- What the company does in one sentence
- Quick outlook
- Quick price or technical context when reliable public price data is available

The table should be followed by a short synthesis paragraph explaining what the covered companies imply for ETF concentration, cyclicality, upside drivers, risk, and monitoring.

This is not a requirement to produce full single-company research for each holding. If company-level facts or price data are unavailable from public/free sources in the run, state the limitation in investor terms and avoid filling gaps with guesswork.

## Validation And Tests

Validation should treat missing `Portfolio Companies Snapshot` as a report-quality issue when ETF holdings are available. Severity depends on concentration:

- Moderate when the omitted holdings are necessary to understand a concentrated ETF.
- Minor when broad diversification makes company-level detail less material.

Tests should cover:

- Main-body internal language detection.
- Allowed internal language in source/evidence sections.
- ETF holdings selection rule for 25 or fewer holdings and more than 25 holdings.
- ETF report lint requiring `Portfolio Companies Snapshot` when holdings are present.

## Scope Boundaries

This design does not require a full holdings enrichment engine. The first implementation should update prompts, references, lints, and validation checks. A later helper can automate company descriptions and holding-level technicals if repeated reports show the manual workflow is too slow or inconsistent.
