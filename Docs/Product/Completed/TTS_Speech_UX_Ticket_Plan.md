# Ticket Plan: TTS Reliability & Speech UX Upgrades

This document converts the PRD into issue templates. Each ticket includes scope, acceptance criteria, and suggested files.

---

## 1) Backend: LRU TTS model cache + MPS/GPU cleanup

Scope
- Add LRU cache for local TTS model instances.
- Evict on threshold; run device cleanup (MPS/CUDA/CPU GC).
- Add cache hit/eviction metrics.

Acceptance Criteria
- Repeated TTS requests hit the cache (observable via metrics/logs).
- Eviction triggers device cleanup and does not leak memory.
- Cache size is configurable.

Suggested Files
- tldw_Server_API/app/core/TTS/tts_resource_manager.py
- tldw_Server_API/app/core/TTS/tts_service_v2.py
- tldw_Server_API/app/core/TTS/adapters/*
- tldw_Server_API/app/core/Metrics/*

---

## 2) Backend: min_new_tokens patch + dynamic max token estimation

Scope
- Patch min_new_tokens for supported providers.
- Estimate max_new_tokens from text length with safety cap.
- Expose config defaults.

Acceptance Criteria
- Long TTS outputs no longer truncate early under common prompts.
- Estimation is deterministic and capped.
- Provider capability checks prevent unsupported params.

Suggested Files
- tldw_Server_API/app/core/TTS/tts_service_v2.py
- tldw_Server_API/app/core/TTS/utils.py
- tldw_Server_API/app/core/TTS/adapters/*
- tldw_Server_API/app/core/TTS/tts_config.py

---

## 3) Backend: chunking + crossfade merge for long TTS

Scope
- Sentence chunking for long text.
- Crossfade merge between chunks.
- Preserve timestamps/segment metadata if applicable.

Acceptance Criteria
- Long text is split and merged without audible hard cuts.
- Chunks respect max token limits.
- Output audio duration is within tolerance of expected length.

Suggested Files
- tldw_Server_API/app/core/TTS/audio_utils.py
- tldw_Server_API/app/core/TTS/tts_service_v2.py

---

## 4) Backend: silence/truncation detection + retriable errors

Scope
- RMS/peak checks for silent output.
- Trailing-silence truncation detection.
- Raise retriable errors for failed segments.

Acceptance Criteria
- Silent or truncated segments are detected and flagged.
- Retries are triggered for retriable errors.
- Errors are logged with context.

Suggested Files
- tldw_Server_API/app/core/TTS/audio_utils.py
- tldw_Server_API/app/core/TTS/tts_exceptions.py
- tldw_Server_API/app/core/TTS/tts_service_v2.py

---

## 5) Backend: per-segment retry/backoff + error metadata

Scope
- Retry failed segments with backoff.
- Track per-segment error metadata and status.
- Allow partial success.

Acceptance Criteria
- Failed segments retry up to configured max.
- Partial success is returned with error metadata.
- Retry policy is configurable.

Suggested Files
- tldw_Server_API/app/core/TTS/tts_service_v2.py
- tldw_Server_API/app/core/Jobs/*
- tldw_Server_API/app/api/v1/endpoints/audio/audio_jobs.py

---

## 6) Backend: Jobs integration for long-form TTS

Scope
- Wrap long-form TTS in Jobs for pause/resume, progress, and partial results.
- Return job id and artifact list.

Acceptance Criteria
- Long-form requests create Jobs and return job id.
- Partial artifacts are accessible while job runs.
- Jobs expose final status and errors.

Suggested Files
- tldw_Server_API/app/core/Jobs/*
- tldw_Server_API/app/api/v1/endpoints/audio/audio_jobs.py
- tldw_Server_API/app/api/v1/endpoints/audio/audio_tts.py

---

## 7) Backend: progress snapshots + ETA (SSE/WebSocket)

Scope
- Emit progress snapshots with step weights and ETA.
- Provide SSE/WebSocket endpoint for clients.
- Persist snapshots for audit.

Acceptance Criteria
- Clients can subscribe to progress updates.
- ETA updates over time during long jobs.
- Snapshots persist for completed jobs.

Suggested Files
- tldw_Server_API/app/core/Jobs/*
- tldw_Server_API/app/core/Streaming/*
- tldw_Server_API/app/api/v1/endpoints/audio/audio_jobs.py

---

## 8) Backend: per-user TTS history model

Scope
- Create DB table for TTS history with metadata.
- Add query and pagination.
- Attach segment-level metadata.

Acceptance Criteria
- History is stored per user and queryable.
- Includes duration, generation time, params, model, voice_info.
- Supports favorites flag.

Suggested Files
- tldw_Server_API/app/core/DB_Management/*
- tldw_Server_API/app/core/Data_Tables/*
- tldw_Server_API/app/api/v1/endpoints/audio/audio_tts.py
- tldw_Server_API/app/api/v1/endpoints/audio/audio.py

---

## 9) Backend: filename sanitization for artifacts

Scope
- Enforce strict filename sanitization for stored artifacts.
- Block traversal and invalid characters.

Acceptance Criteria
- Unsafe filenames are rejected or sanitized.
- Path traversal attempts fail safely.

Suggested Files
- tldw_Server_API/app/core/Utils/*
- tldw_Server_API/app/core/TTS/utils.py
- tldw_Server_API/app/core/TTS/voice_manager.py

---

## 10) Frontend: multi-step progress UI + ETA

Scope
- Add progress component (steps, counts, ETA).
- Bind to backend progress stream.

Acceptance Criteria
- Progress indicator updates live during long jobs.
- ETA is visible and reasonable.

Suggested Files
- apps/packages/ui/src/components/Option/Speech/SpeechPlaygroundPage.tsx
- apps/packages/ui/src/components/Common/*
- apps/packages/ui/src/services/tldw/TldwApiClient.ts

---

## 11) Frontend: voice cards with role + preview

Scope
- Implement voice cards UI with role selection and preview.
- Validate 1-4 voices.

Acceptance Criteria
- User can select voices, assign roles, and preview audio.
- Validation prevents invalid selections.

Suggested Files
- apps/packages/ui/src/components/Option/Speech/*
- apps/packages/ui/src/components/Option/TTS/VoiceCloningManager.tsx
- apps/packages/ui/src/services/tldw/voice-cloning.ts

---

## 12) Frontend: draft editor + preview for long-form

Scope
- Two-column outline + transcript editor.
- Validation prior to synthesis.

Acceptance Criteria
- Users can edit outline and transcript before TTS.
- Validation errors are shown inline.

Suggested Files
- apps/packages/ui/src/components/Option/Speech/*
- apps/packages/ui/src/components/Common/*

---

## 13) Frontend: history search + favorites

Scope
- Add search box and favorites toggle in Speech Playground history.
- Persist favorites in local storage or backend.

Acceptance Criteria
- History can be filtered by search.
- Favorites persist across sessions.

Suggested Files
- apps/packages/ui/src/components/Option/Speech/SpeechPlaygroundPage.tsx
- apps/packages/ui/src/services/tldw/TldwApiClient.ts

---

## 14) Frontend: Fast/Balanced/Quality presets

Scope
- Preset buttons that map to TTS parameter sets.
- Update current settings on click.

Acceptance Criteria
- Preset selection updates relevant TTS params.
- Preset state is visible to the user.

Suggested Files
- apps/packages/ui/src/hooks/useTtsPlayground.tsx
- apps/packages/ui/src/components/Option/TTS/TtsProviderPanel.tsx
- apps/packages/ui/src/components/Option/Speech/SpeechPlaygroundPage.tsx

---

## 15) Frontend: character count warnings + time estimates

Scope
- Show character count, thresholds, and estimated duration.
- Use same estimation logic as backend where possible.

Acceptance Criteria
- Warnings appear at threshold and limit.
- Estimated duration updates as text changes.

Suggested Files
- apps/packages/ui/src/components/Option/Speech/SpeechPlaygroundPage.tsx
- apps/packages/ui/src/utils/tts.ts

---

## 16) Frontend: history metadata display

Scope
- Show duration, model, voice, params summary in history list.
- Link metadata to detailed view or tooltip.

Acceptance Criteria
- Each history item surfaces metadata.
- Metadata matches backend history record.

Suggested Files
- apps/packages/ui/src/components/Option/Speech/SpeechPlaygroundPage.tsx
- apps/packages/ui/src/services/tldw/TldwApiClient.ts

