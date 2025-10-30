<div align="center">

<h1>tldw Server</h1>
<p>Too Long; Didn't Watch — API‑first media analysis & research platform</p>

<a href="https://www.gnu.org/licenses/old-licenses/gpl-2.0.en.html">
  <img alt="License: GPLv2" src="https://img.shields.io/badge/license-GPLv2-blue.svg" />
  </a>

</div>

---

## Table of Contents

- Overview
- What's New
- Highlights
- Architecture & Repo Layout
- Architecture Diagram
- Quickstart
- Usage Examples
- Key Endpoints
- Configuration & Auth
- Frontend & UI
- Deployment
- Troubleshooting
- Contributing & License
- Roadmap & Privacy

## Overview

tldw_server (Too Long; Didn’t Watch Server) is an open‑source backend for ingesting, transcribing, analyzing, and retrieving knowledge from video, audio, and document sources. It exposes a FastAPI‑first architecture with OpenAI‑compatible Chat and Audio APIs, a unified RAG pipeline, knowledge management, and integrations with local or hosted LLM providers.

The long‑term vision is a personal research assistant inspired by The Young Lady’s Illustrated Primer—helping people learn, reason about, and retain what they watch or read.

## Current Status

- v0.1.0 reflects the rebuild around FastAPI and async services.
- AuthNZ supports single‑user API key and multi‑user JWT modes with usage logging and rate limiting.
- Next.js client lives in `tldw-frontend`; the FastAPI‑served WebUI (`/webui`) is legacy but available.
- Active WIP: workflow automation, browser extensions, writing helpers, and research providers.

## What's New

- FastAPI‑first backend with OpenAI‑compatible Chat and Audio APIs (including streaming STT and TTS)
- Unified RAG and Evaluations modules (hybrid BM25 + vector with re‑ranking; unified metrics)
- MCP Unified module with JWT/RBAC, tool execution APIs, and WebSockets
- Next.js web client (`tldw-frontend`) as the primary UI; integrated WebUI remains for compatibility
- Strict OpenAI compatibility mode for local/self‑hosted providers
- PostgreSQL content mode + backup/restore helpers; Prometheus metrics and monitoring improvements

See: `Docs/Published/RELEASE_NOTES.md` for detailed release notes.

## Highlights

- Media ingestion & processing: video, audio, PDFs, EPUB, DOCX, HTML, Markdown, XML, MediaWiki dumps; metadata extraction; configurable chunking.
- Audio & speech: real‑time and file STT via faster_whisper, NVIDIA NeMo (Canary/Parakeet), Qwen2Audio; OpenAI‑compatible TTS and local Kokoro ONNX.
- Search & retrieval (RAG): hybrid BM25 + vector (ChromaDB/pgvector), re‑ranking, contextual retrieval, OpenAI‑compatible embeddings.
- Chat & providers: `/api/v1/chat/completions` (OpenAI‑compatible), 16+ providers (commercial + self‑hosted), character chat, budgets/allowlists.
- Knowledge management: notes, prompt library, character cards, soft‑delete with recovery, Chatbooks import/export.
- Prompt Studio & evaluations: projects, prompt testing/optimization, unified evaluation APIs (G‑Eval, RAG, batch metrics).
- MCP Unified: production MCP with JWT/RBAC, tool execution, WebSockets, metrics, and health endpoints.

## Architecture & Repo Layout

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
│   └── requirements.txt          # Python dependencies
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
  subgraph Clients
    WebUI[Next.js WebUI]:::client
    LegacyUI[Legacy WebUI (/webui)]:::client
    APIClients[CLI/HTTP Clients]:::client
  end

  WebUI -->|HTTP| API
  LegacyUI -->|HTTP| API
  APIClients -->|HTTP/WebSocket| API

  subgraph FastAPI App
    API[FastAPI App /api/v1]:::api
    Endpoints[Endpoints]:::module
    Dependencies[API_Deps (Auth, DB, rate limits)]:::module
    Services[Background Services]:::module
  end

  API --> Endpoints
  API --> Dependencies
  API --> Services

  subgraph Core
    AuthNZ[AuthNZ]:::core
    RAG[RAG]:::core
    LLM[LLM Calls]:::core
    Embeddings[Embeddings]:::core
    Media[Ingestion & Media Processing]:::core
    TTS[Audio STT/TTS]:::core
    Chatbooks[Chatbooks]:::core
    MCP[MCP Unified]:::core
  end

  Endpoints --> AuthNZ
  Endpoints --> RAG
  Endpoints --> LLM
  Endpoints --> Embeddings
  Endpoints --> Media
  Endpoints --> TTS
  Endpoints --> Chatbooks
  Endpoints --> MCP

  subgraph Storage
    UsersDB[(AuthNZ DB: SQLite/PostgreSQL)]:::db
    ContentDB[(Content DBs: SQLite/PostgreSQL)]:::db
    VectorDB[(ChromaDB / pgvector)]:::db
  end

  Core --> UsersDB
  Core --> ContentDB
  RAG --> VectorDB

  subgraph External Providers
    OpenAI[OpenAI/Anthropic/etc.]:::ext
    LocalLLM[Local Providers (vLLM, Ollama, llama.cpp,…)]:::ext
    OCR[OCR (Tesseract, dots, POINTS)]:::ext
    MediaDL[yt-dlp / ffmpeg]:::ext
  end

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

## Quickstart

Prerequisites
- Python 3.11+ (3.12/3.13 supported)
- ffmpeg (for audio/video pipelines)

Virtualenv
1) Create environment and install dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r tldw_Server_API/requirements.txt
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
# Bring up the stack (app + dependencies where applicable)
docker compose -f Dockerfiles/docker-compose.yml up -d --build

# Optional proxy overlay examples are available:
#   - Dockerfiles/docker-compose.proxy.yml
#   - Dockerfiles/docker-compose.proxy-nginx.yml
```

Tip: See multi-user setup and production hardening in Docs/User_Guides/Authentication_Setup.md and Docs/Published/Deployment/First_Time_Production_Setup.md.

## Usage Examples

Use the single‑user API key with the `X-API-KEY` header.

Chat (OpenAI‑compatible)
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

Embeddings (OpenAI‑compatible)
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

- `POST /api/v1/media/process`         — ingest/process media (URLs or files)
- `GET  /api/v1/media/search`          — search ingested content
- `POST /api/v1/chat/completions`      — OpenAI‑compatible chat
- `POST /api/v1/embeddings`            — OpenAI‑compatible embeddings
- `POST /api/v1/rag/search`            — unified RAG search
- `POST /api/v1/audio/transcriptions`  — file‑based STT
- `WS   /api/v1/audio/stream/transcribe` — real‑time STT
- `POST /api/v1/chatbooks/export`      — export to chatbook
- `POST /api/v1/chatbooks/import`      — import chatbook
- `GET  /api/v1/llm/providers`         — provider/models list
- `GET  /api/v1/mcp/status`            — MCP status

## Running Tests

- `python -m pytest -v` — full test suite (skips heavy optional suites by default).
- `python -m pytest --cov=tldw_Server_API --cov-report=term-missing` — coverage report.
- Use markers (`unit`, `integration`, `e2e`, `external_api`, `performance`) to focus specific areas.
- Enable optional suites with environment flags such as `RUN_MCP_TESTS=1`, `TLDW_TEST_POSTGRES_REQUIRED=1`, or `RUN_MOCK_OPENAI=1`.

## Frontend & UI

- The actively developed Next.js client lives in `tldw-frontend` (see its README for setup/build).
- The FastAPI backend serves a legacy UI at `/webui`; it is stable but feature‑frozen.

## Documentation & Resources

- `Docs/Documentation.md` — documentation index and developer guide links
- `Docs/About.md` — project background and philosophy
- Module deep dives: `Docs/Development/AuthNZ-Developer-Guide.md`, `Docs/Development/RAG-Developer-Guide.md`, `Docs/MCP/Unified/Developer_Guide.md`
- API references: `Docs/API-related/RAG-API-Guide.md`, `Docs/API-related/OCR_API_Documentation.md`, `Docs/API-related/Prompt_Studio_API.md`
- Deployment/Monitoring: `Docs/Published/Deployment/First_Time_Production_Setup.md`, `Docs/Published/Deployment/Reverse_Proxy_Examples.md`, `Docs/Deployment/Monitoring/`
- Design notes (WIP features): `Docs/Design/` — e.g., `Docs/Design/Custom_Scrapers_Router.md`

### OpenAI‑Compatible Strict Mode (Local Providers)

Some self-hosted OpenAI-compatible servers reject unknown fields (like `top_k`). For local providers you can enable a strict mode that filters non-standard keys from chat payloads.

- Set `strict_openai_compat: true` in the relevant provider section (`local_llm`, `llama_api`, `ooba_api`, `tabby_api`, `vllm_api`, `aphrodite_api`, `ollama_api`).
- For `local_llm`, you can also use `LOCAL_LLM_STRICT_OPENAI_COMPAT=1`.
- When enabled, only standard OpenAI Chat Completions parameters are sent:
  `messages, model, temperature, top_p, max_tokens, n, stop, presence_penalty, frequency_penalty, logit_bias, seed, response_format, tools, tool_choice, logprobs, top_logprobs, user, stream`.

## Deployment

- Dockerfiles and compose templates live under `Dockerfiles/`.
- Reverse proxy samples: `Helper_Scripts/Samples/Nginx/`, `Helper_Scripts/Samples/Caddy/`.
- Monitoring: `Docs/Deployment/Monitoring/` and `Helper_Scripts/Samples/Grafana/`.
- Prometheus metrics exposed at `/metrics` and `/api/v1/metrics`.
- Production hardening: `Docs/Published/User_Guides/Production_Hardening_Checklist.md`.

### PostgreSQL Content Mode

- Content DBs (Media, ChaChaNotes, Workflows) can run on Postgres.
- See: `Docs/Published/Deployment/Postgres_Content_Mode.md`, `Docs/Published/Deployment/Postgres_Migration_Guide.md`, and `Docs/Published/Deployment/Postgres_Backups.md`.


## Troubleshooting

- ffmpeg missing: ensure `ffmpeg -version` works; install via your package manager.
- Torch/CUDA mismatch: install a CUDA‑compatible PyTorch or use CPU wheels.
- SQLite locks: prefer short‑lived transactions and context managers; consider Postgres for concurrency.
- OpenAI strict mode: enable strict compatibility for local providers that reject unknown fields.
- Docker: inspect with `docker compose ps` and `docker compose logs -f`.

## Contributing & Support

- Read `CONTRIBUTING.md`, `Project_Guidelines.md`, and `AGENTS.md` before submitting changes.
- File bugs or feature requests via GitHub Issues; longer-form discussions live in GitHub Discussions.
- Respect the project philosophy: incremental progress, clear intent, and kindness toward contributors.

## License

GNU General Public License v2.0 — see `LICENSE` for details.

## Roadmap & Privacy

Roadmap & WIP
- Browser extension for direct web capture (WIP)
- Expanded writing assistance and workflow automation (WIP)
- Additional research providers, evaluation tooling, and flashcard improvements

Privacy & Security
- Self‑hosted by design; no telemetry or data collection
- Users own and control their data; see hardening guide for production
