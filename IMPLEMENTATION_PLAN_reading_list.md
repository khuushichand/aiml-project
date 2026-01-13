## Stage 1: Data Model + DB Management
**Goal**: Add Reading List tables to per-user Media_DB_v2 with FTS5 support and a DB access layer.
**Success Criteria**: `reading_items`, tags, highlights (P1), and FTS5 tables exist; CRUD + search helpers live in `DB_Management`; migrations documented and runnable.
**Tests**: Unit tests for DB CRUD + FTS indexing/search; migration helper tests for new tables.
**Status**: Complete

## Stage 2: Ingestion Pipeline (Fetch → Extract → Store)
**Goal**: Implement ingestion service with SSRF-safe fetch, readability extraction, sanitization, canonicalization, dedupe, and headless rendering (config-gated).
**Success Criteria**: `POST /reading/save` can ingest typical HTML; non-HTML routes into existing document ingestion and links back to `reading_items`.
**Tests**: Unit tests for SSRF guardrails, canonicalization/dedupe, readability extraction on fixtures, HTML sanitization; property-based tests for tag normalization or URL normalization invariants.
**Status**: Complete

## Stage 3: Core API Endpoints + Search
**Goal**: Add schemas and endpoints for save/list/get/update/delete with filtering, sorting, and per-user isolation.
**Success Criteria**: Endpoints return consistent payloads with `processing|ready` status; FTS search filters/sort work at API level; rate limiting applied.
**Tests**: Integration tests for save → ingest → retrieve → search flow; auth isolation tests; delete semantics (soft/hard) tests.
**Status**: Complete

## Stage 4: Background Jobs + RAG/Actions
**Goal**: Wire embeddings, RAG exposure, summarize, and TTS actions into background jobs where appropriate.
**Success Criteria**: Embedding jobs enqueue per user; items are retrievable via unified RAG; summarize and TTS actions return outputs with citations/metadata.
**Tests**: Integration tests for embedding job enqueue + namespace isolation; summarize/TTS action wiring with mocked providers.
**Status**: Complete

## Stage 5: Import/Export + Frontend Handoff
**Goal**: Implement Pocket/Instapaper importers, JSONL export, and publish API contract artifacts for frontend integration.
**Success Criteria**: Imports handle official export formats with tag mapping; export supports filters; OpenAPI examples and sample payloads are shared with `tldw-frontend/` owners.
**Tests**: Integration tests for import/export flows; fixture-based tests for export formats.
**Status**: Complete
