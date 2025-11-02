# Paper Search Endpoints (Design)

This document outlines provider-specific paper search endpoints under `/api/v1/paper-search`.

## Overview

- Each endpoint handles exactly one provider (arXiv, BioRxiv/MedRxiv, Semantic Scholar).
- Uniform response envelope for pagination and totals; provider-specific `items` shape.
- Built on small provider adapters with retries, timeouts, and conservative parsing.

## Endpoints

- GET `/api/v1/paper-search/arxiv`
  - Params: `query`, `author`, `year`, `page` (>=1), `results_per_page` (1..100)
  - Response: `{ query_echo, items: ArxivPaper[], total_results, page, results_per_page, total_pages }`
\n+- GET `/api/v1/paper-search/arxiv/by-id`
  - Params: `id` (arXiv ID, e.g., `1706.03762`)
  - Response: `ArxivPaper`
  - Uses export API `id_list` under the hood and normalizes to our schema.

- GET `/api/v1/paper-search/biorxiv`
  - Params: `q`, `server` (biorxiv|medrxiv), `from_date` (YYYY-MM-DD), `to_date` (YYYY-MM-DD), `category`, `page`, `results_per_page`
  - Response: `{ query_echo, items: BioRxivPaper[], total_results, page, results_per_page, total_pages }`
  - Notes: The public API exposes date-window listing via `/details/{server}/{from}/{to}/{cursor}`; keyword and category filters are applied client-side over fetched batches (page fill guaranteed, but filtered totals are best-effort).
  - Optional intervals: `recent_days` (maps to `Nd`), `recent_count` (maps to `N`) via `/details/{server}/{interval}/{cursor}`.
  - Category query param is passed when provided and also enforced client-side for consistency.

- GET `/api/v1/paper-search/biorxiv/by-doi`
  - Params: `server` (biorxiv|medrxiv), `doi`
  - Response: `BioRxivPaper`
  - Uses `/details/{server}/{DOI}/na`.

- GET `/api/v1/paper-search/semantic-scholar`
  - Params: `query`, `fields_of_study`, `publication_types`, `year_range`, `venue`, `min_citations`, `page`, `results_per_page`
  - Response: `{ query_echo, items: SemanticScholarPaper[], total_results, offset, limit, next_offset, page, total_pages }`

- GET `/api/v1/paper-search/pubmed`
  - Params: `q` (query), `from_year`, `to_year`, `free_full_text` (bool), `page`, `results_per_page`
  - Response: `{ query_echo, items: PubMedPaper[], total_results, page, results_per_page, total_pages }`
  - Notes: Uses E-utilities (ESearch + ESummary); abstracts are not included for performance. PMC links and PDF URLs are provided when available.

### PMC Harvesting

- GET `/api/v1/paper-search/pmc-oai/identify`
  - Response: `{ info }` - OAI-PMH Identify details

- GET `/api/v1/paper-search/pmc-oai/list-sets`
  - Params: `resumptionToken`
  - Response: `{ query_echo, items: { setSpec, setName }[], resumption_token }`

- GET `/api/v1/paper-search/pmc-oai/list-identifiers`
  - Params: `metadataPrefix` (default `oai_dc`), `from`, `until`, `set`, `resumptionToken`
  - Response: `{ query_echo, items: PMCOAIHeader[], resumption_token }`

- GET `/api/v1/paper-search/pmc-oai/list-records`
  - Params: `metadataPrefix` (default `oai_dc`), `from`, `until`, `set`, `resumptionToken`
  - Response: `{ query_echo, items: PMCOAIRecord[], resumption_token }`

- GET `/api/v1/paper-search/pmc-oai/get-record`
  - Params: `identifier`, `metadataPrefix` (default `oai_dc`)
  - Response: `PMCOAIRecord`

### PMC OA Web Service

- GET `/api/v1/paper-search/pmc-oa/identify`
  - Response: `{ info }` - OA repository info and latest update

- GET `/api/v1/paper-search/pmc-oa/query`
  - Params: `from`, `until`, `format` (`pdf|tgz`), `resumptionToken`, `id`, `pdf_only` (bool), `license_contains` (str)
  - Response: `{ query_echo, items: PMCOARecord[], resumption_token }`
  - Notes: `pdf_only` returns only records with a PDF link; `license_contains` performs a case-insensitive substring filter over the `license` field.

- GET `/api/v1/paper-search/pmc-oa/fetch-pdf`
  - Params: `pmcid` (e.g., `PMC1234567`)
  - Response: PDF bytes (attachment); useful for integration with `/api/v1/media/process-pdfs`

- POST `/api/v1/paper-search/pmc-oa/ingest-pdf`
  - Params: `pmcid` (required), optional `title`, `author`, `keywords` (comma-separated), `perform_chunking` (bool), `parser` (default `pymupdf4llm`)
  - Behavior: Downloads the PMC PDF, runs the standard PDF processing pipeline, and persists content to the user's Media DB via `add_media_with_keywords`.
  - Response: `{ pmcid, filename, status, result, db_id, media_uuid, db_message }`
  - Advanced processing options:
    - OCR: `enable_ocr` (bool), `ocr_backend` (e.g., `tesseract`), `ocr_lang` (e.g., `eng`), `ocr_dpi`, `ocr_mode`, `ocr_min_page_text_chars`
    - Chunking: `chunk_method` (e.g., `sentences`, `semantic`), `chunk_size`, `chunk_overlap`
    - Analysis: `perform_analysis` (bool), `summarize_recursively` (bool), `api_name`, `custom_prompt`, `system_prompt`
    - Metadata: `enrich_metadata` (bool; defaults true) - fetches `oai_dc` from PMC OAI-PMH to enrich `title/author/ids/license`, embeds the JSON in analysis content, and stores a safe JSON payload in `DocumentVersions.safe_metadata`

## Provider Adapters

- `core/Third_Party/Arxiv.py` (existing)
  - `search_arxiv_custom_api(query, author, year, start_index, page_size)` -> `(papers, total, err)`

- `core/Third_Party/BioRxiv.py` (new)
  - `search_biorxiv(q, server, from_date, to_date, category, offset, limit)` -> `(items, total, err)`
  - Uses `/search/{server}/{q}/{from}/{to}/{cursor}` when `q` present, else `/details/{server}/{from}/{to}/{cursor}[/{category}]`.
  - Batches in steps of 100; slices and optionally fetches the next batch once to fill the page.

- `core/Third_Party/Semantic_Scholar.py` (existing)
  - `search_papers_semantic_scholar(...)` -> `({json}, err)`

## Error Handling

- Provider timeouts -> HTTP 504
- Provider HTTP/5xx/4xx -> HTTP 502 (best-effort mapping)
- Unexpected internal -> HTTP 500

## Notes

- Tests mock provider functions; no external network in CI.
- Rate limiting via SlowAPI can be added per-route if needed; test mode bypass respected.
- GET `/api/v1/paper-search/semantic-scholar/by-id`
  - Params: `paper_id` (Semantic Scholar paperId)
  - Response: `SemanticScholarPaper`
  - Uses `graph/v1/paper/{paperId}`; removes `openAccessPdf` if null for validation.
Published metadata (bioRxiv/medRxiv)

- GET `/api/v1/paper-search/biorxiv-pubs`
  - Params: `server`, `from_date`/`to_date` or `recent_days`/`recent_count`, optional `q` (client-side filter), `include_abstracts` (default true), `page`, `results_per_page`
  - Response: `{ query_echo, items: BioRxivPublishedRecord[], total_results, page, results_per_page, total_pages }`
  - Uses `/pubs/{server}/{interval}/{cursor}`; 100 items per page from source.

- GET `/api/v1/paper-search/biorxiv-pubs/by-doi`
  - Params: `server`, `doi`, `include_abstracts` (default true)
  - Response: `BioRxivPublishedRecord`
  - Uses `/pubs/{server}/{DOI}/na`.
