<div align="center">

<h1>tldw Server - API-First Media Analysis & Research Platform</h1>

[![License](https://img.shields.io/badge/license-Apache%202-blue)](https://img.shields.io/badge/license-Apache%202-blue)
[![madewithlove](https://img.shields.io/badge/made_with-%E2%9D%A4-red?style=for-the-badge&labelColor=orange)](https://github.com/rmusser01/tldw_server) 

<h3>FastAPI-powered backend for media ingestion, analysis, and AI-powered research</h3>
<h3>Process videos, audio, documents, and web content with 16+ LLM providers</h3>
<h3>OpenAI-compatible API with RAG search, note-taking, and knowledge management</h3>

## Your own local, open-source platform for media analysis and knowledge management
</div>

---

## Samples (Quick Links)

- Reverse Proxy guide: `Docs/Deployment/Reverse_Proxy_Examples.md`
- Nginx sample config: `Samples/Nginx/nginx.conf`
- Traefik sample dynamic config: `Samples/Traefik/traefik-dynamic.yml`
- Production Hardening Checklist: `Docs/User_Guides/Production_Hardening_Checklist.md`

## QuickStart

```bash
git clone https://github.com/rmusser01/tldw_server
cd tldw_server
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Configure API providers
cp config.txt.example config.txt  # Add your LLM API keys

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

## Auth Quickstart

- Single-user mode:
  - Use the API key printed at startup in the `X-API-KEY` header.
  - Example: `curl -H "X-API-KEY: <your_key>" http://127.0.0.1:8000/api/v1/media/search`

- Multi-user mode:
  - Login with form-encoded credentials to get JWTs:
    ```bash
    curl -X POST http://127.0.0.1:8000/api/v1/auth/login \
      -H "Content-Type: application/x-www-form-urlencoded" \
      -d "username=<user>&password=<pass>"
    ```
  - Use the access token: `Authorization: Bearer <token>`
  - Get current user: `GET /api/v1/auth/me`

More details: see `Docs/API-related/AuthNZ-API-Guide.md` and `tldw_Server_API/app/core/AuthNZ/API_INTEGRATION_GUIDE.md`.

## Web UI

- Navigate to `http://127.0.0.1:8000/webui/` for the integrated Web UI.
- Use the tabs to explore API features, run requests, and view responses.
 - For reverse proxy and TLS examples (Nginx/Traefik), see `Docs/Deployment/Reverse_Proxy_Examples.md`.

### Chat Dictionaries UI
- Location: Chat → Dictionaries
- Capabilities:
  - Create/activate/deactivate/delete dictionaries
  - Add entries (pattern, replacement, type literal/regex, probability 0.0–1.0, enabled, case sensitivity, group, max replacements)
  - Inline edit entries and toggle enabled state
  - Filter entries by pattern and type
  - Process sample text through a dictionary with optional token budget and group filter
  - Import dictionaries from markdown content and export the current dictionary to markdown
- API Reference: see `Docs/API-related/Chatbook_Features_API_Documentation.md` → Chat Dictionary API

### Providers UI
- Location: Providers tab (or Settings → Providers) in the WebUI.
- Capabilities:
  - List configured providers and available models with basic metadata
  - Inspect provider health (status, circuit breaker, recent performance)
  - View request queue status (size, workers) and rate limiter settings
  - Copy `<provider>/<model>` names for use in Chat and RAG requests
- Backed by the Providers API:
  - `GET /api/v1/llm/health`
  - `GET /api/v1/llm/providers`
  - `GET /api/v1/llm/providers/{provider}`
  - `GET /api/v1/llm/models`
  - `GET /api/v1/llm/models/metadata`
- Docs: `Docs/API-related/Providers_API_Documentation.md`

<details>
<summary>What is this? - Click-here</summary>

### What is tldw_server?
**tldw_server** was originally `tldw`, a versatile tool designed to help you manage and interact with media content (videos, audio, documents, web articles, and books) via:
1. **Ingesting**: Importing media from URLs or local files into an offline database.
2. **Transcribing**: Automatically generating text transcripts from videos and audio using various whisper models using faster_whisper.
3. **Analyzing(Not Just Summarizing)**: Using LLMs (local or API-based) to perform analyses of the ingested content.
4. **Searching**: Full-text search across ingested content, including metadata like titles, authors, and keywords.
5. **Chatting**: Interacting with ingested content using natural language queries through supported LLMs.

All features were (are) designed to run **locally** on your device, ensuring privacy and data ownership. The tool was (is) open-source and free to use, with the goal of supporting research, learning, and personal knowledge management.

It has now been rewritten as a FastAPI Python server to support larger deployments and multiple users. This includes:
- A modern FastAPI backend with OpenAPI docs and integrated WebUI
- OpenAI-compatible Chat, Embeddings, STT/TTS endpoints
- AuthNZ module with single-user (API key) and multi-user (JWT) modes
- Hybrid RAG (FTS5 + vector + re-ranking) and a unified RAG API
- Multi-provider LLM integration (commercial + local)

</details>


---

## Developer Guides

- Documentation index: `Docs/Documentation.md` (see the "Developer Guides" section)
- Core module guides:
  - Chat Module: `Docs/Code_Documentation/Chat_Developer_Guide.md`
  - Chunking Module: `Docs/Code_Documentation/Chunking-Module.md`

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

## Core Features

<summary>Core Features</summary>

<details>

### Media Processing
- **Multi-format Support**: Video, audio, PDF, EPUB, DOCX, HTML, Markdown, XML, MediaWiki dumps
- **Advanced Transcription**: 
  - **Multiple Engines**: faster_whisper, NVIDIA Nemo (Canary, Parakeet), Qwen2Audio
  - **Live Transcription**: Real-time audio streaming with VAD and silence detection
  - **OpenAI Compatible API**: Drop-in replacement for OpenAI's audio transcription endpoints
  - **Model Variants**: Support for ONNX and MLX optimized models
- **Web Scraping**: Advanced pipeline with job queue, rate limiting, and progress tracking
- **Batch Processing**: Handle multiple files/URLs simultaneously
- **1000+ Sites**: Compatible with any site supported by yt-dlp

### Content Analysis
- **16+ LLM Providers**: 
  - Commercial: OpenAI, Anthropic, Cohere, DeepSeek, Google, Groq, HuggingFace, Mistral, OpenRouter
  - Local: Llama.cpp, Kobold.cpp, Oobabooga, TabbyAPI, vLLM, Ollama, Aphrodite
- **Flexible Analysis**: Multiple chunking strategies and prompt customization
- **Evaluation System**: G-Eval, RAG evaluation, response quality metrics

### Search & Retrieval (RAG v2)
- **Production-Ready RAG**: 100% test coverage, fully async architecture
- **Hybrid Search**: BM25 (SQLite FTS5) + vector embeddings (ChromaDB) with Reciprocal Rank Fusion
- **Advanced Strategies**: Query Fusion, HyDE (Hypothetical Document Embeddings), vanilla search
- **Multi-Source Retrieval**: Search across media, notes, characters, and chat history simultaneously
- **Smart Caching**: LRU cache with semantic matching and TTL management
- **Flexible Configuration**: Fine-tune semantic/fulltext weights, similarity thresholds, and reranking

### API Capabilities
- **OpenAI Compatible**: `/chat/completions` endpoint for drop-in replacement
- **RESTful Design**: Consistent endpoint patterns following OpenAPI 3.0
- **WebSocket Support**: Real-time connections via MCP (Model Context Protocol)
- **Comprehensive Docs**: Auto-generated OpenAPI documentation at `/docs`

### Knowledge Management
- **Note System**: Create, search, and organize research notes
- **Prompt Library**: Store and manage reusable prompts with import/export
- **Character Chat**: SillyTavern-compatible character cards
- **Soft Delete**: Trash system with recovery options

### Chatbooks - Portable Content Archives
- **Export/Import**: Back up and migrate your content between servers
- **Selective Export**: Choose specific conversations, notes, and characters to include
- **Media Preservation**: Optionally include images, audio, and video files
- **Conflict Resolution**: Smart handling of duplicate content during import
- **Background Processing**: Async job queue for large exports/imports
- **Version Control**: Create snapshots of your knowledge base at specific points
- **Sharing**: Share curated collections with colleagues or team members

### Advanced Features
- **MCP Server**: Model Context Protocol for tool integration and extensibility
- **Database Migrations**: Automatic schema updates with versioning
- **Authentication**: JWT-based auth with RBAC for MCP connections
- **Evaluation Tools**: Benchmark your configurations and LLM performance

</details>
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
└── config.txt              # Configuration
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
pip install -r requirements.txt

# Configure
cp config.txt.example config.txt
# Edit config.txt with your API keys

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
- Grafana dashboard (security): `Samples/Grafana/security-dashboard.json`
  - Mount into Traefik file provider (e.g., `/etc/traefik/dynamic`)
  - Configure static settings for Docker provider, entrypoints, and LetsEncrypt

See `Docs/Deployment/Reverse_Proxy_Examples.md` for end-to-end examples and Docker Compose snippets.

## Metrics Cheatsheet

The server exports extensive metrics across HTTP, DB, LLM, RAG, embeddings, uploads, system, security, chat, chunking, MCP, and Prompt Studio. Scrape `GET /api/v1/metrics` for Prometheus text or `GET /api/v1/metrics/json` for structured stats. Also available:
- `GET /api/v1/metrics/health`: Health snapshot with `status`, `active_requests`, `active_streams`, `active_transactions`.
- `GET /api/v1/metrics/chat`: Chat‑specific metrics and `token_costs` map.

### HTTP
- `http_requests_total{method,endpoint,status}`: Counter of HTTP requests.
- `http_request_duration_seconds{method,endpoint}`: Histogram of request latency.

Example PromQL:
- P95 latency by route: `histogram_quantile(0.95, sum by (le,endpoint) (rate(http_request_duration_seconds_bucket[5m])))`
- Error rate: `sum by (endpoint) (increase(http_requests_total{status=~"5.."}[5m]))`

### Database
- `db_connections_active{database}`: Gauge of active DB connections.
- `db_queries_total{database,operation}`: Counter of DB queries.
- `db_query_duration_seconds{database,operation}`: Histogram of DB latency.

### LLM
- `llm_requests_total{provider,model,status}`: Counter of LLM calls.
- `llm_tokens_used_total{provider,model,type}`: Counter of tokens by type `prompt|completion`.
- `llm_request_duration_seconds{provider,model}`: Histogram of call latency.
- `llm_cost_dollars{provider,model}`: Counter of cumulative cost (USD).

Example PromQL:
- P95 latency per model: `histogram_quantile(0.95, sum by (le,provider,model) (rate(llm_request_duration_seconds_bucket[5m])))`
- Cost per minute by provider: `sum by (provider) (rate(llm_cost_dollars[5m]))`

### RAG
- `rag_queries_total{pipeline,status}`: Counter of RAG queries.
- `rag_retrieval_latency_seconds{source,pipeline}`: Histogram of retrieval latency.
- `rag_documents_retrieved{source,pipeline}`: Histogram of docs retrieved.
- `rag_cache_hits_total{cache_type}` / `rag_cache_misses_total{cache_type}`: Counters of cache results.

Example PromQL:
- P95 retrieval latency by source: `histogram_quantile(0.95, sum by (le,source) (rate(rag_retrieval_latency_seconds_bucket[5m])))`
- Cache hit rate: `sum(rate(rag_cache_hits_total[5m])) / (sum(rate(rag_cache_hits_total[5m])) + sum(rate(rag_cache_misses_total[5m])))`

### Embeddings (core)
- `embeddings_generated_total{provider,model}`: Counter of embeddings created.
- `embedding_generation_duration_seconds{provider,model}`: Histogram of generation time.

### Embeddings v5 endpoint
- `embedding_requests_total{provider,model,status}`: Counter of embedding requests.
- `embedding_request_duration_seconds{provider,model}`: Histogram of request latency.
- `embedding_cache_hits_total{provider,model}`: Counter of cache hits.
- `embedding_cache_size`: Gauge of current embedding cache size.
- `active_embedding_requests`: Gauge of in‑flight embedding requests.

### Uploads & Storage
- `uploads_total{user_id,media_type}`: Counter of uploaded files.
- `upload_bytes_total{user_id,media_type}`: Counter of uploaded bytes.
- `user_storage_used_mb{user_id}`: Gauge of current storage used (MB).
- `user_storage_quota_mb{user_id}`: Gauge of configured storage quota (MB).

Example PromQL:
- Upload throughput (bytes/s): `rate(upload_bytes_total[1m])`
- Top users by bytes (1h): `sum by (user_id) (increase(upload_bytes_total[1h]))`
- Users near quota: `user_storage_used_mb / user_storage_quota_mb > 0.9`

### System
- `system_cpu_usage_percent`: Gauge of CPU usage percent.
- `system_memory_usage_bytes`: Gauge of memory usage.
- `system_disk_usage_bytes{mount_point}`: Gauge of disk usage by mount.

### Errors & Security
- `errors_total{component,error_type}`: Counter of errors by component.
- `security_ssrf_block_total`: Counter of outbound URL validations blocked.
- `security_headers_responses_total`: Counter of responses with security headers applied.

### Circuit Breakers
- `circuit_breaker_state{service}`: Gauge of state (0=closed, 1=open, 2=half‑open).
- `circuit_breaker_trips_total{service,reason}`: Counter of trips.

### Chat (OpenAI‑compatible Chat API)
- Requests: `chat_requests_total{provider,model,status}`; latency: `chat_request_duration_seconds{provider,model}`.
- Streaming: `chat_streaming_duration_seconds{conversation_id}`, `chat_streaming_chunks_total{conversation_id}`, `chat_streaming_heartbeats_total{conversation_id}`, `chat_streaming_timeouts_total{conversation_id}`.
- Tokens: `chat_tokens_prompt{provider,model}`, `chat_tokens_completion{provider,model}`, `chat_tokens_total{provider,model}`.
- LLM calls: `chat_llm_requests_total{provider,model,status}`, `chat_llm_latency_seconds{provider,model}`, `chat_llm_errors_total{provider,model,error_type}`, `chat_llm_cost_estimate_usd{provider,model}`.
- Conversations: `chat_conversations_created_total{conversation_id}`, `chat_conversations_resumed_total{conversation_id}`, `chat_messages_saved_total{conversation_id,message_type}`.
- Validation & DB: `chat_validation_failures_total`, `chat_validation_duration_seconds`, `chat_db_transactions_total{status}`, `chat_db_retries_total{retry_count}`, `chat_db_rollbacks_total`, `chat_db_operation_duration_seconds{operation}`.
- Auth/limits: `chat_rate_limits_total{client_id}`, `chat_auth_failures_total`.

Example PromQL:
- Chat error rate: `sum(increase(chat_errors_total[5m]))`
- Streaming timeouts (rate): `rate(chat_streaming_timeouts_total[5m])`

Note: Chat metrics are produced via OpenTelemetry meters; Prometheus export depends on your OTel → Prom exporter configuration.

### Chunking Module
- Requests: `chunking_requests_total{method,status}`.
- Latency: `chunking_duration_seconds{method}`.
- Sizes: `chunk_size_characters{method}`, `chunking_input_size_bytes{method}`.
- Output: `chunks_per_request{method}`.
- Cache: `chunking_cache_hits_total{method}`, `chunking_cache_misses_total{method}`, `chunking_cache_size`.
- Errors: `chunking_errors_total{method,error_type}`.
- Additional server metrics: `chunk_time_seconds{method,unit,splitter,language,stream}`, `chunk_output_bytes{...}`, `chunk_input_bytes{...}`, `chunk_count{...}`, `chunk_avg_chunk_size_bytes{...}`, plus gauges `chunk_last_count{...}`, `chunk_last_output_bytes{...}`.

### MCP Unified
- Requests: `mcp_requests_total{method,status}`, latency: `mcp_request_duration_seconds{method}`.
- Modules: `mcp_module_health{module}`, `mcp_module_operations_total{module,operation,status}`.
- Connections: `mcp_active_connections{type}`, `mcp_connection_errors_total{type,error}`.
- Rate limits: `mcp_rate_limit_hits_total{key_type}`.
- Cache: `mcp_cache_hits_total{cache_name}`, `mcp_cache_misses_total{cache_name}`.
- System: `mcp_memory_usage_bytes`, `mcp_cpu_usage_percent`.

### Prompt Studio
- Executions: `prompt_studio.executions.total{provider,model,status}`, `prompt_studio.executions.duration_seconds{provider,model}`.
- Tokens/Cost: `prompt_studio.tokens.used{provider,model,type}`, `prompt_studio.cost.total{provider,model}`.
- Tests/Evals: `prompt_studio.tests.total{project,status}`, `prompt_studio.evaluations.score{project,metric_type}`, `prompt_studio.evaluations.duration_seconds{project}`.
- Optimizations: `prompt_studio.optimizations.total{strategy,status}`, `prompt_studio.optimizations.improvement{strategy}`, `prompt_studio.optimizations.iterations{strategy}`.
- Jobs: `prompt_studio.jobs.queued{job_type}`, `prompt_studio.jobs.processing{job_type}`, `prompt_studio.jobs.completed{job_type,status}`, `prompt_studio.jobs.duration_seconds{job_type}`.
- WebSocket: `prompt_studio.websocket.connections`, `prompt_studio.websocket.messages{event_type}`.
- DB: `prompt_studio.database.operations{operation,table}`, `prompt_studio.database.latency_ms{operation}`.

Grafana: Import `Samples/Grafana/security-dashboard.json` for a base dashboard (HTTP/security). Add panels for the metrics above to monitor app, RAG, embeddings, and chat health.

### Platform-Specific Notes

**Windows**: If you need CUDA support for transcription without full CUDA installation:
- Download [Faster-Whisper-XXL](https://github.com/Purfview/whisper-standalone-win/releases/download/Faster-Whisper-XXL/Faster-Whisper-XXL_r192.3.4_windows.7z)
- Extract `cudnn_ops_infer64_8.dll` and `cudnn_cnn_infer64_8.dll` to the tldw_server directory

**Linux/macOS**: Install system dependencies:
```bash
# Debian/Ubuntu
sudo apt install ffmpeg portaudio19-dev gcc build-essential python3-dev

# Fedora
sudo dnf install ffmpeg portaudio-devel gcc gcc-c++ python3-devel

# macOS
brew install ffmpeg portaudio
```

</details>

---

## Authentication Setup

<summary>Authentication Setup</summary>

<details>

The tldw_server uses the AuthNZ module for authentication, supporting both single-user (personal) and multi-user (team) deployments.

### Quick Setup (Single-User Mode)

For personal use, the simplest setup:

```bash
# 1. Copy the authentication template
cp .env.authnz.template .env

# 2. Generate a secure API key
python -c "import secrets; print('SINGLE_USER_API_KEY=' + secrets.token_urlsafe(32))"

# 3. Add the generated key to your .env file
# Edit .env and replace SINGLE_USER_API_KEY value

# 4. Set AUTH_MODE to single_user in .env
AUTH_MODE=single_user

# 5. Initialize the authentication system
python -m tldw_Server_API.app.core.AuthNZ.initialize

# 6. Start the server - your API key will be displayed in the console
python -m uvicorn tldw_Server_API.app.main:app --reload
```

When the server starts, you'll see:
```
INFO: 🔑 Single-user mode active
INFO: 📌 API Key: your-generated-api-key-here
INFO: Use header 'X-API-KEY: your-key' for authentication
```

Use this API key in all requests:
```bash
curl -H "X-API-KEY: your-api-key" http://localhost:8000/api/v1/media/search
```

### Multi-User Setup (Team/Production)

For team deployments with user management:

```bash
# 1. Copy and configure authentication
cp .env.authnz.template .env

# 2. Generate secure keys
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))"
python -c "from cryptography.fernet import Fernet; print('SESSION_ENCRYPTION_KEY=' + Fernet.generate_key().decode())"

# 3. Edit .env file:
#    - Set AUTH_MODE=multi_user
#    - Add generated JWT_SECRET_KEY
#    - Add generated SESSION_ENCRYPTION_KEY
#    - Configure database settings

# 4. Initialize and create admin user
python -m tldw_Server_API.app.core.AuthNZ.initialize
# You'll be prompted to create an admin user

# 5. Start the server
python -m uvicorn tldw_Server_API.app.main:app --reload
```

Login to get JWT token:
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your-password"}'
```

Use the token in requests:
```bash
curl -H "Authorization: Bearer your-jwt-token" \
  http://localhost:8000/api/v1/media/search
```

### Configuration Options

Key settings in `.env`:

| Setting | Description | Default |
|---------|-------------|---------|
| `AUTH_MODE` | `single_user` or `multi_user` | `multi_user` |
| `JWT_SECRET_KEY` | Secret for JWT signing (multi-user) | Required for multi-user |
| `SINGLE_USER_API_KEY` | API key for single-user mode | Required for single-user |
| `ENABLE_REGISTRATION` | Allow new user registration | `false` |
| `DATABASE_URL` | User database location | `sqlite:///./Databases/users.db` |

### Single-User API Key (How to obtain)

- Recommended: set `SINGLE_USER_API_KEY` explicitly in your `.env` (or environment). You know the key because you set it.
- Development logs: in dev mode (default), the server prints the full key at startup.
- Production logs: set `tldw_production=true` to mask the key in logs. To briefly show it once on startup (e.g., for initial bootstrap), also set `SHOW_API_KEY_ON_STARTUP=true`, then remove it.
- Programmatic retrieval:
  - Python (same env as server):
    ```bash
    python -c "from tldw_Server_API.app.core.AuthNZ.settings import get_settings; print(get_settings().SINGLE_USER_API_KEY)"
    ```
  - Docker Compose:
    ```bash
    docker compose exec app printenv SINGLE_USER_API_KEY
    ```
- WebUI convenience (dev): `GET /webui/config.json` returns the key in single-user mode so the WebUI can auto-configure. Avoid relying on this in production.
  - In production (`tldw_production=true`), `/webui/config.json` omits the `apiKey` field for security.
- Important: Always set a secure `SINGLE_USER_API_KEY` in production. If unset, the server may use a deterministic test key for convenience during development/testing.
  - When `tldw_production=true`, the server refuses to start if `SINGLE_USER_API_KEY` is missing, a default/test value, or shorter than 24 characters.

### Multi-User JWT Secret (production)

- When `tldw_production=true` and `AUTH_MODE=multi_user`, the server refuses to start unless `JWT_SECRET_KEY` is set via environment, at least 32 characters, and not the default template value.

### Database (production, multi-user mode)

- When `tldw_production=true` and `AUTH_MODE=multi_user`, SQLite is not supported and startup will fail if `DATABASE_URL` points to SQLite.
- Configure PostgreSQL via `DATABASE_URL` (examples):
  - Local:
    ```bash
    export DATABASE_URL=postgresql://tldw_user:ChangeMeStrong123!@localhost:5432/tldw_users
    ```
  - With docker-compose (service name `postgres`):
    ```bash
    export DATABASE_URL=postgresql://tldw_user:ChangeMeStrong123!@postgres:5432/tldw_users
    ```
  - See Multi-User Deployment Guide for more details.

### Security Best Practices

1. **Never commit `.env` to version control** - Add to `.gitignore`
2. **Use strong, unique keys** - Generate with the provided commands
3. **Enable HTTPS in production** - Required for secure cookies
4. **Rotate keys periodically** - Use the API key rotation feature
5. **Monitor authentication failures** - Check logs for attacks
6. See the Production Hardening Checklist: `Docs/User_Guides/Production_Hardening_Checklist.md`

### Security Controls (env)

- `tldw_production`: Set to `true` in production to enable stricter guards (secrets validation, DB checks, masked logs, WebUI config hardening).
- `ENABLE_OPENAPI`: Set `false` to hide docs/Redoc/OpenAPI; defaults to `false` in production when unspecified.
- `ALLOWED_ORIGINS`: Comma-separated list or JSON array to restrict CORS in production.
- `ENABLE_SECURITY_HEADERS`: Enable/disable security headers middleware (defaults to `true` in production).

### Troubleshooting

**"JWT_SECRET_KEY not set"**
- Ensure JWT_SECRET_KEY is set in your .env file for multi-user mode

**"API key not found"**
- Check that X-API-KEY header is included in requests
- Verify the API key matches what's in .env (single-user) or displayed at startup

**"Rate limit exceeded"**
- Default: 60 requests/minute for authenticated users
- Adjust RATE_LIMIT_PER_MINUTE in .env if needed

### Documentation

- **[AuthNZ Developer Guide](Docs/Development/AuthNZ-Developer-Guide.md)** - Architecture and extending the authentication system
- **[AuthNZ API Guide](Docs/API-related/AuthNZ-API-Guide.md)** - Complete API reference with examples

</details>

### Quick Setup (Multi‑User with SQLite – Dev)

For local/dev multi-user without Postgres:

```bash
# 1) Enable multi-user mode with SQLite AuthNZ DB
export AUTH_MODE=multi_user
export DATABASE_URL=sqlite:///./Databases/users.db

# 2) Initialize the AuthNZ database
python -m tldw_Server_API.app.core.AuthNZ.initialize

# 3) Start the server
uvicorn tldw_Server_API.app.main:app --reload

# 4) Open the simple auth page to register/login and get a JWT
open http://127.0.0.1:8000/webui/auth.html   # macOS
# xdg-open on Linux, or just paste the URL in a browser
```

Notes
- This is suitable for development and light testing. For production multi-user, use PostgreSQL for `DATABASE_URL`.
- The auth page posts to `/api/v1/auth/register` and `/api/v1/auth/login` and shows the access token.

### Using config.txt for AuthNZ

You can configure authentication and the AuthNZ database in `Config_Files/config.txt` (env still overrides):

```
[AuthNZ]
auth_mode = multi_user
# Option A: full URL
database_url = postgresql://tldw_user:ChangeMeStrong123!@localhost:5432/tldw_users
# Option B: structured fields (used if DATABASE_URL not set)
db_type = postgresql
pg_host = localhost
pg_port = 5432
pg_db = tldw_users
pg_user = tldw_user
pg_password = ChangeMeStrong123!
pg_sslmode = prefer
enable_registration = true
require_registration_code = false
```

Environment precedence and a complete list of environment variables is in `Env_Vars.md`.

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
\n+#### Paper Search (Provider-specific)
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
  "final_answer": "The capital of France is Paris.",
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
    "enable_claims": true
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

This project is Licensed under an Apache 2.0 License.

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
