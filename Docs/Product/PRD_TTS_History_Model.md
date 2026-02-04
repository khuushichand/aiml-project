# PRD: Per‑User TTS History (Backend)

Owner:
Date: 2026-02-04
Status: Draft
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

Create `tts_history` with the following fields (SQLite + Postgres):

- `id` (PK, int)
- `user_id` (TEXT, required)
- `created_at` (ISO timestamp)
- `text` (TEXT, nullable) — only if `TTS_HISTORY_STORE_TEXT=true`
- `text_hash` (TEXT, required) — sha256 of normalized text
- `text_length` (INT)
- `provider` (TEXT)
- `model` (TEXT)
- `voice_info` (JSON)
- `format` (TEXT)
- `duration_ms` (INT)
- `generation_time_ms` (INT)
- `params_json` (JSON) — extra_params + speed/pitch/volume etc.
- `status` (TEXT enum: success|partial|failed)
- `segments_json` (JSON) — segment status/attempts/errors
- `favorite` (BOOL default false)
- `job_id` (INT nullable)
- `output_id` (INT nullable)
- `artifact_ids` (JSON list nullable)
- `error_message` (TEXT nullable)

**Indexes**
- `(user_id, created_at DESC)`
- `(user_id, favorite)`
- `(user_id, provider)`
- `(user_id, model)`
- optional `(user_id, text_hash)`

### 6.2 History Write Path

**Non‑job TTS** (audio.speech):
- Write a history row when generation completes.
- If streaming: write at end of stream (after last chunk).
- If failure: write status=`failed` with `error_message` (configurable; see 6.4).

**Job‑based TTS**:
- Worker writes a history row after output artifact creation.
- Links `job_id`, `output_id`, and `artifact_ids` (if multiple).

### 6.3 Segment Metadata

If chunking/segment metadata exists (from ticket 5):
- Store `segments_json` with schema:
  ```json
  [{"index":0,"status":"success|failed","attempts":2,"error":"...","duration_ms":1234}]
  ```
- If absent, store `null`.

### 6.4 Text Storage & Privacy (Config)

Add config flags:
- `TTS_HISTORY_ENABLED` (default true)
- `TTS_HISTORY_STORE_TEXT` (default true)
- `TTS_HISTORY_STORE_FAILED` (default true)

If `STORE_TEXT=false`, only save `text_hash` + `text_length`.
Text must never be logged.

### 6.5 API Endpoints

#### `GET /api/v1/audio/history`
Query:
- `q` (string; matches `text` if stored, else ignored)
- `favorite` (bool)
- `provider` (string)
- `model` (string)
- `limit` (1–200)
- `offset` (>=0)
- `from` / `to` (timestamps)

Response:
```json
{
  "items": [
    {
      "id": 123,
      "created_at": "...",
      "text_preview": "first 120 chars...",
      "provider": "qwen3_tts",
      "model": "...",
      "voice_info": {},
      "duration_ms": 12345,
      "format": "mp3",
      "status": "success",
      "favorite": false,
      "job_id": 55,
      "output_id": 777
    }
  ],
  "total": 321,
  "limit": 50,
  "offset": 0
}
```

#### `PATCH /api/v1/audio/history/{id}`
Body:
```json
{ "favorite": true }
```

#### Optional
`GET /api/v1/audio/history/{id}` for full metadata + segment list.

### 6.6 Access Control

- Only the owner can read/update a row.
- Admin access only via existing admin patterns.

---

## 7) Non‑Functional Requirements

- Insert overhead: +5ms p95 per request on average.
- Query p95 < 200ms for 10k history rows per user.
- JSON metadata size capped (e.g., 64KB) — drop or truncate segments if exceeded.

---

## 8) Error Handling / Edge Cases

- If history insert fails: do not fail TTS response; log once with request_id.
- For job failures: still write a failed history row if `STORE_FAILED=true`.
- If artifacts are deleted later: history remains, but `output_id` may be stale.

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
- Integration: end‑to‑end job -> artifact -> history entry.

---

## 12) Rollout Plan

1. Add schema + data access layer.
2. Write path integration (audio.speech + worker).
3. Add list + favorite endpoints.
4. Add metrics and logs.
5. Enable by default; allow env‑based disable.

---

## 13) Open Questions

1. Store full text by default or hash‑only?
2. Should failed requests always create history rows?
3. Should history rows expire with artifact retention?
