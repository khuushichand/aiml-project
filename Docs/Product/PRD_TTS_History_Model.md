# PRD: Per‑User TTS History (Backend)

Owner:
Date: 2026-02-04
Status: Draft (implementation largely complete; gap closure in progress)
Target Release:
Document Version: v2.0

---

## 1) Problem / Why Now

TTS outputs are currently transient for many flows. Users cannot reliably find, replay, or compare generations, and we have no canonical record of model/voice/params, duration, or segment health. Long‑form jobs produce artifacts but no structured history entry. This blocks UX features (favorites, search) and makes reliability analysis hard.

---

## 2) Goals (Measurable)

1. **Durable history**: 100% of TTS runs (job + non‑job) create a history row within 2 seconds of completion.
2. **Queryable**: history list supports pagination + filters + favorites, returns in < 200ms p95 on 10k rows.
3. **Replay‑ready**: history row can link to output artifact(s) when available.
4. **Reliability metadata**: includes segment‑level warnings/errors and retry attempts when present.

---

## 3) Non‑Goals

- UI work (history panel, favorites UI) — separate ticket.
- STT history or voice cloning reference history.
- Analytics dashboards beyond basic metrics.

---

## 4) Scope

**In scope**
- New `tts_history` table + access layer.
- History write paths for: audio.speech (stream + non‑stream) and TTS job worker.
- New API endpoints for list + favorite toggle (+ optional detail).
- Minimal retention controls and privacy options.

**Out of scope**
- Advanced full‑text ranking beyond basic query (v1 ok with `LIKE` or FTS if already available).
- Cross‑user sharing or public history.

---

## 5) Users / Use Cases

1. **Power user**: Find prior outputs by keyword, model, voice.
2. **Creator**: Favorite the best take and replay it.
3. **Researcher**: Compare runs using metadata (params, duration, status).

---

## 6) Functional Requirements

### 6.1 Data Model

**Storage location**
- SQLite default: per‑user `Databases/user_databases/<user_id>/Media_DB_v2.db`.
- Postgres deployments: shared `tts_history` table keyed by `user_id`.

Create `tts_history` with the following fields (SQLite + Postgres):

- `id` (PK, int)
- `user_id` (TEXT, required)
- `created_at` (ISO timestamp)
- `text` (TEXT, nullable) — only if `TTS_HISTORY_STORE_TEXT=true`
- `text_hash` (TEXT, required) — HMAC‑SHA256 of normalized text using `TTS_HISTORY_HASH_KEY` (always stored)
- `text_length` (INT) — Unicode codepoint length of normalized text
- `provider` (TEXT)
- `model` (TEXT)
- `voice_id` (TEXT) — normalized voice identifier for filtering
- `voice_name` (TEXT) — human‑readable voice label
- `voice_info` (JSON)
- `format` (TEXT)
- `duration_ms` (INT)
- `generation_time_ms` (INT)
- `params_json` (JSON) — extra_params + speed/pitch/volume etc.
- `status` (TEXT enum: success|partial|failed)
- `segments_json` (JSON) — segment metadata object (see 6.3)
- `favorite` (BOOL default false)
- `job_id` (INT nullable)
- `output_id` (INT nullable)
- `artifact_ids` (JSON list nullable)
- `artifact_deleted_at` (ISO timestamp nullable) — set if artifacts are purged
- `error_message` (TEXT nullable)
- `deleted` (BOOL default false)
- `deleted_at` (ISO timestamp nullable)

**Text storage rules**
- If `TTS_HISTORY_STORE_TEXT=true`, store both plaintext `text` (for search) and `text_hash` + `text_length` (for dedup/privacy).
- If `TTS_HISTORY_STORE_TEXT=false`, store only `text_hash` + `text_length` and keep `text` null (no plaintext).
- `text_hash` must always be computed from the original request text when available (after normalization) and stored even when `text` is present so downstream dedup/lookup is consistent.

**Indexes**
- `(user_id, created_at DESC)`
- `(user_id, favorite)`
- `(user_id, provider)`
- `(user_id, model)`
- `(user_id, voice_id)`
- optional `(user_id, text_hash)`

**Text normalization & hashing**
- Normalize by: Unicode NFKC, normalize newlines to `\n`, trim leading/trailing whitespace, collapse internal whitespace to single spaces.
- `text_hash` uses HMAC‑SHA256 with `TTS_HISTORY_HASH_KEY` (per deployment).
- `text_length` is computed from the normalized text.

### 6.2 History Write Path

**Non‑job TTS** (audio.speech):
- Write a history row when generation completes.
- If streaming: write at end of stream (after last chunk).
- If failure: write status=`failed` with `error_message` (configurable; see 6.4).
- `duration_ms` should come from provider metadata or audio header when available; otherwise store `null`.
- `generation_time_ms` is wall‑clock from request start to final chunk/response.

**Job‑based TTS**:
- Worker writes a history row after output artifact creation.
- Links `job_id`, `output_id`, and `artifact_ids` (if multiple).

### 6.3 Segment Metadata

If chunking/segment metadata exists (from ticket 5):
- Store `segments_json` with schema:
  ```json
  {
    "segments": [
      {"index":0,"status":"success|failed","attempts":2,"error":"...","duration_ms":1234}
    ],
    "summary": {
      "total": 10,
      "success": 9,
      "failed": 1,
      "total_duration_ms": 12000,
      "max_attempts": 3
    },
    "truncated": false
  }
  ```
- If serialized `segments_json` exceeds 64KB, truncate by dropping successful segments first, keep up to the most recent 256 failed segments, then add most recent successes to fill remaining space. Always preserve `summary` and set `truncated=true`.
- If absent, store `null`.

### 6.4 Text Storage & Privacy (Config)

Add config flags:
- `TTS_HISTORY_ENABLED` (default true)
- `TTS_HISTORY_STORE_TEXT` (default true)
- `TTS_HISTORY_STORE_FAILED` (default true)
- `TTS_HISTORY_HASH_KEY` (required for HMAC; use deployment secret)

If `STORE_TEXT=false`, only save `text_hash` + `text_length`.
When `STORE_TEXT=false`, keyword search is unavailable (see API). Text must never be logged.

### 6.5 API Endpoints

#### `GET /api/v1/audio/history`
Query:
- `q` (string; matches `text` if stored; otherwise 400 with clear error)
- `text_exact` (string; server computes HMAC and matches `text_hash` exactly)
- `favorite` (bool)
- `provider` (string)
- `model` (string)
- `voice_id` (string)
- `voice_name` (string)
- `limit` (1–200)
- `offset` (>=0)
- `cursor` (string; optional keyset cursor; if set, `offset` ignored)
- `include_total` (bool; default false)
- `from` / `to` (timestamps)

Cursor behavior:
- Ordering is `created_at DESC, id DESC`.
- `next_cursor` is returned when more rows are available.
- Cursor format is base64url‑encoded JSON: `{"v":1,"created_at":"<UTC ISO8601>","id":<int>}`. Clients must treat this token as opaque.
- When `cursor` is provided, the server returns rows where `(created_at, id) < (cursor_created_at, cursor_id)` in the same ordering.

Response:
```json
{
  "items": [
    {
      "id": 123,
      "created_at": "...",
      "has_text": true,
      "text_preview": "first 120 chars...",
      "provider": "qwen3_tts",
      "model": "...",
      "voice_id": "alloy",
      "voice_name": "Alloy",
      "voice_info": {},
      "duration_ms": 12345,
      "format": "mp3",
      "status": "success",
      "favorite": false,
      "job_id": 55,
      "output_id": 777,
      "artifact_deleted_at": null
    }
  ],
  "total": 321,
  "limit": 50,
  "offset": 0,
  "next_cursor": "eyJ2IjoxLCJjcmVhdGVkX2F0IjoiMjAyNi0wMi0wNFQxMjowMDowMFoiLCJpZCI6MTIzfQ"
}
```

#### `PATCH /api/v1/audio/history/{id}`
Body:
```json
{ "favorite": true }
```

#### Optional
`GET /api/v1/audio/history/{id}` for full metadata + segment list.

#### `DELETE /api/v1/audio/history/{id}`
Remove a single history row (soft delete; hard purge controlled by retention settings).

### 6.6 Access Control

- Only the owner can read/update a row.
- Admin access only via existing admin patterns.
- Delete follows the same access rules.

### 6.7 Retention & Deletion

Config:
- `TTS_HISTORY_RETENTION_DAYS` (default 90; 0 disables age‑based purge)
- `TTS_HISTORY_MAX_ROWS_PER_USER` (default 10_000; 0 disables row cap)
- `TTS_HISTORY_PURGE_INTERVAL_HOURS` (default 24)

Behavior:
- Purge job runs every `TTS_HISTORY_PURGE_INTERVAL_HOURS` and is idempotent.
- Age‑based purge: delete rows where `created_at < now - RETENTION_DAYS` (UTC).
- Row cap: if a user exceeds `MAX_ROWS_PER_USER`, delete the oldest rows by `created_at ASC, id ASC` until within cap.
- If both limits are set, apply age‑based purge first, then row cap.
- Artifact retention is independent; when artifacts are deleted, update history rows to set `artifact_deleted_at` and clear `output_id`/`artifact_ids`.
Default retention targets 90 days and 10k rows per user to cap storage while preserving typical work histories. This aligns with other 90‑day retention defaults (e.g., audit logs) while avoiding long‑term storage of user‑provided text.

---

## 7) Non‑Functional Requirements

- Insert overhead: +5ms p95 per request on average.
- Query p95 < 200ms for 10k history rows per user.
- JSON metadata size capped (e.g., 64KB) — drop or truncate segments if exceeded.
- For large datasets, prefer `cursor` pagination and `include_total=false` to maintain p95.

---

## 8) Error Handling / Edge Cases

- If history insert fails: do not fail TTS response; log once with request_id.
- For job failures: still write a failed history row if `STORE_FAILED=true`.
- If artifacts are deleted later: history remains; references are cleared and `artifact_deleted_at` is set.
- If `q` is provided while `STORE_TEXT=false`, return 400 with a clear error message.

---

## 9) Migration / Backfill

- New migration for `tts_history` table and indexes.
- No backfill (v1). Optional future: infer from outputs.

---

## 10) Observability

Metrics:
- `tts_history_writes_total` (labels: status, provider)
- `tts_history_reads_total` (labels: favorite, provider)
- `tts_history_write_latency_ms`

Logs:
- Only metadata; never log `text`.

---

## 11) Testing

- Unit: history insert with/without text storage.
- Unit: list filters + favorite toggle.
- Unit: `q` rejected when `STORE_TEXT=false`; `text_exact` matches hash.
- Unit: voice filters (`voice_id`, `voice_name`) and index coverage.
- Unit: segment truncation policy preserves failed segments and sets `truncated=true`.
- Unit: delete history row (soft delete) hides it from list/detail.
- Integration: end‑to‑end job -> artifact -> history entry.
- Integration: streaming failure produces `failed` history row with `error_message`.
- Integration: artifact purge clears references and sets `artifact_deleted_at`.

---

## 12) Rollout Plan

1. Add schema + data access layer.
2. Write path integration (audio.speech + worker).
3. Add list + favorite endpoints.
4. Add metrics and logs.
5. Enable by default; allow env‑based disable.

---

## 13) Decisions

1. Store full text by default; allow hash‑only via `TTS_HISTORY_STORE_TEXT=false`.
2. Failed requests create history rows when `TTS_HISTORY_STORE_FAILED=true` (default true).
3. History retention is independent of artifact retention; artifact deletions clear references but keep history.

---

## 14) Known Gaps (As Of 2026-02-08)

- Job-based history rows do not yet populate `artifact_ids` on successful writes.
- History insert failure logs do not consistently include request/job correlation IDs.
- TTS history cleanup reads retention config from env directly; align with shared settings resolution.
- Explicit tests still needed for:
  - segment truncation policy behavior at/over 64KB,
  - `voice_id` / `voice_name` history filters,
  - end-to-end `speech/jobs` -> artifact -> history linkage.

---

## 15) Design Doc (Implementation Plan)

### Stage 1: Schema, Settings, and Migrations
**Goal**: Add `tts_history` storage with indexes and config flags across SQLite and Postgres paths.
**Success Criteria**:
- `tts_history` table exists with all columns and indexes in both SQLite (per‑user Media DB) and Postgres.
- Settings include `TTS_HISTORY_*` flags and `TTS_HISTORY_HASH_KEY`, documented in env/config references.
- Text normalization + HMAC spec implemented in a shared utility.
**Tests**:
- Unit: schema creation/migration verification.
- Unit: normalization + HMAC output consistency.
**Status**: Complete

### Stage 2: Write Path Integration
**Goal**: Persist history rows for non‑job and job‑based TTS runs.
**Success Criteria**:
- `audio.speech` writes history for success/failure, including streaming completion behavior.
- Job worker writes history after artifact creation and links `job_id`, `output_id`, `artifact_ids`.
- `segments_json` supports truncation policy and summary.
**Tests**:
- Unit: history insert with/without text storage.
- Integration: streaming failure produces `failed` row with `error_message`.
**Status**: Complete

### Stage 3: Read Path and API Endpoints
**Goal**: Implement list/detail/favorite/delete endpoints with filtering and pagination.
**Success Criteria**:
- `GET /api/v1/audio/history` supports filters, cursor pagination, and `include_total`.
- `GET /api/v1/audio/history/{id}` returns full metadata and segments.
- `PATCH /api/v1/audio/history/{id}` toggles favorite.
- `DELETE /api/v1/audio/history/{id}` soft‑deletes rows.
- Access control enforced for all endpoints.
**Tests**:
- Unit: list filters + favorite toggle + delete behavior.
- Unit: `q` rejected when `STORE_TEXT=false`; `text_exact` matches hash.
**Status**: Complete

### Stage 4: Retention and Artifact Purge Integration
**Goal**: Add automated cleanup and artifact reference handling.
**Success Criteria**:
- Scheduled purge respects `RETENTION_DAYS` and `MAX_ROWS_PER_USER` with defined ordering.
- Artifact deletion clears references and sets `artifact_deleted_at`.
**Tests**:
- Integration: artifact purge updates history references.
**Status**: Complete

### Stage 5: Observability and Performance
**Goal**: Ensure metrics, logging, and performance targets are met.
**Success Criteria**:
- Metrics emitted for writes, reads, and write latency.
- Logs contain metadata only; text never logged.
- Query p95 < 200ms for 10k rows (cursor pagination recommended).
**Tests**:
- Integration: basic performance sanity (non‑blocking).
**Status**: Complete
