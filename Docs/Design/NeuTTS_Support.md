# NeuTTS Support Design

## Overview

Integrate NeuTTS (Nano/Air) into the existing TTS adapter framework with offline-first defaults, stored voice references, and GGUF-only streaming. This design complements `Docs/Product/PRD_NeuTTS.md` and focuses on implementation details and integration points.

## Key Decisions

- NeuTTS uses stored `custom:<voice_id>` references by default; per-request reference audio/text remains optional.
- Streaming is limited to GGUF backbones and PCM output; WAV streaming is rejected.
- A bundled default voice is registered on first use from `/Helper_Scripts/Audio/Sample_Voices/Sample_Voice_1.mp3`.
- Default voice reference text is loaded from a sidecar `Sample_Voice_1.txt` when available.
- Auto-encode NeuTTS reference codes when reference text is provided on upload.

## Integration Points

- **Adapter registry**: Map `neutts-nano`/`neutts-air` model aliases (including GGUF) to the NeuTTS adapter.
- **Validation**: Add `neutts` to supported languages, formats, and text length limits.
- **Adapter**: Enforce GGUF-only streaming and PCM-only streaming output.
- **Voice manager**:
  - Store `reference_text` and `ref_codes` metadata in per-user voice metadata.
  - Auto-encode on upload when `reference_text` is present.
  - Register a default voice per user on first use.

## Data Storage

- Voice files: `<user_db_base_dir>/<user_id>/voices/processed`
- Metadata: `<user_db_base_dir>/<user_id>/voices/metadata/<voice_id>.json`
- Default voice assets live in `/Helper_Scripts/Audio/Sample_Voices/`.

## Streaming Constraints

- Only GGUF backbones support NeuTTS streaming.
- PCM s16le at 24kHz is the default streaming format.
- WAV streaming is disallowed due to header finalization requirements.

## Rollout Notes

- Auto-download remains disabled by default; local paths required unless explicitly enabled.
- Default voice registration is best-effort and should not block non-default voice usage.
