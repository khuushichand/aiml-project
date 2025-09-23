# [Changelog](https://keepachangelog.com)

## 0.1.0 (2025-09-21)

Highlights
- FastAPI backend with OpenAPI docs and integrated WebUI at `/webui`.
- AuthNZ: Single-user (API key) and multi-user (JWT). Postgres recommended for multi-user AuthNZ; SQLite supported for dev.
- Media: Ingest video/audio/PDF/EPUB/DOCX/HTML/Markdown; metadata extraction; yt-dlp.
- Audio: File transcription and real-time streaming (faster_whisper, NeMo, Qwen2Audio). OpenAI-compatible STT/TTS.
- Search/RAG: Hybrid FTS5 + vector (Chroma) + re-ranking; unified RAG API.
- Chat: OpenAI-compatible `/chat/completions`; 16+ providers; character chat; chat history.
- Embeddings: v5 API with batching and trusted remote-code allowlist.
- MCP Unified: Secure server + endpoints (labelled Experimental in this release).
- Chatbooks: Export/import for backups/portability.
- Observability: Prometheus metrics, preflight report, production hardening guide.

Notes
- Gradio UI is deprecated.
- Experimental: Workflows, Flashcards, Prompt Studio, and MCP Unified APIs are available but marked Experimental.
- In multi-user production, use Postgres for AuthNZ. Content DBs (media/RAG) remain SQLite by default in v0.1.

## Prior changelog from Gist
