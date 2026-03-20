# Setup: Supertonic ONNX TTS

This guide walks through installing Supertonic ONNX assets, enabling the provider, and smoke‑testing the API.

## 1) Prepare assets
Use the installer helper (requires git + git-lfs):
```
python Helper_Scripts/TTS_Installers/install_tts_supertonic.py
```
What it does:
- Clones `https://huggingface.co/Supertone/supertonic`
- Copies ONNX models into `models/supertonic/onnx`
- Copies voice style JSONs into `models/supertonic/voice_styles`
- Prints a config snippet for `tts_providers_config.yaml`

Optional flags:
- `--repo-url <url>` override source repo
- `--base-dir <path>` base install dir (default: models/supertonic)
- `--overwrite` replace existing files
- `--keep-clone` leave the clone on disk

## 2) Enable in config
Edit `tldw_Server_API/Config_Files/tts_providers_config.yaml`:
```yaml
providers:
  supertonic:
    enabled: true
    model_path: "models/supertonic/onnx"
    sample_rate: 24000
    device: "cpu"
    extra_params:
      voice_styles_dir: "models/supertonic/voice_styles"
      default_voice: "supertonic_m1"
      voice_files:
        supertonic_m1: "M1.json"
        supertonic_f1: "F1.json"
      default_total_step: 5
      default_speed: 1.05
      n_test: 1
```

## 3) Run the server
From repo root:
```
python -m uvicorn tldw_Server_API.app.main:app --reload
```

## 4) Smoke tests
Include your auth header (examples use `X-API-KEY`):

- Provider inventory (capabilities):
  `curl -s http://127.0.0.1:8000/api/v1/audio/providers -H "X-API-KEY: <key>" | jq .providers.supertonic`

- Voice catalog:
  `curl -s http://127.0.0.1:8000/api/v1/audio/voices/catalog -H "X-API-KEY: <key>" | jq .supertonic`

- Non-streaming MP3:
  `curl -o supertonic.mp3 -X POST http://127.0.0.1:8000/api/v1/audio/speech -H "X-API-KEY: <key>" -H "Content-Type: application/json" -d '{"model":"tts-supertonic-1","input":"Hello from Supertonic","voice":"supertonic_m1","response_format":"mp3","stream":false}'`

- Streaming WAV (chunked):
  `curl --no-buffer -X POST http://127.0.0.1:8000/api/v1/audio/speech -H "X-API-KEY: <key>" -H "Content-Type: application/json" -d '{"model":"tts-supertonic-1","input":"Streaming from Supertonic","voice":"supertonic_m1","response_format":"wav","stream":true}' > supertonic_stream.wav`

If you see HTTP 500s, check logs for missing model/style files or mismatched paths.

## Common pitfalls
- Auth header missing: add `-H "X-API-KEY: <key>"` (or your Bearer token header).
- Newlines in JSON: keep the request body on a single line or use `--data-binary @file.json`; embedded newlines trigger JSON decode errors.
- Missing metadata files: ensure `models/supertonic/onnx` contains `duration_predictor.onnx`, `text_encoder.onnx`, `vector_estimator.onnx`, `vocoder.onnx`, `tts.json`, and `unicode_indexer.json`.
- Wrong config path: confirm you edited `tldw_Server_API/Config_Files/tts_providers_config.yaml` and set `providers.supertonic.enabled: true`.
- Stale server process: restart after changing config or installing assets.
