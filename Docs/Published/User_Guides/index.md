# User Guides

Welcome to the tldw_server User Guides. This section collects practical, task-focused docs to help you install, configure, and use the server, the integrated WebUI, and key features like media ingestion, chat, RAG, embeddings, and evaluations.

## Quick Start

1) Install dependencies and required tools

```bash
pip install -e .
# FFmpeg is required for audio/video processing (install via your OS package manager)
```

2) Configure authentication

- Single-user mode: set `AUTH_MODE=single_user` and `SINGLE_USER_API_KEY=<your_key>`
- Multi-user mode: set `AUTH_MODE=multi_user` and required JWT/DB settings
- See: Authentication Setup (below) for full details

3) Start the server

```bash
python -m uvicorn tldw_Server_API.app.main:app --reload
# API docs:   http://127.0.0.1:8000/docs
# Web UI:     http://127.0.0.1:8000/webui/
```

## Start Here

- Installation & Setup: Installation-Setup-Guide.md
- Authentication: Authentication_Setup.md
- Using the app (WebUI + API basics): User_Guide.md

## Core Guides

- RAG Deployment: RAG_Deployment_Guide.md
- RAG Production Configuration: RAG_Production_Configuration_Guide.md
- Evaluations (End-User): Evaluations_User_Guide.md
- Evaluations (Deployment): Evaluations_Deployment_Guide.md
- Evaluations (Production): Evaluations_Production_Deployment_Guide.md
- Chunking Templates: Chunking_Templates_User_Guide.md
- Chatbooks (export/import): Chatbook_User_Guide.md

## Operations & Admin

- Multi-User Deployment: Multi-User_Deployment_Guide.md
- Production Hardening Checklist: Production_Hardening_Checklist.md
- Backups with Litestream (SQLite): Backups_Using_Litestream.md
- CLI Reference: CLI_Reference.md
- Prompt Engineering Notes: Prompt_Engineering_Notes.md
- Local LLM Setup: Setting_up_a_local_LLM.md

Tip: The WebUI is served at `/webui` from the same server to avoid CORS issues. The OpenAPI docs at `/docs` include an Authorize button that supports both auth modes: use `X-API-KEY` for single-user or `Bearer` JWT for multi-user.
