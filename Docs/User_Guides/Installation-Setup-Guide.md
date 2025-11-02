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

Prefer installing via the project’s pyproject extras:

```bash
# Core server
pip install -e .

# Useful extras
# pip install -e ".[dev]"           # tests, linters, tooling
# pip install -e ".[multiplayer]"   # multi-user/PostgreSQL support
# pip install -e ".[otel]"          # OpenTelemetry exporters (optional)
```

Notes:
- Some optional features (OCR backends, GPU variants) have extra steps noted in their respective docs.
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

## 5) Start the server

```bash
python -m uvicorn tldw_Server_API.app.main:app --reload
# API docs:   http://127.0.0.1:8000/docs
# Web UI:     http://127.0.0.1:8000/webui/
```

Tip: You can also use the convenience script from the repo root:

```bash
./start-webui.sh
```

## 6) Verify

- Health: `GET http://127.0.0.1:8000/health` should return `{ "status": "healthy" }`
- On startup, logs display the auth mode and URLs. In single-user mode the API key may be masked unless explicitly allowed.

## Troubleshooting

- “ffmpeg not found”: Ensure FFmpeg is installed and available on PATH.
- Auth errors: Confirm `.env` is loaded and `AUTH_MODE`/keys are correctly set.
- SQLite locks: Prefer PostgreSQL for multi-user production. Ensure proper shutdown before restarting.
- Port 8000 in use: Stop the other process or change the port (`--port 8001`).

## Next Steps

- Read the User Guide for common tasks: `User_Guide.md`
- Configure providers and test chat/embeddings via the WebUI and `/docs`
- See Production Hardening and Multi-User Deployment guides for production use

## Optional: Tokenizer strategy (Chat Dictionaries & World Books)

The server estimates tokens when enforcing budgets in Chat Dictionary and World Book processing. You can adjust this strategy at runtime:

- `GET /api/v1/config/tokenizer` → view current mode (`whitespace` or `char_approx`) and divisor
- `PUT /api/v1/config/tokenizer` → update mode and divisor (in-memory; not persisted)

Example:
```
GET /api/v1/config/tokenizer
{
  "mode": "whitespace",
  "divisor": 4
}

PUT /api/v1/config/tokenizer
{
  "mode": "char_approx",
  "divisor": 4
}
```

To set defaults, you can also add environment or config values:
- `TOKEN_ESTIMATOR_MODE`: `whitespace` (default) or `char_approx`
- `TOKEN_CHAR_APPROX_DIVISOR`: integer (default `4`)
