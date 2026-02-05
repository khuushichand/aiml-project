## Stage 1: Schema, Settings, and Migrations
**Goal**: Add `tts_history` storage with indexes and config flags across SQLite and Postgres paths.
**Success Criteria**:
- `tts_history` table exists with all columns and indexes in both SQLite (per-user Media DB) and Postgres.
- Settings include `TTS_HISTORY_*` flags and `TTS_HISTORY_HASH_KEY`, documented in env/config references.
- Text normalization + HMAC spec implemented in a shared utility.
**Tests**:
- Unit: schema creation/migration verification.
- Unit: normalization + HMAC output consistency.
**Status**: Complete

## Stage 2: Write Path Integration
**Goal**: Persist history rows for non-job and job-based TTS runs.
**Success Criteria**:
- `audio.speech` writes history for success/failure, including streaming completion behavior.
- Job worker writes history after artifact creation and links `job_id`, `output_id`, `artifact_ids`.
- `segments_json` supports truncation policy and summary.
**Tests**:
- Unit: history insert with/without text storage.
- Integration: streaming failure produces `failed` row with `error_message`.
**Status**: Complete

## Stage 3: Read Path and API Endpoints
**Goal**: Implement list/detail/favorite/delete endpoints with filtering and pagination.
**Success Criteria**:
- `GET /api/v1/audio/history` supports filters, cursor pagination, and `include_total`.
- `GET /api/v1/audio/history/{id}` returns full metadata and segments.
- `PATCH /api/v1/audio/history/{id}` toggles favorite.
- `DELETE /api/v1/audio/history/{id}` soft-deletes rows.
- Access control enforced for all endpoints.
**Tests**:
- Unit: list filters + favorite toggle + delete behavior.
- Unit: `q` rejected when `STORE_TEXT=false`; `text_exact` matches hash.
**Status**: Complete

## Stage 4: Retention and Artifact Purge Integration
**Goal**: Add automated cleanup and artifact reference handling.
**Success Criteria**:
- Scheduled purge respects `RETENTION_DAYS` and `MAX_ROWS_PER_USER` with defined ordering.
- Artifact deletion clears references and sets `artifact_deleted_at`.
**Tests**:
- Integration: artifact purge updates history references.
**Status**: Complete

## Stage 5: Observability and Performance
**Goal**: Ensure metrics, logging, and performance targets are met.
**Success Criteria**:
- Metrics emitted for writes, reads, and write latency.
- Logs contain metadata only; text never logged.
- Query p95 < 200ms for 10k rows (cursor pagination recommended).
**Tests**:
- Integration: basic performance sanity (non-blocking).
**Status**: Complete
