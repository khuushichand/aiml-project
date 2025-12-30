<div align="center">

<h1>tldw Server</h1>
<p>Too Long; Didn't Watch - API-first media analysis & research platform</p>

<a href="https://www.gnu.org/licenses/old-licenses/gpl-3.0.en.html">[![madewithlove](https://img.shields.io/badge/made_with-%E2%9D%A4-red?style=for-the-badge&labelColor=orange)](https://github.com/rmusser01/tldw_server)
<img alt="License: GPLv3" src="https://img.shields.io/badge/license-GPLv3-blue.svg" />
  </a>

<p>
  <a href="https://github.com/rmusser01/tldw_server/actions/workflows/e2e-smoke.yml">
    <img alt="E2E Critical Smoke" src="https://github.com/rmusser01/tldw_server/actions/workflows/e2e-smoke.yml/badge.svg" />
  </a>
</p>

<h3>Process Media and more with 16+ LLM providers + OpenAI-compatible APIs for Chat, Embeddings and Evals</h3>

<h3>Hosted SaaS + Browser Extension coming soon.</h3>

## Your Own Local Open-Source Platform for Media Analysis, Knowledge Work and LLM-Backed (Creative) Efforts
</div>

---

## Table of Contents

<details>
<summary>Table of Contents</summary>

- [Overview](#overview)
- [Current Status](#current-status)
- [What's New](#whats-new)
- [Privacy & Security](#privacy--security)
- [Highlights](#highlights)
- [Feature Status](#feature-status)
- [Quickstart](#quickstart)
  - [Run the API](#run-the-api)
  - [Run the Web UI (WIP)](#run-the-web-ui-wip)
  - [Docker Compose](#docker-compose)
  - [Supporting Services via Docker](#supporting-services-via-docker)
- [Usage Examples](#usage-examples)
- [Key Endpoints](#key-endpoints)
- [Architecture & Repo Layout](#architecture--repo-layout)
- [Architecture Diagram](#architecture-diagram)
- [Networking & Limits](#networking--limits)
- [Running Tests](#running-tests)
- [CI Status & Smoke Tests](#ci-status--smoke-tests)
- [Documentation & Resources](#documentation--resources)
  - [Resource Governor Config](#resource-governor-config)
  - [OpenAI-Compatible Strict Mode (Local Providers)](#openai-compatible-strict-mode-local-providers)
  - [Chatbook Tools Guide](#chatbook-tools-guide)
- [Deployment](#deployment)
- [Monitoring](#monitoring)
  - [PostgreSQL Content Mode](#postgresql-content-mode)
- [Troubleshooting](#troubleshooting)
- [Contributing & Support](#contributing--support)
- [Developer Guides](#developer-guides)
  - [Ingestion & Media Processing Docs](#ingestion--media-processing-docs)
- [More Detailed Explanation & Background](#more-detailed-explanation--background)
- [Local Models I recommend](#local-models-i-recommend)
- [License](#license)
- [Credits](#credits)
- [About](#about)
  - [Getting Help](#getting-help)
  - [Security Disclosures](#security-disclosures)
  - [Project Guidelines](#project-guidelines)
</details>

## Overview
**tldw_server** is an open-source research assistant and media analysis backend for ingesting, transcribing, analyzing, and retrieving knowledge from video, audio, documents, websites, and more.
It runs a FastAPI server with OpenAI-compatible Chat, Audio, Embeddings, and Evals APIs, plus a unified RAG pipeline, knowledge tools, and integrations with local or hosted LLM providers.
The long-term vision is a personal research assistant inspired by "The Young Lady's Illustrated Primer" that helps people learn, reason about, and retain what they watch or read.

Great for:
- Turning videos, podcasts, and documents into searchable, citable knowledge.
- Running local or hosted LLMs behind a consistent OpenAI-compatible API.
- Building research workflows with RAG, evaluation, and prompt tooling.

New here? Start with the Quickstart section below.
If you're looking for a one line non-jargon explanation: Modular monolithic FastAPI application, exposes different functionality via REST endpoints for access to each core module, each module following loose coupling, aiming towards atomicity of each where/when possible.


## Current Status

Version 0.1.13 (beta). Expect bugs and rough edges; please report issues.

<details>
<summary>Current focus and migration notes</summary>

### Active Work-in-Progress (not in order)
- Workflows
- Browser extension ([tldw_Browser_Assistant](https://github.com/rmusser01/tldw_browser_assistant))
- Unified Admin Dashboard ([admin-ui](./admin-ui))
- Front-End webapp ([tldw-frontend](./tldw-frontend))
- Watchlists
- Collections (read-it-later)
- Documentation

### Migrating From Gradio Version (pre-0.1.0)
- Backup:
    - `cp -a ./Databases ./Databases.backup`
- Update configuration:
    - Copy provider keys to `.env`.
    - For AuthNZ setup: `cp .env.authnz.template .env && python -m tldw_Server_API.app.core.AuthNZ.initialize`
- Database migration:
    - Inspect: `python -m tldw_Server_API.app.core.DB_Management.migrate_db status`
    - Migrate: `python -m tldw_Server_API.app.core.DB_Management.migrate_db migrate`
    - Optional: `--db-path /path/to/Media_DB_v2.db` if not using defaults
    - If migrating content to Postgres later, use the tools under `tldw_Server_API/app/core/DB_Management/` (e.g., migration_tools.py)
- API changes:
    - Use FastAPI routes; see http://127.0.0.1:8000/docs. OpenAI-compatible endpoints are available (e.g., `/api/v1/chat/completions`).
- Frontend:
    - Legacy: /webui
    - Or integrate directly against the API;
</details>

## What's New (compared to Gradio)

- FastAPI-first backend with OpenAI-compatible Chat and Audio APIs (including streaming STT and TTS)
- Unified RAG and Evaluations modules (hybrid BM25 + vector with re-ranking; unified metrics)
- MCP Unified module with JWT/RBAC, tool execution APIs, and WebSockets
- New WebUI (current Next.js UI is WIP and may be unstable or rough)
- Strict OpenAI compatibility mode for local/self-hosted providers
- PostgreSQL content mode + backup/restore helpers; Prometheus metrics and monitoring improvements

See: `Docs/Published/RELEASE_NOTES.md` for detailed release notes.

## Privacy & Security

- Self-hosted by design; no telemetry or data collection.
- Users own and control their data; see hardening guidance for production.
- Auth modes: single-user API key or multi-user JWT.
- Security reporting and hardening docs: `SECURITY.md`, `Docs/Published/User_Guides/Production_Hardening_Checklist.md`.
- Outbound URL egress policy blocks SSRF to private networks and disallowed ports for media downloads (audio/video/doc URLs), with test-mode DNS relaxations for hostnames.

## Highlights

- Media ingestion & processing: video, audio, PDFs, EPUB, DOCX, HTML, Markdown, XML, MediaWiki dumps; metadata extraction; configurable chunking.
- Custom-built Chunking library, tldw_Chunker, supporting token, word, sentence, paragraph, semantic, hierarchical and template chunking approaches.
- Audio & speech: real-time and file STT via faster_whisper, NVIDIA NeMo (Canary/Parakeet), Qwen2Audio; TTS: OpenAI-compatible TTS supporting ElevenLabs, OpenAI and locally: kokoro, Higgs, Dia, VibeVoice.
- Search & retrieval (RAG): hybrid BM25 + vector (ChromaDB/pgvector), re-ranking, contextual retrieval, OpenAI-compatible embeddings. 50+ optional parameters available for tuning.
- Chat & providers: `/api/v1/chat/completions` (OpenAI-compatible), 16+ providers (commercial + self-hosted), character chat, budgets/allowlists.
- Knowledge management: notes, prompt library, character cards, soft-delete with recovery, Chatbooks import/export. (Support for import/edit/export of .apkg files - anki)
- Prompt Studio & evaluations: projects, prompt testing/optimization, unified evaluation APIs (G-Eval, RAG, batch metrics). Full evaluations and prompt management.
- MCP Server: production MCP with JWT/RBAC, tool execution, WebSockets, metrics, and health endpoints. Use existing tools or add your own using a handy guide. Setup tool categories and collections, allowing for easier context management.


## Feature Status

See the full [Feature Status Matrix at `Docs/Published/Overview/Feature_Status.md`](./Docs/Published/Overview/Feature_Status.md).

## Quickstart

### Run the API

Prerequisites
- Python 3.11+ (3.12/3.13 supported)
- ffmpeg (for audio/video pipelines)

1) Create environment and install dependencies (via pyproject.toml)
```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
# Core server
pip install -e .

# Optional extras (choose as needed)
# pip install -e ".[multiplayer]"   # multi-user/PostgreSQL features
# pip install -e ".[dev]"           # tests, linters, tooling
# pip install -e ".[otel]"          # OpenTelemetry metrics/tracing exporters

# Install pyaudio - needed for audio processing
# Linux
sudo apt install python3-pyaudio

# macOS
brew install portaudio
pip install pyaudio
```
2) Configure authentication and providers
```bash
# Create .env with at least:
cat > .env << 'EOF'
AUTH_MODE=single_user
SINGLE_USER_API_KEY=CHANGE_ME_TO_SECURE_API_KEY
DATABASE_URL=sqlite:///./Databases/users.db
EOF

# First-time initialization (validates config, sets up DBs)
python -m tldw_Server_API.app.core.AuthNZ.initialize
# Add provider API keys in .env or tldw_Server_API/Config_Files/config.txt
```
3) Run the API
```bash
python -m uvicorn tldw_Server_API.app.main:app --reload
```
- API docs: http://127.0.0.1:8000/docs
- Legacy WebUI: http://127.0.0.1:8000/webui/ (deprecated)

### Run the Web UI (WIP)

The current Next.js UI is a work in progress and may be unstable, buggy, or rough around the edges.
Make sure the API from the section above is running.
Requires Node.js and npm (or yarn/pnpm).

1) From the repo root:
```bash
cd tldw-frontend
cp .env.local.example .env.local
```
2) Set your API URL (defaults shown):
```bash
# .env.local
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
NEXT_PUBLIC_API_VERSION=v1
# Optional for single-user mode:
# NEXT_PUBLIC_X_API_KEY=your_api_key
```
3) Install and run the dev server (use port 8080 to match default CORS):
```bash
npm install
npm run dev -- -p 8080
```
Open http://localhost:8080

Tip: `./start-webui.sh` launches the API and opens the legacy `/webui/` client.

### Docker Compose

Optional path for running the API + services with Docker.
```bash
# Run from repo root

# Option A) Single-user (SQLite users DB)
docker compose -f Dockerfiles/docker-compose.yml up -d --build

# Option B) Multi-user (Postgres users DB)
export AUTH_MODE=multi_user
export DATABASE_URL=postgresql://tldw_user:TestPassword123!@postgres:5432/tldw_users
# Optional: route Jobs module to Postgres as well
export JOBS_DB_URL=postgresql://tldw_user:TestPassword123!@postgres:5432/tldw_users
docker compose -f Dockerfiles/docker-compose.postgres.yml up -d

# Option C) Dev overlay — enable unified streaming (non-prod)
# This turns on the SSE/WS unified streams (STREAMS_UNIFIED=1) for pilot endpoints.
# Keep disabled in production until validated in your environment.
docker compose -f Dockerfiles/docker-compose.yml -f Dockerfiles/docker-compose.dev.yml up -d --build

# Check status
docker compose -f Dockerfiles/docker-compose.yml ps
docker compose -f Dockerfiles/docker-compose.yml logs -f app

# First-time AuthNZ initialization (inside the running app container)
docker compose -f Dockerfiles/docker-compose.yml exec app \
  python -m tldw_Server_API.app.core.AuthNZ.initialize

# Optional: proxy overlays
#   - Dockerfiles/docker-compose.proxy.yml
#   - Dockerfiles/docker-compose.proxy-nginx.yml

# Optional: use pgvector + pgbouncer for Postgres
docker compose -f Dockerfiles/docker-compose.yml -f Dockerfiles/docker-compose.pg.yml up -d --build
```

Notes
- Run compose commands from the repository root. The base compose file at `Dockerfiles/docker-compose.yml` builds with context at the repo root and includes Postgres and Redis services.
- The legacy WebUI is served at `/webui`; the primary UI is the Next.js client in `tldw-frontend/`.
  - For unified streaming validation in non-prod, prefer the dev overlay above. You can also export `STREAMS_UNIFIED=1` directly in your environment.

### Supporting Services via Docker

<details>
<summary>Supporting services (Postgres, Redis, Prometheus, Grafana)</summary>

Run only infrastructure services without the app.

Postgres + Redis (base compose)
```bash
docker compose -f Dockerfiles/docker-compose.yml up -d postgres redis
```

Prometheus + Grafana (embeddings compose, monitoring profile)
```bash
docker compose -f Dockerfiles/docker-compose.embeddings.yml --profile monitoring up -d prometheus grafana
```

All four together
```bash
docker compose -f Dockerfiles/docker-compose.yml up -d postgres redis
docker compose -f Dockerfiles/docker-compose.embeddings.yml --profile monitoring up -d prometheus grafana
```

Manage and verify
```bash
# Status
docker compose -f Dockerfiles/docker-compose.yml ps
docker compose -f Dockerfiles/docker-compose.embeddings.yml ps

# Logs
docker compose -f Dockerfiles/docker-compose.yml logs -f postgres redis
docker compose -f Dockerfiles/docker-compose.embeddings.yml logs -f prometheus grafana

# Stop
docker compose -f Dockerfiles/docker-compose.yml stop postgres redis
docker compose -f Dockerfiles/docker-compose.embeddings.yml stop prometheus grafana

# Remove
docker compose -f Dockerfiles/docker-compose.yml down
docker compose -f Dockerfiles/docker-compose.embeddings.yml down
```

Ports
- Postgres: 5432
- Redis: 6379
- Prometheus: 9091 (container listens on 9090)
- Grafana: 3000

Prometheus config
- Create `Config_Files/prometheus.yml` to define scrape targets. Minimal self-scrape example:
```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
```
See Docs/Operations/monitoring/README.md for examples that scrape the API and worker orchestrator.

Tip: See multi-user setup and production hardening in Docs/User_Guides/Authentication_Setup.md and Docs/Published/Deployment/First_Time_Production_Setup.md.

</details>

## Usage Examples

<details>
<summary>Usage Examples</summary>

Use the single-user API key with the `X-API-KEY` header.

Chat (OpenAI-compatible)
```bash
curl -s http://127.0.0.1:8000/api/v1/chat/completions \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": false
  }'
```

Embeddings (OpenAI-compatible)
```bash
curl -s http://127.0.0.1:8000/api/v1/embeddings \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "text-embedding-3-small",
    "input": "hello world"
  }'
```

Media Ingest (URL)
```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/media/add \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -F "media_type=document" \
  -F "title=Example Article" \
  -F "keywords=demo,quickstart" \
  -F "urls=https://www.example.com/some-article"
```

Media Search
```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/media/search \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "keyword"
  }'
```

Audio Transcription (file)
```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/audio/transcriptions \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -F "file=@sample.wav" -F "model=whisper-1"
```
</details>

## Key Endpoints
<details>
<summary>Key Endpoints</summary>

- Media: `POST /api/v1/media/add` - ingest/process media (URLs/files) with DB persistence ([docs](Docs/Code_Documentation/Ingestion_Media_Processing.md))
- Media Search: `POST /api/v1/media/search` - search ingested content ([docs](Docs/API-related/API_Design.md))
- Chat: `POST /api/v1/chat/completions` - OpenAI-compatible chat ([docs](Docs/API-related/Chat_API_Documentation.md))
- Chat Commands: `GET /api/v1/chat/commands` - list available slash commands ([docs](Docs/API-related/Chatbook_Features_API_Documentation.md#chat-tools-slash-commands))
- Chat Dictionary Validate: `POST /api/v1/chat/dictionaries/validate` - validate a chat dictionary ([docs](Docs/API-related/Chatbook_Features_API_Documentation.md#chat-dictionary-api))
- Embeddings: `POST /api/v1/embeddings` - OpenAI-compatible embeddings ([docs](Docs/API-related/Embeddings_API_Documentation.md))
- RAG: `POST /api/v1/rag/search` - unified RAG search ([docs](Docs/API-related/RAG-API-Guide.md))
- Audio STT: `POST /api/v1/audio/transcriptions` - file-based transcription ([docs](Docs/API-related/Audio_Transcription_API.md))
- Audio STT (WS): `WS /api/v1/audio/stream/transcribe` - real-time transcription ([docs](Docs/API-related/Audio_Transcription_API.md))
- Audio TTS: `POST /api/v1/audio/speech` - text-to-speech (streaming and non-streaming) ([docs](Docs/API-related/TTS_API.md))
- TTS Voices: `GET /api/v1/audio/voices/catalog` - voice catalog across providers ([docs](Docs/API-related/TTS_API.md))
- Vector Stores: `POST /api/v1/vector_stores` - create; `POST /api/v1/vector_stores/{id}/query` - query ([docs](Docs/API-related/Vector_Stores_Admin_and_Query.md))
- OCR Backends: `GET /api/v1/ocr/backends` - available OCR providers ([docs](Docs/API-related/OCR_API_Documentation.md))
- VLM Backends: `GET /api/v1/vlm/backends` - available VLM providers ([docs](Docs/Code_Documentation/VLM_Backends.md))
- Connectors: `GET /api/v1/connectors/providers` - Drive/Notion providers ([docs](Docs/Product/External_Connectors_PRD.md))
- Outputs: `POST /api/v1/outputs` - generate output artifact (md/html/mp3) ([docs](Docs/Product/Content_Collections_PRD.md))
- Metrics: `GET /api/v1/metrics/text` - Prometheus metrics (text format) ([docs](Docs/Deployment/Monitoring/Metrics_Cheatsheet.md))
- Providers: `GET /api/v1/llm/providers` - provider/models list ([docs](Docs/API-related/Providers_API_Documentation.md))
- MCP: `GET /api/v1/mcp/status` - MCP server status ([docs](Docs/MCP/Unified/System_Admin_Guide.md))

Admin maintenance
- Chat model aliases cache reload: `POST /api/v1/admin/chat/model-aliases/reload`
  - Single-user (API key)
    ```bash
    curl -s -X POST http://127.0.0.1:8000/api/v1/admin/chat/model-aliases/reload \
      -H "X-API-KEY: $SINGLE_USER_API_KEY"
    ```
  - Multi-user (JWT)
    ```bash
    curl -s -X POST http://127.0.0.1:8000/api/v1/admin/chat/model-aliases/reload \
      -H "Authorization: Bearer $JWT"
    ```

Examples
- GET `/api/v1/chat/commands` response
  ```json
  {
    "commands": [
      {"name": "time", "description": "Show the current time (optional TZ).", "required_permission": "chat.commands.time"},
      {"name": "weather", "description": "Show current weather for a location.", "required_permission": "chat.commands.weather"}
    ]
  }
  ```
- POST `/api/v1/chat/dictionaries/validate` request
  ```json
  {
    "data": {
      "name": "Example",
      "entries": [
        {"type": "literal", "pattern": "today", "replacement": "It is {{ now('%B %d') }}."},
        {"type": "regex", "pattern": "User:(\\w+)", "replacement": "Hello, {{ match.group(1) }}!"}
      ]
    },
    "schema_version": 1,
    "strict": false
  }
  ```
  Minimal success response
  ```json
  {
    "ok": true,
    "schema_version": 1,
    "errors": [],
    "warnings": [],
    "entry_stats": {"total": 2, "regex": 1, "literal": 1},
    "suggested_fixes": []
  }
  ```

</details>

## Architecture & Repo Layout

<details>
<summary>Architecture & Repo Layout</summary>

```text
<repo_root>/
├── tldw_Server_API/              # Main API server implementation
│   ├── app/
│   │   ├── api/v1/
│   │   │   ├── endpoints/        # REST endpoints (media, chat, audio, rag, evals, etc.)
│   │   │   ├── schemas/          # Pydantic models
│   │   │   └── API_Deps/         # Shared dependencies (auth, DB, rate limits)
│   │   ├── core/                 # Core logic (AuthNZ, RAG, LLM, DB, TTS, MCP, etc.)
│   │   ├── services/             # Background services
│   │   └── main.py               # FastAPI entry point
│   ├── WebUI/                    # Legacy integrated WebUI served at /webui (deprecated)
│   ├── Config_Files/             # config.txt, example YAMLs, migration helpers
│   ├── Databases/                # Default DBs (runtime data; some are gitignored)
│   ├── tests/                    # Pytest suite
│   └── requirements.txt          # Legacy pin set (prefer pyproject extras)
├── tldw-frontend/                # Next.js WebUI (current client)
├── Docs/                         # Documentation (API, Development, RAG, AuthNZ, TTS, etc.)
├── Helper_Scripts/               # Utilities (installers, prompt tools, doc generators)
├── mock_openai_server/           # Mock OpenAI-compatible API server for tests/dev
├── Dockerfiles/                  # Docker images and compose files
├── Databases/                    # DBs (AuthNZ defaults here; content DBs per-user under user_databases/)
├── models/                       # Optional model assets (if used)
├── pyproject.toml                # Project configuration
├── README.md                     # Project README (this file)
├── start-webui.sh                # Convenience script for WebUI + server
└── Project_Guidelines.md         # Development philosophy
```

Notes
- The FastAPI app serves a legacy UI at `/webui` (deprecated); the Next.js UI in `tldw-frontend/` is the current client.
- SQLite is default for local dev; PostgreSQL supported for AuthNZ and content DBs.
- `mock_openai_server/` is handy for local OpenAI-compatible API testing.

</details>

## Architecture Diagram

```mermaid
flowchart LR
  subgraph CLIENTS [Clients]
    WebUI[Next.js WebUI (current)]:::client
    LegacyUI[Legacy WebUI (/webui, deprecated)]:::client
    MCPClients[MCP Clients (IDE/tools)]:::client
    APIClients[CLI/HTTP Clients]:::client
  end

  subgraph API_STACK [FastAPI App]
    API[FastAPI App /api/v1]:::api
    Endpoints[Endpoints + Schemas]:::module
    Dependencies[API Deps (Auth, DB, rate limits, resource governor)]:::module
    Services[Background Services/Jobs]:::module
  end

  subgraph CORE [Core Modules]
    AuthNZ[AuthNZ]:::core
    RAG[RAG]:::core
    LLM[LLM Calls]:::core
    Embeddings[Embeddings]:::core
    Media[Ingestion & Media Processing]:::core
    Chunking[Chunking]:::core
    Chat[Chat/Characters]:::core
    Audio[Audio STT/TTS]:::core
    Evaluations[Evaluations]:::core
    PromptStudio[Prompt Studio]:::core
    Knowledge[Notes/Prompts/Chatbooks]:::core
    MCP[MCP Unified]:::core
    Research[Research/Web Search]:::core
  end

  subgraph STORAGE [Storage]
    UsersDB[(AuthNZ DB: SQLite/PostgreSQL)]:::db
    ContentDB[(Content DBs: Media/Notes/Chats)]:::db
    EvalsDB[(Evaluations DB: SQLite/PostgreSQL)]:::db
    VectorDB[(Vector DB: ChromaDB/pgvector)]:::db
  end

  subgraph EXTERNAL [External Providers]
    LLMCloud[LLM APIs (OpenAI, Anthropic, etc.)]:::ext
    LLMOnPrem[Local LLMs (vLLM, Ollama, llama.cpp, ...)]:::ext
    AudioProv[STT/TTS Providers]:::ext
    OCRVLM[OCR/VLM (tesseract, dots, points)]:::ext
    MediaDL[yt-dlp / ffmpeg]:::ext
    WebSearch[Web Search/Scrapers]:::ext
  end

  %% Client to API
  WebUI -->|HTTP| API
  LegacyUI -->|HTTP| API
  MCPClients -->|HTTP/WebSocket| API
  APIClients -->|HTTP/WebSocket| API

  %% Inside API stack
  API --> Endpoints
  API --> Dependencies
  API --> Services

  %% Endpoints to core modules
  Endpoints --> AuthNZ
  Endpoints --> RAG
  Endpoints --> LLM
  Endpoints --> Embeddings
  Endpoints --> Media
  Endpoints --> Chunking
  Endpoints --> Chat
  Endpoints --> Audio
  Endpoints --> Evaluations
  Endpoints --> PromptStudio
  Endpoints --> Knowledge
  Endpoints --> MCP
  Endpoints --> Research

  %% Core to storage
  AuthNZ --> UsersDB
  Media --> ContentDB
  Knowledge --> ContentDB
  Chat --> ContentDB
  Evaluations --> EvalsDB
  RAG --> ContentDB
  RAG --> VectorDB
  Embeddings --> VectorDB

  %% Core to external services
  LLM --> LLMCloud
  LLM --> LLMOnPrem
  Audio --> AudioProv
  Media --> MediaDL
  Media --> OCRVLM
  Research --> WebSearch

  classDef client fill:#e8f3ff,stroke:#5b8def,color:#1f3b6e;
  classDef api fill:#fff4e6,stroke:#ff9800,color:#5d3d00;
  classDef module fill:#f4f6f8,stroke:#9aa5b1,color:#2d3748;
  classDef core fill:#eefbea,stroke:#34a853,color:#1e4620;
  classDef db fill:#f0eaff,stroke:#8e6cf1,color:#3a2a87;
  classDef ext fill:#fff0f0,stroke:#e57373,color:#7b1f1f;
```

## Networking & Limits

- HTTP client and TLS/pinning configuration: `tldw_Server_API/Config_Files/README.md` (timeouts, retries, redirects/proxies, JSON limits, TLS min version, cert pinning, SSE/download helpers).
- Egress/SSRF policy and security middleware: `tldw_Server_API/app/core/Security/README.md`.
- Resource Governor (rate limits, tokens, streams; Redis backend optional): `tldw_Server_API/app/core/Resource_Governance/README.md`.

### API Rate Limits (High-Level)

- **Characters & Character Chat**
  - Per-user caps (configurable via env/settings; defaults documented in `Docs/API-related/CHARACTER_CHAT_API_DOCUMENTATION.md`):
    - Max operations/hour (character operations).
    - Max characters per user.
    - Max concurrent chats per user.
    - Max messages per chat.
    - Per-minute limits for chat completions and message sends.
  - Status endpoint:
    - `GET /api/v1/characters/rate-limit-status` → returns a simple snapshot:
      - `operations_used`, `operations_remaining`, `reset_time` (Unix timestamp or `null`).
  - Enforcement is handled by `CharacterRateLimiter` with Redis-backed ZSETs when `REDIS_ENABLED=true`, or per-process in-memory counters otherwise.

- **Core Chat / RAG / Embeddings**
  - Per-user RPM/TPM limits enforced via the Resource Governor (optional Redis backend).
  - See:
    - `tldw_Server_API/app/core/Chat/rate_limiter.py`
    - `tldw_Server_API/app/core/Resource_Governance/README.md`

All limits are designed to be conservative by default and can be tuned using the various `*_RATE_LIMIT_*`, `MAX_*`, and RG policy settings in `Config_Files/` and environment variables.

## Running Tests

<details>
<summary>Running tests locally</summary>

- `python -m pytest -v` - full test suite (skips heavy optional suites by default).
- `python -m pytest --cov=tldw_Server_API --cov-report=term-missing` - coverage report.
- Use markers (`unit`, `integration`, `e2e`, `external_api`, `performance`) to focus specific areas.
- Enable optional suites with environment flags such as `RUN_MCP_TESTS=1`, `TLDW_TEST_POSTGRES_REQUIRED=1`, or `RUN_MOCK_OPENAI=1`.

</details>

## Frontend Integration Testing

Use the helper script to run frontend unit tests plus smoke checks against a live backend:

```bash
cd tldw-frontend
npm run test:integration
```

Notes:
- Starts the backend (uvicorn) by default and runs `pytest -m integration`, then `npm run test:run` + `npm run smoke`.
- Set `TLDW_X_API_KEY=...` for single-user mode (a temporary key is generated if missing).
- Use `--backend-docker` to start the backend via Docker Compose, or `--skip-backend` if you already have it running.
- Use `--no-backend-tests` to skip backend integration tests.

## CI Status & Smoke Tests

<details>
<summary>CI status and smoke tests</summary>

| Workflow | Status |
| --- | --- |
| E2E Critical Smoke (In-Process) | [![E2E Critical Smoke](https://github.com/rmusser01/tldw_server/actions/workflows/e2e-smoke.yml/badge.svg)](https://github.com/rmusser01/tldw_server/actions/workflows/e2e-smoke.yml) |

Run locally

- In-process (no open port):
  - `export E2E_INPROCESS=1 AUTH_MODE=single_user TEST_MODE=1`
  - `export SINGLE_USER_API_KEY=test-api-key-for-e2e-testing-12345`
  - `export SINGLE_USER_TEST_API_KEY=$SINGLE_USER_API_KEY`
  - `python -m pytest tldw_Server_API/tests/e2e/ --critical-only -q`
- Live server (normal):
  - `python -m uvicorn tldw_Server_API.app.main:app --reload`
  - `export E2E_TEST_BASE_URL=http://localhost:8000`
  - `python -m pytest tldw_Server_API/tests/e2e/ --critical-only -q`

</details>

## Documentation & Resources

<details>
<summary>Documentation and resources</summary>

- `Docs/Documentation.md` - documentation index and developer guide links
- `Docs/About.md` - project background and philosophy
- `New-User-Guide.md` - guided walkthrough for first-time setup and usage
- Module deep dives: `Docs/Development/AuthNZ-Developer-Guide.md`, `Docs/Development/RAG-Developer-Guide.md`, `Docs/MCP/Unified/Developer_Guide.md`
- API references: `Docs/API-related/RAG-API-Guide.md`, `Docs/API-related/OCR_API_Documentation.md`, `Docs/API-related/Prompt_Studio_API.md`
- Deployment/Monitoring: `Docs/Published/Deployment/First_Time_Production_Setup.md`, `Docs/Published/Deployment/Reverse_Proxy_Examples.md`, `Docs/Deployment/Monitoring/`
- TTS onboarding: `Docs/User_Guides/TTS_Getting_Started.md` – hosted/local provider setup, verification, and troubleshooting
- Design notes (WIP features): `Docs/Design/` - e.g., `Docs/Design/Custom_Scrapers_Router.md`

### Resource Governor Config

For complete Resource Governor setup and examples (env, DB store bootstrap, YAML policy, middleware, diagnostics, and tests), see `tldw_Server_API/app/core/Resource_Governance/README.md`.

### OpenAI-Compatible Strict Mode (Local Providers)

Some self-hosted OpenAI-compatible servers reject unknown fields (like `top_k`). For local providers you can enable a strict mode that filters non-standard keys from chat payloads.

### Chatbook Tools Guide

- Getting started: `Docs/User_Guides/Chatbook_Tools_Getting_Started.md`
- Product spec (PRD): `Docs/Product/Chatbook-Tools-PRD.md`
- Related endpoints (also listed above under Key Endpoints):
  - `GET /api/v1/chat/commands` — list slash commands (RBAC-filtered when enabled; returns empty list when disabled)
  - `POST /api/v1/chat/dictionaries/validate` — validate chat dictionaries (schema, regex, templates)

- Set `strict_openai_compat: true` in the relevant provider section (`local_llm`, `llama_api`, `ooba_api`, `tabby_api`, `vllm_api`, `aphrodite_api`, `ollama_api`).
- For `local_llm`, you can also use `LOCAL_LLM_STRICT_OPENAI_COMPAT=1`.
- When enabled, only standard OpenAI Chat Completions parameters are sent:
  `messages, model, temperature, top_p, max_tokens, n, stop, presence_penalty, frequency_penalty, logit_bias, seed, response_format, tools, tool_choice, logprobs, top_logprobs, user, stream`.

</details>

## Deployment

<details>
<summary>Deployment resources</summary>
- Dockerfiles and compose templates live under `Dockerfiles/` (see `Dockerfiles/README.md`).
- Reverse proxy samples: `Helper_Scripts/Samples/Nginx/`, `Helper_Scripts/Samples/Caddy/`.
- Monitoring: `Docs/Deployment/Monitoring/` and `Helper_Scripts/Samples/Grafana/`.
- Prometheus metrics exposed at `/metrics` and `/api/v1/metrics`.
- Production hardening: `Docs/Published/User_Guides/Production_Hardening_Checklist.md`.
</details>

## Monitoring

<details>
<summary>Monitoring resources</summary>

- Monitoring docs and setup: `Docs/Deployment/Monitoring/README.md`
- Grafana dashboards and samples: `Helper_Scripts/Samples/Grafana/README.md`
- Prometheus scrape endpoints: `GET /metrics` and `GET /api/v1/mcp/metrics/prometheus` (both require authenticated principals with appropriate permissions; MCP Prometheus uses `system.logs`)

### PostgreSQL Content Mode

- Content DBs (Media, ChaChaNotes, Workflows) can run on Postgres.
- See: `Docs/Published/Deployment/Postgres_Content_Mode.md`, `Docs/Published/Deployment/Postgres_Migration_Guide.md`, and `Docs/Published/Deployment/Postgres_Backups.md`.

</details>

## Troubleshooting

- ffmpeg missing: ensure `ffmpeg -version` works; install via your package manager.
- Torch/CUDA mismatch: install a CUDA-compatible PyTorch or use CPU wheels.
- SQLite locks: prefer short-lived transactions and context managers; consider Postgres for concurrency.
- OpenAI strict mode: enable strict compatibility for local providers that reject unknown fields.
- Docker: inspect with `docker compose ps` and `docker compose logs -f`.

## Contributing & Support

- Read `CONTRIBUTING.md`, `Project_Guidelines.md`, and `AGENTS.md` before submitting changes.
- File bugs or feature requests via GitHub Issues; longer-form discussions live in GitHub Discussions.
- Respect the project philosophy: incremental progress, clear intent, and kindness toward contributors.

---

## Developer Guides

<details>
<summary>Developer Guides + Links</summary>

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

</details>

-------------------


### More Detailed Explanation & Background
<details>
<summary>More Detailed Explanation & Background</summary>

Optional background reading for deeper context; not required to use the project.

- See `Docs/About.md` for the extended project background, vision, and notes.
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


----------------------

### Local Models I recommend

<details>
<summary>Local Models I Can Recommend</summary>

Personal recommendations; optional reading.

- These are just the 'standard smaller' models I recommend, there are many more out there, and you can use any of them with this project.
  - One should also be aware that people create 'fine-tunes' and 'merges' of existing models, to create new models that are more suited to their needs.
  - This can result in models that may be better at some tasks but worse at others, so it's important to test and see what works best for you.
- Mistral Nemo Instruct 2407 - https://huggingface.co/QuantFactory/Mistral-Nemo-Instruct-2407-GGUF
- Magistral Small: https://huggingface.co/mistralai/Magistral-Small-2509-GGUF
- Qwen 3/VL Series
  - Qwen/Qwen3-VL-4B-Instruct (Qwen3 4B+Vision): https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF
  - Qwen3-30B-A3B-Instruct-2507: https://huggingface.co/unsloth/Qwen3-30B-A3B-Instruct-2507-GGUF

For commercial API usage for use with this project: GPT-5.1, Anthropic's models(The Temu of AI services/models), Kimi k2, DeepSeek
Originally written: Flipside I would say none, honestly. The (largest players) will gaslight you and charge you money for it. Fun.  That being said they obviously can provide help/be useful(helped me make this app), but it's important to remember that they're not your friend, and they're not there to help you. They are there to make money not off you, but off large institutions and your data.  You are just a stepping stone to their goals.
2025 Nov: I would say service quality has improved enough to the point where it can make sense to use a 'premium' subscription/usage of API services without expecting to be screwed 7-8/10 times.
2025 Dec: I spoke too soon. I have the opinion of GPT-5.1 High > Sonnet/Opus. The Anthropic models are just too 'independent/lazy'. I personally have never had gpt5 fill out a PRD with completely hallucinated bullshit, or gaslight me repeatedly across multiple different sessions. Sonnet/Opus 4.0-4.5? Complete opposite.


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

---

## License

GNU General Public License v3.0 - see `LICENSE` for details.

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
- The people who have helped me get to this point(SC & CS), and especially for those not around to see it(DT & CC).

---

## About

tldw_server started as a tool to transcribe and summarize YouTube videos but has evolved into a comprehensive media analysis and knowledge management platform. The goal is to help researchers, students, and professionals manage and analyze their media consumption effectively.

Long-term vision: Building towards a personal AI research assistant inspired by "The Young Lady's Illustrated Primer" from Neal Stephenson's "The Diamond Age" - a tool that helps you learn and research at your own pace.

### Getting Help
- API Documentation: `http://localhost:8000/docs`
- GitHub Issues: [Report bugs or request features](https://github.com/rmusser01/tldw_server/issues)
- Discussions: [Community forum](https://github.com/rmusser01/tldw_server/discussions)


### Security Disclosures
See `SECURITY.md` for reporting guidelines and disclosures.


### Project Guidelines
See [Project_Guidelines.md](Project_Guidelines.md) for development philosophy and contribution guidelines.


---


#### And because Who doesn't love a good quote or two? (Particularly relevant to this material/LLMs)
- `I like the lies-to-children motif, because it underlies the way we run our society and resonates nicely with Discworld. Like the reason for Unseen being a storehouse of knowledge - you arrive knowing everything and leave realising that you know practically nothing, therefore all the knowledge you had must be stored in the university. But it's like that in "real Science", too. You arrive with your sparkling A-levels all agleam, and the first job of the tutors is to reveal that what you thought was true is only true for a given value of "truth". Most of us need just "enough" knowledge of the sciences, and it's delivered to us in metaphors and analogies that bite us in the bum if we think they're the same as the truth.`
    * Terry Pratchett
- `The first principle is that you must not fool yourself - and you are the easiest person to fool.`
    * Richard Feynman
