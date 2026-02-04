# PRD: Per-User TTS History Model

Owner:
Date: 2026-02-04
Status: Draft
Target Release:
Document Version: v1.0

---

## 1) Summary

Add a per-user TTS history system that persists generation metadata and artifacts so users can search, favorite, and replay outputs. This is the backend foundation for history UI and auditability across streaming and job-based TTS.

---

## 2) Problem Statement

Currently, TTS outputs are ephemeral for many flows:
- Users cannot reliably find, filter, or replay previous generations.
- There is no unified record for metadata like duration, model, voice, or params.
- Long-form TTS jobs produce artifacts but lack a structured history entry.

This results in poor discoverability, weak analytics, and limited UX improvement opportunities.

---

## 3) Goals and Non-Goals

### Goals

1. Persist a canonical per-user history row for each TTS generation (streaming + job).
2. Store rich metadata (duration, model, voice, params, status, segments).
3. Provide query APIs with pagination, search, and favorites.
4. Link history rows to output artifacts when present.
5. Support future UX features (favorites, history search, replay).

### Non-Goals

- Full UI redesign (front-end work is out of scope here).
- Audio transcription history (this is TTS‑only).
- Complex analytics dashboards (basic retrieval only).

---

## 4) Users and Personas

1. Researcher — replays narrations and wants to find specific output by model/voice.
2. Creator — saves and favorites best takes for reuse.
3. Power User — wants metadata to compare models/params.

---

## 5) User Journeys

### A) Replay a previous generation
1. Generate TTS output.
2. History row is created with artifact link.
3. Later, user searches by keyword and replays.

### B) Favorite a best take
1. Generate several variants.
2. User marks favorites via API or UI.
3. Favorites list is quickly filtered.

---

## 6) Functional Requirements

### 6.1 Data Model

Create `tts_history` table with:
- `id` (pk), `user_id`, `created_at`
- `text` (optional) or `text_hash` (required) and `text_length`
- `provider`, `model`
- `voice_info` (JSON; voice id + label + provider-specific data)
- `format`, `duration_ms`, `generation_time_ms`
- `params_json` (JSON; includes extra_params, speed, pitch, etc.)
- `status` (`success` | `partial` | `failed`)
- `segments_json` (JSON; per-segment status, attempts, error, duration)
- `favorite` (bool, default false)
- `job_id` (optional), `output_id` (optional), `artifact_ids` (optional list)

Decision point: store `text`?
- Option A: store full text (improves search).
- Option B: store only `text_hash` + `text_length` (privacy-first; search requires client-provided index).
- Default recommendation: store `text` unless `TTS_HISTORY_STORE_TEXT=false`.

### 6.2 Write Path

- Streaming / non-job TTS: write history row at end of response.
- Job-based TTS: write history row when artifact is created.
- Include `segments_json` when chunking/segment metadata exists.

### 6.3 Read APIs

Add:
- `GET /api/v1/audio/history`
  - Query params: `q`, `favorite`, `provider`, `model`, `limit`, `offset`, `from`, `to`
- `PATCH /api/v1/audio/history/{id}`
  - Body: `{"favorite": true|false}`
- Optional: `GET /api/v1/audio/history/{id}` for detail & replay metadata.

---

## 7) Non-Functional Requirements

- Must not exceed +5ms per request on average for history insert.
- Must enforce user isolation (no cross-user reads).
- Must handle large metadata JSON safely.
- Must support deletion/retention policies in future.

---

## 8) Data Retention & Privacy

- Default retention: align with outputs retention.
- If `text` storage is enabled, it should be sanitized and never logged.
- Add configuration to disable text storage or hash only.

---

## 9) Metrics & Observability

- `tts_history_writes_total` (success/failure)
- `tts_history_reads_total` (query volume)
- `tts_history_write_latency_ms`

---

## 10) API Contracts (Detailed)

### `GET /api/v1/audio/history`

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
      "favorite": false
    }
  ],
  "total": 321,
  "limit": 50,
  "offset": 0
}
```

### `PATCH /api/v1/audio/history/{id}`

```json
{ "favorite": true }
```

---

## 11) Rollout Plan

1. Add schema + migration.
2. Write path integration for streaming + jobs.
3. Add read APIs and pagination.
4. Add favorite toggle.
5. Wire to WebUI (future ticket).

---

## 12) Risks & Mitigations

Risk: Storing full text increases privacy exposure.
Mitigation: Config to disable text storage; use hash-only mode.

Risk: Large JSON metadata bloat.
Mitigation: Clamp per‑segment metadata size; drop oversized arrays.

---

## 13) Open Questions

1. Should we store full text by default or hash-only?
2. Should history be created for failed requests?
3. Should history rows auto-delete when artifacts expire?
