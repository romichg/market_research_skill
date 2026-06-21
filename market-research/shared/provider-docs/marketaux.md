# MarketAux Endpoint Audit

Official docs checked:
- https://www.marketaux.com/documentation
- https://www.marketaux.com/pricing

Free/configured endpoints to attempt:
- news: `/v1/news/all`; unique news, entities, sentiment, relevance, source, tags, and published date fields; normalized target is `news`.

Plan-gated or fallback endpoints:
- market stats endpoints: not default on the free plan because entity-stat limits vary by plan; record provider status if attempted explicitly.

Duplicate endpoints intentionally skipped:
- none; MarketAux is the default dedicated news/sentiment source when configured.
