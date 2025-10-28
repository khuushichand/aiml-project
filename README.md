<div align="center">

<h1>tldw Server</h1>
<p>Too Long; Didn't Watch — API-first media analysis & research platform</p>

[![Version](https://img.shields.io/badge/version-v0.1.0-blue.svg)](https://github.com/rmusser01/tldw_server/releases)
[![License](https://img.shields.io/badge/license-GPLv2-blue.svg)](https://www.gnu.org/licenses/old-licenses/gpl-2.0.en.html)

<!-- CI Status: per-module and E2E -->
<p>
  <a href="https://github.com/rmusser01/tldw_server/actions/workflows/authnz-tests.yml">
    <img alt="AuthNZ Tests" src="https://github.com/rmusser01/tldw_server/actions/workflows/authnz-tests.yml/badge.svg?branch=main" />
  </a>
  <a href="https://github.com/rmusser01/tldw_server/actions/workflows/embeddings-tests.yml">
    <img alt="Embeddings Tests" src="https://github.com/rmusser01/tldw_server/actions/workflows/embeddings-tests.yml/badge.svg?branch=main" />
  </a>
  <a href="https://github.com/rmusser01/tldw_server/actions/workflows/vector-chroma-tests.yml">
    <img alt="Vector Chroma" src="https://github.com/rmusser01/tldw_server/actions/workflows/vector-chroma-tests.yml/badge.svg?branch=main" />
  </a>
  <a href="https://github.com/rmusser01/tldw_server/actions/workflows/vector-pgvector-tests.yml">
    <img alt="Vector PGVector" src="https://github.com/rmusser01/tldw_server/actions/workflows/vector-pgvector-tests.yml/badge.svg?branch=main" />
  </a>
  <a href="https://github.com/rmusser01/tldw_server/actions/workflows/prompt-studio.yml">
    <img alt="Prompt Studio Tests" src="https://github.com/rmusser01/tldw_server/actions/workflows/prompt-studio.yml/badge.svg?branch=main" />
  </a>
  <a href="https://github.com/rmusser01/tldw_server/actions/workflows/llm-tests.yml">
    <img alt="LLM/Chat Tests" src="https://github.com/rmusser01/tldw_server/actions/workflows/llm-tests.yml/badge.svg?branch=main" />
  </a>
  <a href="https://github.com/rmusser01/tldw_server/actions/workflows/rag-tests.yml">
    <img alt="RAG Tests" src="https://github.com/rmusser01/tldw_server/actions/workflows/rag-tests.yml/badge.svg?branch=main" />
  </a>
  <a href="https://github.com/rmusser01/tldw_server/actions/workflows/media-tests.yml">
    <img alt="Media Tests" src="https://github.com/rmusser01/tldw_server/actions/workflows/media-tests.yml/badge.svg?branch=main" />
  </a>
  <a href="https://github.com/rmusser01/tldw_server/actions/workflows/db-tests.yml">
    <img alt="DB Management Tests" src="https://github.com/rmusser01/tldw_server/actions/workflows/db-tests.yml/badge.svg?branch=main" />
  </a>
  <a href="https://github.com/rmusser01/tldw_server/actions/workflows/audio-tts-tests.yml">
    <img alt="Audio/TTS Tests" src="https://github.com/rmusser01/tldw_server/actions/workflows/audio-tts-tests.yml/badge.svg?branch=main" />
  </a>
  <a href="https://github.com/rmusser01/tldw_server/actions/workflows/mcp-unified-tests.yml">
    <img alt="MCP Unified Tests" src="https://github.com/rmusser01/tldw_server/actions/workflows/mcp-unified-tests.yml/badge.svg?branch=main" />
  </a>
  <a href="https://github.com/rmusser01/tldw_server/actions/workflows/postgres-evaluations.yml">
    <img alt="Evaluations (Postgres)" src="https://github.com/rmusser01/tldw_server/actions/workflows/postgres-evaluations.yml/badge.svg?branch=main" />
  </a>
  <a href="https://github.com/rmusser01/tldw_server/actions/workflows/workflows-tests.yml">
    <img alt="Workflows Suite" src="https://github.com/rmusser01/tldw_server/actions/workflows/workflows-tests.yml/badge.svg?branch=main" />
  </a>
  <a href="https://github.com/rmusser01/tldw_server/actions/workflows/webui-tests.yml">
    <img alt="WebUI Tests" src="https://github.com/rmusser01/tldw_server/actions/workflows/webui-tests.yml/badge.svg?branch=main" />
  </a>
  <a href="https://github.com/rmusser01/tldw_server/actions/workflows/e2e-smoke.yml">
    <img alt="E2E Smoke" src="https://github.com/rmusser01/tldw_server/actions/workflows/e2e-smoke.yml/badge.svg?branch=main" />
  </a>
</p>

</div>

---

## Overview

tldw_server (Too Long; Didn't Watch Server) is an open-source backend for ingesting, transcribing, analyzing, and retrieving knowledge from video, audio, and document sources. It exposes a FastAPI-first architecture with OpenAI-compatible chat and audio APIs, rich retrieval pipelines, knowledge management features, and smooth integration with local or hosted LLM providers.

The long-term vision is to create a personal research assistant inspired by The Young Lady's Illustrated Primer—helping people learn, reason about, and retain what they watch or read.

## Current Status

- Version 0.1.0 reflects the complete rebuild around FastAPI and asynchronous services.
- AuthNZ ships with both single-user API key and multi-user JWT modes, usage logging, and granular rate limiting.
- The modern web client lives in `tldw-frontend` (Next.js). The FastAPI-served WebUI (`/webui`) remains for compatibility but is now legacy.
- The original Gradio UI and standalone Chatbook app have been retired.
- Active work continues on workflow automation, browser extensions, writing helpers, and expanded research providers—expect WIP labels around those areas.

## Highlights

- **Media ingestion & processing**: Handle video, audio, PDFs, EPUB, DOCX, HTML, Markdown, XML, MediaWiki dumps, and email archives with automatic metadata extraction and configurable chunking strategies.
- **Audio & speech**: Real-time streaming and file transcription via faster_whisper, NVIDIA NeMo (Canary/Parakeet), and Qwen2Audio, plus OpenAI-compatible TTS with local Kokoro ONNX support.
- **Search & retrieval (Unified RAG)**: Hybrid BM25 + vector search (ChromaDB or pgvector), reranking pipelines, adaptive claim verification, caching, and OpenAI-compatible embeddings endpoints.
- **Chat & provider hub**: `/api/v1/chat/completions` mirrors OpenAI’s API, connects to 16+ commercial and self-hosted providers, supports character chat, and enforces virtual key budgets and allowlists.
- **Knowledge management**: Notebook-style notes, prompt library, SillyTavern-compatible character cards, soft-delete with recovery, and Chatbooks import/export for backups and migrations.
- **Prompt Studio & evaluations**: Projects, prompt testing, optimization jobs, and unified evaluation APIs (G-Eval, RAG, batch metrics) with cost and usage analytics.
- **MCP Unified & tooling**: Production Model Context Protocol deployment with JWT/RBAC, tool execution APIs, WebSocket support, metrics, and health endpoints.
- **Workflow & research tooling**: Composable workflow engine, hybrid web search, paper search providers, flashcards module, and agentic chunking experiments.

## Architecture & Repo Layout

```text
tldw_server/
├── tldw_Server_API/              # FastAPI backend (core app, endpoints, services)
│   ├── app/api/v1/               # REST endpoints, schemas, dependencies
│   ├── app/core/                 # Domain modules (AuthNZ, RAG, LLM, DB, TTS, MCP, etc.)
│   ├── app/services/             # Background schedulers and workers
│   └── tests/                    # Pytest suite
├── tldw-frontend/                # Next.js web client (current UI)
├── Docs/                         # Architecture, API, deployment, and module documentation
├── Helper_Scripts/               # Utilities and setup helpers
├── Dockerfiles/                  # Container builds and compose samples
├── Databases/                    # Default SQLite databases for local development
├── models/                       # Optional model assets (if used)
├── mock_openai_server/           # Mock server for OpenAI-compatible testing
└── start-webui.sh                # Legacy WebUI + server launcher
```

The FastAPI app still serves a legacy UI from `tldw_Server_API/WebUI/`; new features target the Next.js client.

## Key API Endpoints

- `POST /api/v1/media/process` — ingest or process media sources (URLs or files).
- `GET /api/v1/media/search` — search across processed content.
- `POST /api/v1/chat/completions` — OpenAI-compatible chat completions with optional persistence.
- `POST /api/v1/embeddings` — OpenAI-compatible embeddings endpoint.
- `POST /api/v1/rag/search` — unified retrieval with hybrid strategies, citations, and claim verification.
- `POST /api/v1/audio/transcriptions` / `WS /api/v1/audio/stream/transcribe` — batch and streaming STT.
- `POST /api/v1/chatbooks/export` / `POST /api/v1/chatbooks/import` — backup and restore knowledge bases.
- `GET /api/v1/llm/providers` — inspect configured providers, models, and health.
- `GET /api/v1/mcp/status` — status for the MCP Unified deployment.

## Getting Started

1. Clone the repository and create a virtual environment:
   ```bash
   git clone https://github.com/rmusser01/tldw_server.git
   cd tldw_server
   python3 -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```
2. Install dependencies (ffmpeg must be installed separately for media/audio pipelines):
   ```bash
   pip install -r tldw_Server_API/requirements.txt
   ```
3. Configure authentication and providers:
   ```bash
   cp .env.authnz.template .env
   python -m tldw_Server_API.app.core.AuthNZ.initialize
   # Populate .env or tldw_Server_API/Config_Files/config.txt with provider keys
   ```
4. Run the API server:
   ```bash
   python -m uvicorn tldw_Server_API.app.main:app --reload
   ```
   - API docs: http://127.0.0.1:8000/docs
   - Legacy WebUI: http://127.0.0.1:8000/webui/

## Running Tests

- `python -m pytest -v` — full test suite (skips heavy optional suites by default).
- `python -m pytest --cov=tldw_Server_API --cov-report=term-missing` — coverage report.
- Use markers (`unit`, `integration`, `e2e`, `external_api`, `performance`) to focus specific areas.
- Enable optional suites with environment flags such as `RUN_MCP_TESTS=1`, `TLDW_TEST_POSTGRES_REQUIRED=1`, or `RUN_MOCK_OPENAI=1`.

## Frontend & UI Options

- The actively developed web client lives in `tldw-frontend` (Next.js). Follow its README for installation and build instructions.
- The FastAPI backend still serves a legacy UI at `/webui`; it is stable but feature-frozen.

## Documentation & Resources

- `Docs/Documentation.md` — documentation index and developer guide links.
- `Docs/About.md` — project background and philosophy.
- `Docs/Development/AuthNZ-Developer-Guide.md`, `Docs/Development/RAG-Developer-Guide.md`, `Docs/MCP/Unified/Developer_Guide.md` — module deep dives.
- `Docs/API-related/RAG-API-Guide.md`, `Docs/API-related/OCR_API_Documentation.md`, `Docs/API-related/Prompt_Studio_API.md` — API references with examples.
- `Docs/Deployment/Reverse_Proxy_Examples.md`, `Docs/Deployment/Monitoring/` — deployment, metrics, and operations guides.
- `Docs/Design/` — design notes for in-progress features (Flashcards, Workflows, Agentic Chunking, etc.).
  - See `Docs/Design/Custom_Scrapers_Router.md` for the curl/UA router YAML schema and setup.

### OpenAI-Compatible Strict Mode (Local Providers)

Some self-hosted OpenAI-compatible servers reject unknown fields (like `top_k`). For local providers you can enable a strict mode that filters non-standard keys from chat payloads.

- Set `strict_openai_compat: true` in the relevant provider section (`local_llm`, `llama_api`, `ooba_api`, `tabby_api`, `vllm_api`, `aphrodite_api`, `ollama_api`).
- For `local_llm`, you can also use the environment variable `LOCAL_LLM_STRICT_OPENAI_COMPAT=1`.
- When enabled, only standard OpenAI Chat Completions parameters are sent:
  `messages, model, temperature, top_p, max_tokens, n, stop, presence_penalty, frequency_penalty, logit_bias, seed, response_format, tools, tool_choice, logprobs, top_logprobs, user, stream`.

## Deployment & Operations

- Dockerfiles and compose templates live under `Dockerfiles/` and `Samples/`.
- Prometheus and Grafana assets are in `Docs/Deployment/Monitoring/` and `Samples/Prometheus/`.
- Usage and LLM cost tracking export Prometheus metrics (`/metrics`, `/api/v1/metrics`) and ship with alert samples.
- For reverse proxy hardening, see `Docs/User_Guides/Production_Hardening_Checklist.md`.

### Backups (PostgreSQL)

For deployments using PostgreSQL as the content database, use the new backup/restore helpers and docs:

- CLI helper script: `Helper_Scripts/pg_backup_restore.py`
  - Create a backup:
    ```bash
    python Helper_Scripts/pg_backup_restore.py backup \
      --backup-dir ./tldw_DB_Backups/postgres \
      --label content
    ```
  - Restore a backup:
    ```bash
    python Helper_Scripts/pg_backup_restore.py restore \
      --dump-file ./tldw_DB_Backups/postgres/content_YYYYMMDD_HHMMSS.dump
    ```
  - Requires `pg_dump` / `pg_restore` on PATH and PostgreSQL content mode configured.

- Docs:
  - Deployment guide: `Docs/Published/Deployment/Postgres_Backups.md`
  - Cross‑backend FTS & placeholders: `Docs/Published/Development/DB-Backends-Query-FTS-Guidelines.md`

Make targets for convenience are available (see `Makefile`):
```bash
make pg-backup PG_BACKUP_DIR=./tldw_DB_Backups/postgres PG_LABEL=content
make pg-restore PG_DUMP_FILE=./tldw_DB_Backups/postgres/content_YYYYMMDD_HHMMSS.dump
```

### PostgreSQL Content Mode — Quick Start

To run the content databases (Media, ChaChaNotes, Workflows, etc.) on PostgreSQL instead of SQLite:

1) Install dependencies

```bash
pip install "psycopg[binary]"  # PostgreSQL driver
# Optional if using pgvector in your RAG stack:
pip install pgvector
```

2) Provide connection details via environment variables

```bash
export TLDW_CONTENT_DB_BACKEND=postgresql
export TLDW_PG_HOST=localhost
export TLDW_PG_PORT=5432
export TLDW_PG_DATABASE=tldw_content
export TLDW_PG_USER=tldw_user
export TLDW_PG_PASSWORD=super-secret
```

3) Start the API once to initialize/validate the schema

```bash
python -m uvicorn tldw_Server_API.app.main:app --reload
```

You should see logs indicating the PostgreSQL content backend has been validated. If migrating existing content from SQLite, see the Postgres Migration Guide in the docs.


## Contributing & Support

- Read `CONTRIBUTING.md`, `Project_Guidelines.md`, and `AGENTS.md` before submitting changes.
- File bugs or feature requests via GitHub Issues; longer-form discussions live in GitHub Discussions.
- Respect the project philosophy: incremental progress, clear intent, and kindness toward contributors.

## License

GNU General Public License v2.0 — see `LICENSE` for details.

## Roadmap & WIP

- Browser extension for direct web capture (WIP).
- Expanded writing assistance and workflow automation (WIP).
- Additional research providers, evaluation tooling, and flashcard improvements are being actively explored.

For the latest plans, follow the GitHub milestones and `Docs/Design/` proposals.
## Custom Scrapers (curl/UA router)

The server supports a curl-backed fetch path with realistic browser headers and a per-domain router for scraping.

Enable and customize rules (config.txt driven; no environment variables):
- Copy the example to your config file:
  - `cp tldw_Server_API/Config_Files/custom_scrapers.example.yaml tldw_Server_API/Config_Files/custom_scrapers.yaml`
- Edit `tldw_Server_API/Config_Files/custom_scrapers.yaml` to add per-domain overrides (backend, UA profile, impersonate, extra headers, cookies, proxies, robots policy, url patterns).
- The router validates and normalizes rules at load time; unknown keys are dropped and invalid patterns ignored.

Notes:
- Backends: `auto|curl|httpx|playwright` (curl uses curl_cffi impersonation; httpx is the fallback).
- UA profiles set `User-Agent` + sec-ch-ua*, Accept-Language, Sec-Fetch-*, Accept-Encoding.
- Proxies can be set per-domain (e.g., `http`/`https`).
- Robots: `respect_robots: true` by default; set false per domain if you need to override.

Config keys (`Web-Scraper` section in `Config_Files/config.txt`):
- `custom_scrapers_yaml_path`: override YAML path (optional)
- `web_scraper_default_backend`: `auto|curl|httpx|playwright` (optional)
- `web_scraper_ua_mode`: `fixed|rotate` (optional; default `fixed`)
- `web_scraper_respect_robots`: `True|False` (optional; default `True`)
