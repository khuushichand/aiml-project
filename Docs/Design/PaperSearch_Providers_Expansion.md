# Paper Search Providers Expansion

Goal: Add first-class search and ingestion support for IEEE Xplore, ACM Digital Library, Springer Nature, Wiley Online Library, and Elsevier/Scopus while preserving the project’s existing patterns (provider adapters in `core/Third_Party`, typed schemas, FastAPI endpoints under `/api/v1/paper-search/*`, robust error handling, and unit/integration tests).

## Summary

We will implement provider adapters and endpoints for:
- IEEE Xplore (official API)
- ACM Digital Library (via OpenAlex/Crossref constraints; no public ACM DL API)
- Springer Nature (Metadata API)
- Wiley Online Library (via Crossref/OpenAlex constraints)
- Elsevier Scopus (Search, Abstract/Article metadata API)

Where providers do not expose open download links, we will link out to the provider page and attempt Open Access retrieval via Unpaywall (given DOI) when possible. This mirrors current patterns used for PubMed/PMC and Semantic Scholar.

## Design Principles

- Respect terms of service; avoid scraping sites without an API.
- Prefer official APIs where available; otherwise use aggregators (OpenAlex, Crossref) to constrain by venue/publisher.
- Normalize results into a consistent shape similar to `ArxivPaper`/`SemanticScholarPaper` and current `BioRxiv/PubMed` schemas.
- Provide robust error mapping with timeouts, retries, and clear HTTPException codes.
- Keep ingestion flows optional and OA-first via DOI+Unpaywall.

## Endpoints

Each endpoint returns a provider-specific response model (consistent with existing patterns) and supports pagination, filtering, and DOI/ID lookup where applicable.

- IEEE Xplore
  - `GET /api/v1/paper-search/ieee` — params: `q`, `from_year`, `to_year`, `publication_title`, `authors`, `page`, `results_per_page`
  - `GET /api/v1/paper-search/ieee/by-doi` — params: `doi`
  - `GET /api/v1/paper-search/ieee/by-id` — params: `article_number`

- ACM Digital Library (via OpenAlex/Crossref filters)
  - `GET /api/v1/paper-search/acm` — params: `q`, `venue` (defaults to ACM venues), `from_year`, `to_year`, `page`, `results_per_page`
  - `GET /api/v1/paper-search/acm/by-doi` — params: `doi`

- Springer Nature
  - `GET /api/v1/paper-search/springer` — params: `q`, `journal`, `from_year`, `to_year`, `page`, `results_per_page`
  - `GET /api/v1/paper-search/springer/by-doi` — params: `doi`

- Wiley Online Library (via Crossref/OpenAlex filters)
  - `GET /api/v1/paper-search/wiley` — params: `q`, `journal`, `from_year`, `to_year`, `page`, `results_per_page`
  - `GET /api/v1/paper-search/wiley/by-doi` — params: `doi`

- Elsevier/Scopus
  - `GET /api/v1/paper-search/scopus` — params: `q`, `from_year`, `to_year`, `open_access_only`, `page`, `results_per_page`
  - `GET /api/v1/paper-search/scopus/by-doi` — params: `doi`

- Common OA Ingestion
  - `POST /api/v1/paper-search/ingest/by-doi` — params: `doi`, plus existing PDF processing options. Resolves OA link via Unpaywall -> download -> process -> persist.

Notes:
- ACM and Wiley endpoints will internally use OpenAlex and/or Crossref with venue/publisher constraints and return normalized shapes, with links to canonical pages.
- OA ingestion is best-effort; non-OA papers will be linked, not downloaded.

## Schemas

Add provider-specific Pydantic models to `app/api/v1/schemas/paper_search_schemas.py` (consistent with current style):

- `IEEEPapersSearchResponse`, `IEEEPapersPaper`
- `ACMSearchResponse`, `ACMPaper`
- `SpringerSearchResponse`, `SpringerPaper`
- `WileySearchResponse`, `WileyPaper`
- `ScopusSearchResponse`, `ScopusPaper`

Fields (normalized superset):
- `id` or provider key (e.g., `article_number`, `eid`)
- `title`, `authors` (string or list), `venue`/`journal`, `pub_date`, `abstract`
- `doi`, `url`, `pdf_url` (if OA), `open_access` (bool), `provider`

We will continue to keep provider-specific models, but include a helper normalize-to-generic function for downstream RAG usage.

## Core Adapters (Third_Party)

Implement modules under `app/core/Third_Party/`:

- `IEEE_Xplore.py`
  - Config: `IEEE_API_KEY`
  - Functions: `search_ieee(q, offset, limit, filters...)`, `get_ieee_by_doi(doi)`, `get_ieee_by_id(article_number)`
  - Notes: Use official REST API; include retries; respect rate limits.

- `ACM_DL.py`
  - No public API: use `OpenAlex` and `Crossref` clients to constrain by ACM venues/publisher.
  - Functions: `search_acm_via_aggregators(...)`, `get_acm_by_doi(doi)`

- `Springer_Nature.py`
  - Config: `SPRINGER_NATURE_API_KEY`
  - Functions: `search_springer(...)`, `get_springer_by_doi(doi)`

- `Wiley.py`
  - Use `Crossref`/`OpenAlex` constraints to Wiley journals.
  - Functions: `search_wiley_via_aggregators(...)`, `get_wiley_by_doi(doi)`

- `Elsevier_Scopus.py`
  - Config: `ELSEVIER_API_KEY` (header `X-ELS-APIKey`), optional `ELSEVIER_INST_TOKEN`
  - Functions: `search_scopus(...)`, `get_scopus_by_doi(doi)`

- Aggregators & OA
  - `OpenAlex.py`: `search_openalex(...)`, `get_by_doi(...)`
  - `Crossref.py`: `search_crossref(...)`, `get_by_doi(...)`
  - `Unpaywall.py`: `resolve_oa_pdf(doi)`, requires `UNPAYWALL_EMAIL`

All adapters follow existing patterns: `requests.Session` with `HTTPAdapter` + `Retry`, 20–30s timeouts, `(items, total, error_message)` or `(item, error_message)` return signatures.

## Config & Env Vars

- `IEEE_API_KEY`
- `SPRINGER_NATURE_API_KEY`
- `ELSEVIER_API_KEY`
- `ELSEVIER_INST_TOKEN` (optional)
- `UNPAYWALL_EMAIL` (required for Unpaywall)

Optional tuning (via `config.txt` or env): default page sizes, max limits, request timeouts, retry policy.

## Error Handling & Rate Limits

- Map provider errors to HTTP 4xx/5xx with helpful messages.
- Timeout -> 504, provider HTTP errors -> corresponding status if known, else 502.
- Backoff with `Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])`.

## Ingestion Flow (OA-first)

1) Given DOI, try `Unpaywall.resolve_oa_pdf(doi)`.
2) If OA PDF found, download bytes and call existing `process_pdf_task(...)` with chunking/analysis options.
3) Persist via a database instance, for example:
   `db = create_media_database(client_id="paper_search") ; db.add_media_with_keywords(...)` with enriched metadata.
4) If OA not found, return metadata and link-only response.

## Tests

- Unit tests (pure) for parameter building, normalization, and error handling.
- Integration tests using mocks for HTTP responses (no real network): pytest + monkeypatch, `responses` or `httpx` mock.
- Markers: `unit`, `integration`, `external_api` (skipped by default in CI).
- Coverage target: >80% for new modules.

## WebUI

- Extend Paper Search section to include new providers.
- Reuse existing UI forms: query string, filters, pagination; display OA badge and ingest button when OA available.

## Risks & Limitations

- ACM/Wiley lack public APIs: rely on OpenAlex/Crossref. Coverage may vary; PDFs often not OA.
- Elsevier/Scopus key distribution: some endpoints may require institution entitlements.
- Legal/ToS: avoid scraping and respect rate limits.

## Milestones & Estimates (engineering days)

1) Foundations (OpenAlex, Crossref, Unpaywall, common schemas, OA ingest): 2–3d
2) IEEE Xplore adapter + endpoints + tests: 2d
3) Springer Nature adapter + endpoints + tests: 1.5–2d
4) Elsevier/Scopus adapter + endpoints + tests: 3–4d (API nuances)
5) ACM/Wiley via aggregators + endpoints + tests: 2d
6) WebUI updates + docs polish: 1–1.5d

Total: ~11–14 days, assuming keys available and no unexpected API blockers.

## Success Criteria

- Endpoints return paginated results with normalized fields and stable error handling.
- DOI and ID lookups work across providers.
- OA ingestion by DOI works where available.
- Tests passing with >80% coverage for new modules; docs updated.
