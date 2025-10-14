<div align="center">

<h1>tldw Server </br> API-First Media Analysis & Research Platform</h1>



[![Version](https://img.shields.io/badge/version-v0.1.0-blue)](https://github.com/rmusser01/tldw_server/releases)

[![madewithlove](https://img.shields.io/badge/made_with-%E2%9D%A4-red?style=for-the-badge&labelColor=orange)](https://github.com/rmusser01/tldw_server) 

[![License](https://img.shields.io/badge/license-GPLv2-blue)](https://www.gnu.org/licenses/old-licenses/gpl-2.0.en.html)


<h3>Process videos, audio, documents, web content and more with 16+ LLM providers + OpenAI-compatible APIs for Chat, Embeddings and Evals</h3>

<h3>Hosted SaaS + Browser Extension coming soon.</h3>

## Your own local, Open-Source Platform for Media Analysis, Knowledge Work and LLM-Backed (Creative) Efforts
</div>

---

## Core Features

<summary>Core Features</summary>

<details>

Legend: Stable = production-ready; WIP = actively evolving; Planned = upcoming

- Docs Hub: `Docs/Documentation.md`
- MCP Rate Limits Tuning: `Docs/Deployment/Operations/MCP_Rate_Limits_Tuning.md`
- Database Backends & Migrations: `Docs/Database-Backends.md`
- Moderation/Guardrails: `Docs/Moderation-Guardrails.md`
- Usage & Cost Tracking: `Docs/User_Guides/Usage_Module.md`

### Admin Reporting
- HTTP usage (daily): `GET /api/v1/admin/usage/daily`
- HTTP top users: `GET /api/v1/admin/usage/top`
- LLM usage log: `GET /api/v1/admin/llm-usage`
- LLM usage summary: `GET /api/v1/admin/llm-usage/summary` (group_by=`user|provider|model|operation|day`)
- LLM top spenders: `GET /api/v1/admin/llm-usage/top-spenders`
- LLM CSV export: `GET /api/v1/admin/llm-usage/export.csv`
- Grafana dashboard JSON (LLM cost + tokens): `Docs/Deployment/Monitoring/Grafana_LLM_Cost_Top_Providers.json`
 - Grafana dashboard JSON (LLM Daily Spend): `Docs/Deployment/Monitoring/Grafana_LLM_Daily_Spend.json`
- Prometheus alert rules (daily spend thresholds): `Samples/Prometheus/alerts.yml`

### Media Processing
- **Multi-format Support** [Stable]: Video, audio, PDF, EPUB, DOCX, HTML, Markdown, XML, MediaWiki dumps
- **Advanced Transcription** [Stable]: 
  - **Multiple Engines**: faster_whisper, NVIDIA Nemo (Canary, Parakeet), Qwen2Audio
  - **Live Transcription**: Real-time audio streaming with VAD and silence detection
  - **OpenAI Compatible API**: Drop-in replacement for OpenAI's audio transcription endpoints
  - **Model Variants**: Support for ONNX and MLX optimized models
- **Web Scraping** [Stable]: Advanced pipeline with job queue, rate limiting, and progress tracking
- **Batch Processing** [Stable]: Handle multiple files/URLs simultaneously
- **1000+ Sites** [Stable]: Compatible with any site supported by yt-dlp
- **OCR Backends** [Stable]: List/health for OCR backends and preload support (`GET /api/v1/ocr/backends`, `POST /api/v1/ocr/points/preload`). Docs: `Docs/API-related/OCR_API_Documentation.md`

#### Email Archives (ZIP of .eml, MBOX, PST/OST)
- Supported: Single `.eml` files (default), ZIP archives of `.eml`, and MBOX mailboxes when explicitly enabled per request. PST/OST is feature‑flagged with informative errors until external tools are configured.
- Opt-in flags:
  - `accept_archives=true` to allow `.zip` uploads of `.eml` files.
  - `accept_mbox=true` to allow `.mbox` uploads.
  - `accept_pst=true` to allow `.pst`/`.ost` uploads (feature flag; parsing requires external tools).
- Grouping: Each child email extracted from a ZIP receives `email_archive:<zip_file_stem>`; from an MBOX receives `email_mbox:<mbox_file_stem>`; PST/OST include `email_pst:<pst_file_stem>` for easy filtering in UI and search.
- Persistence: For `/api/v1/media/add`, each child email is persisted individually; the synthetic parent (ZIP/MBOX/PST) is not persisted.

Examples (cURL)

Process-only (returns child results, does not persist):

```
curl -X POST http://127.0.0.1:8000/api/v1/media/process-emails \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -F "accept_archives=true" \
  -F "perform_chunking=true" \
  -F "files=@/path/to/emails.zip;type=application/zip"
```

Add to media (persists each child email):

```
curl -X POST http://127.0.0.1:8000/api/v1/media/add \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -F "media_type=email" \
  -F "accept_archives=true" \
  -F "perform_chunking=true" \
  -F "files=@/path/to/emails.zip;type=application/zip"
```

MBOX (process-only and add):

```
curl -X POST http://127.0.0.1:8000/api/v1/media/process-emails \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -F "accept_mbox=true" \
  -F "perform_chunking=true" \
  -F "files=@/path/to/emails.mbox;type=application/mbox"

curl -X POST http://127.0.0.1:8000/api/v1/media/add \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -F "media_type=email" \
  -F "accept_mbox=true" \
  -F "perform_chunking=true" \
  -F "files=@/path/to/emails.mbox;type=application/mbox"
```

Notes:
- By default, only `.eml` is accepted for `media_type=email`. When `accept_archives=true`, `.zip` is also allowed; when `accept_mbox=true`, `.mbox` is also allowed; when `accept_pst=true`, `.pst`/`.ost` uploads are accepted but require external tooling to parse.
- Non-`.eml` entries inside the ZIP are ignored. Container limits (member count and uncompressed size) are enforced for safety; MBOX enforces message count and size limits.

PST/OST note
- When `pypff` (libpff) is installed, PST/OST messages are expanded and processed like MBOX with guardrails. Without `pypff`, enabling `accept_pst=true` returns an informative error; grouping keyword is still included for UI filtering.

### Content Analysis
- **17+ LLM Providers** [Stable]: 
  - Commercial: OpenAI, Anthropic, Cohere, DeepSeek, Google, Groq, HuggingFace, Mistral, OpenRouter, Qwen, AWS Bedrock
  - Local: Llama.cpp, Kobold.cpp, Oobabooga, TabbyAPI, vLLM, Ollama, Aphrodite, Custom OpenAI API endpoints supported
- **Flexible Analysis** [Stable]: Multiple chunking strategies and prompt customization
- **Evaluation System** [Stable]: G-Eval, RAG evaluation, response quality metrics

### Chunking
- **Strategy Registry** [Stable]: `words`, `sentences`, `paragraphs`, `tokens`, `semantic`, `structure_aware`, `propositions`, `json`, `xml`, `ebook_chapters`, `rolling_summarize` (`tldw_Server_API/app/core/Chunking/`)
- **Hierarchical Chunking** [Stable]: Structure-aware segmentation with ancestry metadata; outputs leaf chunks with offsets (ancestry metadata is used by RAG for parent/sibling expansions and citations)
- **Templates System** [Stable]: Stage-based and simple JSON templates with preprocessing/chunking/postprocessing; built-ins auto-seeded into DB at startup
- **Seed‑Driven Templates** [Stable]: Learn boundary rules from example documents; validate and match templates
- **APIs** [Stable]: Manage/apply templates and learn from examples (`/api/v1/chunking/templates/*`)
- **Scale‑Out Optional** [Stable]: Chunking workers in the embeddings pipeline (queues + workers) for high-throughput ingestion

### Chat & LLM
- **Chat API** [Stable]: OpenAI-compatible chat with history (`/api/v1/chat/completions`, `app/core/Chat/`)
- **Chat Dictionaries** [Stable]: CRUD + processing endpoints (`/api/v1/chat/*dictionaries*`)
- **Providers** [Stable]: 16+ providers + local backends; listing/health and model metadata (`/api/v1/llm/providers`, `/api/v1/llm/providers/{name}`, `/api/v1/llm/models`, `/api/v1/llm/models/metadata`, `/api/v1/llm/health`; code: `app/api/v1/endpoints/llm_providers.py`)

### AuthNZ, Organizations, and Keys
- **Auth Modes** [Stable]: Single-user API key; Multi-user JWT
- **Organizations & Teams** [New]: Group users into orgs and teams; membership management APIs
- **Virtual Keys** [New]: API keys with endpoint allowlists and day/month token/USD budgets for LLM usage control; optional provider/model allowlists
  - See: Docs/API-related/Virtual_Keys.md

### Audio
- **Speech-to-Text** [Stable]: faster_whisper, NeMo, Qwen2Audio; WebSocket streaming (`/api/v1/audio/stream/transcribe`)
- **File Transcription** [Stable]: OpenAI-compatible file API (`/api/v1/audio/transcriptions`)
- **Text-to-Speech** [Stable]: OpenAI-compatible TTS + local Kokoro ONNX (`/api/v1/audio/speech`)

### Search & Retrieval (Unified RAG)
- **Unified Pipeline** [Stable]: Async architecture with a single, parameter-driven pipeline
- **Hybrid Search** [Stable]: BM25 (SQLite FTS5) + vector embeddings (ChromaDB) with Reciprocal Rank Fusion
- **Advanced Strategies** [Stable]: Query Fusion, HyDE (Hypothetical Document Embeddings), vanilla search
- **Multi-Source Retrieval** [Stable]: Search across media, notes, characters, and chat history simultaneously
- **Smart Caching** [Stable]: LRU cache with semantic matching and TTL management
- **Flexible Configuration** [Stable]: Tune FTS/vector weights, thresholds, and reranking
- **RAG Docs**: `tldw_Server_API/app/core/RAG/README.md`, `tldw_Server_API/app/core/RAG/API_DOCUMENTATION.md`, `tldw_Server_API/app/core/RAG/UNIFIED_PIPELINE_EXAMPLES.md`, `tldw_Server_API/app/core/RAG/CAPABILITIES.md`

### Reranking (llama.cpp, GGUF: Qwen3, BGE, Jina-AI)
- **HTTP Reranker Endpoints** [Stable]:
  - `POST /v1/reranking` and `POST /v1/rerank` (versioned public aliases; auth required)
  - `POST /api/v1/llamacpp/reranking` (namespaced; fine‑grained controls)
- **Models**: Use GGUF embedding models via llama.cpp `llama-embedding`, including:
  - Qwen3 (e.g., `Qwen3-Embedding-0.6B_f16.gguf`)
  - BGE (e.g., `bge-small-en-v1.5.gguf`)
  - Jina-AI (e.g., `jina-embeddings-v2-base-en.gguf`)
- **Scoring**: Cosine(query, passage) similarity normalized to [0,1]
- **Config**: `.env`/`tldw_Server_API/Config_Files/config.txt` `[RAG]` keys like `llama_reranker_model`, `llama_reranker_binary`, `llama_reranker_ngl`, etc.
- **Model formatting**: Auto-instruct formatting for BGE (adds `query: ` and `passage: ` prefixes). You can override with `llama_reranker_template_mode`, `llama_reranker_query_prefix`, `llama_reranker_doc_prefix`. Default pooling automatically selected per model family (BGE/Jina → `mean`, Qwen → `last`).

Try it (cURL)

```bash
curl http://127.0.0.1:8000/v1/reranking \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -d '{
    "model": "/abs/path/Qwen3-Embedding-0.6B_f16.gguf",
    "query": "What is panda?",
    "top_n": 3,
    "documents": [
      "hi",
      "it is a bear",
      "The giant panda (Ailuropoda melanoleuca), sometimes called a panda bear or simply panda, is a bear species endemic to China."
    ]
  }'
```

Use Transformers backend (GPU):

```bash
curl http://127.0.0.1:8000/v1/reranking \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -d '{
    "backend": "transformers",
    "model": "BAAI/bge-reranker-v2-m3",
    "query": "What is panda?",
    "top_n": 3,
    "documents": [
      "hi",
      "it is a bear",
      "The giant panda (Ailuropoda melanoleuca), sometimes called a panda bear or simply panda, is a bear species endemic to China."
    ]
  }'
```

Use Transformers with Qwen3 Reranker (official yes/no prompt):

```bash
curl http://127.0.0.1:8000/v1/reranking \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -d '{
    "backend": "transformers",
    "model": "Qwen/Qwen3-Reranker-8B",
    "query": "What is the capital of China?",
    "top_n": 2,
    "documents": [
      "The capital of China is Beijing.",
      "Shanghai is the largest city in China."
    ]
  }'
```

- To customize the Qwen3 reranker instruction used in the `<Instruct>:` block, edit:
  - `tldw_Server_API/Config_Files/Prompts/rag.prompts.yaml: qwen3_reranker_instruction`
  - If unset, the default is: `Given a web search query, retrieve relevant passages that answer the query`.
  - You can also customize the ChatML system message via `qwen3_reranker_system`.

Programmatic (namespaced)

```bash
curl http://127.0.0.1:8000/api/v1/llamacpp/reranking \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -d '{
    "query": "What do llamas eat?",
    "passages": [
      {"id": "a", "text": "Llamas eat bananas"},
      {"id": "b", "text": "Llamas in pyjamas"}
    ],
    "top_k": 2,
    "model": "/abs/path/Qwen3-Embedding-0.6B_f16.gguf",
    "ngl": 99,
    "separator": "<#sep#>",
    "output_format": "json+",
    "pooling": "last",
    "normalize": -1
  }'
```

### API Capabilities
- **OpenAI Compatible** [Stable]: `/chat/completions` endpoint for drop-in replacement
- **RESTful Design** [Stable]: Consistent endpoint patterns following OpenAPI 3.0
- **WebSocket Support** [Stable]: Real-time connections via MCP (Model Context Protocol)
- **Comprehensive Docs** [Stable]: Auto-generated OpenAPI documentation at `/docs`

## Tokenizer Configuration (Chat Dictionaries & World Books)

Dictionary and World Book modules estimate tokens when enforcing token budgets. You can read and adjust the server’s token counting strategy via API:

- GET `/api/v1/config/tokenizer` → returns current mode (`whitespace`|`char_approx`) and divisor
- PUT `/api/v1/config/tokenizer` → updates mode and divisor (in‑memory; not persisted)

Example:

```
GET /api/v1/config/tokenizer
{
  "mode": "whitespace",
  "divisor": 4,
  "available_modes": ["whitespace", "char_approx"]
}

PUT /api/v1/config/tokenizer
{
  "mode": "char_approx",
  "divisor": 4
}
```

Notes:
- Affects token budgets in Chat Dictionary and World Book processing.
- Process‑wide and non‑persistent; add to env/config for defaults if needed.

### Knowledge Management
- **Note System** [Stable]: Create, search, and organize research notes
- **Prompt Library** [Stable]: Store and manage reusable prompts with import/export
- **Character Chat** [Stable]: SillyTavern-compatible character cards
- **Soft Delete** [Stable]: Trash system with recovery options

### Flashcards
- **Flashcards API** [WIP]: Deck + card CRUD, tags, review scheduling (SM-2), import (CSV/TSV, JSON/JSONL), and export (CSV/TSV, `.apkg`) (`tldw_Server_API/app/api/v1/endpoints/flashcards.py`)
- **Anki Export** [WIP]: `.apkg` generation with Basic/Cloze models (`tldw_Server_API/app/core/Flashcards/apkg_exporter.py`)
- Status: Experimental in 0.1 (tagged as such in OpenAPI); underlying DB is ChaChaNotes v5/v6 (`tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`)
- Design notes: `Docs/Design/Flashcards.md`

### Chatbooks - Portable Content Archives
- **Export/Import** [Stable]: Back up and migrate your content between servers
- **Selective Export** [Stable]: Choose specific conversations, notes, and characters to include
- **Media Preservation** [Stable]: Optionally include images, audio, and video files
- **Conflict Resolution** [Stable]: Smart handling of duplicate content during import
- **Background Processing** [Stable]: Async job queue for large exports/imports
- **Version Control** [Stable]: Create snapshots of your knowledge base at specific points
- **Sharing** [Stable]: Share curated collections with colleagues or team members

### Advanced Features
- **MCP Unified** [Stable core]: Production MCP server + tools with JWT/RBAC and WS/HTTP; Experimental tag in 0.1 OpenAPI. Endpoints: `/api/v1/mcp/ws`, `/api/v1/mcp/request`, `/api/v1/mcp/tools`, `/api/v1/mcp/tools/execute`, `/api/v1/mcp/modules`, `/api/v1/mcp/modules/health`, `/api/v1/mcp/status`, `/api/v1/mcp/metrics`, `/api/v1/mcp/metrics/prometheus`, `/api/v1/mcp/health` (see `app/api/v1/endpoints/mcp_unified_endpoint.py`).
- **Database Migrations** [Stable]: Automatic schema updates with versioning
- **Authentication** [Stable]: JWT-based auth with RBAC for MCP connections
- **Evaluation Tools** [Stable]: Benchmark your configurations and LLM performance
- **Prompt Studio** [WIP]: Projects, prompts, tests, optimization, reports; HTTP + WebSocket APIs under `/api/v1/prompt-studio/*`

### Core Platform
- **AuthNZ** [Stable]: Single-user API key and multi-user JWT (`app/core/AuthNZ/`); endpoints `/api/v1/auth/*`
- **Security & Rate Limiting** [Stable]: CORS, headers, request limiters (`app/core/Security/`, `app/core/RateLimiting/`)
- **DB Management** [Stable]: SQLite defaults, FTS5, versioning, sync log (`app/core/DB_Management/`)
- **Web UI** [Stable]: Integrated UI at `/webui` (`tldw_Server_API/WebUI/`)

### Evaluations
- **Unified Evaluations** [Stable]: Geval/RAG/batch/metrics (`/api/v1/evaluations/*`, `app/core/Evaluations/`)
- **Prompt Studio Jobs** [WIP]: Lightweight background execution + polling

### Research & Web
- **Paper Search** [Stable]: arXiv and related endpoints (`/api/v1/paper-search/*`)
- **Web Search Aggregator** [WIP]: Multi-provider search + aggregation (`/api/v1/research/websearch`) — supports Google, Bing, DuckDuckGo, and Brave today.
- **Browser Extension** [WIP]: `https://github.com/rmusser01/tldw_browser_assistant`

### Tooling & Integration
- **Metrics/Observability** [Stable]: Prometheus/OTel metrics & logging (`app/core/Metrics/`, Loguru throughout). Endpoints: root Prometheus `/metrics`, JSON `/api/v1/metrics`, plus `/api/v1/metrics/json`, `/api/v1/metrics/health`, `/api/v1/metrics/chat`.
- **Scheduler/Services** [Stable]: Background services & job helpers (`app/core/Scheduler/`, `app/services/`)
- **Sync** [Stable]: Sync logging and higher-level flows (`app/core/Sync/`)
- **Utilities & Third-Party** [Stable]: Helpers and vendor shims (`app/core/Utils/`, `app/core/Third_Party/`)
- **Flashcards** [WIP]: Early features for study workflows (`app/core/Flashcards/`)
- **Writing Tools** [Planned]: Expanded drafting/editing utilities (`app/core/Writing/`)

### Workflows
- **Composable Steps** [WIP]: Linear workflows with adapters for `prompt`, `rag_search`, `media_ingest`, `mcp_tool`, `webhook`, and `wait_for_human` (`tldw_Server_API/app/core/Workflows/`)
- **Execution Modes** [WIP]: Async/sync runs with in-process scheduler, per-tenant/workflow concurrency, and heartbeats
- **Resilience** [WIP]: Per-step retries, timeouts, cooperative cancel/pause; emits structured events for observability
- **State + Metrics** [WIP]: Persists run/step state in SQLite (`Workflows_DB.py`); integrates counters, histograms, spans
- **Templating** [WIP]: Jinja-sandboxed prompt templating with artifact capture
- **API** [WIP]: Definitions + runs + control under `/api/v1/workflows` (`endpoints/workflows.py`, `engine.py`, `registry.py`)
  - Status: Experimental in 0.1 (tagged in OpenAPI; engine labeled scaffolding in code)

### Deployment & Ops
- **Config & Env** [Stable]: `.env`, `config.txt`, examples (`tldw_Server_API/Config_Files/`)
- **Containers** [Stable]: Dockerfiles, compose, samples (`tldw_Server_API/Dockerfiles/`, `docker-compose.yml`)
- **Samples & Docs** [Stable]: Reverse proxy, Prometheus, Grafana (`Samples/*`, `Docs/*`)

</details>


## Samples (Quick Links)

- Reverse Proxy guide: `Docs/Deployment/Reverse_Proxy_Examples.md`
- Nginx sample config: `Samples/Nginx/nginx.conf`
- Traefik sample dynamic config: `Samples/Traefik/traefik-dynamic.yml`
- Production Hardening Checklist: `Docs/User_Guides/Production_Hardening_Checklist.md`
- Prometheus alert rules (near-quota): `Samples/Prometheus/alerts.yml`
- VibeVoice TTS (getting started): `Docs/VIBEVOICE_GETTING_STARTED.md`

### Monitoring (Prometheus + Grafana)
- Prometheus scrape endpoints:
  - Unauthenticated scrape: `GET /metrics` (Prometheus text)
  - MCP Prometheus text: `GET /api/v1/mcp/metrics/prometheus`
- LLM usage dashboard (cost + tokens):
  - Import JSON: `Docs/Deployment/Monitoring/Grafana_LLM_Cost_Top_Providers.json`
  - Panels included:
    - Cost rate by provider: `sum by (provider) (rate(llm_cost_dollars[$__rate_interval]))`
    - Top 5 providers by cost (range): `topk(5, sum by (provider) (increase(llm_cost_dollars[$__range])))`
    - Token rate by provider and type: `sum by (provider, type) (rate(llm_tokens_used_total[$__rate_interval]))`
  - Set Prometheus datasource UID to `prometheus` or edit to match your setup.

## QuickStart

```bash
git clone https://github.com/rmusser01/tldw_server
cd tldw_server
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r tldw_Server_API/requirements.txt

# Configure API providers (add keys to .env or tldw_Server_API/Config_Files/config.txt)
# ffmpeg is required for media/audio processing (brew install ffmpeg | apt install ffmpeg)

# Setup authentication (choose single or multi-user mode)
cp .env.authnz.template .env
# For single-user: Set AUTH_MODE=single_user and generate API key
# For multi-user: Set AUTH_MODE=multi_user and generate JWT secret
python -m tldw_Server_API.app.core.AuthNZ.initialize

# Start server
python -m uvicorn tldw_Server_API.app.main:app --reload
# API docs: http://127.0.0.1:8000/docs
# Web UI:   http://127.0.0.1:8000/webui/
# Your API key will be shown in console (single-user mode)
```

## Web UI

- Navigate to `http://127.0.0.1:8000/webui/` for the integrated Web UI.
- Use the tabs to explore API features, run requests, and view responses.
 - For reverse proxy and TLS examples (Nginx/Traefik), see `Docs/Deployment/Reverse_Proxy_Examples.md`.

### Web UI Feature Details
- Chat Dictionaries UI and Providers UI details have moved to: `tldw_Server_API/WebUI/README.md#ui-feature-details`
  - Chat Dictionary API docs: `Docs/API-related/Chatbook_Features_API_Documentation.md`
  - Providers API docs: `Docs/API-related/Providers_API_Documentation.md`

Note: Background and project story moved to `Docs/About.md`.


---

## Developer Guides

- Documentation index: `Docs/Documentation.md` (see the "Developer Guides" section)
- Core module guides:
  - Chat Module: `Docs/Code_Documentation/Chat_Developer_Guide.md`
  - Chunking Module: `Docs/Code_Documentation/Chunking-Module.md`
  - RAG Module: `tldw_Server_API/app/core/RAG/README.md` and `tldw_Server_API/app/core/RAG/API_DOCUMENTATION.md`

### Ingestion & Media Processing Docs
- Overview: `Docs/Code_Documentation/Ingestion_Media_Processing.md`
- Pipelines:
  - Audio: `Docs/Code_Documentation/Ingestion_Pipeline_Audio.md`
  - Video: `Docs/Code_Documentation/Ingestion_Pipeline_Video.md`
  - PDF: `Docs/Code_Documentation/Ingestion_Pipeline_PDF.md`
  - EPUB: `Docs/Code_Documentation/Ingestion_Pipeline_Ebooks.md`
  - Documents: `Docs/Code_Documentation/Ingestion_Pipeline_Documents.md`
  - MediaWiki: `Docs/Code_Documentation/Ingestion_Pipeline_MediaWiki.md`

---

## Version 0.1.0 - API-First Architecture (Complete rebuild from Gradio PoC)

This is a major milestone release that transitions tldw from a Gradio-based application to a robust FastAPI backend:

- **API-First Design**: Full RESTful API with OpenAPI documentation
- **Stable Core**: Production-ready media processing and analysis
- **Extensive Features**: 14+ endpoint categories with 100+ operations
- **OpenAI Compatible**: Drop-in replacement for chat completions (Chat Proxy Server)
- **Gradio Deprecated**: The Gradio UI remains available but is no longer maintained/part of this project.
- **tldw_Chatbook**: Has become a separate standalone application

See the [Migration Guide](#migration-guide) if upgrading from a previous version.

---

## Architecture

<summary>Architecture</summary>
<details>
### Architecture Overview
![Architecture Overview](https://github.com/rmusser01/tldw_server/blob/main/Docs/Architecture_Overview.png)

tldw_server is built as a modern, scalable API service:

- **Framework**: FastAPI with async/await support
- **Database**: SQLite with FTS5 for search, ChromaDB for embeddings
- **API Design**: RESTful endpoints following OpenAPI 3.0
- **Authentication**: JWT tokens with role-based access control
- **Background Jobs**: Async task processing for long operations
- **Extensibility**: Plugin system via MCP (Model Context Protocol)

#### Database Scope (v0.1)
- **AuthNZ/User DB**: Supports PostgreSQL (recommended for multi-user) and SQLite (dev/local). Configure via `DATABASE_URL`.
- **Content/Media DBs**: SQLite with FTS5 by default (media, notes, characters, chat). PostgreSQL for content DBs is on the roadmap.

### Project Structure
```
tldw_server/
├── tldw_Server_API/          # Main API implementation
│   ├── app/
│   │   ├── api/v1/          # API endpoints
│   │   ├── core/            # Business logic
│   │   └── services/        # Background services
│   └── tests/               # Test suite
├── Docs/                    # Documentation
├── Helper_Scripts/          # Utilities
├── tldw_Server_API/Config_Files/config.txt  # Configuration
└── start-webui.sh          # Convenience script (optional)
```
</details>

---

## Installation

<summary>Installation</summary>

<details>

### Requirements
- Python 3.9+
- ffmpeg (for media processing)
- 8GB+ RAM (server takes up 3-4GB, rest to models)
- 10GB+ disk space

### Quick Install

```bash
# Clone repository
git clone https://github.com/rmusser01/tldw_server
cd tldw_server

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r tldw_Server_API/requirements.txt

# Configure
# Configure provider keys in .env or edit tldw_Server_API/Config_Files/config.txt

# Setup Authentication (First Time Only)
cp .env.authnz.template .env
# Edit .env with secure values (see Authentication Setup below)
python -m tldw_Server_API.app.core.AuthNZ.initialize

# Run server
python -m uvicorn tldw_Server_API.app.main:app --reload
```

### HuggingFace Remote Code Allowlist (trust_remote_code)

Some HuggingFace embedding models (e.g., the Stella v5 family) require executing repository code to load correctly. For security, the server enables `trust_remote_code=True` only for models matching a configurable allowlist.

- Variable: `TRUSTED_HF_REMOTE_CODE_MODELS`
- Type: Comma‑separated list of patterns (wildcards supported via fnmatch)
- Default: `*stella*` (enables Stella models such as `NovaSearch/stella_en_400M_v5`)
- Applied in: Embeddings v5 endpoint and the background embedding worker
- Logging: When enabled for a model, logs
  `HF trust_remote_code enabled for model '<model>' (matched '<pattern>')`

Examples

```bash
# Enable only Stella models (default)
export TRUSTED_HF_REMOTE_CODE_MODELS="*stella*"

# Enable a specific repo
export TRUSTED_HF_REMOTE_CODE_MODELS="NovaSearch/stella_en_400M_v5"

# Multiple entries (comma-separated)
export TRUSTED_HF_REMOTE_CODE_MODELS="NovaSearch/stella_en_400M_v5,thenlper/*-instructor*"

# Docker Compose (environment: section)
TRUSTED_HF_REMOTE_CODE_MODELS: "NovaSearch/stella_en_400M_v5,BAAI/*bge*"
```

Using config.txt

You can also set this in `Config_Files/config.txt` under the `[Embeddings]` section:

```
[Embeddings]
# ...other embedding settings...
trusted_hf_remote_code_models = NovaSearch/stella_en_400M_v5, BAAI/*bge*
```

Environment variables take precedence over config.txt.

Security Notes

- Enabling `trust_remote_code` executes code from the model repository. Only allow models you trust.
- The allowlist is case-insensitive and supports wildcards. Non‑matching models keep `trust_remote_code=False` by default.

### Docker Installation

```bash
# CPU only
docker build -f tldw_Server_API/Dockerfiles/Dockerfile -t tldw-cpu .
docker run -p 8000:8000 tldw-cpu

# With GPU support
docker build -f tldw_Server_API/Dockerfiles/Dockerfile -t tldw-gpu .
docker run --gpus all -p 8000:8000 tldw-gpu
```

### Reverse Proxy & TLS (Samples)

- Examples and guidance: `Docs/Deployment/Reverse_Proxy_Examples.md`
- Sample config files included in this repo:
  - Nginx: `Samples/Nginx/nginx.conf`
  - Traefik (dynamic config): `Samples/Traefik/traefik-dynamic.yml`
- Set `tldw_production=true` and restrict CORS via `ALLOWED_ORIGINS` in production.

## Samples

Prebuilt configuration samples are included to speed up deployments:

- Nginx reverse proxy: `Samples/Nginx/nginx.conf`
  - Copy/mount as `/etc/nginx/conf.d/default.conf`
  - Update `server_name` and TLS certificate paths
  - Ensures WebSocket upgrades and long request timeouts

- Traefik dynamic config: `Samples/Traefik/traefik-dynamic.yml`
- Grafana dashboard (security): `Docs/Deployment/Monitoring/security-dashboard.json`
- Prometheus alerts (near-quota): `Samples/Prometheus/alerts.yml`
  - Mount into Traefik file provider (e.g., `/etc/traefik/dynamic`)
  - Configure static settings for Docker provider, entrypoints, and LetsEncrypt

See `Docs/Deployment/Reverse_Proxy_Examples.md` for end-to-end examples and Docker Compose snippets.

## Metrics Cheatsheet

- See: `Docs/Deployment/Monitoring/Metrics_Cheatsheet.md` (Prometheus endpoints, metric names, and PromQL examples).

</details>

---

## Authentication Setup

- Single-user (X-API-KEY): `cp .env.authnz.template .env` → set `AUTH_MODE=single_user` and `SINGLE_USER_API_KEY` → `python -m tldw_Server_API.app.core.AuthNZ.initialize`. The API key prints at startup (masked in production).
- Multi-user (JWT): set `AUTH_MODE=multi_user`, `JWT_SECRET_KEY`, and `DATABASE_URL` (PostgreSQL in production) → initialize → login via `/api/v1/auth/login`.
- Full guide: `Docs/User_Guides/Authentication_Setup.md` • API reference: `Docs/API-related/AuthNZ-API-Guide.md` • Dev guide: `Docs/Development/AuthNZ-Developer-Guide.md`

---

## OCR Support

- Overview: Optional OCR for scanned/low-text PDFs via a pluggable adapter. Default backend uses the system `tesseract` CLI.
- Install Tesseract:
  - macOS: `brew install tesseract`
  - Debian/Ubuntu: `sudo apt-get install tesseract-ocr`
  - Windows: Install Tesseract and ensure `tesseract.exe` is on PATH
- API options (PDF endpoints):
  - `enable_ocr`: boolean (default: false)
  - `ocr_backend`: string (e.g., `tesseract` or `auto`)
  - `ocr_lang`: string (e.g., `eng`)
  - `ocr_dpi`: integer (72–600, default 300)
  - `ocr_mode`: `always` or `fallback` (default `fallback`)
  - `ocr_min_page_text_chars`: int threshold per page to trigger fallback (default 40)
  - API docs: `Docs/API-related/OCR_API_Documentation.md`

---

## API Documentation

Full API documentation is available at `http://localhost:8000/docs` when the server is running.

<summary>API Documentation</summary>

<details>

### Main Endpoints

#### Media Processing
- `POST /api/v1/media/process` - Process media from URL or file
- `POST /api/v1/media/ingest` - Ingest media into database
- `GET /api/v1/media/search` - Search ingested content
- `GET /api/v1/media/{id}` - Get media details
  - Query params:
    - `include_content` (bool, default: true): include the main content text
    - `include_versions` (bool, default: true): include versions list summary
    - `include_version_content` (bool, default: false): include content text for each version
  - Notes: Response shape is unified across GET/PUT/POST version/rollback and conforms to `MediaDetailResponse`

#### Chat (OpenAI Compatible)
- `POST /api/v1/chat/completions` - Chat completion (OpenAI format)
- `GET /api/v1/chat/history` - Get chat history
- `POST /api/v1/chat/characters` - Character chat

#### RAG (Retrieval-Augmented Generation)
- `POST /api/v1/rag/search` - Unified search with all features accessible
- `POST /api/v1/rag/search/stream` - Streamed answer with incremental claim overlay (NDJSON)
- `POST /api/v1/rag/batch` - Batch processing for multiple queries
- `GET /api/v1/rag/simple` - Simplified search interface
- `GET /api/v1/rag/advanced` - Advanced search with common features
- `GET /api/v1/rag/features` - List available features
- `GET /api/v1/rag/capabilities` - Feature defaults, limits, and supported options
- `GET /api/v1/rag/health` - RAG service health status

#### Content Management
- `POST /api/v1/notes` - Create note
- `GET /api/v1/notes` - List notes
- `POST /api/v1/prompts` - Create prompt
- `GET /api/v1/prompts` - List prompts

#### Chatbooks
- `POST /api/v1/chatbooks/export` - Export content to chatbook
- `POST /api/v1/chatbooks/import` - Import chatbook file
- `POST /api/v1/chatbooks/preview` - Preview chatbook contents
- `GET /api/v1/chatbooks/export/jobs` - List export jobs
- `GET /api/v1/chatbooks/import/jobs` - List import jobs
- `GET /api/v1/chatbooks/download/{job_id}` - Download exported chatbook

#### Providers
- `GET /api/v1/llm/health` - LLM inference subsystem health
- `GET /api/v1/llm/providers` - Configured providers and models
- `GET /api/v1/llm/providers/{provider}` - Details for a specific provider
- `GET /api/v1/llm/models` - Flat list of `<provider>/<model>` values
- `GET /api/v1/llm/models/metadata` - Flattened model capability metadata

Providers API reference: `Docs/API-related/Providers_API_Documentation.md`

#### Advanced Features
- `POST /api/v1/chunking/chunk` - Chunk text content
- `POST /api/v1/research/websearch` - Web search across providers with optional aggregation
- `POST /api/v1/evaluations/geval` - Run G-Eval
- `POST /api/v1/evaluations/propositions` - Proposition extraction evaluation (precision/recall/F1)
- `GET /api/v1/mcp/status` - MCP server status
#### Paper Search (Provider-specific)
- `GET /api/v1/paper-search/arxiv` - Search arXiv papers
- `GET /api/v1/paper-search/arxiv/by-id` - Fetch arXiv by ID
- `GET /api/v1/paper-search/biorxiv` - Search BioRxiv/MedRxiv papers
- `GET /api/v1/paper-search/semantic-scholar` - Search Semantic Scholar
- `GET /api/v1/paper-search/pubmed` - Search PubMed (E-utilities)
- `GET /api/v1/paper-search/biorxiv/by-doi` - Fetch BioRxiv/MedRxiv by DOI
- `GET /api/v1/paper-search/biorxiv-pubs` - Search published metadata (bioRxiv/medRxiv)
- `GET /api/v1/paper-search/biorxiv-pubs/by-doi` - Fetch published metadata by DOI
- `GET /api/v1/paper-search/semantic-scholar/by-id` - Fetch Semantic Scholar by paperId

### Example Usage

#### Process a YouTube Video
```bash
curl -X POST "http://localhost:8000/api/v1/media/process" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.youtube.com/watch?v=...",
    "api_name": "openai",
    "summary_prompt": "Summarize the key points"
  }'
```

#### Research Websearch (New)
```bash
curl -X POST "http://localhost:8000/api/v1/research/websearch" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "what is the capital of france",
    "engine": "duckduckgo",
    "result_count": 5,
    "aggregate": false
  }'
```

Sample response (aggregate=false):
```json
{
  "web_search_results_dict": {
    "results": [
      {
        "title": "Paris - Wikipedia",
        "url": "https://en.wikipedia.org/wiki/Paris",
        "content": "Paris is the capital and most populous city of France...",
        "metadata": {"source": "wikipedia.org"}
      }
    ],
    "total_results_found": 5
  },
  "sub_query_dict": {"main_goal": "what is the capital of france", "sub_questions": []}
}
```

Set `aggregate: true` to also get a `final_answer` and `relevant_results` generated by the server:
```json
{
"final_answer": {
  "text": "The capital of France is Paris.",
  "confidence": 0.9,
  "evidence": [
    {"content": "Paris is the capital of France...", "reasoning": "Direct statement"}
  ],
  "chunks": [
    {"chunk_index": 1, "summary": "Chunk 1 Summary...", "generated": true}
  ]
},
  "relevant_results": {"0": {"title": "Paris - Wikipedia", "url": "https://..."}},
  "web_search_results_dict": {"results": [...]},
  "sub_query_dict": {"main_goal": "...", "sub_questions": ["..."]}
}
```

#### Chat Completion (OpenAI Compatible)
```bash
curl -X POST "http://localhost:8000/api/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

Ephemeral by default: By default, new chats are not saved to the database. To persist a chat, set `save_to_db: true` in the request body:

```bash
curl -X POST "http://localhost:8000/api/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Hello!"}],
    "save_to_db": true
  }'
```

Server-wide default: You can change the default persistence behavior without modifying clients.

- Environment (highest precedence): `CHAT_SAVE_DEFAULT=true`
- Config file (`tldw_Server_API/Config_Files/config.txt`):

```
[Chat-Module]
# Save new chats by default (True/False)
chat_save_default = False
```

If neither is set, the server falls back to `[Auto-Save] save_character_chats` for legacy configs. The WebUI exposes a “Save to DB” checkbox and defaults it based on server config.

#### Search Media
```bash
curl -X GET "http://localhost:8000/api/v1/media/search?query=machine+learning&limit=10"
```

#### RAG Search & Q&A
```bash
# Unified search with all features
curl -X POST "http://localhost:8000/api/v1/rag/search" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: your-api-key" \
  -d '{
    "query": "machine learning concepts",
    "sources": ["media_db", "notes"],
    "search_mode": "hybrid",
    "enable_citations": true,
    "citation_style": "apa",
    "top_k": 10
  }'

# Enable factual claims (APS) and summary
curl -X POST "http://localhost:8000/api/v1/rag/search" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: your-api-key" \
  -d '{
    "query": "What is CRISPR?",
    "enable_generation": true,
    "enable_claims": true,
    "claim_extractor": "aps",
    "claim_verifier": "hybrid",
    "claims_top_k": 5,
    "claims_conf_threshold": 0.7,
    "claims_max": 20
  }'

# Streaming with NDJSON (emits text deltas and claims_overlay events)
curl -X POST "http://localhost:8000/api/v1/rag/search/stream" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: your-api-key" \
  -N \
  -d '{
    "query": "What is CRISPR?",
    "enable_generation": true,
    "enable_claims": true,
    "claims_concurrency": 8
  }'
## Events:
# {"type":"delta","text":"..."}
# {"type":"claims_overlay", ...}
# {"type":"final_claims", ...}

# Optional: Set a local NLI model for offline verification
# export RAG_NLI_MODEL=/models/roberta-large-mnli

### APS (Abstractive Proposition Segmentation)

APS decomposes text into atomic, verifiable propositions for claim‑level grounding.
https://huggingface.co/google/gemma-2b-aps-it
https://huggingface.co/google/gemma-7b-aps-it
- Enable in RAG: set `"enable_claims": true, "claim_extractor": "aps"` to extract APS‑style claims from the generated answer and verify each against retrieved contexts.
- Proposition chunking: use `method="propositions"`, `proposition_engine="llm"`, `proposition_prompt_profile="gemma_aps"` to chunk text into APS‑style propositions outside of RAG.
- Model options (optional):
  - `google/gemma-2b-aps-it`
  - `google/gemma-7b-aps-it` (and community GGUF variants)
- Configuration tips:
  - The APS extractor calls your default OpenAI‑compatible chat endpoint; to back it with a specific APS‑IT model, set your gateway (vLLM/TabbyAPI/OpenRouter/custom‑openai) to use that model by default.
  - For ingestion‑time claims (non‑APS path), you can also set `CLAIMS_LLM_PROVIDER` and `CLAIMS_LLM_MODEL` in `tldw_Server_API/Config_Files/config.txt`.
  - For local verification, set `RAG_NLI_MODEL` (e.g., `roberta-large-mnli`).
  - For streaming overlays, control verification fan‑out with `claims_concurrency` (default 8, range 1–32).

# Simple search interface
curl -X GET "http://localhost:8000/api/v1/rag/simple?q=machine%20learning&limit=5" \
  -H "X-API-KEY: your-api-key"

# Batch processing
curl -X POST "http://localhost:8000/api/v1/rag/batch" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: your-api-key" \
  -d '{
    "queries": ["What is AI?", "Explain ML", "Define neural networks"],
    "sources": ["media_db"],
    "max_concurrent": 3
  }'
```

#### Chatbook Export/Import
```bash
# Export all content to a chatbook
curl -X POST "http://localhost:8000/api/v1/chatbooks/export" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "name": "Weekly Backup",
    "description": "Full backup of all content",
    "content_selections": {},
    "include_media": true,
    "async_mode": true
  }'

# Import a chatbook
curl -X POST "http://localhost:8000/api/v1/chatbooks/import" \
  -H "Authorization: Bearer your-api-key" \
  -F "file=@my_chatbook.chatbook" \
  -F 'options={"conflict_resolution": "skip"}'
```

</details>

---

## RAG Documentation

The RAG module has comprehensive documentation for both developers and API consumers:

- **[RAG Developer Guide](Docs/Development/RAG-Developer-Guide.md)** - Architecture, components, testing, and extending the RAG module
- **[RAG API Guide](Docs/API-related/RAG-API-Guide.md)** - Complete API reference with examples in JavaScript, Python, and cURL

### Anthropic Contextual RAG (example config)

To enable Contextual RAG using Anthropic for generating per‑chunk context headers and optional document outlines, set these in `tldw_Server_API/Config_Files/config.txt`:

```ini
# Use Anthropic as the default provider so contextualization calls route correctly
default_api = anthropic

[Embeddings]
enable_contextual_chunking = true
contextual_llm_provider = anthropic
contextual_llm_model = claude-3-7-sonnet-20250219
contextual_llm_temperature = 0.1
context_strategy = outline_window   # options: auto | full | window | outline_window
context_window_size = 1200          # integer; or set to None to always use full document
context_token_budget = 6000         # used when strategy=auto

[API]
# Ensure your Anthropic API is configured; also set ANTHROPIC_API_KEY in your .env
anthropic_model = claude-3-7-sonnet-20250219
anthropic_temperature = 0.1
```

Notes:
- Customize the prompts for contextualization and outline under `tldw_Server_API/Config_Files/Prompts/embeddings.prompts.yaml|.md` using keys `situate_context_prompt` and `document_outline_prompt`.
- You can override the contextual LLM model per call using `llm_model_for_context` in `process_and_store_content`.

---

## Configuration

<summary>Configuration </summary>

<details>

### config.txt
The main configuration file contains API keys and settings:

```ini
# LLM API Keys
openai_api_key = sk-...
anthropic_api_key = sk-ant-...
cohere_api_key = ...

# Local LLM Endpoints
llama_api_url = http://localhost:8080/v1
kobold_api_url = http://localhost:5000

# Database Settings
database_path = ./Databases/
backup_path = ./Backups/

# Processing Settings
whisper_model = medium
chunk_size = 1000

# Speech-to-Text Settings
[STT-Settings]
default_transcriber = faster-whisper  # Options: faster-whisper, parakeet, canary, qwen2audio
nemo_model_variant = standard         # Options: standard, onnx, mlx (for Parakeet)
nemo_device = cuda                    # Options: cpu, cuda
nemo_cache_dir = ./models/nemo        # Where to cache Nemo models
```

### Environment Variables
Override config.txt with environment variables:
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `DATABASE_PATH`

Chunking (regex safety)
- `CHUNKING_REGEX_TIMEOUT` — float seconds to cap regex execution for chapter/section detection in the ebook chunker. Default: `2`. Values <= 0 are ignored. On timeout, the strategy falls back to size-based splitting. Example: `export CHUNKING_REGEX_TIMEOUT=0.5`.
- `CHUNKING_DISABLE_MP` — disable process-based isolation for regex. Default: Enabled (multiprocessing is disabled) when unset, for cross‑platform stability. Set to `0`/`false`/`no` to enable the optional process fallback; set to `1`/`true`/`yes` to keep it disabled. Note: enabling MP may not be supported in restricted environments or on some platforms.
- `CHUNKING_REGEX_SIMPLE_ONLY` — when set to `1`/`true`/`yes`, only a safe subset of regex constructs is permitted for custom chapter patterns (no grouping `()`, alternation `|`, wildcard `.`, `?`, `*`; allows literals, `^`/`$`, character classes, `\d`/`\w`, and `+` after safe atoms). Unsafe patterns are rejected during validation.

Test/CI (Prompt Studio)
- `TLDW_PS_BACKEND` = `sqlite` | `postgres` — select backend for the heavy optimization suite (default: `sqlite`).
- `TLDW_PS_STRESS` = `1` — enable larger datasets/iterations in heavy tests.
- `TLDW_PS_TC_COUNT` — override test-case volume (default 250; stress 1000).
- `TLDW_PS_ITERATIONS` — override iteration count (default 5; stress 10).
- `TLDW_PS_OPT_COUNT` — override concurrent optimizations (default 3; stress 8).
- `TLDW_TEST_POSTGRES_REQUIRED` = `1` — fail fast if Postgres probe fails; otherwise Postgres tests are skipped when unreachable.
- `TLDW_PS_SQLITE_WAL` = `1` — opt-in to WAL for per-test SQLite DBs; default is DELETE mode to reduce CI file churn.
- `DISABLE_HEAVY_STARTUP` = `1` — skip unrelated heavy app startup (MCP, TTS, chat workers, background loops) during tests; `TEST_MODE=true` also enables this.
- `TLDW_PS_JOB_LEASE_SECONDS` — lease window (seconds) for Prompt Studio job processing; expired processing jobs are reclaimed on the next acquire (default: 60).
- `TLDW_PS_HEARTBEAT_SECONDS` — heartbeat interval (seconds) for renewing job leases (default: half of lease window, up to 30).

Usage logging and LLM cost aggregation
- `USAGE_LOG_ENABLED` — enable HTTP usage logging middleware.
- `USAGE_LOG_EXCLUDE_PREFIXES` — JSON array of excluded path prefixes.
- `USAGE_AGGREGATOR_INTERVAL_MINUTES` — cadence for HTTP daily aggregation.
- `USAGE_LOG_RETENTION_DAYS` — retention window for `usage_log` pruning.
- `USAGE_LOG_DISABLE_META` — store `{}` instead of IP/User-Agent in meta.
- `DISABLE_USAGE_AGGREGATOR` — skip starting HTTP usage aggregator at startup.
- `LLM_USAGE_ENABLED` — enable LLM usage logging (tokens/cost).
- `LLM_USAGE_AGGREGATOR_ENABLED` — enable background LLM daily aggregation.
- `LLM_USAGE_AGGREGATOR_INTERVAL_MINUTES` — cadence for LLM daily aggregation.
- `LLM_USAGE_LOG_RETENTION_DAYS` — retention window for `llm_usage_log` pruning.
- `DISABLE_LLM_USAGE_AGGREGATOR` — skip starting LLM usage aggregator at startup.
- `PRICING_OVERRIDES` — JSON pricing overrides for token costs (see `Docs/User_Guides/Usage_Module.md`).

</details>

---

## Migration Guide

<summary> Migration Guide </summary>

<details>

### From Gradio Version (pre-0.1.0)

1. **Backup your databases**:
   ```bash
   cp -r ./Databases ./Databases.backup
   ```

2. **Update configuration**:
   - Copy your API keys from old config
   - New config.txt has additional settings

3. **Database migration**:
   ```bash
   python -m tldw_Server_API.app.core.DB_Management.migrate_db migrate
   ```
 
4. **API endpoints have changed**:
   - Gradio routes → FastAPI routes
   - See API documentation for new endpoints

5. **Frontend options**:
   - Gradio UI is deprecated
   - Use API directly or wait for chatbook release
   - Build your own frontend using the API

</details>

---

## Development

<summary> Development </summary>

<details>

### Running Tests
```bash
# All tests
python -m pytest -v

# Specific module
python -m pytest tests/Media_Ingestion_Modification/ -v

# With coverage
python -m pytest --cov=tldw_Server_API --cov-report=html
```

### Test Suite Toggles and CI Profile
- Postgres-backed AuthNZ integration tests are skipped unless Postgres is reachable. Force run by setting `TLDW_TEST_POSTGRES_REQUIRED=1`.
- MCP Unified tests are disabled by default. Enable with `RUN_MCP_TESTS=1`.
- Mock OpenAI server tests are disabled by default. Enable with `RUN_MOCK_OPENAI=1`.

Recommended CI env for broad coverage without heavy services:
```bash
TEST_MODE=true DISABLE_HEAVY_STARTUP=1 DISABLE_NLTK_DOWNLOADS=true SKIP_PROMPT_STUDIO_FTS=true \
RUN_MCP_TESTS=0 RUN_MOCK_OPENAI=0 python -m pytest -q
```
Use targeted jobs to run MCP or Postgres suites by enabling the corresponding flags and ensuring dependencies are available.

Suggested CI job profiles:
- Baseline (fast, wide coverage):
  - `TEST_MODE=true DISABLE_HEAVY_STARTUP=1 DISABLE_NLTK_DOWNLOADS=true SKIP_PROMPT_STUDIO_FTS=true`
  - `RUN_MCP_TESTS=0 RUN_MOCK_OPENAI=0`
- MCP Unified (integration):
  - `RUN_MCP_TESTS=1`
  - Do not set `DISABLE_HEAVY_STARTUP` for this job (MCP server initialization required)
- AuthNZ Postgres (integration):
  - `AUTH_MODE=multi_user` and `DATABASE_URL=postgresql://...`
  - `TLDW_TEST_POSTGRES_REQUIRED=1` to fail-fast if Postgres is unreachable
  - Provide Postgres service in CI (docker service/container)

### Pytest Markers
Use markers to target the right slice of the suite:

- unit: Fast, isolated tests. May mock external services or internal adapters. Example: TTS/Chat adapter mock tests.
- integration: Real flows with no mocking of internal components. Use real local fixtures (e.g., aiohttp webhook receiver, temp SQLite DBs).
- property: Hypothesis-based property tests that generate data and verify invariants.
- slow: Long-running tests; exclude by default in quick runs.
- requires_llm / requires_embeddings: Tests that need API keys or network; skipped in CI without credentials.

Examples
```bash
# Only unit tests
python -m pytest -m "unit" -v

# Only integration tests
python -m pytest -m "integration" -v

# Property tests for a specific area
python -m pytest -m "property" tldw_Server_API/tests/Embeddings_NEW/property -v
```

Notes
- Legacy RAG tests under `tldw_Server_API/tests/RAG` are deprecated and skipped by default. The unified pipeline lives under `tldw_Server_API/tests/RAG_NEW`.
- Integration tests should not mock internal components; prefer local, real fixtures (e.g., a local HTTP webhook server) for deterministic behavior.

#### Prompt Studio tests
- Heavy optimization suite is marked `slow` and runs against a single backend per run.
- Select backend with `TLDW_PS_BACKEND=sqlite|postgres` (default sqlite).
- Useful env vars: `TLDW_PS_STRESS=1`, `TLDW_PS_TC_COUNT`, `TLDW_PS_ITERATIONS`, `TLDW_PS_OPT_COUNT`, `TLDW_TEST_POSTGRES_REQUIRED=1`, `TLDW_PS_SQLITE_WAL=1`, `DISABLE_HEAVY_STARTUP=1`.

### Prompt Studio Metrics (quick reference)
- Gauges/counters: `prompt_studio.jobs.queued{job_type}`, `prompt_studio.jobs.processing{job_type}`, `prompt_studio.jobs.backlog{job_type}`, `prompt_studio.jobs.stale_processing`.
- Histograms: `prompt_studio.jobs.duration_seconds{job_type}`, `prompt_studio.jobs.queue_latency_seconds{job_type}`.
- Counters: `prompt_studio.jobs.retries_total{job_type}`, `prompt_studio.jobs.failures_total{job_type,reason}`, `prompt_studio.jobs.lease_renewals_total{job_type}`, `prompt_studio.jobs.reclaims_total{job_type}`.
- Idempotency counters: `prompt_studio.idempotency.hit_total{entity_type}`, `prompt_studio.idempotency.miss_total{entity_type}`.
- Postgres advisory locks: `prompt_studio.pg_advisory.lock_attempts_total`, `locks_acquired_total`, `unlocks_total`.
- See Docs: `Docs/API-related/Prompt_Studio_API.md` and `Docs/Postgres_Support_Status_and_Testing.md` for details.
</details>


### More Detailed explanation of this project (tldw_project)
<details>
<summary>**What is this Project? (Extended) - Click-Here**</summary>

### What is this Project?
- **What it is now:**
  - A tool that can ingest: audio, videos, articles, free form text, documents, and books as text into a personal, database, so that you can then search and chat with it at any time.
    - (+ act as a nice way of creating your personal 'media' database, a personal digital library with search!)
  - And of course, this is all open-source/free, with the idea being that this can massively help people in their efforts of research and learning.
    - I don't plan to pivot and turn this into a commercial project. I do plan to make a server version of it, with the potential for offering a hosted version of it, and am in the process of doing so. The hosted version will be 95% the same, missing billing and similar from the open source branch.
    - I'd like to see this project be used in schools, universities, and research institutions, or anyone who wants to keep a record of what they've consumed and be able to search and ask questions about it.
    - I believe that this project can be a great tool for learning and research, and I'd like to see it develop to a point where it could be reasonably used as such.
    - In the meantime, if you don't care about data ownership or privacy, https://notebooklm.google/ is a good alternative that works and is free.
- **Where its headed:**
  - Act as a Multi-Purpose Research tool. The idea being that there is so much data one comes across, and we can store it all as text. (with tagging!)
  - Imagine, if you were able to keep a copy of every talk, research paper or article you've ever read, and have it at your fingertips at a moments notice.
  - Now, imagine if you could ask questions about that data/information(LLM), and be able to string it together with other pieces of data, to try and create sense of it all (RAG)
  - Basically a [cheap foreign knockoff](https://tvtropes.org/pmwiki/pmwiki.php/Main/ShoddyKnockoffProduct) [`Young Lady's Illustrated Primer`](https://en.wikipedia.org/wiki/The_Diamond_Age) that you'd buy from some [shady dude in a van at a swap meet](https://tvtropes.org/pmwiki/pmwiki.php/Main/TheLittleShopThatWasntThereYesterday).
    * Some food for thought: https://notes.andymatuschak.org/z9R3ho4NmDFScAohj3J8J3Y
    * I say this recognizing the inherent difficulties in replicating such a device and acknowledging the current limitations of technology.
  - This is a free-time project, so I'm not going to be able to work on it all the time, but I do have some ideas for where I'd like to take it.
    - I view this as a personal tool I'll ideally continue to use for some time until something better/more suited to my needs comes along.
    - Until then, I plan to continue working on this project and improving as much as possible.
    - If I can't get a "Young Lady's Illustrated Primer" in the immediate, I'll just have to hack together some poor imitation of one....
</details>


### Local Models I recommend
<details>
<summary>**Local Models I Can Recommend - Click-Here**</summary>

### Local Models I recommend
- These are just the 'standard smaller' models I recommend, there are many more out there, and you can use any of them with this project.
  - One should also be aware that people create 'fine-tunes' and 'merges' of existing models, to create new models that are more suited to their needs.
  - This can result in models that may be better at some tasks but worse at others, so it's important to test and see what works best for you.
- Llama 3.1 - The native llamas will give you censored output by default, but you can jailbreak them, or use a finetune which has attempted to tune out their refusals. 

For commercial API usage for use with this project: Claude Sonnet 3.5, Cohere Command R+, DeepSeek, gpt4o. 
Flipside I would say none, honestly. The (largest players) will gaslight you and charge you money for it. Fun.
That being said they obviously can provide help/be useful(helped me make this app), but it's important to remember that they're not your friend, and they're not there to help you. They are there to make money not off you, but off large institutions and your data.
You are just a stepping stone to their goals.

From @nrose 05/08/2024 on Threads:
```
No, it’s a design. First they train it, then they optimize it. Optimize it for what- better answers?
  No. For efficiency. 
Per watt. Because they need all the compute they can get to train the next model.So it’s a sawtooth. 
The model declines over time, then the optimization makes it somewhat better, then in a sort of 
  reverse asymptote, they dedicate all their “good compute” to the next bigger model.Which they then 
  trim down over time, so they can train the next big model… etc etc.
None of these companies exist to provide AI services in 2024. They’re only doing it to finance the 
 things they want to build in 2025 and 2026 and so on, and the goal is to obsolete computing in general
  and become a hidden monopoly like the oil and electric companies. 
2024 service quality is not a metric they want to optimize, they’re forced to, only to maintain some 
  directional income
```
</details>


### <a name="helpful"></a> Helpful Terms and Things to Know
<details>
<summary>**Helpful things to know - Click-Here**</summary>

### Helpful things to know
- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5049562
- Purpose of this section is to help bring awareness to certain concepts and terms that are used in the field of AI/ML/NLP, as well as to provide some resources for learning more about them.
- Also because some of those things are extremely relevant and important to know if you care about accuracy and the effectiveness of the LLMs you're using.
- Some of this stuff may be 101 level, but I'm going to include it anyways. This repo is aimed at people from a lot of different fields, so I want to make sure everyone can understand what's going on. Or at least has an idea.
- LLMs 101(coming from a tech background): https://vinija.ai/models/LLM/
- LLM Fundamentals / LLM Scientist / LLM Engineer courses(Free): https://github.com/mlabonne/llm-course
- **Phrases & Terms**
  - **LLM** - Large Language Model - A type of neural network that can generate human-like text.
  - **API** - Application Programming Interface - A set of rules and protocols that allows one software application to communicate with another.
  - **API Wrapper** - A set of functions that provide a simplified interface to a larger body of code.
  - **API Key** - A unique identifier that is used to authenticate a user, developer, or calling program to an API.
  - **GUI** - Graphical User Interface
  - **CLI** - Command Line Interface
  - **DB** - Database
  - **SQLite** - A C-language library that implements a small, fast, self-contained, high-reliability, full-featured, SQL database engine.
  - **Prompt Engineering** - The process of designing prompts that are used to guide the output of a language model.
  - **Quantization** - The process of converting a continuous range of values into a finite range of discrete values.
  - **GGUF Files** - GGUF is a binary format that is designed for fast loading and saving of models, and for ease of reading. Models are traditionally developed using PyTorch or another framework, and then converted to GGUF for use in GGML. https://github.com/ggerganov/ggml/blob/master/docs/gguf.md
  - **Inference Engine** - A software system that is designed to execute a model that has been trained by a machine learning algorithm. Llama.cpp and Kobold.cpp are examples of inference engines.
- **Papers & Concepts**
  1. Lost in the Middle: How Language Models Use Long Contexts(2023)
    - https://arxiv.org/abs/2307.03172 
    - `We analyze the performance of language models on two tasks that require identifying relevant information in their input contexts: multi-document question answering and key-value retrieval. We find that performance can degrade significantly when changing the position of relevant information, indicating that current language models do not robustly make use of information in long input contexts. In particular, we observe that performance is often highest when relevant information occurs at the beginning or end of the input context, and significantly degrades when models must access relevant information in the middle of long contexts, even for explicitly long-context models`
  2. [Same Task, More Tokens: the Impact of Input Length on the Reasoning Performance of Large Language Models(2024)](https://arxiv.org/abs/2402.14848)
     - `Our findings show a notable degradation in LLMs' reasoning performance at much shorter input lengths than their technical maximum. We show that the degradation trend appears in every version of our dataset, although at different intensities. Additionally, our study reveals that the traditional metric of next word prediction correlates negatively with performance of LLMs' on our reasoning dataset. We analyse our results and identify failure modes that can serve as useful guides for future research, potentially informing strategies to address the limitations observed in LLMs.`
  3. Why Does the Effective Context Length of LLMs Fall Short?(2024)
    - https://arxiv.org/abs/2410.18745
    - `     Advancements in distributed training and efficient attention mechanisms have significantly expanded the context window sizes of large language models (LLMs). However, recent work reveals that the effective context lengths of open-source LLMs often fall short, typically not exceeding half of their training lengths. In this work, we attribute this limitation to the left-skewed frequency distribution of relative positions formed in LLMs pretraining and post-training stages, which impedes their ability to effectively gather distant information. To address this challenge, we introduce ShifTed Rotray position embeddING (STRING). STRING shifts well-trained positions to overwrite the original ineffective positions during inference, enhancing performance within their existing training lengths. Experimental results show that without additional training, STRING dramatically improves the performance of the latest large-scale models, such as Llama3.1 70B and Qwen2 72B, by over 10 points on popular long-context benchmarks RULER and InfiniteBench, establishing new state-of-the-art results for open-source LLMs. Compared to commercial models, Llama 3.1 70B with \method even achieves better performance than GPT-4-128K and clearly surpasses Claude 2 and Kimi-chat.`
  4. [RULER: What's the Real Context Size of Your Long-Context Language Models?(2024)](https://arxiv.org/abs/2404.06654)
    - `The needle-in-a-haystack (NIAH) test, which examines the ability to retrieve a piece of information (the "needle") from long distractor texts (the "haystack"), has been widely adopted to evaluate long-context language models (LMs). However, this simple retrieval-based test is indicative of only a superficial form of long-context understanding. To provide a more comprehensive evaluation of long-context LMs, we create a new synthetic benchmark RULER with flexible configurations for customized sequence length and task complexity. RULER expands upon the vanilla NIAH test to encompass variations with diverse types and quantities of needles. Moreover, RULER introduces new task categories multi-hop tracing and aggregation to test behaviors beyond searching from context. We evaluate ten long-context LMs with 13 representative tasks in RULER. Despite achieving nearly perfect accuracy in the vanilla NIAH test, all models exhibit large performance drops as the context length increases. While these models all claim context sizes of 32K tokens or greater, only four models (GPT-4, Command-R, Yi-34B, and Mixtral) can maintain satisfactory performance at the length of 32K. Our analysis of Yi-34B, which supports context length of 200K, reveals large room for improvement as we increase input length and task complexity.`
  5. Abliteration (Uncensoring LLMs)
     - [Uncensor any LLM with abliteration - Maxime Labonne(2024)](https://huggingface.co/blog/mlabonne/abliteration)
  6. Retrieval-Augmented-Generation
        - [Retrieval-Augmented Generation for Large Language Models: A Survey](https://arxiv.org/abs/2312.10997)
          - https://arxiv.org/abs/2312.10997
          - `Retrieval-Augmented Generation (RAG) has emerged as a promising solution by incorporating knowledge from external databases. This enhances the accuracy and credibility of the generation, particularly for knowledge-intensive tasks, and allows for continuous knowledge updates and integration of domain-specific information. RAG synergistically merges LLMs' intrinsic knowledge with the vast, dynamic repositories of external databases. This comprehensive review paper offers a detailed examination of the progression of RAG paradigms, encompassing the Naive RAG, the Advanced RAG, and the Modular RAG. It meticulously scrutinizes the tripartite foundation of RAG frameworks, which includes the retrieval, the generation and the augmentation techniques. The paper highlights the state-of-the-art technologies embedded in each of these critical components, providing a profound understanding of the advancements in RAG systems. Furthermore, this paper introduces up-to-date evaluation framework and benchmark. At the end, this article delineates the challenges currently faced and points out prospective avenues for research and development. `
  7. Prompt Engineering
     - Prompt Engineering Guide: https://www.promptingguide.ai/ & https://github.com/dair-ai/Prompt-Engineering-Guide
     - 'The Prompt Report' - https://arxiv.org/abs/2406.06608
  8. Bias and Fairness in LLMs
     - [ChatGPT Doesn't Trust Chargers Fans: Guardrail Sensitivity in Context](https://arxiv.org/abs/2407.06866)
       - `While the biases of language models in production are extensively documented, the biases of their guardrails have been neglected. This paper studies how contextual information about the user influences the likelihood of an LLM to refuse to execute a request. By generating user biographies that offer ideological and demographic information, we find a number of biases in guardrail sensitivity on GPT-3.5. Younger, female, and Asian-American personas are more likely to trigger a refusal guardrail when requesting censored or illegal information. Guardrails are also sycophantic, refusing to comply with requests for a political position the user is likely to disagree with. We find that certain identity groups and seemingly innocuous information, e.g., sports fandom, can elicit changes in guardrail sensitivity similar to direct statements of political ideology. For each demographic category and even for American football team fandom, we find that ChatGPT appears to infer a likely political ideology and modify guardrail behavior accordingly.`
- **Tools & Libraries**
  1. `llama.cpp` - A C++ inference engine. Highly recommend. 
     * https://github.com/ggerganov/llama.cpp
  2. `kobold.cpp` - A C++ inference engine. GUI wrapper of llama.cpp with some tweaks. 
     * https://github.com/LostRuins/koboldcpp
  3. `sillytavern` - A web-based interface for text generation models. Supports inference engines. Ignore the cat girls and weebness. This software is _powerful_ and _useful_. Also supports just about every API you could want.
     * https://github.com/SillyTavern/SillyTavern
  4. `llamafile` - A wrapper for llama.cpp that allows for easy use of local LLMs.
     * Uses libcosomopolitan for cross-platform compatibility. 
     * Can be used to run LLMs on Windows, Linux, and MacOS with a single binary wrapper around Llama.cpp.
  5. `pytorch` - An open-source machine learning library based on the Torch library.
  6. `ffmpeg` - A free software project consisting of a large suite of libraries and programs for handling video, audio, and other multimedia files and streams.
  7. `pandoc` - A free and open-source document converter, widely used as a writing tool (especially by scholars) and as a basis for publishing workflows. 
     * https://pandoc.org/
  8. `marker` - A tool for converting PDFs(and other document types) to markdown. 
     * https://github.com/VikParuchuri/marker
  9. `faster_whisper` - A fast, lightweight, and accurate speech-to-text model. 
      * https://github.com/SYSTRAN/faster-whisper

</details>


### Project Guidelines
See [Project_Guidelines.md](Project_Guidelines.md) for development philosophy and contribution guidelines.

---

## License

This project is licensed under the GNU General Public License v2.0.

---

## Credits

### <a name="credits"></a>Credits
- [The original version of tldw by @the-crypt-keeper](https://github.com/the-crypt-keeper/tldw/tree/main/tldw-original-scripts)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [ffmpeg](https://github.com/FFmpeg/FFmpeg)
- [faster_whisper](https://github.com/SYSTRAN/faster-whisper)
- [pyannote](https://github.com/pyannote/pyannote-audio)
- Thank you cognitivetech for the summarization system prompt: https://github.com/cognitivetech/llm-long-text-summarization/tree/main?tab=readme-ov-file#one-shot-prompting
- [Fabric](https://github.com/danielmiessler/fabric)
- [Llamafile](https://github.com/Mozilla-Ocho/llamafile) - For the local LLM inference engine
- [Mikupad](https://github.com/lmg-anon/mikupad) - Because I'm not going to write a whole new frontend for non-chat writing.
- The people who have helped me get to this point, and especially for those not around to see it(DT & CC).



### Security Disclosures
1. Information disclosure via developer print debugging statement in `chat_functions.py` - Thank you to @luca-ing for pointing this out!
    - Fixed in commit: `8c2484a`

---

## About

tldw_server started as a tool to transcribe and summarize YouTube videos but has evolved into a comprehensive media analysis and knowledge management platform. The goal is to help researchers, students, and professionals manage and analyze their media consumption effectively.

Long-term vision: Building towards a personal AI research assistant inspired by "The Young Lady's Illustrated Primer" from Neal Stephenson's "The Diamond Age" - a tool that helps you learn and research at your own pace.

### Getting Help
- API Documentation: `http://localhost:8000/docs`
- GitHub Issues: [Report bugs or request features](https://github.com/rmusser01/tldw_server/issues)
- Discussions: [Community forum](https://github.com/rmusser01/tldw_server/discussions)


#### And because Who doesn't love a good quote or two? (Particularly relevant to this material/LLMs)
- `I like the lies-to-children motif, because it underlies the way we run our society and resonates nicely with Discworld. Like the reason for Unseen being a storehouse of knowledge - you arrive knowing everything and leave realising that you know practically nothing, therefore all the knowledge you had must be stored in the university. But it's like that in "real Science", too. You arrive with your sparkling A-levels all agleam, and the first job of the tutors is to reveal that what you thought was true is only true for a given value of "truth". Most of us need just "enough" knowledge of the sciences, and it's delivered to us in metaphors and analogies that bite us in the bum if we think they're the same as the truth.`
    * Terry Pratchett
- `The first principle is that you must not fool yourself - and you are the easiest person to fool.`
  *Richard Feynman
  
---

**Note**: This is v0.1.0 with stable core functionality. Some features are still in development. Check the [roadmap](https://github.com/rmusser01/tldw_server/milestone/22) for upcoming features.
- AWS Bedrock (OpenAI-compatible Chat API)

  - Env vars (or config.txt [API] keys):
    - `BEDROCK_API_KEY` or `AWS_BEARER_TOKEN_BEDROCK`
    - `BEDROCK_REGION` (e.g., `us-west-2`) or `BEDROCK_RUNTIME_ENDPOINT` (e.g., `https://bedrock-runtime.us-west-2.amazonaws.com`)
    - `BEDROCK_MODEL` (optional default, e.g., `openai.gpt-oss-20b-1:0`)

  - Request example (Bedrock guardrails supported):

    POST /api/v1/chat/completions
    {
      "api_provider": "bedrock",
      "model": "openai.gpt-oss-20b-1:0",
      "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
      ],
      "extra_headers": {
        "X-Amzn-Bedrock-GuardrailIdentifier": "gr-123",
        "X-Amzn-Bedrock-GuardrailVersion": "1",
        "X-Amzn-Bedrock-Trace": "ENABLED"
      },
      "extra_body": {
        "amazon-bedrock-guardrailConfig": {"tagSuffix": "audit-tag"}
      }
    }

  - See Docs/Providers/AWS_Bedrock.md for details.
- performance: opt-in performance/scale tests (e.g., large ZIP/MBOX containers). Run with `-m "performance"`.
- requires_pypff: tests that require `pypff`/`libpff` to be installed locally. Run with `-m "requires_pypff"` (these skip if the module is not available).

Examples:

```
python -m pytest -q -m "performance" tldw_Server_API/tests/Media_Ingestion_Modification
python -m pytest -q -m "requires_pypff" tldw_Server_API/tests/Media_Ingestion_Modification
```
## Organizations, Teams, and Virtual Keys

You can logically group users into Organizations and Teams (teams belong to an org) and issue Virtual API Keys with tight scopes and budgets to limit LLM usage and reduce blast radius if a key leaks.

- Hierarchy
  - Organization → Teams → Users (membership tables managed by admin endpoints)
- Virtual Keys (API keys with extra metadata)
  - Endpoint allowlists: e.g., allow only `chat.completions` and/or `embeddings`
  - Budgets: day/month token limits and day/month USD limits
  - Optional provider/model allowlists: set allowlists and send `X-LLM-Provider` header; models are read from request JSON when available

Server-side enforcement
- Middleware checks Virtual Keys on LLM endpoints (`/api/v1/chat/completions`, `/api/v1/embeddings` by default)
- Blocks disallowed endpoints with 403
- Checks budgets from `llm_usage_log` and returns 402 if exceeded

Admin API (selected)
- POST `/api/v1/admin/orgs` — create organization; GET `/api/v1/admin/orgs` — list
- POST `/api/v1/admin/orgs/{org_id}/teams` — create team; GET `/api/v1/admin/orgs/{org_id}/teams` — list
- POST `/api/v1/admin/teams/{team_id}/members` — add user to team; GET `/api/v1/admin/teams/{team_id}/members` — list
- POST `/api/v1/admin/users/{user_id}/virtual-keys` — create virtual key with budgets/scopes
- GET `/api/v1/admin/users/{user_id}/virtual-keys` — list virtual keys (metadata only)
  - For a fuller RBAC endpoint list with OpenAPI snippets, see `Docs/Published/Admin_RBAC_API.md`.

RBAC: Effective Permissions View
- GET `/api/v1/admin/roles/{role_id}/permissions/effective` — Convenience view that combines a role’s granted permissions and tool-execution permissions.
  - Response fields:
    - `role_id`, `role_name`
    - `permissions`: non-tool permissions (e.g., `media.read`)
    - `tool_permissions`: tool permissions (e.g., `tools.execute:my_tool`)
    - `all_permissions`: union of both, sorted
- Example:
  ```bash
  curl -s -H "X-API-KEY: $SINGLE_USER_API_KEY" \
    http://127.0.0.1:8000/api/v1/admin/roles/2/permissions/effective | jq
  ```

Configuration
- `VIRTUAL_KEYS_ENABLED` default true
- `LLM_BUDGET_ENFORCE` default true
- `LLM_BUDGET_ENDPOINTS`: defaults to `[/api/v1/chat/completions, /api/v1/embeddings]`

Notes
- Budgets use the `llm_usage_log` table (already part of usage/cost tracking)
- Provider/model allowlist enforcement is optional and best-effort (parses JSON body when possible)
### Schedulers & Background Jobs

- AuthNZ Scheduled Jobs: The AuthNZ scheduler runs maintenance tasks such as session cleanup, API key cleanup, rate limit cleanup, audit log pruning, and usage log pruning according to configured retention periods.
  - Enabled by default at app startup.
  - Disable via `DISABLE_AUTHNZ_SCHEDULER=1` (or `true/yes/on`).
  - Recommended to keep enabled in production so retention and cleanup run automatically.

- Usage Aggregators: Background tasks aggregate request and LLM usage into daily tables to power reporting endpoints.
  - HTTP usage aggregator: controlled by `USAGE_LOG_ENABLED` and `USAGE_AGGREGATOR_INTERVAL_MINUTES`.
  - LLM usage aggregator: controlled by `LLM_USAGE_AGGREGATOR_ENABLED` and `LLM_USAGE_AGGREGATOR_INTERVAL_MINUTES`.
  - Disable via `DISABLE_USAGE_AGGREGATOR=1` or `DISABLE_LLM_USAGE_AGGREGATOR=1`.

Environment flags summary:

- `DISABLE_AUTHNZ_SCHEDULER`: Disable AuthNZ scheduler (retention/cleanup). Default: off.
- `DISABLE_USAGE_AGGREGATOR`: Disable HTTP usage daily aggregator. Default: off.
- `DISABLE_LLM_USAGE_AGGREGATOR`: Disable LLM usage daily aggregator. Default: off.
