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

## Further API Docs

- Chat API: `Docs/API-related/Chat_API_Documentation.md`
- Character Chat API: `Docs/CHARACTER_CHAT_API_DOCUMENTATION.md`
- OCR Providers: `Docs/OCR/OCR_Providers.md`

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

## OCR Backends (dots.ocr)

- The PDF pipeline supports pluggable OCR backends via `ocr_backend`.
- Built-in: `tesseract` (CLI). Optional: `dots` (dots.ocr project).

Using dots.ocr
- Select via API: set `enable_ocr=true` and `ocr_backend=dots` on PDF ingestion or OCR evaluation endpoints.
- Prompt control: set `DOTS_OCR_PROMPT` (default: `prompt_ocr`) to switch between text-only and layout prompts (see dots.ocr docs for options like `prompt_layout_only_en`).
- Installation (summary; see upstream for details):
  - Create env (Python 3.12), install a compatible PyTorch build (CUDA/CPU), then `pip install -e .` from the dots.ocr repo.
  - Download model weights: `python3 tools/download_model.py` (save directory name should not contain periods; e.g., `DotsOCR`).
  - Recommended: run a vLLM server with the downloaded weights for best performance and consistency.
- Optional extras: `pip install .[ocr_dots]` to pull dots.ocr automatically.
- Backend behavior:
  - The `dots` backend shells out to `python -m dots_ocr.parser` per page image.
  - If dots.ocr is not installed/available, auto-detect falls back to `tesseract` unless `ocr_backend=dots` is explicitly forced.
  - `ocr_mode=fallback` OCRs only pages without selectable text; use `always` to force OCR for all pages.

Integration tests
- A unit test validates backend availability handling.
- An integration test (skipped unless `dots_ocr` is importable) exercises `/api/v1/evaluations/ocr-pdf` with a tiny generated PDF and `ocr_backend=dots`.

### OCR Backends (POINTS-Reader)

- Backend name: `points`.
- Usage: set `enable_ocr=true` and `ocr_backend=points`.

Two integration modes
- Transformers (local model):
  - Install WePOINTS and use the HF model `tencent/POINTS-Reader` locally.
  - Env (optional): `POINTS_MODEL_PATH` to override model id/path.
  - Requirements: `transformers`, `torch` (CUDA recommended for performance).
- SGLang server (recommended for production):
  - Launch SGLang with `--model-path tencent/POINTS-Reader --trust-remote-code --chat-template points-v15-chat` on port 8081 (per upstream docs).
  - Env: `POINTS_SGLANG_URL` (default `http://127.0.0.1:8081/v1/chat/completions`), `POINTS_SGLANG_MODEL` (default `WePoints`).

Mode selection
- `POINTS_MODE` selects behavior: `auto` (default), `sglang`, or `transformers`.
  - `auto` prefers SGLang if `POINTS_SGLANG_URL` is set; otherwise uses transformers if libraries exist.

Prompt and generation
- Set `POINTS_PROMPT` to override the default extraction prompt (tables in HTML, others in Markdown).
- Optional generation envs: `POINTS_MAX_NEW_TOKENS`, `POINTS_TEMPERATURE`, `POINTS_REPETITION_PENALTY`, `POINTS_TOP_P`, `POINTS_TOP_K`, `POINTS_DO_SAMPLE`.

Install via extras (optional)
- Local transformers path: `pip install .[ocr_points_transformers]`
- SGLang client only: `pip install .[ocr_points_sglang]`

Notes
- Known issues from upstream: repeated/missing content on complex layouts, difficulties with handwriting, English/Chinese focus.

See `Docs/OCR/POINTS-Reader.md` for a complete setup and usage guide.

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
