# Setup: Supertonic2 ONNX TTS

This guide walks through installing Supertonic2 ONNX assets, enabling the provider, and smoke-testing the API.
Supported languages: en, ko, es, pt, fr (use `lang_code` in requests).

## 1) Prepare assets
Use the installer helper (requires git + git-lfs):
```
python Helper_Scripts/TTS_Installers/install_tts_supertonic2.py
```
What it does:
- Clones `https://huggingface.co/Supertone/supertonic-2`
- Copies ONNX models into `models/supertonic2/onnx`
- Copies voice style JSONs into `models/supertonic2/voice_styles`
- Updates `tldw_Server_API/Config_Files/tts_providers_config.yaml`
- Prints a config snippet for reference

Skip config edits:
```
python Helper_Scripts/TTS_Installers/install_tts_supertonic2.py --no-config-update
```

Manual alternative:
Download the Supertonic2 ONNX assets from:
`https://huggingface.co/Supertone/supertonic-2`

Place files into the following layout:
- `models/supertonic2/onnx/`
  - `duration_predictor.onnx`
  - `text_encoder.onnx`
  - `vector_estimator.onnx`
  - `vocoder.onnx`
  - `tts.json`
  - `unicode_indexer.json`
- `models/supertonic2/voice_styles/`
  - `M1.json`
  - `F1.json`
  - (any other voice style JSON files you want to expose)

## 2) Enable in config
Edit `tldw_Server_API/Config_Files/tts_providers_config.yaml`:
```yaml
providers:
  supertonic2:
    enabled: true
    model_path: "models/supertonic2/onnx"
    sample_rate: 24000
    device: "cpu"
    extra_params:
      voice_styles_dir: "models/supertonic2/voice_styles"
      default_voice: "supertonic2_m1"
      voice_files:
        supertonic2_m1: "M1.json"
        supertonic2_f1: "F1.json"
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
  `curl -s http://127.0.0.1:8000/api/v1/audio/providers -H "X-API-KEY: <key>" | jq .providers.supertonic2`

- Voice catalog:
  `curl -s http://127.0.0.1:8000/api/v1/audio/voices/catalog -H "X-API-KEY: <key>" | jq .supertonic2`

- Non-streaming MP3 (English):
  `curl -o supertonic2.mp3 -X POST http://127.0.0.1:8000/api/v1/audio/speech -H "X-API-KEY: <key>" -H "Content-Type: application/json" -d '{"model":"tts-supertonic2-1","input":"Hello from Supertonic2","voice":"supertonic2_m1","response_format":"mp3","stream":false}'`

- Streaming WAV (Korean example):
  `curl --no-buffer -X POST http://127.0.0.1:8000/api/v1/audio/speech -H "X-API-KEY: <key>" -H "Content-Type: application/json" -d '{"model":"tts-supertonic2-1","input":"Annyeonghaseyo. Supertonic2 test.","voice":"supertonic2_m1","response_format":"wav","stream":true,"lang_code":"ko"}' > supertonic2_stream.wav`

If you see HTTP 500s, check logs for missing model/style files or mismatched paths.

## Common pitfalls
- Auth header missing: add `-H "X-API-KEY: <key>"` (or your Bearer token header).
- Newlines in JSON: keep the request body on a single line or use `--data-binary @file.json`; embedded newlines trigger JSON decode errors.
- Missing metadata files: ensure `models/supertonic2/onnx` contains `duration_predictor.onnx`, `text_encoder.onnx`, `vector_estimator.onnx`, `vocoder.onnx`, `tts.json`, and `unicode_indexer.json`.
- Wrong config path: confirm you edited `tldw_Server_API/Config_Files/tts_providers_config.yaml` and set `providers.supertonic2.enabled: true`.
- Stale server process: restart after changing config or installing assets.
