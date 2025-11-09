# Feature Status Matrix

Legend
- Working: Stable and actively supported
- WIP: In active development; APIs or behavior may evolve
- Experimental: Available behind flags or with caveats; subject to change

## Admin Reporting
- HTTP usage (daily): `GET /api/v1/admin/usage/daily`
- HTTP top users: `GET /api/v1/admin/usage/top`
- LLM usage log: `GET /api/v1/admin/llm-usage`
- LLM usage summary: `GET /api/v1/admin/llm-usage/summary` (group_by=`user|provider|model|operation|day`)
- LLM top spenders: `GET /api/v1/admin/llm-usage/top-spenders`
- LLM CSV export: `GET /api/v1/admin/llm-usage/export.csv`
- Grafana dashboard JSON (LLM cost + tokens): `Docs/Deployment/Monitoring/Grafana_LLM_Cost_Top_Providers.json`
- Grafana dashboard JSON (LLM Daily Spend): `Docs/Deployment/Monitoring/Grafana_LLM_Daily_Spend.json`
- Prometheus alert rules (daily spend thresholds): `Samples/Prometheus/alerts.yml`

## Media Ingestion

| Capability | Status | Notes | Links |
|---|---|---|---|
| URLs/files: video, audio, PDFs, EPUB, DOCX, HTML, Markdown, XML, MediaWiki | Working | Unified ingestion + metadata | [docs](Docs/Code_Documentation/Ingestion_Media_Processing.md) · [code](tldw_Server_API/app/api/v1/endpoints/media.py) |
| yt-dlp downloads + ffmpeg | Working | 1000+ sites via yt-dlp | [code](tldw_Server_API/app/core/Ingestion_Media_Processing/Video/Video_DL_Ingestion_Lib.py) |
| Adaptive/multi-level chunking | Working | Configurable size/overlap | [docs](Docs/API-related/Chunking_Templates_API_Documentation.md) · [code](tldw_Server_API/app/api/v1/endpoints/chunking.py) |
| OCR on PDFs/images | Working | Tesseract baseline; optional dots.ocr/POINTS | [docs](Docs/API-related/OCR_API_Documentation.md) · [code](tldw_Server_API/app/api/v1/endpoints/ocr.py) |
| MediaWiki import | Working | Config via YAML | [docs](Docs/Code_Documentation/Ingestion_Pipeline_MediaWiki.md) · [config](tldw_Server_API/Config_Files/mediawiki_import_config.yaml) |
| Browser extension capture | WIP | Web capture extension | [docs](Docs/Product/Content_Collections_PRD.md) |

## Audio (STT/TTS)

| Capability | Status | Notes | Links |
|---|---|---|---|
| File-based transcription | Working | faster_whisper, NeMo, Qwen2Audio | [docs](Docs/API-related/Audio_Transcription_API.md) · [code](tldw_Server_API/app/api/v1/endpoints/audio.py) |
| Real-time WS transcription | Working | `WS /api/v1/audio/stream/transcribe` | [docs](Docs/API-related/Audio_Transcription_API.md) · [code](tldw_Server_API/app/api/v1/endpoints/audio.py) |
| Diarization + VAD | Working | Optional diarization, timestamps | [docs](Docs/Code_Documentation/Ingestion_Pipeline_Audio.md) · [code](tldw_Server_API/app/api/v1/endpoints/audio.py) |
| TTS (OpenAI-compatible) | Working | Streaming + non-streaming | [docs](tldw_Server_API/app/core/TTS/TTS-README.md) · [code](tldw_Server_API/app/api/v1/endpoints/audio.py) |
| Voice catalog + management | Working | `GET /api/v1/audio/voices/catalog` | [docs](tldw_Server_API/app/core/TTS/README.md) · [code](tldw_Server_API/app/api/v1/endpoints/audio.py) |
| Audio jobs queue | Working | Background audio processing | [docs](Docs/API-related/Audio_Jobs_API.md) · [code](tldw_Server_API/app/api/v1/endpoints/audio_jobs.py) |

## RAG & Search

| Capability | Status | Notes | Links |
|---|---|---|---|
| Full-text search (FTS5) | Working | Fast local search | [docs](Docs/API-related/RAG-API-Guide.md) · [code](tldw_Server_API/app/api/v1/endpoints/rag_unified.py) |
| Embeddings + ChromaDB | Working | OpenAI-compatible embeddings | [docs](Docs/API-related/Embeddings_API_Documentation.md) · [code](tldw_Server_API/app/api/v1/endpoints/embeddings_v5_production_enhanced.py) |
| Hybrid BM25 + vector + rerank | Working | Contextual retrieval | [docs](Docs/API-related/RAG-API-Guide.md) · [code](tldw_Server_API/app/api/v1/endpoints/rag_unified.py) |
| Vector Stores (OpenAI-compatible) | Working | Chroma/PG adapters | [docs](Docs/API-related/Vector_Stores_Admin_and_Query.md) · [code](tldw_Server_API/app/api/v1/endpoints/vector_stores_openai.py) |
| Media embeddings ingestion | Working | Create vectors from media | [code](tldw_Server_API/app/api/v1/endpoints/media_embeddings.py) |
| pgvector backend | Experimental | Optional backend | [code](tldw_Server_API/app/core/RAG/rag_service/vector_stores/) |

## Chat & LLMs

| Capability | Status | Notes | Links |
|---|---|---|---|
| Chat Completions (OpenAI) | Working | Streaming supported | [docs](Docs/API-related/Chat_API_Documentation.md) · [code](tldw_Server_API/app/api/v1/endpoints/chat.py) |
| Function calling / tools | Working | Tool schema validation | [docs](Docs/API-related/Chat_API_Documentation.md) · [code](tldw_Server_API/app/api/v1/endpoints/chat.py) |
| Provider integrations (16+) | Working | Commercial + local | [docs](Docs/API-related/Providers_API_Documentation.md) · [code](tldw_Server_API/app/api/v1/endpoints/llm_providers.py) |
| Local providers | Working | vLLM, llama.cpp, Ollama, etc. | [docs](tldw_Server_API/app/core/LLM_Calls/README.md) · [code](tldw_Server_API/app/core/LLM_Calls/) |
| Strict OpenAI compat filter | Working | Filter non-standard keys | [docs](tldw_Server_API/app/core/LLM_Calls/README.md) |
| Providers listing | Working | `GET /api/v1/llm/providers` | [docs](Docs/API-related/Providers_API_Documentation.md) · [code](tldw_Server_API/app/api/v1/endpoints/llm_providers.py) |
| Moderation endpoint | Working | Basic wrappers | [code](tldw_Server_API/app/api/v1/endpoints/moderation.py) |

## Knowledge, Notes, Prompt Studio

| Capability | Status | Notes | Links |
|---|---|---|---|
| Notes + tagging | Working | Notebook-style notes | [code](tldw_Server_API/app/api/v1/endpoints/notes.py) |
| Prompt library | Working | Import/export | [code](tldw_Server_API/app/api/v1/endpoints/prompts.py) |
| Prompt Studio: projects/prompts/tests | Working | Test cases + runs | [docs](Docs/API-related/Prompt_Studio_API.md) · [code](tldw_Server_API/app/api/v1/endpoints/prompt_studio_projects.py) |
| Prompt Studio: optimization + WS | Working | Live updates | [docs](Docs/API-related/Prompt_Studio_API.md) · [code](tldw_Server_API/app/api/v1/endpoints/prompt_studio_optimization.py) |
| Character cards & sessions | Working | SillyTavern-compatible | [docs](Docs/API-related/CHARACTER_CHAT_API_DOCUMENTATION.md) · [code](tldw_Server_API/app/api/v1/endpoints/characters_endpoint.py) |
| Chatbooks import/export | Working | Backup/export | [docs](Docs/API-related/Chatbook_API_Documentation.md) · [code](tldw_Server_API/app/api/v1/endpoints/chatbooks.py) |
| Flashcards | Working | Decks/cards, APKG export | [code](tldw_Server_API/app/api/v1/endpoints/flashcards.py) |
| Reading & highlights | Working | Reading items mgmt | [docs](Docs/Product/Content_Collections_PRD.md) · [code](tldw_Server_API/app/api/v1/endpoints/reading.py) |

## Evaluations

| Capability | Status | Notes | Links |
|---|---|---|---|
| G-Eval | Working | Unified eval API | [docs](Docs/API-related/Evaluations_API_Unified_Reference.md) · [code](tldw_Server_API/app/api/v1/endpoints/evaluations_unified.py) |
| RAG evaluation | Working | Pipeline presets + metrics | [docs](Docs/API-related/RAG-API-Guide.md) · [code](tldw_Server_API/app/api/v1/endpoints/evaluations_rag_pipeline.py) |
| OCR evaluation (JSON/PDF) | Working | Text + PDF flows | [docs](Docs/API-related/OCR_API_Documentation.md) · [code](tldw_Server_API/app/api/v1/endpoints/evaluations_unified.py) |
| Embeddings A/B tests | Working | Provider/model compare | [docs](Docs/API-related/Evaluations_API_Unified_Reference.md) · [code](tldw_Server_API/app/api/v1/endpoints/evaluations_embeddings_abtest.py) |
| Response quality & datasets | Working | Datasets CRUD + runs | [docs](Docs/API-related/Evaluations_API_Unified_Reference.md) · [code](tldw_Server_API/app/api/v1/endpoints/evaluations_unified.py) |

## Research & Web Scraping

| Capability | Status | Notes | Links |
|---|---|---|---|
| Web search (multi-provider) | Working | Google, DDG, Brave, Kagi, Tavily, Searx | [code](tldw_Server_API/app/api/v1/endpoints/research.py) |
| Aggregation/final answer | Working | Structured answer + evidence | [code](tldw_Server_API/app/api/v1/endpoints/research.py) |
| Academic paper search | Working | arXiv, BioRxiv/MedRxiv, PubMed/PMC, Semantic Scholar, OSF | [code](tldw_Server_API/app/api/v1/endpoints/paper_search.py) |
| Web scraping service | Working | Status, jobs, progress, cookies | [docs](Docs/Product/Content_Collections_PRD.md) · [code](tldw_Server_API/app/api/v1/endpoints/web_scraping.py) |

## Connectors (External Sources)

| Capability | Status | Notes | Links |
|---|---|---|---|
| Google Drive connector | Working | OAuth2, browse/import | [code](tldw_Server_API/app/api/v1/endpoints/connectors.py) |
| Notion connector | Working | OAuth2, nested blocks→Markdown | [code](tldw_Server_API/app/api/v1/endpoints/connectors.py) |
| Connector policy + quotas | Working | Org policy, job quotas | [docs](Docs/Product/Content_Collections_PRD.md) · [code](tldw_Server_API/app/api/v1/endpoints/connectors.py) |

## MCP Unified

| Capability | Status | Notes | Links |
|---|---|---|---|
| Tool execution APIs + WS | Working | Production MCP with JWT/RBAC | [docs](Docs/MCP/Unified/Developer_Guide.md) · [code](tldw_Server_API/app/api/v1/endpoints/mcp_unified_endpoint.py) |
| Catalog management | Working | Admin tool/permission catalogs | [docs](Docs/MCP/Unified/Modules.md) · [code](tldw_Server_API/app/api/v1/endpoints/mcp_catalogs_manage.py) |
| Status/metrics endpoints | Working | Health + metrics | [docs](Docs/MCP/Unified/System_Admin_Guide.md) · [code](tldw_Server_API/app/api/v1/endpoints/mcp_unified_endpoint.py) |

## AuthNZ, Security, Admin/Ops

| Capability | Status | Notes | Links |
|---|---|---|---|
| Single-user (X-API-KEY) | Working | Simple local deployments | [docs](Docs/API-related/AuthNZ-API-Guide.md) · [code](tldw_Server_API/app/api/v1/endpoints/auth.py) |
| Multi-user JWT + RBAC | Working | Users/roles/permissions | [docs](Docs/API-related/AuthNZ-API-Guide.md) · [code](tldw_Server_API/app/api/v1/endpoints/auth_enhanced.py) |
| API keys manager | Working | Create/rotate/audit | [docs](Docs/API-related/AuthNZ-API-Guide.md) · [code](tldw_Server_API/app/api/v1/endpoints/admin.py) |
| Egress + SSRF guards | Working | Centralized guards | [code](tldw_Server_API/app/api/v1/endpoints/web_scraping.py) |
| Audit logging & alerts | Working | Unified audit + alerts | [docs](Docs/API-related/Audit_Configuration.md) · [code](tldw_Server_API/app/api/v1/endpoints/admin.py) |
| Admin & Ops | Working | Users/orgs/teams, roles/perms, quotas, usage | [docs](Docs/API-related/Admin_Orgs_Teams.md) · [code](tldw_Server_API/app/api/v1/endpoints/admin.py) |
| Monitoring & metrics | Working | Prometheus text + JSON | [docs](Docs/Deployment/Monitoring/README.md) · [code](tldw_Server_API/app/api/v1/endpoints/metrics.py) |

## Storage, Outputs, Watchlists, Workflows, UI

| Capability | Status | Notes | Links |
|---|---|---|---|
| SQLite defaults | Working | Local dev/small deployments | [code](tldw_Server_API/app/core/DB_Management/) |
| PostgreSQL (AuthNZ, content) | Working | Postgres content mode | [docs](Docs/Published/Deployment/Postgres_Content_Mode.md) |
| Outputs: templates | Working | Markdown/HTML/MP3 via TTS | [code](tldw_Server_API/app/api/v1/endpoints/outputs_templates.py) |
| Outputs: artifacts | Working | Persist/list/soft-delete/purge | [code](tldw_Server_API/app/api/v1/endpoints/outputs.py) |
| Watchlists: sources/groups/tags | Working | CRUD + bulk import | [docs](Docs/Product/Watchlist_PRD.md) · [code](tldw_Server_API/app/api/v1/endpoints/watchlists.py) |
| Watchlists: jobs & runs | Working | Schedule, run, run details | [docs](Docs/Product/Watchlist_PRD.md) · [code](tldw_Server_API/app/api/v1/endpoints/watchlists.py) |
| Watchlists: templates & OPML | Working | Template store; OPML import/export | [docs](Docs/Product/Watchlist_PRD.md) · [code](tldw_Server_API/app/api/v1/endpoints/watchlists.py) |
| Watchlists: notifications | Experimental | Email/chatbook delivery | [docs](Docs/Product/Watchlist_PRD.md) |
| Workflows engine & scheduler | WIP | Defs CRUD, runs, scheduler | [docs](Docs/Product/Workflows_PRD.md) · [code](tldw_Server_API/app/api/v1/endpoints/workflows.py) |
| VLM backends listing | Experimental | `/api/v1/vlm/backends` | [code](tldw_Server_API/app/api/v1/endpoints/vlm.py) |
| Next.js WebUI | Working | Primary client | [code](tldw-frontend/) |
| Legacy WebUI (/webui) | Working | Feature-frozen legacy | [code](tldw_Server_API/WebUI/) |
