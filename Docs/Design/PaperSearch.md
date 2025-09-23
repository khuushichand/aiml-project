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

- GET `/api/v1/paper-search/biorxiv`
  - Params: `q`, `server` (biorxiv|medrxiv), `from_date` (YYYY-MM-DD), `to_date` (YYYY-MM-DD), `category`, `page`, `results_per_page`
  - Response: `{ query_echo, items: BioRxivPaper[], total_results, page, results_per_page, total_pages }`
  - Notes: The public API exposes date-window listing via `/details/{server}/{from}/{to}/{cursor}`; keyword and category filters are applied client-side over fetched batches (page fill guaranteed, but filtered totals are best-effort).

- GET `/api/v1/paper-search/semantic-scholar`
  - Params: `query`, `fields_of_study`, `publication_types`, `year_range`, `venue`, `min_citations`, `page`, `results_per_page`
  - Response: `{ query_echo, items: SemanticScholarPaper[], total_results, offset, limit, next_offset, page, total_pages }`

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
