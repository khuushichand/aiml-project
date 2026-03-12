# Qwen3-TTS Setup Runbook

This runbook covers installation, configuration, and operational notes for the runtime-aware Qwen3-TTS adapter.

## Runtime Modes

`qwen3_tts` keeps one public provider key and selects an internal runtime with `providers.qwen3_tts.runtime`.

- `auto`: prefers `mlx` on Apple Silicon macOS and `upstream` elsewhere
- `upstream`: in-process `qwen_tts`
- `mlx`: in-process `mlx-audio`
- `remote`: OpenAI-compatible hosted or sidecar backend

## Capability Matrix

### Upstream
- CustomVoice (9 named speakers + instruction control)
- VoiceDesign (prompted voice creation)
- Base (voice cloning from reference audio)
- Tokenizer encode/decode endpoints

### MLX v1
- Preset-speaker synthesis only
- `stream=true` accepted with buffered fallback chunks
- Uploaded `custom:<voice_id>` voices rejected
- `Base` and `VoiceDesign` rejected

### Remote
- Capabilities depend on the hosted backend
- Health and capability envelopes default to conservative values until `capability_override` is configured

## Install Dependencies

```bash
# Upstream runtime
pip install qwen-tts torch soundfile

# Apple Silicon MLX runtime
pip install mlx mlx-audio
```

If the package name differs in your environment, install from the upstream repo instead.

## Enable the Provider

Edit `tldw_Server_API/Config_Files/tts_providers_config.yaml`:

```yaml
providers:
  qwen3_tts:
    enabled: true
    runtime: "auto"  # auto | upstream | mlx | remote
    model: "auto"  # auto = CustomVoice only
    device: "cuda" # cpu | cuda | mps
    dtype: "float16"
    auto_download: false
    max_text_length: 5000
    stream_chunk_size_ms: 200
    tokenizer_model: "Qwen/Qwen3-TTS-Tokenizer-12Hz"
```

Notes:
- `auto_download` is false by default. Set true only if you want runtime downloads.
- `model: "auto"` is valid only for CustomVoice requests.
- `runtime=mlx` resolves `auto` to preset-speaker synthesis only.

Remote example:

```yaml
providers:
  qwen3_tts:
    enabled: true
    runtime: "remote"
    base_url: "http://127.0.0.1:8001/v1/audio/speech"
    api_key: "${QWEN_REMOTE_API_KEY}"
    capability_override:
      supports_streaming: true
      supports_voice_cloning: true
      supports_emotion_control: false
      supported_modes: ["custom_voice_preset", "voice_clone"]
      supports_uploaded_custom_voices: false
```

## Supported Model IDs

Tokenizer:
- `Qwen/Qwen3-TTS-Tokenizer-12Hz`

TTS models:
- `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice`
- `Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice`
- `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign`
- `Qwen/Qwen3-TTS-12Hz-1.7B-Base`
- `Qwen/Qwen3-TTS-12Hz-0.6B-Base`

## Usage Examples

### CustomVoice (speaker + optional instruction)
```json
{
  "model": "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
  "input": "Hello from Qwen3-TTS.",
  "voice": "Vivian",
  "response_format": "mp3",
  "stream": true,
  "extra_params": {
    "instruct": "Warm and calm delivery."
  }
}
```

This request shape also works on `runtime=mlx` when `voice` is one of the built-in preset speakers.

### VoiceDesign (instruction required)
```json
{
  "model": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
  "input": "Design a new voice sample.",
  "response_format": "wav",
  "stream": false,
  "extra_params": {
    "instruct": "A soft, narrative voice with light rasp."
  }
}
```

`VoiceDesign` is available on `upstream` and on `remote` only if the hosted backend supports it.

### Base Voice Clone (reference audio + optional transcript)
```json
{
  "model": "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
  "input": "Cloned voice output.",
  "response_format": "mp3",
  "stream": true,
  "voice_reference": "<base64 audio>",
  "extra_params": {
    "reference_text": "Transcript of the reference clip."
  }
}
```

Notes:
- `voice_reference` is always required for Base models.
- `extra_params.x_vector_only_mode=true` allows omitting `reference_text` (quality may degrade).
- `reference_duration_min` (seconds) can be provided to enforce a minimum reference clip duration.
- Base models enforce a default 3s minimum reference duration when `reference_duration_min` is omitted.
- `Base` requests are rejected on `runtime=mlx`.

### Voice Clone Prompt Reuse (optional)
You may pass a `voice_clone_prompt` to reuse cached prompt embeddings. Accepted formats:
- base64 string of raw prompt bytes
- `{ "format": "qwen3_tts_prompt_v1", "data_b64": "<base64>" }`

Payload size is limited by `providers.qwen3_tts.voice_clone_prompt_max_kb`.

## Tokenizer Endpoints

Encode audio to tokens:
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/audio/tokenizer/encode" \
  -H "Authorization: Bearer <TOKEN>" \
  -F "file=@/path/to/audio.wav" \
  -F "tokenizer_model=Qwen/Qwen3-TTS-Tokenizer-12Hz"
```

Decode tokens to audio:
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/audio/tokenizer/decode" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"tokens":[1,2,3], "tokenizer_model":"Qwen/Qwen3-TTS-Tokenizer-12Hz", "response_format":"wav"}'
```

Tokenizer endpoints require the `audio.tokenizer` scope.

## Streaming Notes

- Streaming defaults to PCM output; MP3/OPUS/AAC are transcoded in real time when available.
- If real-time transcoding is unavailable, Qwen3 falls back to buffered streaming (collects audio then streams it in chunks).
- `runtime=mlx` always uses buffered streaming fallback in v1.
- WAV streaming emits data only on finalize (WAV headers are written at the end).

## Apple Silicon Validation

Run this smoke test on a real M-series Mac to verify `mlx-audio` model and speaker compatibility:

```bash
source .venv/bin/activate
TLDW_RUN_QWEN3_MLX_INTEGRATION=1 \
QWEN3_MLX_MODEL=mlx-community/Qwen3-TTS-12Hz-0.6B-Base-bf16 \
python -m pytest tldw_Server_API/tests/TTS_NEW/integration/test_qwen3_mlx_runtime_integration.py -v
```

## Troubleshooting

- **Import error: qwen_tts missing**: Install `qwen-tts` or use the upstream repo for your environment.
- **Import error: mlx_audio missing**: Install `mlx` and `mlx-audio` on Apple Silicon, then set `runtime=mlx`.
- **Streaming MP3/OPUS/AAC fails**: Ensure `av` is installed (PyAV). Without it, streaming transcoding is disabled.
- **Base model rejects request**: Base requires `voice_reference`. Use `extra_params.x_vector_only_mode=true` only to skip `reference_text`.
- **MLX rejects uploaded or Base requests**: `runtime=mlx` supports preset-speaker CustomVoice only in v1.
- **Remote health/capabilities look too limited**: Add `capability_override` so the hosted backend advertises its real support.
- **`model="auto"` rejected**: Auto model selection is only for CustomVoice. Set a VoiceDesign/Base model explicitly.

## Useful Files
- Adapter: `tldw_Server_API/app/core/TTS/adapters/qwen3_tts_adapter.py`
- Provider config: `tldw_Server_API/Config_Files/tts_providers_config.yaml`
- PRD: `Docs/Product/Completed/PRD_Qwen3_TTS.md`
