# tldw_server New User Guide

This guide walks a brand-new user through the shortest path to a working local deployment, a first media ingestion, and the most useful follow-up resources. It complements `README.md` by focusing on actionable steps rather than full feature listings.

---

## 1. What You Get
- **API-first media assistant**: ingest video/audio/docs, run hybrid RAG, and expose OpenAI-compatible Chat, Audio, and Embeddings endpoints.
- **Bring your own models**: plug in 16+ commercial or local providers (OpenAI, Anthropic, vLLM, Ollama, etc.).
- **Knowledge tooling**: searchable notes, prompt studio, character chats, evaluations, Chatbooks import/export.
- **Deployment flexibility**: run everything locally with Python, Docker Compose, or pair the backend with the Next.js Web UI.

---

## 2. Before You Start

| Requirement | Notes |
|-------------|-------|
| **OS** | Linux, macOS, WSL2, or Windows with Python build tools |
| **Python** | 3.11+ (3.12/3.13 tested) |
| **System packages** | `ffmpeg`, `portaudio/pyaudio` (macOS) or `python3-pyaudio` (Linux) for audio capture |
| **Disk** | Plan for SQLite DBs under `Databases/` plus media storage |
| **GPU (optional)** | Enables faster STT/LLM backends; fallback CPU works |
| **Provider credentials** | Add OpenAI/Anthropic/etc. keys to `.env` or `Config_Files/config.txt` |

> Tip: If you are on Windows without WSL2, install the Python build tools and `ffmpeg` manually, or use the Docker path below to avoid native dependencies.

### 2.1 Install ffmpeg + audio capture libraries

These packages let the server transcode media and access microphones. Install **before** running `pip install -e .`.

| Platform | Commands |
|----------|----------|
| **macOS (Homebrew)** | `brew install ffmpeg portaudio`<br>`pip install pyaudio` |
| **Ubuntu/Debian** | `sudo apt update && sudo apt install ffmpeg portaudio19-dev python3-pyaudio` |
| **Fedora** | `sudo dnf install ffmpeg portaudio portaudio-devel python3-pyaudio` |
| **Windows** | `choco install ffmpeg` (or download binaries)<br>`pip install pipwin && pipwin install pyaudio` |
| **WSL2** | Use the Linux instructions inside WSL; Windows audio devices stay accessible through ALSA/Pulse. |

> If `pip install pyaudio` fails, install the system `portaudio` dev headers first (Linux) or use `pipwin` (Windows) to pull a matching wheel.

---

## 3. Fast Path: Local Python Install

Follow these steps from the repository root (`tldw_server2/`):

### 3.1 Create a virtual environment and install dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e .
# Optional extras:
# pip install -e ".[dev]"          # linting/tests
# pip install -e ".[multiplayer]"  # Postgres + multi-user helpers
# pip install -e ".[otel]"         # telemetry exporters
```

### 3.2 Configure auth + provider settings
Create `.env` (or extend if it already exists):
```bash
cat > .env <<'EOF'
AUTH_MODE=single_user
SINGLE_USER_API_KEY=CHANGE_ME_TO_SECURE_API_KEY
DATABASE_URL=sqlite:///./Databases/users.db
# Provider keys (examples)
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=...
EOF
```
You can also keep large provider configs in `tldw_Server_API/Config_Files/config.txt`.

### 3.3 Initialize AuthNZ and databases
```bash
python -m tldw_Server_API.app.core.AuthNZ.initialize
```
This validates the environment, seeds the AuthNZ DB, and prints the API key for single-user mode if not set.

### 3.4 Run the API
```bash
python -m uvicorn tldw_Server_API.app.main:app --reload
```
- Docs/UI: http://127.0.0.1:8000/docs
- Legacy Web UI: http://127.0.0.1:8000/webui/

### 3.5 Smoke-test the API
Use your API key (`SINGLE_USER_API_KEY`) in the header:
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: CHANGE_ME_TO_SECURE_API_KEY" \
  -d '{
        "model": "openai:gpt-4o-mini",
        "messages": [{"role": "user", "content": "Say hello from tldw_server"}]
      }'
```
Replace `model` with anything configured in your provider list (see `/api/v1/llm/providers` for active entries).

---

## 4. Runtime & Provider Configuration

Once the server boots, you’ll likely tailor behaviour, credentials, and model lists. Two files drive most settings:

### 4.1 `.env`: secrets, auth, and DB targets
- Location: `tldw_server2/.env` (same folder as `pyproject.toml`).
- Best place for **secrets**: API keys, DB passwords, Postgres URLs, JWT secrets.
- Common fields:
  - `AUTH_MODE` = `single_user` (API key header) or `multi_user` (JWT/auth endpoints).
  - `SINGLE_USER_API_KEY` or `JWT_SECRET_KEY`.
  - `DATABASE_URL` (AuthNZ DB), `JOBS_DB_URL`, `TEST_DATABASE_URL`.
  - Provider keys: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, etc.
  - `STREAMS_UNIFIED`, `LOG_LEVEL`, and other boolean toggles documented in `Env_Vars.md`.
- After editing `.env`, restart the FastAPI server (env variables are read at startup).

### 4.2 `config.txt`: user-facing defaults and feature flags
- Location: `tldw_Server_API/Config_Files/config.txt`.
- Back this file up or keep a copy in `.git/info/exclude` if you don’t want Git noise.
- Controls everything from file-size limits to chat rate limits. Key sections:
  - `[Server]`: `disable_cors`, `allow_remote_webui_access`, and `webui_ip_allowlist` for restricting the legacy UI.
  - `[Media-Processing]`: per-file-size caps/timeouts for video/audio/PDF ingestion.
  - `[Chat-Module]`: streaming defaults, history depth, rate limits.
  - `[Database]`: choose SQLite vs Postgres for content (`pg_*` fields).
  - `[Chunking]`, `[RAG]`, `[Embeddings]`: tune context windows and vector backends.
- Use any editor, then restart the API (or run `python -m tldw_Server_API.app.core.AuthNZ.initialize` once to validate the config).

### 4.3 Adding cloud LLM providers & keys
1. Drop the API key into `.env`, e.g. `ANTHROPIC_API_KEY=sk-ant-...`.
2. In `config.txt`, open the `[API]` section and set the defaults for that provider:
   ```ini
   [API]
   anthropic_model = claude-3-5-sonnet-latest
   anthropic_temperature = 0.6
   default_api = anthropic        # optional: make it the default `/chat/completions` target
   ```
3. If the provider exposes a custom base URL, set it here as well (e.g. `qwen_api_base_url`).
4. Call `GET /api/v1/llm/providers` to confirm the provider is now listed.

### 4.4 Pointing to self-hosted/local LLMs
Edit the `[Local-API]` section of `config.txt`. Each entry maps to a backend host:

```ini
[Local-API]
ollama_api_IP = http://192.168.1.50:11434/v1/chat/completions
ollama_model = llama3:instruct
vllm_api_IP = http://localhost:8001/v1/chat/completions
vllm_model = my-hf-model-id
tabby_api_IP = http://127.0.0.1:5000/v1/chat/completions
```

- Use full URLs (protocol + host + port + path). For LAN hosts, whitelist their CIDRs via `[Server] webui_ip_allowlist`.
- Update temperature/top_p/max_tokens per provider if the backend expects different defaults.
- After editing, restart the API so the provider manager reloads the endpoints.

### 4.5 Where to adjust user-facing behaviour
- **Rate limits**: `[Chat-Module] rate_limit_per_minute`, `[Character-Chat]` guards.
- **Storage paths**: `[Database] sqlite_path`, `backup_path`, and `chroma_db_path`.
- **Web access**: `[Server] allow_remote_webui_access=true` plus `webui_ip_allowlist=10.0.0.0/24`.
- **Setup UI**: `[Setup] allow_remote_setup_access=true` if you must run first-time setup remotely (only on trusted networks).

---

## 5. Docker Compose Path (All Services)

If you prefer containers (or are on Windows without build tools):
```bash
# Base stack (SQLite users DB + Redis + app)
docker compose -f Dockerfiles/docker-compose.yml up -d --build

# Multi-user/Postgres mode
export AUTH_MODE=multi_user
export DATABASE_URL=postgresql://tldw_user:TestPassword123!@postgres:5432/tldw_users
docker compose -f Dockerfiles/docker-compose.yml \
             -f Dockerfiles/docker-compose.override.yml up -d --build
```
After the containers are up, initialize AuthNZ inside the app container:
```bash
docker compose -f Dockerfiles/docker-compose.yml exec app \
  python -m tldw_Server_API.app.core.AuthNZ.initialize
```
- Check logs: `docker compose -f Dockerfiles/docker-compose.yml logs -f app`
- Optional overlays: `docker-compose.dev.yml` (unified streaming), `docker-compose.pg.yml` (pgvector/pgbouncer), proxy variants.

---

## 6. Connect the Next.js Web UI (Optional but Friendly)
The `tldw-frontend/` directory hosts the current Next.js client.
```bash
cd tldw-frontend
cp .env.local.example .env.local        # set NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
echo "NEXT_PUBLIC_X_API_KEY=CHANGE_ME_TO_SECURE_API_KEY" >> .env.local
npm install
npm run dev -- -p 8080
```
Open http://localhost:8080 to use the UI. CORS defaults allow 8080, so matching the port avoids manual server tweaks.

---

## 7. Process Your First Media File
Once the API is running:
1. Place a sample file under `Samples/` (the repo already includes several fixtures).
2. Use the media ingestion endpoint:
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/media/process" \
  -H "X-API-KEY: CHANGE_ME_TO_SECURE_API_KEY" \
  -F "source_type=file" \
  -F "file=@Samples/sample_audio.mp3" \
  -F "title=Sample Audio" \
  -F "tags=demo,quickstart"
```
3. Track progress via `/api/v1/media/status/{job_id}` (returned from the process call) or use `/api/v1/media/search` once ingestion finishes.

---

## 8. Common Next Steps
- **Explore docs**: OpenAPI docs at `/docs`, plus deep dives in `Docs/` (RAG, AuthNZ, MCP, etc.).
- **List available providers**: `GET /api/v1/llm/providers` to confirm names/models you can target.
- **Run tests**: `python -m pytest -v` (add `-m "unit"` or `-m "integration"` as needed).
- **Switch to PostgreSQL**: set `DATABASE_URL` and leverage `tldw_Server_API/app/core/DB_Management/` migration helpers.
- **Enable unified streaming**: export `STREAMS_UNIFIED=1` or use the Docker dev overlay for SSE/WS pilots.

---

## 9. Troubleshooting Cheat Sheet

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| `uvicorn` crashes on startup | Missing `.env` or invalid provider config | Re-run `AuthNZ.initialize`, inspect `.env` values |
| `ffmpeg`/audio errors | Binary not installed or not in `PATH` | Install `ffmpeg`, restart terminal |
| `X-API-KEY` rejected | Key mismatch or wrong auth mode | Verify `AUTH_MODE`, check env, inspect server logs |
| Media stuck in `processing` | Background workers blocked or DB locked | Check logs under `Databases/`, ensure only one writer, consider Postgres |
| Docker health fails | Compose overlay mismatch | Start with base compose file, then add overlays gradually |

> Enable debug logging by setting `LOG_LEVEL=DEBUG` before launching the server if you need granular traces (Loguru handles formatting).

---

## 10. Where to Learn More
- `README.md`: feature matrix, architecture diagrams, release notes.
- `Docs/`: AuthNZ, RAG, TTS/STT, MCP, deployment profiles.
- `Project_Guidelines.md`: development philosophy if you plan to contribute.
- GitHub Issues/Discussions: report bugs, request features, or ask setup questions.

Happy building! Once you ingest your first file and run a chat completion, you have the full pipeline working—everything else (prompt studio, evaluations, MCP, browser extension) builds on the same foundation.
