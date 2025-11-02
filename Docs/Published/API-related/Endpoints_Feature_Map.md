# Endpoints Feature Map

This page summarizes the primary API endpoints exposed by the server, grouped by router prefix. It complements the OpenAPI docs and provides a quick, human-readable index of capabilities.

Note: This map focuses on the most important, stable routes. Many modules expose additional granular endpoints not listed here for brevity.

## JSON Map (prefix → endpoints)

```json
{
  "/api/v1/auth": [
    {"method": "POST", "path": "/login", "summary": "Login"},
    {"method": "POST", "path": "/logout", "summary": "Logout"},
    {"method": "POST", "path": "/refresh", "summary": "Refresh token"},
    {"method": "POST", "path": "/register", "summary": "Register"},
    {"method": "GET",  "path": "/me", "summary": "Current user"},
    {"method": "POST", "path": "/virtual-key", "summary": "Mint scoped virtual key (JWT)"}
  ],
  "/api/v1/users": [
    {"method": "GET",  "path": "/me", "summary": "Get profile"},
    {"method": "PUT",  "path": "/me", "summary": "Update profile"},
    {"method": "POST", "path": "/change-password", "summary": "Change password"},
    {"method": "GET",  "path": "/api-keys", "summary": "List API keys"},
    {"method": "POST", "path": "/api-keys", "summary": "Create API key"},
    {"method": "POST", "path": "/api-keys/virtual", "summary": "Create virtual API key"},
    {"method": "POST", "path": "/api-keys/{key_id}/rotate", "summary": "Rotate API key"},
    {"method": "DELETE","path": "/api-keys/{key_id}", "summary": "Delete API key"},
    {"method": "GET",  "path": "/sessions", "summary": "List sessions"},
    {"method": "DELETE","path": "/sessions/{session_id}", "summary": "Revoke session"},
    {"method": "POST", "path": "/sessions/revoke-all", "summary": "Revoke all sessions"},
    {"method": "GET",  "path": "/storage", "summary": "Storage quota"},
    {"method": "POST", "path": "/storage/recalculate", "summary": "Recalculate storage"}
  ],
  "/api/v1/privileges": [
    {"method": "GET", "path": "/org", "summary": "Org-level privileges"},
    {"method": "GET", "path": "/teams/{team_id}", "summary": "Team privileges"},
    {"method": "GET", "path": "/users/{user_id}", "summary": "User privileges"},
    {"method": "GET", "path": "/snapshots", "summary": "List snapshots"},
    {"method": "GET", "path": "/snapshots/{snapshot_id}", "summary": "Get snapshot"},
    {"method": "GET", "path": "/snapshots/{snapshot_id}/export.json", "summary": "Export JSON"},
    {"method": "GET", "path": "/snapshots/{snapshot_id}/export.csv", "summary": "Export CSV"}
  ],
  "/api/v1/media": [
    {"method": "GET",  "path": "/", "summary": "List media"},
    {"method": "POST", "path": "/add", "summary": "Ingest media"},
    {"method": "POST", "path": "/process-web-scraping", "summary": "Ingest from web scraping"},
    {"method": "GET",  "path": "/debug/schema", "summary": "Debug DB schema"},
    {"method": "GET",  "path": "/{media_id}/embeddings/status", "summary": "Embeddings status"},
    {"method": "POST", "path": "/{media_id}/embeddings", "summary": "Generate embeddings"},
    {"method": "DELETE","path": "/{media_id}/embeddings", "summary": "Delete embeddings"},
    {"method": "GET",  "path": "/embeddings/jobs", "summary": "List embedding jobs"},
    {"method": "GET",  "path": "/embeddings/jobs/{job_id}", "summary": "Embedding job status"}
  ],
  "/api/v1/audio": [
    {"method": "POST", "path": "/speech", "summary": "Text-to-speech (stream/non-stream)"},
    {"method": "POST", "path": "/transcriptions", "summary": "File STT"},
    {"method": "POST", "path": "/translations", "summary": "Audio translation"},
    {"method": "GET",  "path": "/voices/catalog", "summary": "TTS voice catalog"},
    {"method": "GET",  "path": "/health", "summary": "Audio health"},
    {"method": "GET",  "path": "/providers", "summary": "Audio providers"},
    {"method": "GET",  "path": "/stream/status", "summary": "Streaming availability"},
    {"method": "POST", "path": "/stream/test", "summary": "Test streaming setup"},
    {"method": "WS",   "path": "/stream/transcribe", "summary": "Real-time streaming transcription"},
    {"method": "POST", "path": "/jobs/submit", "summary": "Submit audio job"},
    {"method": "GET",  "path": "/jobs/{job_id}", "summary": "Audio job status"}
  ],
  "/api/v1/chat": [
    {"method": "POST", "path": "/completions", "summary": "OpenAI-compatible chat completions"}
  ],
  "/api/v1/characters": [
    {"method": "GET",  "path": "/", "summary": "List characters"},
    {"method": "POST", "path": "/", "summary": "Create character"},
    {"method": "GET",  "path": "/{character_id}", "summary": "Get character"},
    {"method": "PUT",  "path": "/{character_id}", "summary": "Update character"},
    {"method": "DELETE","path": "/{character_id}", "summary": "Delete character"},
    {"method": "GET",  "path": "/world-books", "summary": "List world books"},
    {"method": "POST", "path": "/world-books", "summary": "Create world book"}
  ],
  "/api/v1/chats": [
    {"method": "POST", "path": "/", "summary": "Create chat session"},
    {"method": "GET",  "path": "/", "summary": "List chat sessions"},
    {"method": "GET",  "path": "/{chat_id}", "summary": "Get session"},
    {"method": "POST", "path": "/{chat_id}/completions", "summary": "Prepare/complete chat"},
    {"method": "POST", "path": "/{chat_id}/messages", "summary": "Add message"},
    {"method": "GET",  "path": "/{chat_id}/messages", "summary": "List messages"},
    {"method": "GET",  "path": "/{chat_id}/messages/search", "summary": "Search messages"},
    {"method": "GET",  "path": "/messages/{message_id}", "summary": "Get message"},
    {"method": "PUT",  "path": "/messages/{message_id}", "summary": "Update message"},
    {"method": "DELETE","path": "/messages/{message_id}", "summary": "Delete message"}
  ],
  "/api/v1/embeddings": [
    {"method": "POST", "path": "", "summary": "Create embeddings (OpenAI-compatible)"},
    {"method": "GET",  "path": "/providers-config", "summary": "List configured providers"},
    {"method": "GET",  "path": "/models", "summary": "List embedding models"},
    {"method": "GET",  "path": "/models/{model_id:path}", "summary": "Embedding model metadata"},
    {"method": "GET",  "path": "/tenant/quotas", "summary": "Tenant quotas"},
    {"method": "POST", "path": "/job/priority/bump", "summary": "Bump job priority"},
    {"method": "POST", "path": "/models/warmup", "summary": "Warmup model"},
    {"method": "POST", "path": "/models/download", "summary": "Download model"}
  ],
  "/api/v1/vector_stores": [
    {"method": "POST", "path": "", "summary": "Create vector store"},
    {"method": "GET",  "path": "", "summary": "List vector stores"},
    {"method": "GET",  "path": "/{store_id}", "summary": "Get vector store"},
    {"method": "PATCH","path": "/{store_id}", "summary": "Update vector store"},
    {"method": "DELETE","path": "/{store_id}", "summary": "Delete vector store"},
    {"method": "POST", "path": "/{store_id}/vectors", "summary": "Upsert vectors"},
    {"method": "GET",  "path": "/{store_id}/vectors", "summary": "List vectors"},
    {"method": "POST", "path": "/{store_id}/query", "summary": "Query"}
  ],
  "/api/v1/rag": [
    {"method": "GET",  "path": "/capabilities", "summary": "RAG capabilities"},
    {"method": "POST", "path": "/ablate", "summary": "RAG ablations"},
    {"method": "POST", "path": "/search", "summary": "Unified RAG search"}
  ],
  "/api/v1/research": [
    {"method": "POST", "path": "/websearch", "summary": "Web search (aggregate optional)"},
    {"method": "GET",  "path": "/arxiv-search", "summary": "DEPRECATED: Use paper-search"}
  ],
  "/api/v1/web-scraping": [
    {"method": "GET",  "path": "/status", "summary": "Service status"},
    {"method": "GET",  "path": "/job/{job_id}", "summary": "Job status"},
    {"method": "DELETE","path": "/job/{job_id}", "summary": "Delete job"},
    {"method": "POST", "path": "/service/initialize", "summary": "Init service"},
    {"method": "POST", "path": "/service/shutdown", "summary": "Shutdown service"},
    {"method": "GET",  "path": "/progress/{task_id}", "summary": "Task progress"},
    {"method": "GET",  "path": "/cookies/{domain}", "summary": "Get cookies"},
    {"method": "POST", "path": "/cookies/{domain}", "summary": "Set cookies"},
    {"method": "GET",  "path": "/duplicates/check", "summary": "Check duplicates"}
  ],
  "/api/v1/ocr": [
    {"method": "GET",  "path": "/backends", "summary": "Available OCR backends"},
    {"method": "POST", "path": "/points/preload", "summary": "Preload POINTS-Reader"}
  ],
  "/api/v1/notes": [
    {"method": "GET",  "path": "/health", "summary": "Notes health"},
    {"method": "POST", "path": "/", "summary": "Create note"}
  ],
  "/api/v1/prompts": [
    {"method": "GET",  "path": "/health", "summary": "Prompts health"},
    {"method": "GET",  "path": "/", "summary": "List prompts"},
    {"method": "POST", "path": "/", "summary": "Create prompt"},
    {"method": "POST", "path": "/execute", "summary": "Execute prompt"}
  ],
  "/api/v1/prompt-studio/status": [
    {"method": "GET", "path": "", "summary": "Prompt Studio queue health"}
  ],
  "/api/v1/chatbooks": [
    {"method": "GET",  "path": "/health", "summary": "Chatbooks health"},
    {"method": "POST", "path": "/export", "summary": "Export chatbook"},
    {"method": "POST", "path": "/import", "summary": "Import chatbook"},
    {"method": "POST", "path": "/preview", "summary": "Preview export"},
    {"method": "GET",  "path": "/export/jobs", "summary": "List export jobs"},
    {"method": "GET",  "path": "/export/jobs/{job_id}", "summary": "Export job"},
    {"method": "GET",  "path": "/import/jobs", "summary": "List import jobs"},
    {"method": "GET",  "path": "/import/jobs/{job_id}", "summary": "Import job"},
    {"method": "GET",  "path": "/download/{job_id}", "summary": "Download export"},
    {"method": "POST", "path": "/cleanup", "summary": "Cleanup expired exports"}
  ],
  "/api/v1/reading": [
    {"method": "POST", "path": "/save", "summary": "Save URL to reading list"},
    {"method": "GET",  "path": "/items", "summary": "List reading items"},
    {"method": "PATCH","path": "/items/{item_id}", "summary": "Update item"}
  ],
  "/api/v1": [
    {"method": "POST", "path": "/reading/items/{item_id}/highlight", "summary": "Create highlight"},
    {"method": "GET",  "path": "/reading/items/{item_id}/highlights", "summary": "List highlights"},
    {"method": "PATCH","path": "/reading/highlights/{highlight_id}", "summary": "Update highlight"},
    {"method": "DELETE","path": "/reading/highlights/{highlight_id}", "summary": "Delete highlight"},
    {"method": "GET",  "path": "/llm/health", "summary": "LLM health"},
    {"method": "GET",  "path": "/llm/providers", "summary": "LLM providers"},
    {"method": "GET",  "path": "/llm/providers/{provider_name}", "summary": "Provider details"},
    {"method": "GET",  "path": "/llm/models", "summary": "LLM models"},
    {"method": "GET",  "path": "/llm/models/metadata", "summary": "Models metadata"},
    {"method": "POST", "path": "/llamacpp/start_server", "summary": "Start/swap llama.cpp"},
    {"method": "POST", "path": "/llamacpp/stop_server", "summary": "Stop llama.cpp"},
    {"method": "GET",  "path": "/llamacpp/status", "summary": "Server status"},
    {"method": "GET",  "path": "/llamacpp/models", "summary": "List models"},
    {"method": "POST", "path": "/llamacpp/inference", "summary": "Run inference"},
    {"method": "POST", "path": "/llamacpp/rerank", "summary": "Rerank passages"},
    {"method": "GET",  "path": "/metrics/text", "summary": "Prometheus text"},
    {"method": "GET",  "path": "/metrics/json", "summary": "Metrics JSON"},
    {"method": "GET",  "path": "/metrics/health", "summary": "Metrics health"},
    {"method": "GET",  "path": "/metrics/chat", "summary": "Chat metrics"},
    {"method": "POST", "path": "/metrics/reset", "summary": "Reset metrics"},
    {"method": "GET",  "path": "/config/docs-info", "summary": "Docs info"},
    {"method": "GET",  "path": "/config/flashcards-import-limits", "summary": "Import limits"},
    {"method": "GET",  "path": "/config/tokenizer", "summary": "Tokenizer config"},
    {"method": "PUT",  "path": "/config/tokenizer", "summary": "Update tokenizer"},
    {"method": "GET",  "path": "/config/jobs", "summary": "Jobs config"},
    {"method": "GET",  "path": "/config/quickstart", "summary": "Quickstart hints"},
    {"method": "GET",  "path": "/healthz", "summary": "Liveness"},
    {"method": "GET",  "path": "/readyz", "summary": "Readiness"},
    {"method": "GET",  "path": "/health", "summary": "API health"},
    {"method": "GET",  "path": "/health/live", "summary": "Liveness"},
    {"method": "GET",  "path": "/health/ready", "summary": "Readiness"},
    {"method": "GET",  "path": "/health/metrics", "summary": "System metrics"}
  ],
  "/api/v1/mcp": [
    {"method": "GET",  "path": "/metrics", "summary": "MCP metrics JSON"},
    {"method": "GET",  "path": "/metrics/prometheus", "summary": "MCP Prometheus"},
    {"method": "POST", "path": "/tools/execute", "summary": "Execute tool"},
    {"method": "GET",  "path": "/modules", "summary": "List modules"},
    {"method": "GET",  "path": "/modules/health", "summary": "Modules health"},
    {"method": "GET",  "path": "/resources", "summary": "List resources"},
    {"method": "GET",  "path": "/prompts", "summary": "List prompts"},
    {"method": "POST", "path": "/auth/token", "summary": "Issue token"},
    {"method": "POST", "path": "/auth/refresh", "summary": "Refresh token"},
    {"method": "GET",  "path": "/health", "summary": "Service health"}
  ],
  "/api/v1/workflows": [
    {"method": "POST", "path": "", "summary": "Create definition"},
    {"method": "GET",  "path": "", "summary": "List definitions"},
    {"method": "POST", "path": "/{workflow_id}/versions", "summary": "Create version"},
    {"method": "DELETE","path": "/{workflow_id}", "summary": "Delete definition"},
    {"method": "POST", "path": "/run", "summary": "Run workflow"},
    {"method": "GET",  "path": "/options/chunkers", "summary": "Chunker options"},
    {"method": "GET",  "path": "/templates", "summary": "List templates"},
    {"method": "GET",  "path": "/config", "summary": "Service config"}
  ],
  "/api/v1/scheduler/workflows": [
    {"method": "POST", "path": "", "summary": "Create schedule"},
    {"method": "GET",  "path": "", "summary": "List schedules"},
    {"method": "GET",  "path": "/{schedule_id}", "summary": "Get schedule"},
    {"method": "PATCH","path": "/{schedule_id}", "summary": "Update schedule"},
    {"method": "DELETE","path": "/{schedule_id}", "summary": "Delete schedule"},
    {"method": "POST", "path": "/admin/rescan", "summary": "Admin rescan"}
  ],
  "/api/v1/items": [
    {"method": "GET", "path": "", "summary": "Unified items list"}
  ],
  "/api/v1/outputs": [
    {"method": "GET",  "path": "", "summary": "List outputs"},
    {"method": "GET",  "path": "/deleted", "summary": "List soft-deleted"},
    {"method": "POST", "path": "", "summary": "Generate artifact"},
    {"method": "GET",  "path": "/{output_id}", "summary": "Get output"},
    {"method": "GET",  "path": "/{output_id}/download", "summary": "Download"},
    {"method": "DELETE","path": "/{output_id}", "summary": "Delete"},
    {"method": "PATCH","path": "/{output_id}", "summary": "Update"},
    {"method": "POST", "path": "/purge", "summary": "Purge expired"}
  ],
  "/api/v1/output-templates": [
    {"method": "GET",  "path": "", "summary": "List templates"},
    {"method": "POST", "path": "", "summary": "Create template"},
    {"method": "GET",  "path": "/{template_id}", "summary": "Get template"},
    {"method": "PATCH","path": "/{template_id}", "summary": "Update template"},
    {"method": "DELETE","path": "/{template_id}", "summary": "Delete template"},
    {"method": "POST", "path": "/{template_id}/preview", "summary": "Preview render"}
  ],
  "/api/v1/watchlists": [
    {"method": "POST", "path": "/jobs/{job_id}/run", "summary": "Run job"},
    {"method": "GET",  "path": "/runs", "summary": "List runs"},
    {"method": "GET",  "path": "/runs/{run_id}", "summary": "Get run"},
    {"method": "GET",  "path": "/outputs", "summary": "List outputs"},
    {"method": "GET",  "path": "/templates", "summary": "List templates"}
  ],
  "/api/v1/monitoring": [
    {"method": "GET",  "path": "/watchlists", "summary": "List watchlists"},
    {"method": "POST", "path": "/watchlists", "summary": "Create/update watchlist"},
    {"method": "DELETE","path": "/watchlists/{watchlist_id}", "summary": "Delete watchlist"},
    {"method": "POST", "path": "/reload", "summary": "Reload"},
    {"method": "GET",  "path": "/alerts", "summary": "List alerts"},
    {"method": "POST", "path": "/alerts/{alert_id}/read", "summary": "Mark alert read"},
    {"method": "GET",  "path": "/notifications/settings", "summary": "Get notification settings"},
    {"method": "PUT",  "path": "/notifications/settings", "summary": "Update notification settings"},
    {"method": "POST", "path": "/notifications/test", "summary": "Send test notification"},
    {"method": "GET",  "path": "/notifications/recent", "summary": "Tail recent notifications"}
  ],
  "/api/v1/moderation": [
    {"method": "GET",  "path": "/users", "summary": "List per-user overrides"},
    {"method": "GET",  "path": "/users/{user_id}", "summary": "Get user override"},
    {"method": "PUT",  "path": "/users/{user_id}", "summary": "Set user override"},
    {"method": "DELETE","path": "/users/{user_id}", "summary": "Delete user override"},
    {"method": "GET",  "path": "/blocklist", "summary": "Get blocklist"},
    {"method": "PUT",  "path": "/blocklist", "summary": "Replace blocklist"}
  ],
  "/api/v1/audit": [
    {"method": "GET", "path": "/audit/export", "summary": "Export audit events"},
    {"method": "GET", "path": "/audit/count", "summary": "Count audit events"}
  ]
}
```

## Table View

| Prefix | Method | Path | Summary |
| - | - | - | - |
| /api/v1/auth | POST | /api/v1/auth/login | Login |
| /api/v1/auth | POST | /api/v1/auth/logout | Logout |
| /api/v1/auth | POST | /api/v1/auth/refresh | Refresh token |
| /api/v1/auth | POST | /api/v1/auth/register | Register |
| /api/v1/auth | GET | /api/v1/auth/me | Current user |
| /api/v1/auth | POST | /api/v1/auth/virtual-key | Mint scoped virtual key |
| /api/v1/users | GET | /api/v1/users/me | Get profile |
| /api/v1/users | PUT | /api/v1/users/me | Update profile |
| /api/v1/users | POST | /api/v1/users/change-password | Change password |
| /api/v1/users | GET | /api/v1/users/api-keys | List API keys |
| /api/v1/users | POST | /api/v1/users/api-keys | Create API key |
| /api/v1/users | POST | /api/v1/users/api-keys/virtual | Create virtual API key |
| /api/v1/users | POST | /api/v1/users/api-keys/{key_id}/rotate | Rotate API key |
| /api/v1/users | DELETE | /api/v1/users/api-keys/{key_id} | Delete API key |
| /api/v1/media | GET | /api/v1/media | List media |
| /api/v1/media | POST | /api/v1/media/add | Ingest media |
| /api/v1/media | POST | /api/v1/media/process-web-scraping | Ingest from web scrape |
| /api/v1/media | GET | /api/v1/media/debug/schema | Debug DB schema |
| /api/v1/media | GET | /api/v1/media/{id}/embeddings/status | Media embeddings status |
| /api/v1/media | POST | /api/v1/media/{id}/embeddings | Generate media embeddings |
| /api/v1/media | DELETE | /api/v1/media/{id}/embeddings | Delete media embeddings |
| /api/v1/audio | POST | /api/v1/audio/speech | Text-to-speech |
| /api/v1/audio | POST | /api/v1/audio/transcriptions | File STT |
| /api/v1/audio | POST | /api/v1/audio/translations | Audio translation |
| /api/v1/audio | WS | /api/v1/audio/stream/transcribe | Real-time STT |
| /api/v1/audio | GET | /api/v1/audio/voices/catalog | TTS voice catalog |
| /api/v1/chat | POST | /api/v1/chat/completions | Chat completions (OpenAI) |
| /api/v1/characters | GET | /api/v1/characters | List characters |
| /api/v1/characters | POST | /api/v1/characters | Create character |
| /api/v1/characters | GET | /api/v1/characters/{character_id} | Get character |
| /api/v1/chats | POST | /api/v1/chats | Create chat session |
| /api/v1/chats | GET | /api/v1/chats | List chat sessions |
| /api/v1/chats | POST | /api/v1/chats/{chat_id}/completions | Complete chat |
| /api/v1/chats | POST | /api/v1/chats/{chat_id}/messages | Add message |
| /api/v1/chats | GET | /api/v1/chats/{chat_id}/messages | List messages |
| /api/v1/embeddings | POST | /api/v1/embeddings | Create embeddings |
| /api/v1/embeddings | GET | /api/v1/embeddings/models | List models |
| /api/v1/embeddings | GET | /api/v1/embeddings/providers-config | Providers config |
| /api/v1/vector_stores | POST | /api/v1/vector_stores | Create vector store |
| /api/v1/vector_stores | GET | /api/v1/vector_stores | List vector stores |
| /api/v1/vector_stores | POST | /api/v1/vector_stores/{id}/query | Query vectors |
| /api/v1/rag | GET | /api/v1/rag/capabilities | RAG capabilities |
| /api/v1/rag | POST | /api/v1/rag/ablate | RAG ablations |
| /api/v1/rag | POST | /api/v1/rag/search | Unified RAG search |
| /api/v1/research | POST | /api/v1/research/websearch | Web search |
| /api/v1/web-scraping | GET | /api/v1/web-scraping/status | Scraper status |
| /api/v1/ocr | GET | /api/v1/ocr/backends | OCR backends |
| /api/v1/notes | POST | /api/v1/notes | Create note |
| /api/v1/prompts | GET | /api/v1/prompts | List prompts |
| /api/v1/prompts | POST | /api/v1/prompts | Create prompt |
| /api/v1/prompts | POST | /api/v1/prompts/execute | Execute prompt |
| /api/v1/prompt-studio/status | GET | /api/v1/prompt-studio/status | Prompt Studio status |
| /api/v1/chatbooks | POST | /api/v1/chatbooks/export | Export chatbook |
| /api/v1/chatbooks | POST | /api/v1/chatbooks/import | Import chatbook |
| /api/v1/reading | POST | /api/v1/reading/save | Save reading item |
| /api/v1/reading | GET | /api/v1/reading/items | List reading items |
| /api/v1/mcp | GET | /api/v1/mcp/metrics | MCP metrics |
| /api/v1/mcp | POST | /api/v1/mcp/tools/execute | Execute MCP tool |
| /api/v1/workflows | POST | /api/v1/workflows | Create workflow |
| /api/v1/workflows | GET | /api/v1/workflows | List workflows |
| /api/v1/workflows | POST | /api/v1/workflows/run | Run workflow |
| /api/v1/scheduler/workflows | POST | /api/v1/scheduler/workflows | Create schedule |
| /api/v1/scheduler/workflows | GET | /api/v1/scheduler/workflows | List schedules |
| /api/v1/items | GET | /api/v1/items | Unified items |
| /api/v1/outputs | GET | /api/v1/outputs | List outputs |
| /api/v1/output-templates | GET | /api/v1/output-templates | List templates |
| /api/v1/watchlists | POST | /api/v1/watchlists/jobs/{job_id}/run | Run job |
| /api/v1/monitoring | GET | /api/v1/monitoring/alerts | List alerts |
| /api/v1/moderation | GET | /api/v1/moderation/users | List overrides |
| /api/v1/audit | GET | /api/v1/audit/export | Export audit |
| /api/v1 | GET | /api/v1/metrics/text | Metrics (Prometheus text) |
| /api/v1 | GET | /api/v1/healthz | Liveness |
| /api/v1 | GET | /api/v1/readyz | Readiness |

---

For the complete, authoritative list of routes and schemas, see the interactive OpenAPI docs at `/docs` and the endpoint modules under `tldw_Server_API/app/api/v1/endpoints/`.
