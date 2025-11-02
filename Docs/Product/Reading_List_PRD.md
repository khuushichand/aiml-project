# PRD: Reading List (Pocket/Instapaper-style) for tldw_server

Version: 0.1

Owner: Core Maintainers (Server/API + WebUI)

Status: Draft for Review

Last Updated: 2025-10-18

Related: Project_Guidelines.md, AGENTS.md, tldw_Server_API/app/main.py

---

## 1. Summary

Introduce a first-class, privacy-preserving Reading List feature (akin to Pocket/Instapaper) that lets users save links, extract clean article content, tag and organize items, highlight and annotate text, listen with TTS, summarize, and search across their saved content. Items become part of the unified knowledge substrate (FTS5 + embeddings) so users can retrieve, chat about, and evaluate content via existing RAG and Chat capabilities.

This PRD focuses on a pragmatic MVP with a clear path to a richer experience and extension support.

## 2. Goals and Non-Goals

### Goals (MVP)
- Save URLs to a personal Reading List (API + WebUI action).
- Fetch and extract readable text with metadata (title, author, publish date, domain).
- Sanitize/normalize HTML and store canonical text; compute reading time and word count.
- Dedupe by canonical URL and content hash; track saves and sources.
- Tagging, favorites, status (saved/reading/read/archived), mark as read.
- Full-text search (FTS5) across title and content; filter by tags/status.
- Background embedding to ChromaDB for RAG; items are retrievable via unified search.
- Summarize and TTS via existing endpoints (wire-up and convenience actions).
- Basic WebUI list and detail views (read mode: clean reader, highlights, notes).
- Import from Pocket/Instapaper exports (JSON/CSV) as background jobs.

### Stretch Goals (post-MVP)
- Daily/weekly reading digest with smart suggestions.
- Archive snapshot (PDF, WARC, or sanitized HTML bundle) with storage budget.
- Browser extension + bookmarklet; mobile “share to API” instructions.
- Reading progress (percent scrolled), per-item telemetry stored locally only.

### Non-Goals (now)
- Social features, public sharing, or collaborative reading.
- Paywall bypass or authenticated scraping.
- Full offline sync across devices (beyond local storage/export).

## 3. Users and Value

- Solo researchers and learners: Capture web sources into a private, searchable library.
- Power readers: Tag, queue, and later read in a distraction-free UI; listen while commuting.
- Developers and analysts: Use RAG and Chat to query across saved articles, generate summaries, and cite sources.

Primary value: unify capture → read → annotate → retrieve → converse workflows in one trusted, local-first server.

## 4. User Stories (P0/P1)

P0 (MVP)
- As a user, I can save a URL and see it appear in my Reading List within seconds.
- As a user, I can open a clean “reader view” of saved items without ads or clutter.
- As a user, I can tag items, favorite them, and mark them read/archived.
- As a user, I can search my saved items by keywords and filter by tags/status.
- As a user, I can get a one-click summary and a “listen” action for an item.
- As a user, I can import my Pocket/Instapaper exports.

P1 (post-MVP)
- As a user, I receive a daily digest and suggestions based on interests and recency.
- As a user, I can highlight passages and add inline notes that show up in search.
- As a user, I can export my library with notes/highlights.

## 5. Functional Requirements

### 5.1 Capture & Ingestion
- Accepts `url` plus optional `title`, `tags`, and `notes`.
- Fetch with safe defaults: timeouts, max download size, content-type checks.
- Extract main content using a readability-style parser; store both sanitized HTML and plain text.
- Compute canonical URL, domain, content hash (e.g., SHA256), word count, reading time, language.
- Dedupe by canonical URL and/or content hash; merge metadata (e.g., tags) when duplicates found.
- Queue embeddings generation and optional summary creation as background tasks.

### 5.2 Library & Organization
- Item fields: status (saved/reading/read/archived), favorite (bool), tags (many-to-many), created_at, updated_at, read_at.
- Tag normalization (lowercase, de-dupe, trim). Suggest historical tags.
- Optional highlights (exact quote, start/end offsets in text, color, note, created_at).
- Optional per-item notes (rich text or markdown; stored safely and indexed for search).

### 5.3 Retrieval & Search
- FTS5 index on title, author, domain, and normalized text content.
- Filters: tags, status, favorite, date range, domain.
- Sort: newest saved, oldest saved, longest, shortest, A-Z by title.
- Vector embeddings per item using configured Embeddings provider; stored in ChromaDB with namespace per user.
- Expose items to existing RAG endpoints (opt-in and per-user namespace isolation).

### 5.4 Actions & Integrations
- Summarize: route to Chat/Completions with a standard prompt template and cite source.
- Listen: route to existing TTS endpoint; return audio stream or file ref.
- Export/Import: JSON line format with schema version; Pocket/Instapaper import mappers.

## 6. Non-Functional Requirements

- Privacy: Local-first; never send content externally unless configured by the user.
- Performance: P50 ingest < 3s for typical articles (text only); extraction < 1.5s.
- Robustness: Graceful fallbacks when extraction fails; surface diagnostics.
- Security: Strict input validation, domain parsing, size limits; sanitize HTML; no script execution.
- Rate limiting: Apply existing rate-limit strategy per user/key on capture and batch imports.

## 7. Architecture and Components

Directory and module plan aligning with current repository:

- API Endpoints: `tldw_Server_API/app/api/v1/endpoints/reading.py`
- Schemas: `tldw_Server_API/app/api/v1/schemas/reading.py`
- Core Service: `tldw_Server_API/app/core/Reading_List/`
  - `service.py` (orchestrates fetch → extract → store → embed)
  - `extractors/readability.py` (content extraction & sanitization)
  - `dedupe.py` (canonicalization + hashing)
  - `importers/pocket.py`, `importers/instapaper.py`
- DB Abstractions: integrate via `app/core/DB_Management/Media_DB_v2.py` or a dedicated module if cleaner
- Background Services: reuse `services/` for embedding/summarize queues
- WebUI: `tldw_Server_API/WebUI/` under a new `reading/` feature (list + detail + read view)

### 7.1 Data Model (Conceptual)

New tables (SQLite by default); per-user scoping is required.

`reading_items`
- `id` (PK)
- `user_id`
- `url`, `canonical_url`, `domain`
- `title`, `author`, `published_at`
- `clean_html` (sanitized), `text` (plain)
- `content_hash`
- `word_count`, `reading_time_seconds`, `language`
- `status` ENUM: saved|reading|read|archived
- `favorite` BOOL
- `created_at`, `updated_at`, `read_at`

`reading_item_tags`
- `item_id` (FK), `tag`

`reading_item_highlights` (P1)
- `id` (PK), `item_id` (FK), `quote`, `start_offset`, `end_offset`, `color`, `note`, `created_at`

FTS5 virtual table `reading_items_fts`
- columns: `title`, `domain`, `text`, content rowid ↔ `reading_items.id`

Embeddings mapping (ChromaDB)
- Collection/namespace: `reading_list:{user_id}`
- `item_id` → vector_id; metadata: `title`, `url`, `tags`, `status`, timestamps

Note: If reusing Media_DB_v2, add a lightweight `reading_items` table with FK to existing media item when available; otherwise store standalone and link later during ingestion.

### 7.2 Ingestion Flow

1) `POST /api/v1/reading/save`
2) Validate URL, schedule or perform fetch (timeout, size cap, content-type checks)
3) Extract with readability parser; sanitize HTML, derive plain text
4) Compute canonical URL + content hash; dedupe/merge metadata
5) Persist item; update FTS5; enqueue embedding job; optionally enqueue summary
6) Return item payload with `status: processing|ready`

Failure modes: unreachable URL, non-HTML content, oversized content, extraction failure → store minimal record with error details; allow retry.

## 8. API Design (OpenAPI-style)

Base: `/api/v1/reading`

`POST /save`
- Body: `{ url: string, title?: string, tags?: string[], notes?: string }`
- Returns: `{ id, status, canonical_url, title, tags, created_at }`

`GET /items`
- Query: `q?`, `tags?`, `status?`, `favorite?`, `domain?`, `limit?`, `offset?`, `sort?`
- Returns: `{ items: [...], total }`

`GET /items/{id}`
- Returns: full item with `clean_html`, `text`, metadata, tags, status

`PATCH /items/{id}`
- Body: `{ title?, tags?, status?, favorite?, notes? }`
- Returns: updated item

`DELETE /items/{id}`
- Soft delete by default; supports `?hard=true` for permanent delete

`POST /items/{id}/highlight` (P1)
- Body: `{ quote, start_offset, end_offset, color?, note? }`

`POST /import`
- Multipart file upload (Pocket/Instapaper export); options `{ mergeTags?: bool }`
- Returns job id; progress via background jobs endpoint (existing pattern)

`GET /export`
- Query: `format=jsonl|zip`; filters: status/tags/time range
- Returns downloadable export

`POST /items/{id}/summarize`
- Triggers summarization using configured LLM; returns summary text with citation

`POST /items/{id}/tts`
- Proxies to existing TTS; returns stream or audio file reference

AuthNZ: obeys existing single-user API key or multi-user JWT modes; per-user isolation.

Rate limiting: align with chat/evals rate limiters; tighter limits on `/save` and `/import`.

## 9. WebUI (MVP)

- Reading List page: table/list with quick filters (status, tags, domain), search box, sort control.
- Item view: distraction-free reader; top bar actions (Back, Tag, Favorite, Mark Read, Summarize, Listen).
- Tag editor: multi-select with suggestions.
- Import modal: drag-and-drop Pocket/Instapaper export.
- Empty state with quick instructions (bookmarklet/API curl sample).

Accessibility: keyboard navigation; readable theme; proper heading semantics.

## 10. Security & Privacy

- Validate and sanitize all inputs; reject non-HTTP(S) schemes.
- Enforce fetch timeouts and max size; respect content types; strip scripts/styles from HTML, keep only safe tags/attrs.
- Do not circumvent paywalls or scrape authenticated content.
- Log with context via Loguru; never log raw content or secrets.

## 11. Telemetry & Metrics (local only)

- Ingestion success rate; median time to readable.
- Dedupe ratio; FTS search P50 latency; embedding backlog size.
- WebUI interactions (local only, no external telemetry): saves, reads, summaries, TTS uses.

## 12. Test Plan

Unit Tests (markers: `unit`)
- URL validation and canonicalization
- Readability extraction on diverse fixtures (news/blog/docs)
- HTML sanitization safety and correctness
- Tag normalization, status transitions, dedupe logic

Integration Tests (markers: `integration`)
- Save → ingest → retrieve → search flow
- Import Pocket/Instapaper → items created, tags mapped
- Embedding job enqueued and namespace isolation per user
- Summarize and TTS action wiring

Fixtures
- Sample HTML pages (simple, complex, multi-column, AMP)
- Pocket JSON export; Instapaper CSV export

Coverage target: ≥80% for new modules.

## 13. Rollout Plan

Phase 0: PRD + API design review
Phase 1 (MVP Core): Data model, `/save`, `/items`, FTS, dedupe, WebUI list/detail
Phase 2: Tags, favorites, status management, import/export
Phase 3: Embeddings + RAG exposure, summarize + TTS actions
Phase 4: Highlights/notes, suggestions/digest, bookmarklet, extension scaffolding

Migration: Provide DB migration helpers in `Config_Files/` and `DB_Management` utilities.

## 14. Open Questions & Risks

- JS-rendered pages: do we add optional headless rendering (Playwright) for stubborn sites?
- Storage policy for archived HTML/PDF and images; quotas and cleanup.
- Large/complex documents (magazine layouts, PDFs) - lean on existing document pipeline vs. special handling here?
- Namespace strategy for embeddings when users re-tag or archive: re-embed vs. soft moves.
- WebUI framework conventions: confirm placement and patterns for new feature slice.

## 15. Acceptance Criteria (MVP)

- Can save at least 95% of typical news/blog/article URLs with readable text.
- Search returns relevant items in < 200ms P50 on a library of 1k items.
- Items are discoverable in RAG with correct metadata and per-user isolation.
- WebUI provides a clean reader with basic actions working end-to-end.
- Import of Pocket or Instapaper succeeds on official export formats.

---

Implementation Note: Follow project conventions - PEP 8, type hints, docstrings, Loguru, FastAPI Pydantic models, dependency injection, and rate limiters. Use `MediaDatabase` abstractions or add a dedicated module under `DB_Management` if that yields a simpler design.
