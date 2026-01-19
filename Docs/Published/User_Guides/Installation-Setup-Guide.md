# Installation & Setup Guide

This guide helps you install and run tldw_server locally with the integrated WebUI and API.

## Prerequisites

- Python 3.10+ (3.11 recommended)
- FFmpeg installed and on your PATH (required for audio/video)
- Git (optional but recommended)
- Optional: CUDA/cuDNN for GPU-accelerated STT (faster_whisper/NeMo)

## 1) Clone and create a virtual environment

```bash
git clone https://github.com/<your-fork-or-org>/tldw_server.git
cd tldw_server

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

## 2) Install dependencies

Prefer pyproject-based installs with extras:

```bash
# Core server
pip install -e .

# Useful extras
# pip install -e ".[dev]"           # tests, linters, tooling
# pip install -e ".[multiplayer]"   # multi-user/PostgreSQL support
# pip install -e ".[otel]"          # OpenTelemetry exporters (optional)
```

Notes:
- Some optional features (OCR backends, GPU variants) have extra steps noted in their docs.
- Ensure FFmpeg is installed via your OS package manager (e.g., `brew install ffmpeg`, `apt-get install ffmpeg`).

## 3) Configure authentication

The server supports two modes:
- Single-user: API key via `X-API-KEY` header
- Multi-user: JWT bearer tokens (login/registration)

Quick setup using the template:

```bash
cp .env.authnz.template .env
# Edit .env and set AUTH_MODE and keys
#  - AUTH_MODE=single_user and SINGLE_USER_API_KEY=<your_key>
#  - OR AUTH_MODE=multi_user and JWT_SECRET_KEY=<secure-32+ chars>
```

Initialize AuthNZ (creates DBs, tables, and admin in multi-user mode):

```bash
python -m tldw_Server_API.app.core.AuthNZ.initialize
```

Environment variables of interest (from `.env`):
- `AUTH_MODE`: `single_user` or `multi_user`
- `SINGLE_USER_API_KEY` (single-user)
- `JWT_SECRET_KEY` (multi-user)
- `DATABASE_URL` (auth DB; defaults to SQLite; use PostgreSQL for multi-user prod)
- `REDIS_URL` (optional; background services)

## 4) Provider keys (LLMs, embeddings, TTS)

You can set provider keys either in `.env` or `tldw_Server_API/Config_Files/config.txt`:
- Examples: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, etc.
- The WebUI’s Provider tab and API docs list supported providers.

## 5) Optional: Local inference (llama.cpp / MLX)

You can run local models through the managed llama.cpp server or the in-process MLX provider.

### Llama.cpp (managed server)

1) Build or download the llama.cpp server binary.
2) Put the binary and GGUF models on disk (or point the config at them).

Defaults are:
- Binary: `vendor/llama.cpp/server`
- Models: `models/gguf_models`

Example config in `tldw_Server_API/Config_Files/config.txt`:

```
[LlamaCpp]
enabled = true
executable_path = /path/to/llama.cpp/server
models_dir = /path/to/gguf_models
default_ctx_size = 4096
default_n_gpu_layers = 35
```

Notes:
- `models_dir` must contain `.gguf` files. The handler only loads models under `models_dir` (or `allowed_paths` if set).
- Restart the server after updating config.

Start and check the server:

```
POST /api/v1/llamacpp/start_server
{
  "model_filename": "your-model.gguf",
  "server_args": { "ctx_size": 4096, "ngl": 35 }
}

GET /api/v1/llamacpp/status
```

Optional chat routing:
- If you want `/api/v1/chat/completions` to use llama.cpp, set `[Local-API] llama_api_IP` to the base URL of your running llama.cpp server (for example `http://127.0.0.1:8080` or `http://127.0.0.1:8080/v1`), then use `provider=llama.cpp`.

### MLX (Apple Silicon)

MLX is supported on macOS arm64.

1) Install MLX extras:

```bash
pip install -e ".[LLM_MLX]"
```

2) Set the model in `tldw_Server_API/Config_Files/config.txt`:

```
[MLX]
mlx_model_path = Qwen/Qwen3-0.6B-MLX-4bit
mlx_compile = true
mlx_warmup = true
mlx_max_concurrent = 1
```

3) Load/unload via API (admin-only):

```
POST /api/v1/llm/providers/mlx/load
{
  "model_path": "Qwen/Qwen3-0.6B-MLX-4bit"
}

GET /api/v1/llm/providers/mlx/status
POST /api/v1/llm/providers/mlx/unload
```

Notes:
- `mlx_model_path` can be a local path or a repo id; downloads and caching are handled by `mlx-lm`.
- Use `/api/v1/chat/completions` with `provider=mlx`. `/api/v1/embeddings` works when the model supports embeddings.

Quick usage examples (use `X-API-KEY` for single-user or `Authorization: Bearer` for multi-user):

```bash
# Chat with llama.cpp or MLX
curl -s http://127.0.0.1:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: YOUR_API_KEY" \
  -d '{
    "provider": "llama.cpp",
    "model": "your-model-id",
    "messages": [{"role":"user","content":"Hello!"}]
  }'

curl -s http://127.0.0.1:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: YOUR_API_KEY" \
  -d '{
    "provider": "mlx",
    "model": "your-mlx-model-id",
    "messages": [{"role":"user","content":"Hello!"}]
  }'

# Embeddings (if supported by the model/provider)
curl -s http://127.0.0.1:8000/api/v1/embeddings \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: YOUR_API_KEY" \
  -d '{
    "provider": "mlx",
    "model": "your-mlx-embedding-model-id",
    "input": "short text to embed"
  }'
```

More detail on local backends and llama.cpp flags: [Setting up a local LLM](Setting_up_a_local_LLM.md).

## 6) Optional: Text-to-Speech (TTS)

TTS providers and priority live in `tldw_Server_API/app/core/TTS/tts_providers_config.yaml`. You can also override some settings in `Config_Files/config.txt` under `[TTS-Settings]`.

Quick paths:
- Hosted OpenAI TTS: set `OPENAI_API_KEY` and keep the `openai` provider enabled.
- Local Kokoro ONNX: install the extra, install `espeak-ng`, and download models.

```bash
# Local Kokoro (deps + model/voices)
pip install -e ".[TTS_kokoro_onnx]"
python Helper_Scripts/TTS_Installers/install_tts_kokoro.py
```

Verify TTS:

```bash
# OpenAI (hosted)
curl -sS -X POST http://127.0.0.1:8000/api/v1/audio/speech \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: YOUR_API_KEY" \
  -d '{"model":"tts-1","voice":"alloy","input":"Hello from TTS","response_format":"mp3"}' \
  --output tts.mp3

# Kokoro (local, ONNX)
curl -sS -X POST http://127.0.0.1:8000/api/v1/audio/speech \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: YOUR_API_KEY" \
  -d '{"model":"kokoro","voice":"af_bella","input":"Hello from Kokoro","response_format":"mp3"}' \
  --output kokoro.mp3
```

Notes:
- Local providers do not auto-download unless you set `TTS_AUTO_DOWNLOAD=1`.
- Use `GET /api/v1/audio/voices/catalog` to list available voices.

More detail: [Docs/Published/User_Guides/TTS_Getting_Started.md](TTS_Getting_Started.md).

## 7) Optional: Speech-to-Text (STT)

For STT setup and testing, use the dedicated guide and API reference:
- [Getting-Started-STT_and_TTS.md](../../Getting-Started-STT_and_TTS.md)
- [Docs/Published/API-related/Audio_Transcription_API.md](../API-related/Audio_Transcription_API.md)

Quick STT verification:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/audio/transcriptions \
  -H "X-API-KEY: YOUR_API_KEY" \
  -F "file=@/path/to/audio.wav" \
  -F "model=whisper-1" \
  -F "language=en" \
  -F "response_format=json"
```

## 8) Start the server

```bash
python -m uvicorn tldw_Server_API.app.main:app --reload
# API docs:   http://127.0.0.1:8000/docs
# Web UI:     http://127.0.0.1:8000/webui/
```

Tip: You can also use the convenience script from the repo root:

```bash
./start-webui.sh
```

Optional: run the API + Jobs workers as separate processes (sidecar mode):

```bash
./start-sidecars.sh
```

Notes:
- Sets `TLDW_WORKERS_SIDECAR_MODE=true` so the API process skips in-process workers.
- Default list lives in `Docs/Deployment/sidecar_workers_manifest.json` (regen via `python Helper_Scripts/Deployment/generate_sidecar_files.py`).
- Customize the worker list with `TLDW_SIDECAR_WORKERS=chatbooks,files,data_tables,prompt_studio,privilege_snapshots,audio,media_ingest,evals_abtest` or point to a different manifest with `TLDW_WORKERS_MANIFEST=/path/to/manifest.json`.

## 9) Verify

- Health: `GET http://127.0.0.1:8000/health` should return `{ "status": "healthy" }`
- On startup, logs display the auth mode and URLs. In single-user mode the API key may be masked unless explicitly allowed.

## Troubleshooting

- “ffmpeg not found”: Ensure FFmpeg is installed and available on PATH.
- Auth errors: Confirm `.env` is loaded and `AUTH_MODE`/keys are correctly set.
- SQLite locks: In-process jobs plus multiple Uvicorn workers can increase contention. Prefer sidecar workers or PostgreSQL for production and heavy workloads.
- Port 8000 in use: Stop the other process or change the port (`--port 8001`).

## Next Steps

- Read the User Guide for common tasks: `User_Guide.md`
- Set a default LLM provider: see "Default LLM Provider" in `User_Guide.md`
- Configure providers and test chat/embeddings via the WebUI and `/docs`
- See Production Hardening and Multi-User Deployment guides for production use
