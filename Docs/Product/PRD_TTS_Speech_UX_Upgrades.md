# PRD: TTS Reliability & Speech UX Upgrades

Owner:
Date: 2026-02-03
Status: Draft
Target Release:
Document Version: v1.0

---

## 1) Summary

Improve tldw’s text-to-speech reliability, performance, and long-form user experience by adopting proven patterns from qwen3-TTS-studio. Scope includes model caching, robust long-form synthesis (chunking, retries, silence/truncation checks), progress reporting with ETA, rich per-user history, and frontend UX enhancements (voice cards, progress UI, draft editor, presets, history favorites/search, and input warnings).

---

## 2) Problem Statement

Users generating longer TTS outputs experience:
- Inconsistent quality (truncation, silent output).
- High latency due to repeated model loads.
- Poor visibility into long-running jobs (no ETA or step breakdown).
- Limited history management (no favorites or search).
- No draft-first workflow for long-form audio.

---

## 3) Goals and Non-Goals

### Goals

Backend
1. Reduce repeated-request latency via LRU model cache + cleanup.
2. Reduce truncation/silent output through min-token patching, dynamic max tokens, chunking + crossfade, and silence/truncation checks.
3. Make long-form TTS resilient with retries + per-segment error metadata.
4. Provide progress snapshots + ETA via SSE/WebSocket.
5. Persist rich per-user TTS history.
6. Enforce safe, sanitized filenames for stored artifacts.

WebUI / Extension
1. Voice cards with role assignment + preview.
2. Multi-step progress UI with per-segment counts + ETA.
3. Draft editor + preview for long-form flows.
4. Favorites + search in history.
5. Fast/Balanced/Quality presets.
6. Character count warnings + time estimates.

### Non-Goals
- Replacing providers or core routing logic.
- Changing STT metadata header behavior (intentionally default-on).
- Full redesign of Speech Playground (only additive UX).

---

## 4) Users and Personas

1. Researcher
   - Needs long narration of summaries/notes. Cares about reliability and ETA.

2. Content Creator
   - Uses multi-speaker voices; wants preview and role control.

3. Power User
   - Iterates, replays, and compares outputs. Needs searchable history and favorites.

---

## 5) Key User Journeys

### Journey A: Long-form narration
1. User drafts outline + transcript.
2. Reviews and edits content.
3. Selects quality preset and voices.
4. Starts job; sees step progress + ETA.
5. Receives audio segments and full output.

### Journey B: Multi-speaker podcast style
1. Selects 2-4 voices with roles.
2. Previews voices.
3. Runs synthesis with quality preset.
4. Replays or exports output.

### Journey C: Quick TTS
1. Paste text.
2. Choose preset.
3. Generate; output appears in history.

---

## 6) UX Requirements

### 6.1 Voice Cards (Multi-speaker)
- Cards show name, voice type, role, preview.
- 1-4 voices; validation and selection summary.

### 6.2 Draft Editor + Preview
- Two-column: outline list (left), transcript editor (right).
- Validation before synthesis.

### 6.3 Progress UI
- Step indicator: Outline -> Transcript -> Audio -> Combine.
- Per-segment status + ETA.
- Updates via SSE/WebSocket.

### 6.4 History
- Search + favorites.
- Per-item metadata (duration, model, voice, params).
- Clear history action.

### 6.5 Presets + Input Warnings
- Fast/Balanced/Quality buttons.
- Character count warnings and estimated duration.

---

## 7) Functional Requirements (Backend)

1) Model Cache + Memory Hygiene
- LRU cache for local TTS model instances.
- Evict on threshold; MPS/GPU cleanup.
- Metrics: hit rate, evictions.

2) Min-Token Patch + Dynamic Max Tokens
- Apply min_new_tokens if provider supports.
- Estimate max_new_tokens from text length with cap.

3) Chunking + Crossfade + Silence Checks
- Sentence chunking for long text.
- Crossfade merge between chunks.
- Silent output + truncation detection -> retry.

4) Retry + Crash Logs
- Per-segment retry with backoff.
- Store per-segment errors in metadata.
- Partial success allowed.

5) Progress Callbacks + ETA
- Weighted steps; update snapshots.
- Exposed via SSE/WebSocket.
- Stored for audit + UI.

6) History Metadata Model
- Per-user persistence.
- Fields: duration, generation_time, params, model, voice_info, provider, format, segments, status.

7) Sanitized Filenames
- Safe, strict sanitization for all stored artifacts.
- Prevent traversal or invalid characters.

---

## 8) Non-Functional Requirements

- Must not increase median latency for short text by >10%.
- Memory cap honored on MPS/CUDA; no unbounded cache growth.
- Jobs scale with existing tldw Jobs framework.
- No secrets logged.

---

## 9) Data Model

TTSHistory
- id, user_id, created_at
- text, text_hash
- provider, model, voice_info
- duration_ms, generation_time_ms, params (JSON)
- status: success | partial | failed
- segments: {index, status, duration_ms, error?}
- favorite (bool)

TTSProgressSnapshot
- job_id, step, step_progress, overall_progress
- segment_current, segment_total
- eta_seconds, updated_at

---

## 10) API Requirements

- POST /api/v1/audio/speech
  - Accepts: preset, chunking, min_tokens, max_tokens, progress_id.
- GET /api/v1/audio/history
  - Query: q, favorite, provider, limit, offset.
- PATCH /api/v1/audio/history/{id}
  - Toggle favorite.
- GET /api/v1/audio/jobs/{id}/progress
  - SSE/WebSocket stream.

---

## 11) Telemetry / Metrics

- Cache hit rate, evictions, avg load time.
- Silent/truncation error rate.
- Time-to-first-audio & overall job completion.
- History usage (favorites, search, replay).

---

## 12) Risks and Mitigations

- Memory bloat -> strict cache cap + cleanup.
- Provider differences -> capability checks.
- Long-form latency -> Jobs + progress UI.
- UX complexity -> defaults stay simple; advanced sections collapse.

---

## 13) Acceptance Criteria

Backend
- LRU cache in place with cleanup and metrics.
- Chunking + silence/truncation checks reduce error rate.
- Retries documented, with per-segment error metadata.
- SSE/WebSocket progress snapshots available.
- History metadata stored per user with search.

WebUI/Extension
- Voice cards + preview with 1-4 roles.
- Multi-step progress UI with ETA.
- Draft editor available for long-form.
- History supports favorites + search.
- Presets + input warnings visible.

---

## 14) Milestones

1) Backend core reliability (cache, chunking, min-tokens).
2) Progress API + history model.
3) Speech Playground UI updates.
4) Draft editor + voice cards.

---

## 15) Open Questions

- Which TTS providers support min_new_tokens patching?
- Cache size defaults per hardware profile?
- History retention policy (time vs count)?
- Storage location for large audio artifacts?

