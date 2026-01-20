# PocketTTS ONNX Provider Design

## Goal
Add a local PocketTTS ONNX provider to the unified TTS module with voice cloning and streaming support.

## Scope
- New adapter wired into the TTS registry and model mapping.
- YAML configuration block and provider metadata for validation and voice uploads.
- Documentation updates for setup and voice cloning requirements.
- Unit tests covering adapter capabilities and model-name mapping.

## Integration Points
- `tldw_Server_API/app/core/TTS/adapters/pocket_tts_adapter.py` implements the `TTSAdapter` interface.
- `tldw_Server_API/app/core/TTS/adapter_registry.py` registers the provider enum and model aliases.
- `tldw_Server_API/app/core/TTS/tts_validation.py` adds provider-specific limits and supported formats.
- `tldw_Server_API/app/core/TTS/voice_manager.py` + `audio_utils.py` include PocketTTS voice reference constraints.

## Configuration
YAML (example):
```yaml
providers:
  pocket_tts:
    enabled: true
    model_path: "models/pocket_tts_onnx/onnx"
    tokenizer_path: "models/pocket_tts_onnx/tokenizer.model"
    module_path: "models/pocket_tts_onnx"
    precision: "int8"
    device: "auto"
    temperature: 0.7
    lsd_steps: 10
```

## Voice Reference Handling
- Requires `voice_reference` bytes (base64 string accepted at the API layer).
- Audio is optionally validated and converted to 24kHz WAV when tooling is available.
- Duration guidance: 1–60 seconds, single-speaker, clean speech.

## Dependencies
Primary runtime dependencies:
- `pocket-tts-onnx` module (downloaded from the HuggingFace repo; see installer script)
- `onnxruntime` (or `onnxruntime-gpu`)
- `soundfile`, `sentencepiece`, `scipy`

Installer helper:
- `Helper_Scripts/TTS_Installers/install_tts_pocket_tts_onnx.py`

## Tests
- Mock/unit tests for capabilities and model-name mapping under `tldw_Server_API/tests/TTS/adapters/`.

## Risks / Follow-Ups
- If ffmpeg/librosa are unavailable, audio conversion may be skipped; callers should provide WAV for best results.
- Optional future work: cache voice embeddings per stored voice reference for faster inference.
