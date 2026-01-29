# NeMo Multitalk Diarization Backend

## Summary
Add an optional diarization backend that couples speaker diarization to NVIDIA NeMo Multitalker Parakeet ASR (Sortformer + multitalker streaming). This backend produces speaker-tagged segments in a single pass and is used only for offline transcription flows (no WebSocket streaming support).

## Goals
- Provide a Parakeet-coupled diarization path that mirrors the `Parakeet_Multitalk` implementation.
- Keep the existing embedding-based diarization as the default backend.
- Maintain backward compatibility for current `diarize=True` flows.

## Non-Goals
- Streaming diarization in WebSocket/real-time paths.
- Changing the public API surface beyond configuration.

## Configuration Changes
New/extended keys under the `Diarization` config section:

- `backend` (str): `embedding` (default) or `nemo_multitalk`.
- `nemo_multitalk_asr_model` (str): default `nvidia/multitalker-parakeet-streaming-0.6b-v1`.
- `nemo_multitalk_diar_model` (str): default `nvidia/diar_streaming_sortformer_4spk-v2.1`.
- `nemo_multitalk_device` (str): `auto` (default), `cpu`, or `cuda`.
- `nemo_multitalk_cache_dir` (str|None): optional cache directory; falls back to STT `nemo_cache_dir` when unset.
- `nemo_multitalk_max_speakers` (int): default 4.
- `nemo_multitalk_disable_cuda_graphs` (bool): default True.

Defaults are set in `tldw_Server_API/app/core/config.py` and merged into runtime config.

## Behavior Changes
- When `diarize=True` **and** `backend=nemo_multitalk` **and** the STT provider resolves to Parakeet, the transcription path uses NeMo multitalk diarization directly.
- If provider is not Parakeet or NeMo dependencies are missing, the system falls back to the existing embedding-based diarization.
- Output segments include: `Text`, `start_seconds`, `end_seconds`, `speaker_id`, `speaker_label`, and `segment_id` (plus `start`/`end` convenience fields).

## Implementation Notes
- New backend module: `tldw_Server_API/app/core/Ingestion_Media_Processing/Audio/Diarization_Nemo_Multitalk.py`.
- Integration point: `perform_transcription` in `Audio_Transcription_Lib.py`.
- Audio is already 16kHz mono via `convert_to_wav`; the backend uses NeMo streaming utilities to generate diarized segments.

## Tests
- `tests/Audio/test_nemo_multitalk_diarization.py` covers:
  - Segment normalization/mapping.
  - Selection of the multitalk backend when configured.
