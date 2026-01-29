# LuxTTS Getting Started

LuxTTS is a lightweight ZipVoice-based voice‑cloning TTS model that generates 48kHz audio. This guide walks you through installing LuxTTS, enabling it in tldw_server, and making your first request.

## Prerequisites

- Python environment used by tldw_server (same venv recommended)
- FFmpeg available on PATH (recommended for audio conversions)
- A 3–10s clean reference audio clip (WAV/MP3/FLAC/OGG/M4A)

## 1) Install LuxTTS

From the repo root:

```bash
# Clone LuxTTS next to this repo (recommended)
git clone https://github.com/ysharma3501/LuxTTS.git

# Install LuxTTS dependencies into the same env as tldw_server
pip install -r LuxTTS/requirements.txt
```

## 2) Cache the model (offline-friendly)

LuxTTS defaults to `YatharthS/LuxTTS` on Hugging Face. Cache it once so runtime stays offline:

```bash
python - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download(repo_id="YatharthS/LuxTTS")
print("LuxTTS model cached")
PY
```

### Model cache location

By default, Hugging Face caches models under:

- macOS/Linux: `~/.cache/huggingface/hub`
- Windows: `%USERPROFILE%\\.cache\\huggingface\\hub`

You can override the cache root with `HF_HOME`, e.g.:

```bash
export HF_HOME=/path/to/hf_cache
```

## 3) Enable LuxTTS in config

Edit `tldw_Server_API/Config_Files/tts_providers_config.yaml`:

```yaml
providers:
  lux_tts:
    enabled: true
    model: "YatharthS/LuxTTS"
    module_path: "LuxTTS"   # path to your LuxTTS checkout
    device: "auto"          # auto | cpu | cuda
    threads: 4
    sample_rate: 48000
    reference_sample_rate: 24000
    extra_params:
      prompt_duration: 5
      prompt_rms: 0.001
      num_steps: 4
      guidance_scale: 3.0
      t_shift: 0.5
      return_smooth: false
```

Notes:
- The `extra_params` defaults above match the LuxTTS repo defaults.
- If `module_path` is different, point it at your LuxTTS checkout.

### CPU-only baseline config

Use this if you want a minimal CPU setup:

```yaml
providers:
  lux_tts:
    enabled: true
    model: "YatharthS/LuxTTS"
    module_path: "LuxTTS"
    device: "cpu"
    threads: 4
    sample_rate: 48000
    reference_sample_rate: 24000
```

## 4) Make a request

LuxTTS requires `voice_reference` (base64 audio). Example using `curl`:

```bash
VOICE_B64=$(python - <<'PY'
import base64
from pathlib import Path
print(base64.b64encode(Path("/path/to/ref.wav").read_bytes()).decode("utf-8"))
PY
)

curl -X POST "http://127.0.0.1:8000/api/v1/audio/speech" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d @- <<JSON
{
  "model": "lux_tts",
  "input": "Hello from LuxTTS.",
  "voice_reference": "${VOICE_B64}",
  "response_format": "wav",
  "stream": false
}
JSON
```

### Sample request (raw JSON)

```json
{
  "model": "lux_tts",
  "input": "Hello from LuxTTS.",
  "voice_reference": "<base64 audio>",
  "response_format": "wav",
  "stream": false,
  "extra_params": {
    "prompt_duration": 5,
    "prompt_rms": 0.001,
    "num_steps": 4,
    "guidance_scale": 3.0,
    "t_shift": 0.5,
    "return_smooth": false
  }
}
```

### Streaming example (chunked)

```bash
curl -N -X POST "http://127.0.0.1:8000/api/v1/audio/speech" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d @- <<JSON
{
  "model": "lux_tts",
  "input": "Streaming LuxTTS.",
  "voice_reference": "${VOICE_B64}",
  "response_format": "pcm",
  "stream": true,
  "extra_params": {
    "stream_chunk_samples": 8192
  }
}
JSON
```

## 5) Reference audio tips

- Minimum 3s, ideally 3–10s for best results.
- Keep it clean: avoid background noise and music.
- LuxTTS uses a 24kHz prompt pipeline; the adapter auto‑converts reference audio.

## Troubleshooting

- **`LuxTTS module could not be imported`**: set `module_path` to the LuxTTS checkout.
- **`model not cached`**: run the cache step or set a local `model` path.
- **`voice_reference ... not valid`**: make sure it’s a real audio file and base64‑encoded.
- **Performance**: set `device: cuda` for GPU, `device: cpu` for fallback.

### Troubleshooting checklist

- LuxTTS repo cloned and `module_path` points to it
- `pip install -r LuxTTS/requirements.txt` ran in the same env as tldw_server
- Model cached under `~/.cache/huggingface/hub` (or `HF_HOME`)
- Reference audio is 3–10s, clean, and base64‑encoded
- `providers.lux_tts.enabled=true` in `tts_providers_config.yaml`
- Running on CPU? Expect slower generation; reduce `num_steps` if needed

## Optional: Integration smoke test

```bash
RUN_LUXTTS_INTEGRATION=1 \
LUX_TTS_MODULE_PATH=/path/to/LuxTTS \
python -m pytest -v tldw_Server_API/tests/TTS_NEW/integration/test_luxtts_integration.py
```

If using a local model path:
```bash
RUN_LUXTTS_INTEGRATION=1 \
LUX_TTS_MODULE_PATH=/path/to/LuxTTS \
LUX_TTS_MODEL_PATH=/path/to/model_cache \
python -m pytest -v tldw_Server_API/tests/TTS_NEW/integration/test_luxtts_integration.py
```
