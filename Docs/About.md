# About tldw_server

## What is tldw_server?

Originally `tldw`, a versatile tool to help manage and interact with media content (videos, audio, documents, web articles, and books) via:

1. Ingesting: Importing media from URLs or local files into an offline database.
2. Transcribing: Automatically generating text transcripts from videos and audio using various whisper models (faster_whisper and others).
3. Analyzing (Not Just Summarizing): Using LLMs (local or API-based) to perform analyses of ingested content.
4. Searching: Full-text search across ingested content, including metadata like titles, authors, and keywords.
5. Chatting: Interacting with ingested content using natural language queries through supported LLMs.

All features are designed to run locally on your device, ensuring privacy and data ownership. The tool is open-source and aims to support research, learning, and personal knowledge management.

It has now been rewritten as a FastAPI Python server to support larger deployments and multiple users. This includes:

- A modern FastAPI backend with OpenAPI docs and integrated WebUI
- OpenAI-compatible Chat, Embeddings, STT/TTS endpoints
- AuthNZ module with single-user (API key) and multi-user (JWT) modes
- Hybrid RAG (FTS5 + vector + re-ranking) and a unified RAG API
- Multi-provider LLM integration (commercial + local)
