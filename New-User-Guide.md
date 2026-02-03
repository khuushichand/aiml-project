# tldw_server New User Guide

> **Note:** This guide is being replaced by the new Getting Started guides:
> - [Tire Kicker Guide](Docs/Getting_Started/Tire_Kicker.md) - 5-minute setup
> - [Local Development Guide](Docs/Getting_Started/Local_Development.md) - building against the API
> - [Docker Self-Host Guide](Docs/Getting_Started/Docker_Self_Host.md) - running on your server
> - [Production Guide](Docs/Getting_Started/Production.md) - team deployment
>
> The content below remains valid but may not be actively maintained.

This guide walks a brand-new user through the shortest path to a working local deployment, a first media ingestion, and the most useful follow-up resources. It complements `README.md` by focusing on actionable steps rather than full feature listings.

---

## 1. What You Get
- **API-first media assistant**: ingest video/audio/docs, run hybrid RAG, and expose OpenAI-compatible Chat, Audio, and Embeddings endpoints.
- **Bring your own models**: plug in 16+ commercial or local providers (OpenAI, Anthropic, vLLM, Llama.cpp, Ollama, etc.).
- **Knowledge tooling**: searchable notes, prompt studio, character chats, evaluations, Chatbooks import/export.
- **Deployment flexibility**: run everything locally with Python or Docker Compose, and optionally pair the API with the Next.js WebUI (primary web client).

---

## 2. Before You Start

| Requirement | Notes |
|-------------|-------|
| **OS** | Linux, macOS, WSL2, or Windows with Python build tools |
| **Python** | 3.10+ (3.11 recommended) |
| **System packages** | `ffmpeg` (required for audio/video). `portaudio/pyaudio` only if you want microphone capture. |
| **Disk** | Plan for SQLite DBs under `Databases/` plus media storage |
| **GPU (optional)** | Enables faster STT/LLM backends; fallback CPU works |
| **Provider credentials** | Add OpenAI/Anthropic/etc. keys to `.env` or `Config_Files/config.txt` |

> Tip: If you are on Windows without WSL2, install the Python build tools and `ffmpeg` manually, or use the Docker path below to avoid native dependencies.

### 2.1 Install ffmpeg + audio capture libraries

These packages let the server transcode media and access microphones. Install `ffmpeg` before running `pip install -e .`. Add `pyaudio` only if you need microphone capture.

| Platform | Commands |
|----------|----------|
| **macOS (Homebrew)** | `brew install ffmpeg portaudio`<br>`pip install pyaudio` |
| **Ubuntu/Debian** | `sudo apt update && sudo apt install ffmpeg portaudio19-dev python3-pyaudio` |
| **Fedora** | `sudo dnf install ffmpeg portaudio portaudio-devel python3-pyaudio` |
| **Windows** | `choco install ffmpeg` (or download binaries)<br>`pip install pipwin && pipwin install pyaudio` |
| **WSL2** | Use the Linux instructions inside WSL. Microphone support depends on your WSL audio setup. |

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
Start from the AuthNZ template, then edit it:
```bash
cp tldw_Server_API/Config_Files/.env.authnz.template .env
# Edit .env to set AUTH_MODE and your keys
```
Key fields to set:
- **Single-user**: `AUTH_MODE=single_user` + `SINGLE_USER_API_KEY=<secure value>`
- **Multi-user**: `AUTH_MODE=multi_user` + `JWT_SECRET_KEY=<secure 32+ chars>`
- `DATABASE_URL` (defaults to SQLite; use Postgres for multi-user production)
- Provider keys (optional): `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.

For local multi-user SQLite, see `Docs/User_Guides/Multi-User_SQLite_Setup.md`.

For a full provider list, see `tldw_Server_API/Config_Files/.env.template`. You can also keep large provider configs in `tldw_Server_API/Config_Files/config.txt`.

> Important: Replace placeholder values with strong random keys before continuing.
> - Generate a key: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
> - MCP Unified requires `MCP_JWT_SECRET` and `MCP_API_KEY_SALT`. The initializer will generate and write them to `.env` if they are missing.
> - If you set `tldw_production=true`, weak or default keys will block startup.

### 3.3 Initialize AuthNZ and databases
```bash
python -m tldw_Server_API.app.core.AuthNZ.initialize
```
This validates the environment and seeds the AuthNZ DB.
The command is **interactive**: run it in a terminal and answer the prompts (you can safely answer `N` to optional steps like starting background services). If it reports configuration issues (e.g., placeholder API keys), edit `.env` and run it again.

### 3.4 Run the API
```bash
python -m uvicorn tldw_Server_API.app.main:app --reload
```
- Docs/UI: http://127.0.0.1:8000/docs
- Quickstart: http://127.0.0.1:8000/api/v1/config/quickstart
- Setup UI (if required): http://127.0.0.1:8000/setup

### 3.5 Smoke-test the API
Use your API key (`SINGLE_USER_API_KEY`) in the header. Replace the provider/model with one you have configured, then choose one of the two request styles:

- Option A (explicit provider):
  ```bash
  curl -X POST "http://127.0.0.1:8000/api/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -H "X-API-KEY: CHANGE_ME_TO_SECURE_API_KEY" \
    -d '{
          "api_provider": "openai",
          "model": "gpt-4o",
          "messages": [{"role": "user", "content": "Say hello from tldw_server"}]
        }'
  ```

- Option B (provider-prefixed model):
  ```bash
  curl -X POST "http://127.0.0.1:8000/api/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -H "X-API-KEY: CHANGE_ME_TO_SECURE_API_KEY" \
    -d '{
          "model": "openai/gpt-4o",
          "messages": [{"role": "user", "content": "Say hello from tldw_server"}]
        }'
  ```

If you configured a default provider, you can omit `api_provider` and the prefix and just send the model name you configured (for example, `"model": "gpt-4o"`).
List active providers/models via `GET /api/v1/llm/providers`.

---

## 4. Runtime & Provider Configuration

Once the server boots, you’ll likely tailor behaviour, credentials, and model lists. Two files drive most settings:

### 4.1 `.env`: secrets, auth, and DB targets
- Location: `tldw_server2/.env` (same folder as `pyproject.toml`). Start from `tldw_Server_API/Config_Files/.env.authnz.template` or the full `tldw_Server_API/Config_Files/.env.template`.
- Best place for **secrets**: API keys, DB passwords, Postgres URLs, JWT secrets.
- Common fields:
  - `AUTH_MODE` = `single_user` (API key header) or `multi_user` (JWT/auth endpoints).
  - `SINGLE_USER_API_KEY` (single-user) or `JWT_SECRET_KEY` (multi-user).
  - `MCP_JWT_SECRET`, `MCP_API_KEY_SALT` (MCP Unified).
  - `DATABASE_URL` (AuthNZ DB), `JOBS_DB_URL`, `TEST_DATABASE_URL`.
  - Provider keys: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, etc.
  - `tldw_production`, `SHOW_API_KEY_ON_STARTUP`, `LOG_LEVEL`, `STREAMS_UNIFIED`, and other toggles documented in `Env_Vars.md`.
- After editing `.env`, restart the FastAPI server (env variables are read at startup).

### 4.2 `config.txt`: user-facing defaults and feature flags
- Location: `tldw_Server_API/Config_Files/config.txt`.
- Back this file up or keep a copy in `.git/info/exclude` if you don’t want Git noise.
- Controls everything from file-size limits to chat rate limits. Key sections:
  - `[Server]`: `disable_cors`, `trusted_proxies`, and other server-level settings.
  - `[Media-Processing]`: per-file-size caps/timeouts for video/audio/PDF ingestion.
  - `[Chat-Module]`: streaming defaults, history depth, rate limits.
  - `[Database]`: choose SQLite vs Postgres for content (`pg_*` fields).
  - `[Chunking]`, `[RAG]`, `[Embeddings]`: tune context windows and vector backends.
- Use any editor, then restart the API (or run `python -m tldw_Server_API.app.core.AuthNZ.initialize` once to validate the config).

### 4.3 Adding cloud LLM providers & keys
1. Drop the API key into `.env`, e.g. `ANTHROPIC_API_KEY=sk-ant-...`.
2. In `config.txt`, open the `[API]` section and set the defaults for that provider (use a model id the provider supports):
   ```ini
   [API]
   anthropic_model = claude-opus-4-20250514
   anthropic_temperature = 0.6
   default_api = anthropic        # optional: make it the default `/chat/completions` target
   ```
3. If the provider exposes a custom base URL, set it here as well (e.g. `qwen_api_base_url`).
4. Call `GET /api/v1/llm/providers` to confirm the provider is now listed.

### 4.4 Pointing to self-hosted/local LLMs
Edit the `[Local-API]` section of `config.txt`. Each entry maps to a backend host:

```ini
[Local-API]
ollama_api_IP = http://192.168.1.50:11434/v1
ollama_model = llama3:instruct
vllm_api_IP = http://localhost:8001/v1/chat/completions
vllm_model = my-hf-model-id
tabby_api_IP = http://127.0.0.1:5000/v1/chat/completions
```

- Use full URLs (protocol + host + port + path).
- Update temperature/top_p/max_tokens per provider if the backend expects different defaults.
- After editing, restart the API so the provider manager reloads the endpoints.

### 4.5 Where to adjust user-facing behaviour
- **Rate limits**: `[Chat-Module] rate_limit_per_minute`, `[Character-Chat]` guards.
- **Storage paths**: `[Database] sqlite_path`, `backup_path`, and `chroma_db_path`.
- **Setup UI**: `[Setup] allow_remote_setup_access=true` if you must run first-time setup remotely (only on trusted networks).

### 4.6 Set the default LLM provider
You can set which provider the Chat API uses when a request does not specify one.

- Preferred: set it in `tldw_Server_API/Config_Files/config.txt` under `[API]`:
  ```ini
  [API]
  # All your provider settings...
  default_api = openai        # e.g., openai | anthropic | groq | mistral | ollama | vllm
  # Optional: also set the provider's default model
  openai_model = gpt-4o
  ```

- Alternative: set an environment variable (overrides when `config.txt` lacks a default):
  ```bash
  export DEFAULT_LLM_PROVIDER=openai
  # then restart the server
  ```

- RAG-only defaults (optional): the RAG service has its own default in `[RAG]`:
  ```ini
  [RAG]
  default_llm_provider = openai
  ```

- Verify the default is active:
  - `GET /api/v1/llm/providers` returns `default_provider` from your config.
  - Send a chat request without `api_provider` and with an unprefixed model; it should use the default:
    ```bash
    curl -X POST "http://127.0.0.1:8000/api/v1/chat/completions" \
      -H "Content-Type: application/json" \
      -H "X-API-KEY: CHANGE_ME_TO_SECURE_API_KEY" \
      -d '{
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Which provider did I hit?"}]
          }'
    ```

- Request-level overrides (ignore the default):
  - Provide `api_provider` explicitly, e.g. `"api_provider": "anthropic"`.
  - Or prefix the model with the provider using `provider/model`, e.g. `"model": "anthropic/claude-opus-4-20250514"`.

---

## 5. Docker Compose Path (All Services)

If you prefer containers (or are on Windows without build tools):
```bash
# Choose one path:
# Base stack (single-user, app + postgres + redis)
export SINGLE_USER_API_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
docker compose -f Dockerfiles/docker-compose.yml up -d --build

# Multi-user/Postgres mode (same base compose)
export AUTH_MODE=multi_user
export DATABASE_URL=postgresql://tldw_user:TestPassword123!@postgres:5432/tldw_users
docker compose -f Dockerfiles/docker-compose.yml up -d --build

# Production hardening overlay (optional)
docker compose -f Dockerfiles/docker-compose.yml \
             -f Dockerfiles/docker-compose.override.yml up -d --build
```
After the containers are up, initialize AuthNZ inside the app container:
```bash
docker compose -f Dockerfiles/docker-compose.yml exec app \
  python -m tldw_Server_API.app.core.AuthNZ.initialize
```
- Note: This command is **interactive**; run it in a shell attached to the container and answer the prompts (you can safely answer `N` to optional steps).
- Check logs: `docker compose -f Dockerfiles/docker-compose.yml logs -f app`
- Optional overlays: `Dockerfiles/docker-compose.dev.yml` (unified streaming), `Dockerfiles/docker-compose.pg.yml` (pgvector/pgbouncer), proxy variants.

---

## 6. Connect the Next.js Web UI (Optional but Friendly)
The `apps/tldw-frontend/` directory hosts the Next.js WebUI.
```bash
cd apps/tldw-frontend
cp .env.local.example .env.local
# Edit .env.local:
# - NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
# - NEXT_PUBLIC_API_VERSION=v1
# - Single-user: set NEXT_PUBLIC_X_API_KEY=<your SINGLE_USER_API_KEY>
npm install
npm run dev -- -p 8080
```
Open http://localhost:8080 to use the UI. In multi-user mode, leave `NEXT_PUBLIC_X_API_KEY` unset and register/login in the UI. If you expose the UI remotely, prefer multi-user mode instead of embedding an API key. If you lock down CORS, add `http://localhost:8080` to `ALLOWED_ORIGINS`.

---

## 7. Process Your First Media File
Once the API is running:
1. Pick a local media file you own (for example, an MP3 or MP4) and note its full path, e.g. `/path/to/your_audio_file.mp3`.
2. Use the persistent media ingestion endpoint:
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/media/add" \
  -H "X-API-KEY: CHANGE_ME_TO_SECURE_API_KEY" \
  -F "media_type=audio" \
  -F "title=Sample Audio" \
  -F "keywords=demo,quickstart" \
  -F "perform_analysis=true" \
  -F "files=@/path/to/your_audio_file.mp3"
```
3. After ingestion, confirm it’s stored by querying the media index, for example via the `/api/v1/media/search` endpoint from the OpenAPI docs (searching by title or keyword).

---

## 8. Common Next Steps
- **Explore docs**: OpenAPI docs at `/docs`, plus deep dives in `Docs/` (RAG, AuthNZ, MCP, etc.).
- **Read user guides**: `Docs/User_Guides/Installation-Setup-Guide.md` and `Docs/User_Guides/User_Guide.md`.
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
| Server refuses to start in production | `tldw_production=true` with weak/default secrets | Set strong keys in `.env` or disable `tldw_production` for local dev |
| CORS errors in the browser | `ALLOWED_ORIGINS` does not include the WebUI URL | Add `http://localhost:8080` (or your UI origin) to `ALLOWED_ORIGINS` |
| Media stuck in `processing` | Background workers blocked or DB locked | Check logs under `Databases/`, ensure only one writer, consider Postgres |
| SQLite `database is locked` | In-process workers + multiple Uvicorn workers | Use sidecar workers or Postgres; avoid multiple Uvicorn workers with in-process jobs |
| Docker health fails | Compose overlay mismatch | Start with base compose file, then add overlays gradually |

> Enable debug logging by setting `LOG_LEVEL=DEBUG` before launching the server if you need granular traces (Loguru handles formatting).

---

## 10. Where to Learn More
- `README.md`: feature matrix, architecture diagrams, release notes.
- `Docs/`: AuthNZ, RAG, TTS/STT, MCP, deployment profiles.
- `Project_Guidelines.md`: development philosophy if you plan to contribute.
- GitHub Issues/Discussions: report bugs, request features, or ask setup questions.

Happy building! Once you ingest your first file and run a chat completion, you have the full pipeline working—everything else (prompt studio, evaluations, MCP, browser extension) builds on the same foundation.
