## Stage 1: Schema & Data Model
**Goal**: Add missing Chat Enhancements schema elements and indexes with safe defaults/backfills.
**Success Criteria**:
- `topic_label_source`, `topic_last_tagged_at`, `topic_last_tagged_message_id` columns present on `conversations`.
- `conversation_clusters` table exists with expected columns and indexes.
- `flashcards` table has `conversation_id`/`message_id` backlinks with indexes.
- Composite index on `(source, external_ref)` exists for idempotent connector lookups.
- Migrations apply idempotently on SQLite and Postgres.
**Tests**:
- SQLite migration test validates new columns/indexes.
- Postgres migration conversion test validates new columns/indexes.
**Status**: Complete

## Stage 2: Core APIs (List/Update/Tree/Analytics/Knowledge Save)
**Goal**: Implement Phase 1 endpoints and semantics; alias `/api/v1/chat/conversations` to `/api/v1/chats` where appropriate.
**Success Criteria**:
- `GET /api/v1/chat/conversations` supports filters (query, date range, state, topic_label, keywords, cluster_id, character_id) and ordering (`bm25|recency|hybrid|topic`) with stable pagination.
- `PATCH /api/v1/chat/conversations/{id}` validates state and uses optimistic locking (`version` in body), while `/api/v1/chats/{chat_id}` remains supported.
- `GET /api/v1/chat/conversations/{id}/tree` returns root-thread pagination with depth caps and `truncated` markers.
- `GET /api/v1/chat/analytics` returns UTC buckets with range limits and bucket pagination.
- `POST /api/v1/chat/knowledge/save` returns `export_status=skipped_disabled` when connectors are off and still creates Note/Flashcard.
**Tests**:
- BM25 normalization + pagination stability test for conversation list.
- Recency fallback test (last_modified -> created_at).
- Tree integrity + truncation test.
- Analytics bucket range + UTC behavior test.
- Knowledge-save export_status test (connectors disabled) and backlink validation for notes/flashcards.
**Status**: Complete

## Stage 3: Auto-Tagging & Clustering (Phase 2)
**Goal**: Implement auto-tagging and clustering jobs with idempotency + manual overrides.
**Success Criteria**:
- Auto-tagging updates `topic_label`/keywords and `topic_last_tagged_*` only when new messages exceed threshold and respects `topic_label_source=manual`.
- Clustering assigns `cluster_id` and persists `conversation_clusters` metadata; opt-out supported.
**Tests**:
- Auto-tag idempotency test with manual override preservation.
- Clustering persistence test (cluster metadata + membership).
- Opt-out/unclustered handling test.
**Status**: Not Started

## Stage 4: WebUI & Docs Alignment
**Goal**: Surface new filters, ranking, tree view, analytics, and updated docs.
**Success Criteria**:
- UI lists conversations with state/topic chips and ranking toggles.
- UI supports tree view and knowledge-save actions with export status.
- Analytics tab renders histogram buckets by state/topic/date.
- Docs/OpenAPI updated for `/api/v1/chat/conversations` alias and parameter glossary.
**Tests**:
- UI smoke tests for list/detail/analytics.
- OpenAPI/doc example validation against schemas.
**Status**: Not Started
