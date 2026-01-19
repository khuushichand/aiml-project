# /api/v1/slides (Presentations)

Purpose: create, generate, search, and export slide decks stored per user. Exports support Reveal.js ZIP, Marp-compatible Markdown, and JSON.

## Authentication & Rate Limits
- Auth: API key or JWT (same as other v1 endpoints).
- Rate limits: `rbac_rate_limit("slides.*")` variants per route.
- Mutations require `If-Match` with the latest ETag.

## Data Model (core fields)
- `title` (str, required)
- `description` (str, optional)
- `theme` (Reveal.js theme, default `black`)
- `marp_theme` (optional override for Markdown export; e.g., `default`, `gaia`, `uncover`)
- `settings` (Reveal.js settings allowlist)
- `slides` (array of Slide objects)
- `custom_css` (optional; sanitized)
- `source_type` / `source_ref` / `source_query` (generation provenance)
- `version` (int; used for optimistic locking)

Slide object:
- `order` (int, unique, normalized)
- `layout` (`title|content|two_column|quote|section|blank`)
- `title`, `content`, `speaker_notes`, `metadata`

## CRUD
- `POST /api/v1/slides/presentations`
- `GET /api/v1/slides/presentations`
- `GET /api/v1/slides/presentations/{id}`
- `PUT /api/v1/slides/presentations/{id}`
- `PATCH /api/v1/slides/presentations/{id}`
- `DELETE /api/v1/slides/presentations/{id}` (soft delete)
- `POST /api/v1/slides/presentations/{id}/restore`
- `GET /api/v1/slides/presentations/search?q=...`

### ETag / If-Match
- `GET` returns `ETag: W/"v{version}"` and `Last-Modified`.
- `PUT`, `PATCH`, `DELETE`, `restore` require `If-Match`.
- Missing `If-Match` → 428; mismatch → 412.

## Generation
- `POST /api/v1/slides/generate` (prompt)
- `POST /api/v1/slides/generate/from-chat`
- `POST /api/v1/slides/generate/from-media`
- `POST /api/v1/slides/generate/from-notes`
- `POST /api/v1/slides/generate/from-rag`

Common params:
- `title_hint`, `theme`, `marp_theme`, `settings`, `custom_css`
- `max_source_tokens` / `max_source_chars`
- `enable_chunking`, `chunk_size_tokens`, `summary_tokens`
- `provider`, `model`, `temperature`, `max_tokens`

RAG generation explicitly searches `media_db`, `notes`, and `chats` sources.
Streaming generation is not yet supported; generation endpoints return a full presentation payload.

## Export
- `GET /api/v1/slides/presentations/{id}/export?format=revealjs`
- `GET /api/v1/slides/presentations/{id}/export?format=markdown`
- `GET /api/v1/slides/presentations/{id}/export?format=json`

Notes:
- Reveal.js ZIP bundles assets from `SLIDES_REVEALJS_ASSETS_DIR` or the default bundled assets under `tldw_Server_API/app/core/Slides/revealjs`.
- Markdown export uses `marp_theme` if set; otherwise uses Reveal→Marp mapping.

## Settings Allowlist (Reveal.js)
Allowed keys:
`transition`, `backgroundTransition`, `slideNumber`, `controls`, `progress`, `hash`, `center`,
`width`, `height`, `margin`, `minScale`, `maxScale`, `viewDistance`, `keyboard`, `touch`,
`loop`, `rtl`, `navigationMode`.

## Errors (common)
- 400: invalid query/format/If-Match syntax.
- 404: not found.
- 412: If-Match precondition failed.
- 413: source too large with chunking disabled.
- 422: validation errors (theme/settings/layouts).
- 429: rate limit.

## Metrics
- `slides_generation_latency_seconds{source_type}`
- `slides_generation_errors_total{source_type,error}`
- `slides_export_latency_seconds{format}`
- `slides_export_errors_total{format,error}`
