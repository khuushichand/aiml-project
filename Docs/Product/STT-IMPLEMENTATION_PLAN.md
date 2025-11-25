## Stage 1: STT Turn Detection (VAD & Commit)
**Goal**: Add Silero VAD–driven turn detection to unified streaming STT and finalize transcripts at end‑of‑speech for lower final latency.
**Success Criteria**: Final transcript latency p50 ≤ 600ms on reference setup; server defaults applied; client tunables accepted; no regression in quotas/auth.
**Tests**:
- Unit: VAD threshold/stop‑secs/mute edge cases; buffering → commit behavior; JSON message handling in WS path.
- Integration: WS stream with synthetic audio pauses triggers timely “final” messages; latency assertions with mocked clock.
**Reference Setup**:
- Hardware/OS: 8‑core CPU, optional NVIDIA GPU (if Parakeet GPU path enabled); macOS 14 or Ubuntu 22.04.
- Runtime: Python 3.11, ffmpeg ≥ 6.0, av ≥ 11.0.0.
- Network: Localhost loopback; no WAN hops.
- Input fixture: 10 s 16 kHz float32 speech with 250 ms trailing silence; single speaker.
**Implementation Notes**:
- VAD engine: Silero VAD.
- Integration point: Unified WS loop (tldw_Server_API/app/core/Ingestion_Media_Processing/Audio/Audio_Streaming_Unified.py:1200) before forwarding to `transcriber.process_audio_chunk`.
- Tunables and bounds (server-validated):
  - `vad_threshold` [0.1..0.9], default 0.5
  - `min_silence_ms` [150..1500], default 250
  - `turn_stop_secs` [0.1..0.75], default 0.2 (guard minimum utterance length 0.4 s)
- Commit mapping: VAD end-of-speech triggers a server-side finalize that emits `{type:"full_transcript"}` equivalent to receiving a client `commit` (see Audio_Streaming_Unified.py:1585).
- Fail-open behavior: if Silero VAD is unavailable or fails to load, continue streaming without auto-commit and log once per session.
**Status**: In Progress (auto-commit wired; fail-open fallback and metrics in place)

**Next Steps**:
- Tune Silero thresholds on reference audio (validate `turn_stop_secs`/`min_silence_ms`/`min_utterance_secs` defaults) and document recommended client values.
- Add end-to-end WS test with synthetic pauses (mocked clock or small sleep) asserting finals arrive within target latency and no duplicate commits.
- Add a brief doc snippet in STT docs describing the new VAD knobs and the fail-open behavior for locked-down envs.

## Stage 2: Latency Metrics (STT/TTS + Voice‑to‑Voice)
**Goal**: Instrument STT end‑of‑speech → final transcript, TTS request → first audio chunk (TTFB), and voice‑to‑voice (EOS → first audio on wire).
**Success Criteria**: New histograms (`stt_final_latency_seconds`, `tts_ttfb_seconds`, `voice_to_voice_seconds`) exported with labels; sampling overhead negligible; visible in metrics registry.
**Tests**:
- Unit: Timer guards, labels, and error‑safe recording; metrics manager registration idempotence.
- Integration: Synthetic pipeline run records non‑zero latencies; counters for stream errors/underruns increment on fault injection.
**Reference Setup**:
- Same as Stage 1.
**Implementation Notes**:
- Metrics registration: add histograms to MetricsRegistry with buckets `[0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5]`.
- Label schema:
  - `stt_final_latency_seconds{model,variant,endpoint="audio_unified_ws"}`
  - `tts_ttfb_seconds{provider,voice,format,endpoint="audio.speech"}`
  - `voice_to_voice_seconds{provider,route}`
- Correlation: propagate `X-Request-Id` if present or generate UUIDv4 on entry to WS/REST; include in logs and internal spans to correlate metrics.
- Label guidance: use `route="audio.speech"` for REST; reserve `audio.stream.tts` (or similar) for future WS TTS to keep series distinct.
**Status**: Done

## Stage 3: TTS PCM Streaming Path
**Goal**: Support `response_format=pcm` end‑to‑end for lowest overhead; document and validate output shape/sample rate.
**Success Criteria**: `/api/v1/audio/speech` streams PCM16 with steady throughput; clients can play without encoder; existing formats unaffected.
**Tests**:
- Unit: PCM branch bypasses container remux; chunk framing stable; samplerate/channels honored.
- Integration: Client consumes PCM stream with no underruns; backpressure respected.
**Reference Setup**:
- Same as Stage 1.
**Implementation Notes**:
- Content‑Type: `audio/L16; rate=<sr>; channels=<n>`; default `rate=24000`, `channels=1`.
- Headers: include `X-Audio-Sample-Rate: <sr>` for clarity.
- Negotiation: Default to provider/sample pipeline rate; optional `target_sample_rate` accepted when supported by adapter.
**Status**: Done

## Stage 4: Phoneme/Lexicon Overrides (Kokoro)
**Goal**: Add configurable phoneme mapping for consistent pronunciation of brand/technical terms.
**Success Criteria**: Config file loaded; mapping applied safely (word boundaries, case handling); feature can be toggled per‑request/provider.
**Tests**:
- Unit: Regex/word‑boundary correctness; idempotence on repeated runs; fallback when map missing.
- Integration: Sample prompts produce expected pronunciations without affecting latency materially.
**Reference Setup**:
- Same as Stage 1.
**Implementation Notes**:
- Schema: YAML or JSON file with entries: `{ term: "OpenAI", phonemes: "oʊ p ən aɪ", lang?: "en", boundary?: true }`.
- Tokenization: apply on word boundaries by default (`boundary: true`), case‑insensitive match with preserve‑case replacement.
- Precedence: per‑request > provider‑level > global; if no match, fall back to provider defaults.
- Config location: `Config_Files/tts_phonemes.{yaml,json}` (startup load; no hot-reload required).
- Validation: reject overlapping/ambiguous terms; cap map size to avoid perf regressions; escape regex-like input where needed.
**Status**: Not Started

**Next Steps**:
- Define config schema and load path (YAML/JSON) for Kokoro phoneme overrides; validate entries and precedence.
- Plumb overrides through Kokoro adapter (ONNX/PT) with word-boundary/case handling; add per-request override passthrough.
- Add unit tests for mapping correctness, boundary handling, and fallback when map missing; add integration sample asserting pronunciation change.

## Stage 5: Docs & Perf Harness
**Goal**: Update docs and add a simple harness to measure voice‑to‑voice latency on a reference setup.
**Success Criteria**: Docs updated (API, config, tuning); harness outputs p50/p90 and basic plots; optional diarization workflow documented.
**Tests**:
- Doc lint/check links; harness dry‑run with synthetic audio; CI smoke job (optional) executes harness in short mode.
**Reference Setup**:
- Same as Stage 1.
**Implementation Notes**:
- Harness location: `Helper_Scripts/voice_latency_harness/` (or `tldw_Server_API/tests/perf/`).
- Outputs: JSON summary (p50/p90 for STT final, TTS TTFB, voice‑to‑voice); optional Prometheus text for CI scrape.
- Fixtures: include the 10 s 16 kHz float32 speech sample and scripts to generate variants (noise/silence).
- Use the existing `voice_to_voice_seconds` metric wiring as the measurement source; harness should pull from metrics or emit its own JSON events if Prom scrape is unavailable.
**Status**: Not Started

**Next Steps**:
- Scaffold a minimal harness script under `Helper_Scripts/voice_latency_harness/` (or `tldw_Server_API/tests/perf/`) that drives STT WS → TTS REST, captures `voice_to_voice_seconds` (from metrics or emitted JSON), and outputs p50/p90.
- Add a short-mode flag for CI (fast synthetic audio, no external deps); gate any real-provider runs behind env flags.
- Document how to run and interpret results; link the harness in STT/TTS docs.
- Define CLI shape, e.g., `python Helper_Scripts/voice_latency_harness/run.py --out out.json --short`; document JSON schema for results.

## Stage 6: WebSocket TTS (Optional)
**Goal**: `/api/v1/audio/stream/tts` PCM16 streaming with backpressure and auth/rate‑limit parity with STT WS.
**Success Criteria**: p50 TTFB ≤ 200 ms on reference; zero underruns on happy path; output parity with REST TTS.
**Tests**:
- Slow reader simulation; disconnects mid‑stream; bounded queue/backpressure behavior; quota enforcement and auth parity.
**Reference Setup**:
- Same as Stage 1.
**Implementation Notes**:
- Auth & quotas: mirror STT WS (API key/JWT, endpoint allowlist, quotas with standardized close codes).
- Frames: client `{type:"prompt", text, voice?, speed?, format?:"pcm"}`; server: binary PCM16 frames (20–40 ms) + `{type:"error", message}`.
- Backpressure: bounded queue; if consumer is slow, throttle generation or drop oldest with metric `audio_stream_underruns_total`.
**Status**: Not Started

**Next Steps**:
- Design WS schema (frames, headers, error codes) to mirror STT WS; add handler under `/api/v1/audio/stream/tts`.
- Reuse `streaming_audio_writer` for PCM framing; ensure backpressure via bounded queue and emit `audio_stream_underruns_total` on drops.
- Add auth/quota parity with STT WS; cover slow reader/disconnect tests and ensure TTFB/underrun metrics are emitted.
- Specify PCM frame size (20–40 ms) and queue depth/backpressure policy (block vs drop-oldest) plus close codes for overload/disconnect.

---

References:
- PRD: `Docs/Product/Realtime_Voice_Latency_PRD.md`
- STT WS: `tldw_Server_API/app/api/v1/endpoints/audio.py:1209`
- Unified STT: `tldw_Server_API/app/core/Ingestion_Media_Processing/Audio/Audio_Streaming_Unified.py`
- TTS: `tldw_Server_API/app/api/v1/endpoints/audio.py:268`, `tldw_Server_API/app/core/TTS/adapters/kokoro_adapter.py`, `tldw_Server_API/app/core/TTS/streaming_audio_writer.py`

Global Negative‑Path Tests:
- Underruns (slow reader), client disconnects, silent input segments, high noise segments, invalid PCM chunk sizes, malformed WS config frames, exceeded quotas → standardized errors and metrics.
