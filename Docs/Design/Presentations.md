# Presentations / Slides Module Design

## Summary
- Implement a per-user Slides database and API surface for CRUD, generation, and export.
- Reveal.js ZIP is the primary export format; Markdown (Marp) and JSON are supported.
- Generation uses existing LLM adapters and per-user data sources (chat, notes, RAG, media).

## Storage
- Per-user database: `Databases/user_databases/{user_id}/Slides.db`.
- Tables: `presentations`, `presentations_fts`, `sync_log`.
- `slides` stores JSON array of slide objects; `slides_text` is app-maintained for FTS.

## API
- CRUD routes under `/api/v1/slides/presentations`.
- Generation routes under `/api/v1/slides/generate`.
- Export route under `/api/v1/slides/presentations/{id}/export`.
- ETag/If-Match required for mutating operations.

## Export
- Reveal.js assets are bundled locally and copied into a ZIP along with `index.html`.
- Assets path resolution:
  - Env override: `SLIDES_REVEALJS_ASSETS_DIR` (absolute or repo-relative).
  - Default: `tldw_Server_API/app/core/Slides/revealjs`.
- Bundled assets are a lightweight Reveal.js-compatible set; point `SLIDES_REVEALJS_ASSETS_DIR` to an official Reveal.js dist for full features.
- If assets are missing, export returns a clear error (`slides_assets_missing`).
- Markdown export uses Marp-compatible syntax with a Reveal-to-Marp theme mapping or a stored `marp_theme` override.

## Sanitization
- Markdown is converted to HTML via `markdown` and sanitized with `bleach`.
- Allowed tags/attrs are limited to a safe allowlist; raw HTML is stripped.
- Speaker notes are escaped as plain text.
- Custom CSS is sanitized using `bleach` CSS sanitizer and rejects `@import` and `url()`.

## Generation
- Sources: prompt, chat conversation, RAG results, media transcript, notes.
- Source limits:
  - Enforce `max_source_tokens` or `max_source_chars`.
  - If chunking is disabled and limits are exceeded, return 413.
  - If chunking is enabled, split by token estimate and optionally summarize chunks.
- LLM prompt requests JSON output matching the Slide schema.

## Testing
- Unit tests for Slides DB CRUD, FTS, export renderers, sanitization, and generation parsing.
- Integration tests for CRUD, export headers/body, and generation with mocked LLM.
