# Optional local provider exports

Do not store API keys here. If you license a retail or professional data service, export CSV/JSON/PDF files locally and place them under:

```text
provider-data/<SYMBOL>/
  prices.csv
  estimates.csv
  analyst_ratings.csv
  short_interest.csv
  options_flow.csv
  etf_holdings.csv
  etf_factsheet.pdf
  index_methodology.pdf
```

The OpenClaw orchestrator may pass these files to sub-agents as local context. The agents must cite the file name, upstream provider, provider publication date when available, and access/import date. Licensed data should be marked `primary_or_secondary: "paid_licensed"` unless it is a copy of an official filing/fact sheet.
