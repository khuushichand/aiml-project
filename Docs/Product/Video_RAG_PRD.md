# Video RAG — PRD (Pipeline Option)

## Overview
- Purpose: add a first-class `video_rag` pipeline that extracts transcript + visual scene captions, builds time-aligned chunks, and indexes them for hybrid RAG retrieval.
- Audience: product, backend, ingestion, search/RAG, WebUI/Next, infra.
- Release: staged behind a feature flag; MVP ships with text+caption chunks (no requirement to retain raw video).

## Goals
- Ingest videos (upload or URL) and produce time-stamped, searchable chunks combining audio transcription with per-scene visual captions.
- Enable hybrid retrieval (BM25 + vector) scoped to specific media or time ranges, returning snippets with timestamps and optional keyframe refs.
- Keep storage lean by default: retain derived artifacts (captions, transcripts, chunks, vectors, keyframes optionally) and make raw video retention configurable.

## Non-Goals
- Full video streaming or editing UI.
- Frame-by-frame dense captioning (MVP is 1 caption per scene).
- Training/fine-tuning vision models.

## Scope (Phases)
- Phase 1 (MVP): scene detection, keyframe captioning via configured VLM, ASR transcription via existing audio stack, chunk assembly + hybrid indexing, retrieval path for `video_rag`, optional keyframe thumbnails; raw video retention optional and disabled by default.
- Phase 2: multi-frame summaries per scene, higher-quality VLMs, configurable caption language/style, lightweight in-app playback hook.
- Phase 3: vision embeddings (if available), OCR overlay fusion, adaptive sampling per motion/entropy, richer analytics.

## Functional Requirements
- Ingest: `POST /api/v1/media/process` accepts `mode=video_rag` (upload or URL). Enforce duration and size limits; reject beyond config caps.
- Scene detection: sample frames at configurable FPS (default 1 fps) using grayscale+resize diff; thresholded changes produce segments with `start_sec`/`end_sec`. Cap scene count; merge tiny scenes.
- Captioning: pick mid-frame per scene, resize, run VLM (e.g., Qwen-VL) with deterministic prompt (temp=0). Clean boilerplate prefixes. Limit tokens (e.g., 60). If VLM unavailable, mark caption as unavailable and continue.
- Transcription: reuse existing ASR providers (Whisper/NeMo/Qwen2Audio). Keep full text and timestamped segments. If ASR unavailable, proceed caption-only.
- Chunking: build `combined_text` per scene (or sub-scene) as:
  ```
  [Time 00:01:23–00:01:35]
  Visual: {scene_caption}
  Audio: {transcript_slice}
  ```
  Include metadata: `media_id`, `segment_id`, `start_sec`, `end_sec`, `scene_caption`, `transcript_text`, `source="video"`, optional `frame_ref`, `confidence` from ASR.
- Chunk sizing: cap per-chunk duration (e.g., 30–60s) and transcript token length; split long scenes into overlapping windows to avoid bloated embeddings/FTS entries. Reject or fragment inputs that exceed limits.
- Indexing: store chunks in Media DB (FTS) and Chroma vectors (text embeddings). Hybrid search remains supported (BM25 + vector). Add covering indexes on (`media_id`, `start_sec`, `end_sec`) and FTS over `combined_text`.
- Retrieval: `mode=video_rag` in RAG search filters by `media_id` and optional time range; return ranked chunks with timestamps, captions, transcript slice, and frame_ref if present. Ordering follows existing hybrid semantics.
- Storage policy: default to discard raw video after processing; make retention configurable. Always retain derived artifacts (captions/transcripts/chunks/vectors) and optional keyframe thumbnails.
- Feature flag: gate end-to-end with `VIDEO_RAG_ENABLED`; require configured VLM/ASR providers. Expose safe fallbacks (caption-only or transcript-only).

## Non-Functional Requirements
- Performance: sampling and VLM runs bounded by FPS, scene cap, and max duration (default 90 min). Concurrency obeys existing job slots/rate limits.
- Resource use: clean temp frames; avoid keeping full video in memory; stream via ffmpeg where possible.
- Reliability: fall back gracefully when VLM/ASR unavailable; still produce usable chunks.
- Observability: counters/gauges for scene_count, caption_latency, asr_latency, fallback paths; log media_id and timings.

## Data Model
- Extend/reuse content chunks table with video-specific metadata: `media_id`, `segment_id`, `start_sec`, `end_sec`, `scene_caption`, `transcript_text`, `combined_text`, `source="video"`, `frame_ref` (optional), `confidence`, `client_id`, soft-delete flags.
- Indexes: covering indexes on (`media_id`, `start_sec`, `end_sec`); FTS on `combined_text`; vector store rows keyed by chunk id.
- Optional table for `video_scenes` if we need to persist raw segments separate from chunks; follows same client_id and soft-delete rules.

## Algorithms (MVP defaults)
- Scene detection: grayscale → resize (e.g., 64x64) → L1 diff vs previous sampled frame at 1 fps; threshold ~0.2; merge scenes shorter than a few seconds.
- Captioning: mid-point frame per scene, deterministic prompt, temp=0, max_tokens ~60; strip leading “this image shows…” etc.
- Transcript alignment: if transcript segments overlap a scene, include that text; for long scenes, split transcript slices by overlap windows.
- Hybrid retrieval: reuse existing BM25/vector pipeline; use `combined_text` for both FTS and embeddings.

## API Surface
- Ingest: `POST /api/v1/media/process` with `mode=video_rag`, limits enforced; returns `media_id`, scene_count, chunk_count, retention flag.
- Browse: `GET /api/v1/media/{media_id}/chunks` (optional time filters) to inspect video chunks.
- Search: `POST /api/v1/rag/search` with `mode=video_rag`, `media_id`, optional `time_range`, standard hybrid params; returns chunks with timestamps, captions, transcript slices.
- Config: expose `VIDEO_RAG_ENABLED`, `VIDEO_RAG_MAX_DURATION_MIN`, `VIDEO_RAG_SCENE_FPS`, `VIDEO_RAG_SCENE_THRESHOLD`, `VIDEO_RAG_MAX_SCENES`, `VIDEO_RAG_VLM_MODEL`, `VIDEO_RAG_ASR_MODEL`, `VIDEO_RAG_RETAIN_ORIGINAL` (bool), `VIDEO_RAG_KEYFRAMES` (bool).

## UX Notes (Web/Extension)
- Ingest option “Video (RAG)” with duration and retention hints.
- Search results show timestamp badges, short caption + transcript snippet, and “jump to time” link only when video/keyframes are retained and a playable URL exists; hide/disable when retention is off.
- Detail view lists scenes chronologically with captions; allow filtering by time window.
- Fallback messaging when visual captions are unavailable.

## Security & Permissions
- Enforce per-user/tenant isolation on media/chunk access via `client_id` checks.
- Respect existing rate limits and auth deps on ingest/search endpoints.
- If raw video or keyframes are retained, apply the same storage/ACL rules as other media; ensure temp files and thumbnails follow retention/TTL when “discard after ingest” is enabled.

## Rollout & Testing
- Feature-flagged rollout (`VIDEO_RAG_ENABLED` off by default).
- Tests: scene detection bounds; ingest end-to-end producing chunks; retrieval filters by media/time; fallbacks (VLM off → transcript-only, ASR off → caption-only); temp cleanup; hybrid ordering remains stable.
- Operational checklist: configure VLM/ASR providers; set duration/scene caps; decide retention policy; monitor scene_count and latency metrics on initial runs.
- Execution model: long-running video processing runs asynchronously via the existing job queue; `POST /api/v1/media/process` returns a job/media handle and status can be polled. Respect per-tenant concurrency/queue caps.

## Open Questions
- Which VLMs to support by default (Qwen-VL vs lighter models) and acceptable latency targets?
- Do we ship keyframe thumbnails by default or make them opt-in only?
- Do we need OCR fusion for slides/diagrams in the first release?
