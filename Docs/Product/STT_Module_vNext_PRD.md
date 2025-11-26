**STT Module vNext / TODO PRD (Draft)**

- **Relationship to Existing Docs**
  - This document captures *future* STT work that was intentionally trimmed out of `Docs/Product/STT_Module_PRD.md` to keep that PRD aligned with the current implementation.
  - It should be read alongside:
    - `Docs/Product/STT_Module_PRD.md` (current STT behavior and near-term goals).
    - `Docs/Product/Realtime_Voice_Latency_PRD.md` (end-to-end voice latency, WS TTS, and metrics).

- **Status**
  - Owner: Core Voice & API Team
  - Status: Draft / backlog (not yet scheduled)

- **vNext Themes**
  - Richer WebSocket control/status protocol for STT.
  - Transcript versioning and run history in Media DB v2.
  - Enhanced streaming diagnostics (auto-commit / VAD / diarization flags).
  - Explicit retention/PII controls for audio and transcripts.
  - Finer-grained STT metrics series for dashboards.

- **1. Rich WS Control & Status Protocol (Future)**
  - Goal: allow clients to explicitly pause, resume, and stop streaming, with clear server acknowledgments and bounded backpressure behavior.
  - Proposed client → server control frames:
    - JSON frames of the form: `{ "type": "control", "action": "pause" | "resume" | "stop" | "commit" }`.
    - `pause`: stop accepting/queuing new audio until `resume`.
    - `resume`: re-enable processing; queued audio (if any) is processed according to the backpressure policy.
    - `stop`: server flushes any pending finals, sends a completion marker, and closes the WS.
    - `commit`: force a final transcript for the current utterance (even without VAD trigger).
  - Proposed server → client frames:
    - Status acknowledgments: `{ "type": "status", "state": "paused" | "resumed" }` (idempotent).
    - Control errors: `{ "type": "error", "error_type": "invalid_control", "message": "..." }`.
    - Backpressure warnings (when paused queue exceeds limit): `{ "type": "warning", "warning_type": "audio_dropped_during_pause", "message": "..." }`.
  - Compatibility:
    - Existing `auth` / `config` / `audio` / `commit` messages remain valid.
    - New control/status/warning frames must be additive and safe for older clients that ignore unknown `type` values.
  - Open design items:
    - Exact frame fields and allowed sequences.
    - Whether to introduce protocol versioning for clients that want the richer control surface.

- **2. Transcript Versioning & Run History (Future)**
  - Goal: make transcript history explicit and append-only, with a clear notion of “runs” and which run is the effective/default for a given media item.
  - Proposed schema evolution for `Transcripts` (Media DB v2):
    - Introduce a `transcription_run_id` column and use `(media_id, transcription_run_id)` as the logical key for runs (append-only).
    - Keep `whisper_model` (or a normalized provider/model identifier) for indexing and compatibility.
    - Maintain existing soft-delete and versioning semantics (e.g., `version`, `prev_version`, `deleted`, `merge_parent_uuid`).
  - Proposed ingestion contract changes:
    - Ingestion result JSON includes:
      - `latest_run_id`: the run id considered “current” or default for the media item.
      - `supersedes`: optional run id that the new run replaces (for idempotent re-runs).
    - Downstream consumers (RAG, notebooks) use `latest_run_id` when they need the default transcript; advanced tools may navigate the full run history.
  - Migration considerations:
    - Backfill existing transcripts with a synthetic `transcription_run_id` (e.g., 1).
    - Maintain compatibility with existing code that keys on `(media_id, whisper_model)` until all callers are updated.

- **3. Enhanced Streaming Diagnostics (Future)**
  - Goal: give clients and operators more insight into why/when a final transcript was emitted and which features were active.
  - Proposed additional fields on final WS transcript messages:
    - `auto_commit`: `true` when the final was emitted due to server-side VAD/turn detection; `false` when the client explicitly sent `commit` or closed.
    - `vad_status`: enum/string such as `"enabled"`, `"disabled"`, `"fail_open"` (VAD unavailable) for the session.
    - `diarization_status`: enum/string such as `"enabled"`, `"disabled"`, `"unavailable"`, optionally with a small `details` sub-object when initialization fails.
  - Implementation notes:
    - These fields would be added to the existing `final`/`full_transcript` frames in the unified WS STT implementation.
    - When VAD/diarization are not in use, fields may be omitted or set to `"disabled"`.
  - Compatibility:
    - Fields are additive and optional; older clients that don’t care about diagnostics can ignore them.

- **4. Retention & PII Controls (Future)**
  - Goal: provide first-class configuration for how long raw audio is retained (if at all) and to support optional PII redaction for transcripts.
  - Proposed environment/config flags (names subject to change in final design):
    - `STT_DELETE_AUDIO_AFTER` (bool):
      - When `true` (recommended default in production), delete any persisted raw audio immediately after successful transcription unless a workflow explicitly opts in to retention (e.g., diarization auditing).
    - `STT_AUDIO_RETENTION_HOURS` (int/float):
      - Maximum retention window for raw audio when it is stored (e.g., for diarization or QA); default `0` (no retention) in production.
    - `STT_REDACT_PII` (bool or enum; experimental):
      - When enabled, run transcripts through a redaction pass that masks configured PII categories before persistence and/or API response.
  - Documentation requirements:
    - Clearly mark any PII redaction as best-effort, not a hard compliance guarantee.
    - Document performance/accuracy implications of redaction, especially for RAG.
  - Integration points:
    - Audio ingestion pipeline for retention.
    - Result normalization/persistence layer for transcript redaction.

- **5. Fine-Grained STT Metrics (Future)**
  - Goal: complement the already-implemented latency metrics with request/session-level counters and queue/streaming latency histograms specific to STT.
  - Proposed new metrics (names and labels subject to metrics team review):
    - Counters:
      - `audio.stt.requests{endpoint,provider,model,status}`:
        - Total STT requests via REST and WS (REST ingestion, OpenAI-compatible, unified WS).
      - `audio.stt.streaming_sessions{provider}`:
        - Number of WS streaming sessions started/closed.
      - `audio.stt.errors{endpoint,provider,reason}`:
        - Categorized error counts (auth, quota, provider_error, model_unavailable, etc.).
    - Histograms:
      - `audio.stt.latency{endpoint,provider,model}`:
        - End-to-end STT request latency (REST: request → final transcript).
      - `audio.stt.queue_wait{endpoint}`:
        - Time spent waiting in Jobs queues before STT processing begins.
      - `audio.stt.streaming_token_latency{provider,model}`:
        - Time from audio arrival to partial token/segment emission in WS STT.
  - Interaction with existing metrics:
    - These metrics would be in addition to the already registered:
      - `stt_final_latency_seconds{model,variant,endpoint}`
      - `tts_ttfb_seconds{provider,voice,format}`
      - `voice_to_voice_seconds{provider,route}`
    - The vNext metrics focus on counting and queue/streaming behavior, not replacing the latency histograms.

- **6. Out-of-Scope / To Be Designed Elsewhere**
  - Breaking protocol changes for existing WS clients (e.g., mandatory control frames) are explicitly out of scope here; any such changes must go through a separate versioning/compatibility design.
  - Major schema changes to Media DB v2 beyond transcript run history should be captured in a dedicated DB migration PRD/design.
  - Full-fledged PII/COMPLIANCE frameworks (classification, policy engines) are considered separate projects; this doc only tracks a minimal set of STT-specific knobs.

- **Next Steps**
  - For each theme above, decide whether it:
    - Becomes a Stage in `STT-IMPLEMENTATION_PLAN.md` (with tests and success criteria), or
    - Moves into a more focused PRD (e.g., “Transcript Versioning PRD”, “STT Retention & Privacy PRD”).
  - When a theme is scheduled, update:
    - `STT_Module_PRD.md` with a short, high-level requirement.
    - The relevant design doc with detailed schema/protocol changes and migration plans.

