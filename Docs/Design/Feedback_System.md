# Feedback System Design (Chat + RAG)

## Context
The backend already includes UnifiedFeedbackSystem for storing explicit and implicit feedback in:
- Analytics.db (server-side QA metrics)
- ChaChaNotes DB (user-scoped feedback linked to conversations)

This design bridges the gap by exposing explicit feedback in the API, expanding implicit event capture, and wiring the modern chat UI.

## Scope
- Shared explicit feedback endpoint for chat and RAG.
- Expanded implicit feedback events with richer metadata.
- Schema update for issues in ChaChaNotes conversation_feedback.
- UI integration for quick feedback and detailed feedback.

## Data Model
### ChaChaNotes conversation_feedback
Add column:
- issues TEXT (JSON array of issue IDs)

Existing fields reused:
- conversation_id, message_id, query, document_ids, chunk_ids, relevance_score, helpful, user_notes, created_at

### Analytics DB
Use existing feedback_analytics fields:
- feedback_type, rating, categories, improvement_areas
Map issues -> categories or improvement_areas for reporting.

## Schema Migration Strategy
- ChaChaNotes schema changes live in `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py` as
  `_MIGRATION_SQL_V{n}_TO_V{n+1}` (and `_MIGRATION_SQL_V{n}_TO_V{n+1}_POSTGRES` when needed), with
  `_CURRENT_SCHEMA_VERSION` bumped when a new migration is added.
- For v0.1, `conversation_feedback.issues` is added via the bootstrap DDL in
  `tldw_Server_API/app/core/RAG/rag_service/analytics_system.py` (`UserFeedbackStore._init_schema`)
  to avoid a full schema bump. The `ALTER TABLE` is idempotent for both SQLite and Postgres.
- Backward compatibility: existing rows get `issues` as NULL; API serialization treats missing/NULL
  as `[]`, so no backfill is required.

## API Design

### Explicit Feedback
Endpoint: POST /api/v1/feedback/explicit

Request fields:
- conversation_id (optional; required for chat feedback)
- message_id (optional; required for chat feedback)
- feedback_type: helpful | relevance | report
- helpful (optional boolean)
- relevance_score (optional int 1-5)
- document_ids (optional string[])
- chunk_ids (optional string[])
- corpus (optional string; RAG corpus/namespace)
- issues (optional string[])
- user_notes (optional string)
- query (optional string)
- session_id (optional string)
- idempotency_key (optional string)

Required-by-context rules:
- Chat feedback: message_id required; conversation_id optional and derived from the message when omitted. query optional and derived from message content if omitted.
- RAG-only feedback (no message_id): query required. conversation_id optional.
- Source-level feedback: document_ids or chunk_ids required. corpus recommended when multiple corpora exist.

Query derivation:
- If message_id is present and query is omitted, derive query from stored message content.
- If message_id is absent, query must be provided by the client.

Idempotency:
- If idempotency_key is present, dedupe by (user_id, idempotency_key).
- If idempotency_key is absent, best-effort dedupe within a short window:
  - Chat: (conversation_id, message_id, feedback_type, helpful, relevance_score[, user_notes_hash])
  - RAG-only: (query, feedback_type, helpful, relevance_score, document_ids, chunk_ids[, user_notes_hash])
- user_notes_hash: when user_notes is present, append a SHA-256 hex digest of user_notes after
  UTF-8 encoding and trimming leading/trailing whitespace. This avoids storing raw notes in the
  key while preventing accidental collisions when helpful/relevance_score are omitted.
- For repeated submissions that differ only in user_notes (or if you want stronger guarantees),
  clients should send an idempotency_key so updates are reliably deduped and merged.

Auth and rate limits:
- Require the same AuthNZ modes as other chat/RAG endpoints.
- Add a lightweight per-user rate limit (e.g., 60/min) to prevent spam.

Response:
- ok: true/false
- feedback_id (if stored)

### Implicit Feedback
Endpoint: POST /api/v1/rag/feedback/implicit

Event types:
- click | expand | copy | dwell_time | citation_used

Fields:
- event_type (required)
- query (optional)
- doc_id (optional)
- chunk_ids (optional string[])
- rank (optional int)
- impression_list (optional string[])
- session_id (optional string)
- conversation_id (optional string)
- message_id (optional string)
- dwell_ms (required when event_type=dwell_time)

Capture rules:
- Dwell time: emit once per response after a minimum threshold (e.g., 3s visible). Stop when user sends a new message or navigates away.
- Citation used: emit when user explicitly uses citations (copy-with-citations, insert citation, or similar UI). Include doc_id and/or chunk_ids if available.

Feature flag:
- IMPLICIT_FEEDBACK_ENABLED (default true). When false, server ignores implicit events.

Rate limits and throttling:
- Apply a separate per-user rate limit for implicit events (target: 300/min) so explicit feedback
  stays available even under noisy UI activity.
- Client should debounce high-frequency UI interactions and emit at most one dwell event per response.
- If the implicit rate limit is exceeded, the server may drop events or return 429; the UI should
  treat implicit feedback as best-effort.

## UI Integration

### Quick feedback row
- Show under assistant, system, and tool messages (persisted message_id required).
- Thumbs up/down send explicit feedback with helpful=true|false.
- Ellipsis opens detailed modal.

### Detailed feedback modal
- Star rating 1-5 -> relevance_score
- Issue checklist -> issues[]
- Notes -> user_notes

### Source-level feedback (Pro mode)
- Per-source thumbs up/down emit explicit feedback with document_ids/chunk_ids and corpus.
- Pro mode is a client capability toggle only; API always accepts source-level feedback.

## Validation and Error Handling
- Missing required fields should return 400 with a clear message.
- If message_id is provided but not found, return 404.
- If conversation_id does not match message ownership, return 403.

## Observability
- Log success/failure counts for explicit feedback endpoint.
- Track implicit event rates and drop counts when feature flag is off.

## Setup & Verification
- Enable implicit events via `implicit_feedback_enabled=true` in `Config_Files/config.txt` or `IMPLICIT_FEEDBACK_ENABLED=true` in the environment.
- Explicit feedback is served at `POST /api/v1/feedback/explicit`; implicit feedback is served at `POST /api/v1/rag/feedback/implicit`.
- Use the same auth headers as chat/RAG endpoints.
- Smoke test:
  ```bash
  curl -X POST http://127.0.0.1:8000/api/v1/feedback/explicit \
    -H 'Authorization: Bearer <JWT>' \
    -H 'Content-Type: application/json' \
    -d '{"conversation_id":"C_123","message_id":"M_456","feedback_type":"helpful","helpful":true}'

  curl -X POST http://127.0.0.1:8000/api/v1/rag/feedback/implicit \
    -H 'Authorization: Bearer <JWT>' \
    -H 'Content-Type: application/json' \
    -d '{"event_type":"copy","query":"example query","session_id":"S_1"}'
  ```

## Testing Strategy
- Unit tests for schema validation and required-by-context rules.
- Integration tests for DB writes (issues column persisted).
- UI tests for thumbs and modal submission paths.
- Implicit event tests for dwell_time and citation_used requirements.
- Idempotency tests for repeated submissions.
