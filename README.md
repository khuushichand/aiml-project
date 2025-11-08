<div align="center">

<h1>tldw Server</h1>
<p>Too Long; Didn't Watch - API-first media analysis & research platform</p>

<a href="https://www.gnu.org/licenses/old-licenses/gpl-3.0.en.html">[![madewithlove](https://img.shields.io/badge/made_with-%E2%9D%A4-red?style=for-the-badge&labelColor=orange)](https://github.com/rmusser01/tldw_server)
<img alt="License: GPLv3" src="https://img.shields.io/badge/license-GPLv3-blue.svg" />
  </a>

<h3>Process Media and more with 16+ LLM providers + OpenAI-compatible APIs for Chat, Embeddings and Evals</h3>

<h3>Hosted SaaS + Browser Extension coming soon.</h3>

## Your Own Local Open-Source Platform for Media Analysis, Knowledge Work and LLM-Backed (Creative) Efforts
</div>

---

## Table of Contents

- [Overview](#overview)
- [Current Status](#current-status)
- [What's New](#whats-new)
- [Highlights](#highlights)
- [Feature Status](#feature-status)
- [Architecture & Repo Layout](#architecture--repo-layout)
- [Architecture Diagram](#architecture-diagram)
- [Quickstart](#quickstart)
- [Usage Examples](#usage-examples)
- [Key Endpoints](#key-endpoints)
- [Running Tests](#running-tests)
- [Frontend & UI](#frontend--ui)
- [Documentation & Resources](#documentation--resources)
- [Deployment](#deployment)
- [Networking & Limits](#networking--limits)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)
- [Contributing & Support](#contributing--support)
- [Developer Guides](#developer-guides)
- [License](#license)
- [Credits](#credits)
- [About](#about)
- [Roadmap & Privacy](#roadmap--privacy)

## Overview

tldw_server (Too Long; Didn’t Watch Server) is an open-source backend for ingesting, transcribing, analyzing, and retrieving knowledge from video, audio, and document sources. It exposes a FastAPI-first architecture with OpenAI-compatible Chat and Audio APIs, a unified RAG pipeline, knowledge management, and integrations with local or hosted LLM providers.

The long-term vision is a personal research assistant inspired by The Young Lady’s Illustrated Primer-helping people learn, reason about, and retain what they watch or read.

## Current Status

### Status: Version 0.1.0 published - tldw_server is now in beta
- Expect bugs, and random issues.
- Please report any found/encountered.
- CI/CD reporting green is Top priority next to bug squashing.

## Version 0.1.0 - API-First Architecture (Complete rebuild from Gradio PoC)

This is a major milestone release that transitions tldw from a Gradio-based application to a robust FastAPI backend:

- **API-First Design**: Full RESTful API with OpenAPI documentation
- **Stable Core**: Production-ready media processing and analysis
- **Extensive Features**: 14+ endpoint categories with 100+ operations
- **OpenAI Compatible**: Drop-in replacement for chat completions (Chat Proxy Server)
- **Gradio Deprecated**: The Gradio UI remains available but is no longer maintained/part of this project.
- **tldw_Chatbook**: Has become a separate standalone application
- Active WIP: workflow automation, browser extensions, writing helpers, and research providers.


## What's New

- FastAPI-first backend with OpenAI-compatible Chat and Audio APIs (including streaming STT and TTS)
- Unified RAG and Evaluations modules (hybrid BM25 + vector with re-ranking; unified metrics)
- MCP Unified module with JWT/RBAC, tool execution APIs, and WebSockets
- Next.js web client (`tldw-frontend`) as the primary UI; integrated WebUI remains for compatibility
- Strict OpenAI compatibility mode for local/self-hosted providers
- PostgreSQL content mode + backup/restore helpers; Prometheus metrics and monitoring improvements

See: `Docs/Published/RELEASE_NOTES.md` for detailed release notes.

---

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
---

## Highlights

- Media ingestion & processing: video, audio, PDFs, EPUB, DOCX, HTML, Markdown, XML, MediaWiki dumps; metadata extraction; configurable chunking.
- Audio & speech: real-time and file STT via faster_whisper, NVIDIA NeMo (Canary/Parakeet), Qwen2Audio; OpenAI-compatible TTS and local Kokoro ONNX.
- Search & retrieval (RAG): hybrid BM25 + vector (ChromaDB/pgvector), re-ranking, contextual retrieval, OpenAI-compatible embeddings.
- Chat & providers: `/api/v1/chat/completions` (OpenAI-compatible), 16+ providers (commercial + self-hosted), character chat, budgets/allowlists.
- Knowledge management: notes, prompt library, character cards, soft-delete with recovery, Chatbooks import/export.
- Prompt Studio & evaluations: projects, prompt testing/optimization, unified evaluation APIs (G-Eval, RAG, batch metrics).
- MCP Unified: production MCP with JWT/RBAC, tool execution, WebSockets, metrics, and health endpoints.

## Feature Status

See the full Feature Status Matrix in `Docs/Published/Overview/Feature_Status.md`.

## Networking & Limits

- HTTP client and TLS/pinning configuration: `tldw_Server_API/Config_Files/README.md` (timeouts, retries, redirects/proxies, JSON limits, TLS min version, cert pinning, SSE/download helpers).
- Egress/SSRF policy and security middleware: `tldw_Server_API/app/core/Security/README.md`.
- Resource Governor (rate limits, tokens, streams; Redis backend optional): `tldw_Server_API/app/core/Resource_Governance/README.md`.


## Architecture & Repo Layout

<details>
<summary> Architecture & Repo Layout Here </summary>

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
│   ├── WebUI/                    # Legacy integrated WebUI served at /webui
│   ├── Config_Files/             # config.txt, example YAMLs, migration helpers
│   ├── Databases/                # Default DBs (runtime data; some are gitignored)
│   ├── tests/                    # Pytest suite
│   └── requirements.txt          # Legacy pin set (prefer pyproject extras)
├── tldw-frontend/                # Next.js WebUI (current client)
├── Docs/                         # Documentation (API, Development, RAG, AuthNZ, TTS, etc.)
├── Helper_Scripts/               # Utilities (installers, prompt tools, doc generators)
├── Dockerfiles/                  # Docker images and compose files
├── Databases/                    # DBs (AuthNZ defaults here; content DBs per-user under user_databases/)
├── models/                       # Optional model assets (if used)
├── pyproject.toml                # Project configuration
├── README.md                     # Project README (this file)
├── start-webui.sh                # Convenience script for WebUI + server
└── Project_Guidelines.md         # Development philosophy
```

Notes
- The FastAPI app serves a legacy UI at `/webui`; new features target the Next.js client.
- SQLite is default for local dev; PostgreSQL supported for AuthNZ and content DBs.


## Architecture Diagram

```mermaid
flowchart LR
  subgraph CLIENTS [Clients]
    WebUI[Next.js WebUI]:::client
    LegacyUI[Legacy WebUI (/webui)]:::client
    APIClients[CLI/HTTP Clients]:::client
  end

  subgraph API_STACK [FastAPI App]
    API[FastAPI App /api/v1]:::api
    Endpoints[Endpoints]:::module
    Dependencies[API Deps (Auth, DB, rate limits)]:::module
    Services[Background Services]:::module
  end

  subgraph CORE [Core Modules]
    AuthNZ[AuthNZ]:::core
    RAG[RAG]:::core
    LLM[LLM Calls]:::core
    Embeddings[Embeddings]:::core
    Media[Ingestion & Media Processing]:::core
    TTS[Audio STT/TTS]:::core
    Chatbooks[Chatbooks]:::core
    MCP[MCP Unified]:::core
  end

  subgraph STORAGE [Storage]
    UsersDB[(AuthNZ DB: SQLite/PostgreSQL)]:::db
    ContentDB[(Content DBs: SQLite/PostgreSQL)]:::db
    VectorDB[(ChromaDB / pgvector)]:::db
  end

  subgraph EXTERNAL [External Providers]
    OpenAI[OpenAI/Anthropic/etc.]:::ext
    LocalLLM[Local Providers (vLLM, Ollama, llama.cpp, ...)]:::ext
    OCR[OCR (Tesseract, dots, POINTS)]:::ext
    MediaDL[yt-dlp / ffmpeg]:::ext
  end

  %% Client to API
  WebUI -->|HTTP| API
  LegacyUI -->|HTTP| API
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
  Endpoints --> TTS
  Endpoints --> Chatbooks
  Endpoints --> MCP

  %% Core to storage
  AuthNZ --> UsersDB
  Media --> ContentDB
  Chatbooks --> ContentDB
  RAG --> ContentDB
  RAG --> VectorDB

  %% Core to external services
  LLM --> OpenAI
  LLM --> LocalLLM
  Media --> MediaDL
  TTS --> OpenAI
  Media --> OCR

  classDef client fill:#e8f3ff,stroke:#5b8def,color:#1f3b6e;
  classDef api fill:#fff4e6,stroke:#ff9800,color:#5d3d00;
  classDef module fill:#f4f6f8,stroke:#9aa5b1,color:#2d3748;
  classDef core fill:#eefbea,stroke:#34a853,color:#1e4620;
  classDef db fill:#f0eaff,stroke:#8e6cf1,color:#3a2a87;
  classDef ext fill:#fff0f0,stroke:#e57373,color:#7b1f1f;
```

</details>


## Quickstart

Prerequisites
- Python 3.11+ (3.12/3.13 supported)
- ffmpeg (for audio/video pipelines)

Virtualenv
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

#MacOS
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
- Legacy WebUI: http://127.0.0.1:8000/webui/

Docker Compose
```bash
# Run from repo root

# Option A) Single-user (SQLite users DB)
docker compose -f Dockerfiles/docker-compose.yml up -d --build

# Option B) Multi-user (Postgres users DB)
export AUTH_MODE=multi_user
export DATABASE_URL=postgresql://tldw_user:TestPassword123!@postgres:5432/tldw_users
# Optional: route Jobs module to Postgres as well
export JOBS_DB_URL=postgresql://tldw_user:TestPassword123!@postgres:5432/tldw_users
docker compose -f Dockerfiles/docker-compose.yml -f Dockerfiles/docker-compose.override.yml up -d --build

# Option C) Dev overlay — enable unified streaming (non-prod)
# This turns on the SSE/WS unified streams (STREAMS_UNIFIED=1) for pilot endpoints.
# Keep disabled in production until validated in your environment.
docker compose -f Dockerfiles/docker-compose.yml -f Dockerfiles/Dockerfiles/docker-compose.dev.yml up -d --build

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

Run only infrastructure services without the app.

Postgres + Redis (base compose)
```bash
docker compose -f Dockerfiles/docker-compose.yml up -d postgres redis
```

Prometheus + Grafana (embeddings compose, monitoring profile)
```bash
docker compose -f Dockerfiles/Dockerfiles/docker-compose.embeddings.yml --profile monitoring up -d prometheus grafana
```

All four together
```bash
docker compose -f Dockerfiles/docker-compose.yml up -d postgres redis
docker compose -f Dockerfiles/Dockerfiles/docker-compose.embeddings.yml --profile monitoring up -d prometheus grafana
```

Manage and verify
```bash
# Status
docker compose -f Dockerfiles/docker-compose.yml ps
docker compose -f Dockerfiles/Dockerfiles/docker-compose.embeddings.yml ps

# Logs
docker compose -f Dockerfiles/docker-compose.yml logs -f postgres redis
docker compose -f Dockerfiles/Dockerfiles/docker-compose.embeddings.yml logs -f prometheus grafana

# Stop
docker compose -f Dockerfiles/docker-compose.yml stop postgres redis
docker compose -f Dockerfiles/Dockerfiles/docker-compose.embeddings.yml stop prometheus grafana

# Remove
docker compose -f Dockerfiles/docker-compose.yml down
docker compose -f Dockerfiles/Dockerfiles/docker-compose.embeddings.yml down
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

## Usage Examples

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
curl -s http://127.0.0.1:8000/api/v1/media/process \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "https://www.youtube.com/watch?v=..."
  }'
```

Media Search
```bash
curl -s "http://127.0.0.1:8000/api/v1/media/search?q=keyword" \
  -H "X-API-KEY: $SINGLE_USER_API_KEY"
```

Audio Transcription (file)
```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/audio/transcriptions \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -F "file=@sample.wav" -F "model=whisper-1"
```

## Key Endpoints

- Media: `POST /api/v1/media/process` - ingest/process media (URLs/files)
- Media Search: `GET /api/v1/media/search` - search ingested content
- Chat: `POST /api/v1/chat/completions` - OpenAI-compatible chat
- Embeddings: `POST /api/v1/embeddings` - OpenAI-compatible embeddings
- RAG: `POST /api/v1/rag/search` - unified RAG search
- Audio STT: `POST /api/v1/audio/transcriptions` - file-based transcription
- Audio STT (WS): `WS /api/v1/audio/stream/transcribe` - real-time transcription
- Audio TTS: `POST /api/v1/audio/speech` - text-to-speech (streaming and non-streaming)
- TTS Voices: `GET /api/v1/audio/voices/catalog` - voice catalog across providers
- Vector Stores: `POST /api/v1/vector_stores` - create; `POST /api/v1/vector_stores/{id}/query` - query
- OCR Backends: `GET /api/v1/ocr/backends` - available OCR providers
- VLM Backends: `GET /api/v1/vlm/backends` - available VLM providers
- Connectors: `GET /api/v1/connectors/providers` - Drive/Notion providers
- Outputs: `POST /api/v1/outputs` - generate output artifact (md/html/mp3)
- Metrics: `GET /api/v1/metrics/text` - Prometheus metrics (text format)
- Providers: `GET /api/v1/llm/providers` - provider/models list
- MCP: `GET /api/v1/mcp/status` - MCP server status

## Running Tests

- `python -m pytest -v` - full test suite (skips heavy optional suites by default).
- `python -m pytest --cov=tldw_Server_API --cov-report=term-missing` - coverage report.
- Use markers (`unit`, `integration`, `e2e`, `external_api`, `performance`) to focus specific areas.
- Enable optional suites with environment flags such as `RUN_MCP_TESTS=1`, `TLDW_TEST_POSTGRES_REQUIRED=1`, or `RUN_MOCK_OPENAI=1`.

## Frontend & UI

- The actively developed Next.js client lives in `tldw-frontend` (see its README for setup/build).
- The FastAPI backend serves a legacy UI at `/webui`; it is stable but feature-frozen.

## Documentation & Resources

- `Docs/Documentation.md` - documentation index and developer guide links
- `Docs/About.md` - project background and philosophy
- Module deep dives: `Docs/Development/AuthNZ-Developer-Guide.md`, `Docs/Development/RAG-Developer-Guide.md`, `Docs/MCP/Unified/Developer_Guide.md`
- API references: `Docs/API-related/RAG-API-Guide.md`, `Docs/API-related/OCR_API_Documentation.md`, `Docs/API-related/Prompt_Studio_API.md`
- Deployment/Monitoring: `Docs/Published/Deployment/First_Time_Production_Setup.md`, `Docs/Published/Deployment/Reverse_Proxy_Examples.md`, `Docs/Deployment/Monitoring/`
- Design notes (WIP features): `Docs/Design/` - e.g., `Docs/Design/Custom_Scrapers_Router.md`

### Resource Governor Config

For complete Resource Governor setup and examples (env, DB store bootstrap, YAML policy, middleware, diagnostics, and tests), see `tldw_Server_API/app/core/Resource_Governance/README.md`.

### OpenAI-Compatible Strict Mode (Local Providers)

Some self-hosted OpenAI-compatible servers reject unknown fields (like `top_k`). For local providers you can enable a strict mode that filters non-standard keys from chat payloads.

- Set `strict_openai_compat: true` in the relevant provider section (`local_llm`, `llama_api`, `ooba_api`, `tabby_api`, `vllm_api`, `aphrodite_api`, `ollama_api`).
- For `local_llm`, you can also use `LOCAL_LLM_STRICT_OPENAI_COMPAT=1`.
- When enabled, only standard OpenAI Chat Completions parameters are sent:
  `messages, model, temperature, top_p, max_tokens, n, stop, presence_penalty, frequency_penalty, logit_bias, seed, response_format, tools, tool_choice, logprobs, top_logprobs, user, stream`.

## Deployment

- Dockerfiles and compose templates live under `Dockerfiles/` (see `Dockerfiles/README.md`).
- Reverse proxy samples: `Helper_Scripts/Samples/Nginx/`, `Helper_Scripts/Samples/Caddy/`.
- Monitoring: `Docs/Deployment/Monitoring/` and `Helper_Scripts/Samples/Grafana/`.
- Prometheus metrics exposed at `/metrics` and `/api/v1/metrics`.
- Production hardening: `Docs/Published/User_Guides/Production_Hardening_Checklist.md`.

## Monitoring

- Monitoring docs and setup: `Docs/Deployment/Monitoring/README.md`
- Grafana dashboards and samples: `Helper_Scripts/Samples/Grafana/README.md`
- Prometheus scrape endpoints: `GET /metrics` and `GET /api/v1/mcp/metrics/prometheus`

### PostgreSQL Content Mode

- Content DBs (Media, ChaChaNotes, Workflows) can run on Postgres.
- See: `Docs/Published/Deployment/Postgres_Content_Mode.md`, `Docs/Published/Deployment/Postgres_Migration_Guide.md`, and `Docs/Published/Deployment/Postgres_Backups.md`.


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

<details><sumamry>Developer Guides + Links</sumamry>

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

---


### More Detailed Explanation & Background
See `Docs/About.md` for the extended project background, vision, and notes.
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
- The people who have helped me get to this point, and especially for those not around to see it(DT & CC & SC).

---


### Security Disclosures
See `SECURITY.md` for reporting guidelines and disclosures.


---

## About

tldw_server started as a tool to transcribe and summarize YouTube videos but has evolved into a comprehensive media analysis and knowledge management platform. The goal is to help researchers, students, and professionals manage and analyze their media consumption effectively.

Long-term vision: Building towards a personal AI research assistant inspired by "The Young Lady's Illustrated Primer" from Neal Stephenson's "The Diamond Age" - a tool that helps you learn and research at your own pace.

### Getting Help
- API Documentation: `http://localhost:8000/docs`
- GitHub Issues: [Report bugs or request features](https://github.com/rmusser01/tldw_server/issues)
- Discussions: [Community forum](https://github.com/rmusser01/tldw_server/discussions)



---


#### And because Who doesn't love a good quote or two? (Particularly relevant to this material/LLMs)
- `I like the lies-to-children motif, because it underlies the way we run our society and resonates nicely with Discworld. Like the reason for Unseen being a storehouse of knowledge - you arrive knowing everything and leave realising that you know practically nothing, therefore all the knowledge you had must be stored in the university. But it's like that in "real Science", too. You arrive with your sparkling A-levels all agleam, and the first job of the tutors is to reveal that what you thought was true is only true for a given value of "truth". Most of us need just "enough" knowledge of the sciences, and it's delivered to us in metaphors and analogies that bite us in the bum if we think they're the same as the truth.`
    * Terry Pratchett
- `The first principle is that you must not fool yourself - and you are the easiest person to fool.`
  *Richard Feynman


---

## Roadmap & Privacy

Roadmap & WIP
- Browser extension for direct web capture (WIP)
- Expanded writing assistance and workflow automation (WIP)
- Additional research providers, evaluation tooling, and flashcard improvements

Privacy & Security
- Self-hosted by design; no telemetry or data collection
- Users own and control their data; see hardening guide for production
- Metrics & Grafana
  - Emitted metrics (core):
    - `rg_decisions_total{category,scope,backend,result,policy_id}` — allow/deny decisions per category/scope/backend
    - `rg_denials_total{category,scope,reason,policy_id}` — denial events by reason (e.g., `insufficient_capacity`)
    - `rg_refunds_total{category,scope,reason,policy_id}` — refund events from commit/refund paths
    - `rg_concurrency_active{category,scope,policy_id}` — active stream/job leases (gauge)
  - Cardinality guard:
    - By default, metrics DO NOT include `entity` labels to avoid high-cardinality pitfalls. If you truly need per-entity sampling, gate it behind `RG_METRICS_ENTITY_LABEL=true` and ensure hashing/masking is applied upstream.
  - Quick Grafana panel examples:
    - Allow vs Deny over time (per category):
      - Query: `sum by (category, result) (rate(rg_decisions_total[5m]))`
    - Denials by scope (top N):
      - Query: `topk(5, sum by (scope) (rate(rg_denials_total[5m])))`
    - Refund activity (tokens):
      - Query: `sum by (policy_id) (rate(rg_refunds_total{category="tokens"}[5m]))`
    - Active streams (per scope):
      - Query: `avg by (scope) (rg_concurrency_active{category="streams"})`
