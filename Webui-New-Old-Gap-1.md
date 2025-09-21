# New WebUI vs Simple WebUI — Feature Gap Analysis

This document compares the new Next.js WebUI (`tldw-frontend`) with the existing simple WebUI (`tldw_Server_API/WebUI`) and enumerates gaps. The goal is to ensure the new UI fully supersedes the old one.

## Scope & Context
- New WebUI: Next.js app under `tldw-frontend` (Chat, Media, RAG implemented; unified auth/CSRF; model providers; shareable RAG configs).
- Simple WebUI: Static HTML/JS under `tldw_Server_API/WebUI` with comprehensive coverage of API endpoints and utilities.

## Recently Implemented in New WebUI
- Chat
  - OpenAI-compatible `/api/v1/chat/completions` with streaming and non‑streaming.
  - Provider/model dropdown via `/api/v1/llm/providers`.
  - Save to DB toggle; conversation_id capture; recent sessions (local) with migration from temporary local IDs.
  - Prefill support from Media detail.
- Media
  - Search (GET `/api/v1/media/search`) and full listing (POST `/api/v1/media/search`) with pagination.
  - Detail view for `/api/v1/media/{id}`; Summarize action via Chat; Send to Chat.
  - Analyze controls (model, prompt) + “Use Chat model”.
- RAG (Unified)
  - Unified `/api/v1/rag/search` with extensive options (sources, search, cache, security, chunking, claims, rerank, citations, generation, feedback, monitoring, resilience, user context).
  - Presets: list/apply via `/api/v1/evaluations/rag/pipeline/presets`.
  - Shareable URL with full state; Copy Share Link; load state from URL.
- Auth/CSRF
  - Supports JWT (Authorization), single-user X-API-KEY, and Chat API_BEARER.
  - CSRF header added for modifying requests without X-API-KEY.

## Feature Gaps (Old → New)

### General + Utilities
- Connection status UI with response times and health indicators.
- Global configuration panel (base URL, auth token) with auto‑config from `/webui/config.json`.
- Endpoint request builder with per‑endpoint forms and validation.
- Response JSON viewer (collapsible, syntax highlighting, copy tools).
- cURL command generation for any request.
- Global request history (view/replay) across endpoints.
- Theming (dark/light) and persistent UI preferences.

### Media
- Full media management UI:
  - Add media (URLs/uploads/metadata), reindexing, rebuild FTS, claims rebuild, etc.
  - Versioning operations (list versions, fetch content, rollback, update version/doc).
  - Rich search forms: filters, tags, media types, date ranges, sorting.
  - Ingestion/Chunking controls (all chunking options, templates selector, apply/learn templates).
  - Specialized ingestion: ebooks, MediaWiki (dump import/process), scraping workflows, and progress indicators.

### Chat
- Multi‑message composer with role management (system/user/assistant/tool) and presets library.
- Advanced parameters: temperature, max_tokens, n/top_p, presence/frequency penalty, stop sequences, response_format (JSON), logprobs/top_logprobs.
- Tool definitions and `tool_choice` UI; vision/image attachments (image_url/data URIs).
- Conversation export/import; dictionary/terminology tools integration.
- Per‑request cURL generation and request history.

### RAG
- Complex JSON editor for full UnifiedRAGRequest payloads (free‑form advanced mode).
- Capabilities/health panels (e.g., `/api/v1/rag/capabilities`), caching metrics, circuit breaker state.
- Result visualization enhancements:
  - Highlight matching terms in documents/snippets.
  - Structured citation sections (chunk citations, academic citations rendered nicely).
  - Pipeline timings/metrics and cache hit indicators.
- Streaming “claim overlay” UI with Supported/Refuted/NEI annotations during generation.
- Preset management (create/update/delete) beyond list/apply.

### Evaluations
- OCR evaluation UIs:
  - JSON input (`/api/v1/evaluations/ocr`) and PDF uploads (`/api/v1/evaluations/ocr-pdf`).
  - Thresholds and options, result viewers with per‑page metrics.
- Other evaluation forms: `geval`, `response-quality`, batch runs, results aggregation.
- Circuit breaker status visibility across providers.

### Audio
- TTS: Provider selection (OpenAI‑compatible, ElevenLabs, Kokoro, etc.), voice lists, streaming playback, previews.
- STT: Real‑time streaming transcription over WebSocket with live transcript and controls.

### Embeddings
- Embeddings generator for text/batches; model selection; output inspection.

### Prompts + Prompt Studio
- Prompt library CRUD; keyword management; import/export.
- Prompt Studio: projects, prompts, test cases, optimization runs, compare strategies, live progress (WebSocket).

### Notes / Knowledge
- Notes CRUD, tagging, search, and visibility in RAG sources.

### Admin / Users / Sync / Maintenance / Health
- Admin: user/role/permission management; quotas.
- Users: profile update, password change, sessions management.
- Sync: synchronization operations, status UI.
- Maintenance: database maintenance and batch operations.
- Health: system health dashboards and diagnostics (DB/Redis/metrics).

### MCP / Tools / Llama.cpp / Web Scraping
- MCP Unified: status, tools registry, tool invocation; WS connections.
- Tools: generic tools endpoint UI.
- Llama.cpp: model management and server control UI.
- Web Scraping: service initialize/shutdown, cookies, duplicates check, sitemap/recursive scraping, progress.

### Vector Stores / Claims / Research / Workflows
- Vector store (OpenAI‑compatible) UI for stores/files.
- Claims: inspector for extracted claims against media.
- Research: arXiv/Semantic Scholar integrations.
- Workflows: orchestration workflows UI.

### UX Quality‑of‑Life
- Reusable toasts, modals, and consistent error handling across pages.
- Download/import/export helpers for results/payloads/configs.
- Per‑section cURL + request history and “copy payload” affordances.

## Recommended Porting Order (High Value → Effort)
1. General/Config page: connection status, request history, cURL generator (shared utilities).
2. Audio (TTS + STT) and Embeddings tabs: fast wins and important demos.
3. Media management expansion: Add/Search filters/Versions and Chunking Template selector.
4. RAG result visualization: highlights, citations, timings/metrics, cache indicators.
5. Prompt Studio and Evaluations (OCR + RAG): end‑to‑end experimentation flows.
6. Admin/Users/Sessions and Health dashboards.
7. MCP/Tools, Llama.cpp, and Web Scraping management panels.

## Notes on Auth/Config Alignment
- New UI already supports `Authorization: Bearer`, `X-API-KEY`, and `API_BEARER` for Chat.
- CSRF token handled for modifying requests when no `X-API-KEY`.
- Consider adding same‑origin bootstrap from `/webui/config.json` to auto‑configure base URL and auth (parity with simple WebUI).

---

This list will evolve as new sections land in the Next.js WebUI. Once complete, the new UI should fully supersede the simple WebUI.
