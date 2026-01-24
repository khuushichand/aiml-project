# Qwen3-TTS Setup Runbook

This runbook covers installation, configuration, and operational notes for the local Qwen3-TTS adapter.

## What You Get
- CustomVoice (9 named speakers + instruction control)
- VoiceDesign (prompted voice creation)
- Base (voice cloning from reference audio)
- Tokenizer encode/decode endpoints

## Install Dependencies

```bash
pip install qwen-tts torch soundfile
```

If the package name differs in your environment, install from the upstream repo instead.

## Enable the Provider

Edit `tldw_Server_API/Config_Files/tts_providers_config.yaml`:

```yaml
providers:
  qwen3_tts:
    enabled: true
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
- WAV streaming emits data only on finalize (WAV headers are written at the end).

## Troubleshooting

- **Import error: qwen_tts missing**: Install `qwen-tts` or use the upstream repo for your environment.
- **Streaming MP3/OPUS/AAC fails**: Ensure `av` is installed (PyAV). Without it, streaming transcoding is disabled.
- **Base model rejects request**: Base requires `voice_reference`. Use `extra_params.x_vector_only_mode=true` only to skip `reference_text`.
- **`model="auto"` rejected**: Auto model selection is only for CustomVoice. Set a VoiceDesign/Base model explicitly.

## Useful Files
- Adapter: `tldw_Server_API/app/core/TTS/adapters/qwen3_tts_adapter.py`
- Provider config: `tldw_Server_API/Config_Files/tts_providers_config.yaml`
- PRD: `Docs/Product/PRD_Qwen3_TTS.md`
