# tldw_server User Guide

This guide shows how to use the integrated WebUI and API to ingest media, search and retrieve, chat with LLMs, generate embeddings, and run evaluations.

## Quick Start

- Start the server: `python -m uvicorn tldw_Server_API.app.main:app --reload`
- Open the WebUI: `http://127.0.0.1:8000/webui/`
- Open API docs: `http://127.0.0.1:8000/docs`

Authentication:
- Single-user: enter your API key in the WebUI Global Settings; API calls use `X-API-KEY: <key>`.
- Multi-user: register/login in the WebUI; API calls use `Authorization: Bearer <token>`.

## WebUI Overview

Top navigation groups features into tabs. Notable areas include:
- General: global API URL and token, request history, diagnostics.
- Auth: token utilities, auth tests.
- Media: upload/ingest files and URLs (video/audio with yt-dlp; PDFs, EPUB, DOCX, HTML, Markdown), analysis, versioning, DB vs no-DB processing, web scraping.
- Chat: OpenAI-compatible chat completions; Characters and Conversations.
- Prompts and Notes: prompt library and notebook-style notes.
- RAG: unified search and embeddings flows.
- Workflows: definitions and runs (scaffolding in 0.1).
- Keywords: tagging and categorization.
- Embeddings: providers, models, and admin ops.
- Web Scraping: ingest pages, view status and jobs.
- Audio: file transcription and real-time streaming transcription.
- Research: multi-provider web/paper search.
- Chatbooks: export/import and background jobs.
- MCP: Model Context Protocol utilities.
- LLM Inference: llama.cpp helpers and reranking.
- Evaluations: unified evaluation flows and metrics.
- Admin/Config/LLM/Health/Sync/Maintenance: server status, metrics, backups, cleanup, claims, and provider configuration.

## Common Tasks

- Ingest media
  - Go to Media → Ingestion (DB) to persist content; or Processing (No DB) for one-off processing.
  - Paste a URL (video/audio supported via yt-dlp) or upload files (PDF/EPUB/DOCX/HTML/Markdown/audio/video).
  - Optionally enable transcription and chunking; submit and monitor progress.

- Search and retrieve (RAG)
  - Go to RAG → Search.
  - Choose hybrid search options (FTS5 + vectors + re-rank) and run queries against ingested content.

- Chat with an LLM
  - Go to Chat → Chat Completions.
  - Select a provider/model and send prompts; streaming supported for many providers.
  - Use Characters and Conversations for persona-based chats and history.

- Transcribe audio
  - Audio → Transcriptions: upload files for batch transcription.
  - Audio → Streaming: connect microphone and stream real-time transcription over WebSocket.

- Text-to-Speech (TTS)
  - TTS tab: select a voice/provider and synthesize speech; streaming and non-streaming supported.

- Prompt Studio
  - Prompt Studio: manage projects, prompts, test cases, and optimization flows.

- Evaluations
  - Evaluations tab: run unified evaluations (RAG, batch, metrics) and inspect results.

- Vector stores and embeddings
  - Embeddings and Vector Stores tabs: manage providers/models, warmups, caches, collections, upserts, and queries.

- Chatbooks
  - Chatbooks: export/import content and manage background jobs.

## Tips

- Provider keys can be set in `.env` or `tldw_Server_API/Config_Files/config.txt`.
- The WebUI sends either `X-API-KEY` (single-user) or `Authorization: Bearer` (multi-user) automatically.
- The API docs at `/docs` include an Authorize button; you can try endpoints directly.

## Troubleshooting

- Authentication failures: verify mode and token type (API key vs JWT) and ensure the token is set in Global Settings.
- FFmpeg errors: install FFmpeg and ensure it’s on PATH.
- Provider errors: confirm API keys and model names; check logs for rate limits.
- Database locks (SQLite): close other processes or switch to PostgreSQL for multi-user deployments.

## Feedback & Contributing

- File issues or suggestions in the repository.
- Follow the contribution guidelines and write tests for new features.
