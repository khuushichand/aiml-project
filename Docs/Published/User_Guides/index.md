# User Guides

Welcome to the tldw_server User Guides. This section collects practical, task-focused docs to help you install, configure, and use the server, the Next.js WebUI, and key features like media ingestion, chat, RAG, embeddings, and evaluations.

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
# Quickstart: http://127.0.0.1:8000/api/v1/config/quickstart
```

## Start Here

- [Installation & Setup](Installation-Setup-Guide.md)
- [Authentication Setup](Authentication_Setup.md)
- [User Guide](User_Guide.md) - Using the app (WebUI + API basics)
- [CLI Reference](CLI_Reference.md)

## Content & Media

- [Media→Embeddings→RAG→Evals Workflow](Media_to_RAG_Evals_Workflow.md)
- [Web Scraping & Ingestion](Web_Scraping_Ingestion_Guide.md)
- [EPUB Reader Guide](EPUB_Reader_Guide.md)
- [Chatbook User Guide](Chatbook_User_Guide.md) - Export/import content
- [Chatbook Tools Getting Started](Chatbook_Tools_Getting_Started.md)
- [Chunking Templates User Guide](Chunking_Templates_User_Guide.md)
- [Templated Chunking HowTo](Templated_Chunking_Incoming_Documents_HowTo.md)

## RAG & Evaluations

- [RAG Deployment Guide](RAG_Deployment_Guide.md)
- [RAG Production Configuration](RAG_Production_Configuration_Guide.md)
- [Evaluations User Guide](Evaluations_User_Guide.md)
- [Evaluations Deployment Guide](Evaluations_Deployment_Guide.md)
- [Evaluations End User Guide](Evaluations_End_User_Guide.md)
- [Evaluations Production Deployment](Evaluations_Production_Deployment_Guide.md)

## Chat & AI

- [Chat Pages](Chat_Pages.md)
- [Character Roleplay Quickstart](Character_Roleplay_Quickstart.md)
- [Effective Character Roleplay and You](Effective_Character_Roleplay_and_You.md)
- [Advanced Character Roleplay Guide](Advanced_Character_Roleplay_Guide.md)
- [Setting up a local LLM](Setting_up_a_local_LLM.md)
- [Prompt Engineering Notes](Prompt_Engineering_Notes.md)
- [Context MCP Search](context_mcp_search.md)

## Audio & TTS

- [Voice Agent Setup Guide](Voice_Agent_Setup_Guide.md) - Set up and test `/api/v1/voice` REST + WebSocket flows
- [TTS Getting Started](TTS_Getting_Started.md) - Text-to-speech setup and usage

## Organizations & Admin

- [Organizations and Sharing](Organizations_and_Sharing.md) - Joining orgs, content visibility, sharing
- [Organization Administration](Organization_Administration.md) - Managing orgs, teams, billing
- [Multi-User Deployment Guide](Multi-User_Deployment_Guide.md)
- [Production Hardening Checklist](Production_Hardening_Checklist.md)
- [Usage Module](Usage_Module.md)

## Keys & Backups

- [BYOK User Guide](BYOK_User_Guide.md) - Bring Your Own Keys
- [Backups with Litestream](Backups_Using_Litestream.md) - SQLite backup strategy

## Examples & Tutorials

- [Workflows Examples](Workflows_Examples.md)
- [Project2025 RAG Guide](Project2025-RAG-Guide.md)
- [Kanban Board Guide](Kanban_Board_Guide.md)
- [Setup Supertonic](Setup-Supertonic.md)
- [Setup Supertonic 2](Setup-Supertonic2.md)

---

Tip: Use `/api/v1/config/quickstart` to reach the configured UI/docs target. The OpenAPI docs at `/docs` include an Authorize button that supports both auth modes: use `X-API-KEY` for single-user or `Bearer` JWT for multi-user.
