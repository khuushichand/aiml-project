# tldw_Server_API – API Guide

This document covers the API layout, how to run the server, authentication, and how to add or work with endpoints inside `tldw_Server_API`.

## Overview

The server is FastAPI-based with an OpenAI-compatible Chat and Audio API, a unified RAG module, a unified Evaluations module, and an integrated WebUI served from the same origin.

Key directories:
- `app/main.py` – FastAPI app, router includes, middleware, WebUI mount
- `app/api/v1/endpoints/` – Endpoint modules (media, chat, audio, rag, evals, prompts, notes, etc.)
- `app/api/v1/schemas/` – Pydantic request/response models
- `app/api/v1/API_Deps/` – Shared dependencies (auth, DB, rate limits)
- `app/core/` – Business logic (AuthNZ, RAG, LLM, DB, TTS, MCP, etc.)
- `WebUI/` – Static WebUI served at `/webui`

## Running the Server

```bash
python -m uvicorn tldw_Server_API.app.main:app --reload
# API docs: http://127.0.0.1:8000/docs
# WebUI:    http://127.0.0.1:8000/webui/
```

### Authentication
- Single-user mode (personal): Use `X-API-KEY` header.
- Multi-user mode (team): Use `Authorization: Bearer <JWT>`.

Quick setup:
```bash
cp .env.authnz.template .env
python -m tldw_Server_API.app.core.AuthNZ.initialize
```

Configure provider keys in `.env` or `tldw_Server_API/Config_Files/config.txt`.

## Endpoint Overview

- Chat: `POST /api/v1/chat/completions` (OpenAI compatible)
- Embeddings: `POST /api/v1/embeddings` (OpenAI compatible)
- Audio STT/TTS:
  - `POST /api/v1/audio/transcriptions` (file-based STT)
  - `WS  /api/v1/audio/stream/transcribe` (real-time STT)
  - `POST /api/v1/audio/speech` (TTS; streaming and non-streaming)
- Media: `POST /api/v1/media/process`, `GET /api/v1/media/search`, and related
- RAG: `POST /api/v1/rag/search` (unified pipeline)
- Evaluations (unified): `/api/v1/evaluations/...` (geval, rag, batch, metrics)
- LLM Providers: `GET /api/v1/llm/providers`
- Chatbooks: `POST /api/v1/chatbooks/export`, `POST /api/v1/chatbooks/import`
- MCP Unified: `GET /api/v1/mcp/status` and related

See `app/main.py` for router includes and full route namespaces.

## Adding a New Endpoint

1. Implement handler(s) in `app/api/v1/endpoints/<feature>.py` and schemas in `app/api/v1/schemas/`.
2. Place core logic under `app/core/<area>/` (avoid heavy logic in endpoint files).
3. Include the router in `app/main.py` with `app.include_router(...)`.
4. Add tests under `tldw_Server_API/tests/<feature>/`.

## Providers and Configuration

- Central provider configuration lives in `Config_Files/config.txt` (plus `.env`).
- The `GET /api/v1/llm/providers` endpoint reflects configured providers and models.
- Chat request validation is in `app/api/v1/schemas/chat_request_schemas.py` and related modules.

## Running Tests

```bash
pip install pytest httpx
python -m pytest -v
python -m pytest --cov=tldw_Server_API --cov-report=term-missing

# Markers
python -m pytest -m "unit" -v
python -m pytest -m "integration" -v
```

## Notes

- CORS and security middleware are configured in `app/main.py`.
- Single-user mode prints the API key and URLs on startup.
- The WebUI consumes the same-origin API and auto-detects single-user keys.

---

## Maintainer Notes (Original)

The following section preserves the original personal notes that were previously in this README for quick reference.

### Code Calling Pipeline

- You write the logic in `/app/core/<library>` and any backgroundable service processing in `/app/services`
- Then you call into the library/ies via `/api/v1/<route>`
- Which the routes themselves are defined in `main.py`

So to add a new route/API Endpoint:
- Write the endpoint in `main.py`
- Write the handling logic of the endpoint in `/api/v1/<route>`
- Write the majority/main of the processing logic in `/app/core/<library>`
- Write any background-able service processing in `/app/services`

### FastAPI on Windows (process stop)

- FastAPI has a bug, which is caused by starlette, caused by python.
- The gist is that you can't kill the python server on Windows without killing the process itself, or issuing a 'stop' command from within the process.

### Quick Commands

- Launch the API:
  - `python -m uvicorn tldw_Server_API.app.main:app --reload`
  - Visit the API via `127.0.0.1:8000/docs`

- Launching tests
  - `pip install pytest httpx`
  - `python -m pytest test_media_versions.py -v`
  - `python -m pytest .\\tldw_Server_API\\tests\\Media_Ingestion_Modification\\test_media_versions.py -v`

### Notes

- API Providers/Key checks defined in `/app/api/v1/schemas/chat_request_schemas.py`
