# STT Parakeet MLX Parity Design

## Scope
This design captures the Parakeet MLX parity upgrades added to the server STT stack, including:
- Structured MLX transcription artifacts (text, timed segments, tokens).
- Native MLX streaming session integration for incremental decode.
- Long-audio chunk merge improvements using token/timestamp-aware stitching.
- Configurable MLX decoding and sentence-splitting controls.

## Goals
- Preserve upstream `parakeet-mlx` alignment metadata through ingestion and API formatting.
- Keep backward compatibility for existing string-based transcription call paths.
- Reduce duplicate/omitted text in overlap regions for buffered and streaming paths.
- Avoid runtime dependency installation side effects in request paths.

## Non-Goals
- Replacing existing non-MLX providers.
- Introducing new API response schemas.
- Altering authentication or quota behavior for audio endpoints.

## Architecture
### Batch/Buffered
- `Audio_Transcription_Parakeet_MLX.py` now normalizes MLX outputs into a structured artifact.
- `Audio_Buffered_Transcription.py` merges chunk outputs with overlap-aware token logic.
- `Audio_Transcription_Lib.py` converts structured artifacts into provider-neutral segment outputs.

### Streaming
- `Parakeet_Core_Streaming/transcriber.py` uses MLX streaming sessions when available.
- Session lifecycle hooks are exposed (`reset_session`, `close`) and called from transcriber reset/close and WS teardown paths.
- Fallback remains functional if MLX streaming session creation fails.

### API Formatting
- `/audio/transcriptions` can consume provider-timed segments beyond faster-whisper-only handling.
- SRT/VTT/verbose JSON formats use real provider timing when available.

## Configuration
The `[STT-Settings]` section adds/uses:
- `mlx_model_id`, `mlx_cache_dir`
- `mlx_decoding_mode`
- `mlx_beam_size`, `mlx_length_penalty`, `mlx_patience`, `mlx_duration_reward`
- `mlx_sentence_max_words`, `mlx_sentence_silence_gap`, `mlx_sentence_max_duration`
- `mlx_stream_context_left`, `mlx_stream_context_right`, `mlx_stream_depth`
- `mlx_stream_keep_original_attention`
- `streaming_fallback_to_whisper`

## Error Handling
- MLX load/decode failures return explicit error text in wrapper paths.
- Core STT library raises a dedicated `STTTranscriptionError` for provider failures in Parakeet paths.
- Optional MLX imports in unified streaming degrade gracefully to no-op fallbacks.

## Verification
Targeted tests cover:
- Structured artifact propagation and timing normalization.
- Streaming session lifecycle and fallback behavior.
- Non-16kHz structured long-audio resampling.
- Timed segment API formatting for SRT/VTT/verbose JSON.
- Deterministic model default selection behavior in MLX tests.
