# Getting Started with tldw

One page to get you from zero to a running tldw server. Pick your path and follow the steps.

## Choose your setup path

```
Are you using Docker?
|
+-- Yes --> Are you setting up for one person or a team?
|   |
|   +-- One person ----> Section A: Docker Single-User (recommended)
|   |
|   +-- Team / org ----> Section B: Docker Multi-User
|
+-- No ---------------> Section C: Local Installation
```

> After your server is running, skip to [Adding LLM Providers](#adding-llm-providers) and [Verify Your Setup](#verify-your-setup).

---

## Section A: Docker Single-User (Recommended)

**Time: ~2 minutes**

### Prerequisites

- Docker Engine + Docker Compose (Docker Desktop includes both)
- Git

> **Windows:** Use WSL2 or Git Bash. The `make` targets require a Unix-like shell.

### Steps

```bash
# 1. Clone the repo
git clone https://github.com/rmusser01/tldw_server.git
cd tldw_server

# 2. Copy the environment template
cp tldw_Server_API/Config_Files/.env.example tldw_Server_API/Config_Files/.env

# 3. Start everything (API + WebUI)
make quickstart
```

That single command builds and starts the API server and the Next.js WebUI. The Docker entrypoint auto-generates a secure API key if the placeholder value is still in `.env`.

### What you get

| Service | URL |
| --- | --- |
| API server | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |
| WebUI | http://localhost:8080 |

### Retrieve your API key

The API key is needed for direct API access (curl, scripts, browser extension). The WebUI uses a same-origin proxy and does not require it.

```bash
make show-api-key
```

### Data storage

By default, application data lives in Docker named volumes (`app-data`, `chroma-data`, `postgres_data`, `redis_data`). `docker compose down` preserves them; `docker compose down -v` deletes them.

For host-visible storage instead, see the `docker-compose.host-storage.yml` variant in the Docker Single-User guide.

---

## Section B: Docker Multi-User

**Time: ~10 minutes**

### Prerequisites

- Docker Engine + Docker Compose
- Git

### Steps

```bash
# 1. Clone the repo
git clone https://github.com/rmusser01/tldw_server.git
cd tldw_server

# 2. Copy the environment template
cp tldw_Server_API/Config_Files/.env.example tldw_Server_API/Config_Files/.env
```

**3. Edit `tldw_Server_API/Config_Files/.env` and set these values:**

```bash
AUTH_MODE=multi_user

# Database (the bundled Postgres container works out of the box)
DATABASE_URL=postgresql://tldw_user:TestPassword123!@postgres:5432/tldw_users
```

**4. Generate and set the required secrets.** Run each command, then paste the output into `.env`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
# Paste as:  JWT_SECRET_KEY=<output>

python -c "import secrets; print(secrets.token_urlsafe(32))"
# Paste as:  MCP_JWT_SECRET=<output>

python -c "import secrets; print(secrets.token_urlsafe(32))"
# Paste as:  MCP_API_KEY_SALT=<output>
```

All three must be unique values.

**5. Start the server:**

```bash
docker compose --env-file tldw_Server_API/Config_Files/.env \
  -f Dockerfiles/docker-compose.yml up -d --build
```

**6. (Optional) Add the WebUI overlay:**

```bash
docker compose --env-file tldw_Server_API/Config_Files/.env \
  -f Dockerfiles/docker-compose.yml \
  -f Dockerfiles/docker-compose.webui.yml up -d --build
```

### What you get

| Service | URL |
| --- | --- |
| API server | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| WebUI (if overlay added) | http://localhost:8080 |

### Next: create the first admin user

Set `ADMIN_USERNAME` and `ADMIN_PASSWORD` in your `.env` before running quickstart to create the admin user automatically, or run the CLI after startup:

```bash
docker compose exec app python -m tldw_Server_API.app.core.AuthNZ.create_admin \
  --username admin --password <your-password>
```

For full details see `Docs/User_Guides/Server/Multi-User_Postgres_Setup.md`.

### External Postgres

To use your own Postgres instead of the bundled container, point `DATABASE_URL` to your instance:

```bash
DATABASE_URL=postgresql://your_user:your_pass@your-host:5432/your_db
```

The user must have `CREATE TABLE` permissions.

---

## Section C: Local Installation (No Docker)

**Time: ~15 minutes**

### Prerequisites

- Python 3.10+
- FFmpeg (`ffmpeg -version` to check)
- Git

> **Windows:** Use WSL2 or Git Bash.

### Steps

```bash
# 1. Clone the repo
git clone https://github.com/rmusser01/tldw_server.git
cd tldw_server

# 2. Install into a virtual environment
make quickstart-install

# 3. Start the server
make quickstart-local
```

The install target creates a `.venv`, installs dependencies, and copies `.env.example` to `.env` if missing. The server starts at http://127.0.0.1:8000.

If your default `python3` is older than 3.10:

```bash
make quickstart-install PYTHON=python3.12
```

### What you get

| Service | URL |
| --- | --- |
| API server | http://127.0.0.1:8000 |
| API docs | http://127.0.0.1:8000/docs |

The local profile does not include the WebUI by default. To add it, see the [Local Profile: Add the WebUI](../../README.md#local-profile-add-the-webui) section in the main README.

### Manual alternative (no Make)

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -e .
cp tldw_Server_API/Config_Files/.env.example tldw_Server_API/Config_Files/.env
python -m uvicorn tldw_Server_API.app.main:app --reload
```

---

## Adding LLM Providers

Works for all setup paths. You need at least one provider key to use Chat features.

**1. Edit `tldw_Server_API/Config_Files/.env` and add one or more keys:**

```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AI...
GROQ_API_KEY=gsk_...
COHERE_API_KEY=...
```

**2. Restart:**

```bash
# Docker
docker compose -f Dockerfiles/docker-compose.yml -f Dockerfiles/docker-compose.webui.yml up -d

# Local
# Stop the server (Ctrl+C) and re-run:
make quickstart-local
```

**3. Verify the provider is available:**

```bash
API_KEY=$(make show-api-key)
curl -H "X-API-Key: $API_KEY" http://localhost:8000/api/v1/config/providers
```

---

## Verify Your Setup

Run these checks after any setup path:

```bash
# 1. Server health
curl -sS http://localhost:8000/health

# 2. API docs load
curl -sS http://localhost:8000/docs > /dev/null && echo "docs-ok"

# 3. Quickstart info
curl -sS http://localhost:8000/api/v1/config/quickstart

# 4. (Docker + WebUI) WebUI loads
curl -sS http://localhost:8080 > /dev/null && echo "webui-ok"
```

### Try your first API call

```bash
API_KEY=$(make show-api-key)

curl http://localhost:8000/api/v1/chat/completions \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "Hello!"}]}'
```

---

## Guided Setup Wizard (Optional)

For a visual configuration experience, edit `tldw_Server_API/Config_Files/config.txt`:

```ini
[Setup]
enable_first_time_setup = true
setup_completed = false
```

Restart the server, then visit http://localhost:8000/setup. The wizard walks you through provider configuration, audio setup, and more.

---

## Troubleshooting

### Docker containers do not start

```bash
docker compose -f Dockerfiles/docker-compose.yml logs --tail=200
```

### Port 8000 or 8080 already in use

Stop the conflicting process, or change the host port mapping in the compose file (e.g., `"9000:8000"`).

### Auth errors (401/403)

- Confirm `AUTH_MODE` and `SINGLE_USER_API_KEY` are set in `tldw_Server_API/Config_Files/.env`
- For Docker, the entrypoint auto-generates a key if the placeholder is unchanged. Retrieve it with `make show-api-key`.

### Local install fails on audio dependencies

- Verify FFmpeg: `ffmpeg -version`
- Verify Python version: `python3 --version` (must be 3.10+)

### Multi-user: cannot connect to Postgres

- Confirm `DATABASE_URL` is correct and the Postgres container (or external instance) is reachable
- Check: `docker compose -f Dockerfiles/docker-compose.yml logs postgres --tail=50`

### Docker ignores host config changes

The stock Docker image bakes in `Config_Files` at build time. After editing files on the host, rebuild:

```bash
docker compose --env-file tldw_Server_API/Config_Files/.env \
  -f Dockerfiles/docker-compose.yml up -d --build
```

---

## What's Next?

- **Chat**: Open the WebUI and send a message, or use the `/api/v1/chat/completions` endpoint
- **Ingest media**: Upload a PDF, paste a YouTube URL, or use the `/api/v1/media/process` endpoint
- **Speech**: Set up audio with the [CPU](./First_Time_Audio_Setup_CPU.md) or [GPU/Accelerated](./First_Time_Audio_Setup_GPU_Accelerated.md) audio guide
- **Setup wizard**: Try the guided wizard at http://localhost:8000/setup
- **API reference**: Browse the full API at http://localhost:8000/docs

---

## Detailed Guides

This quickstart covers the essentials. For deeper configuration, see:

| Topic | Guide |
| --- | --- |
| Docker single-user (full details) | [Profile_Docker_Single_User.md](./Profile_Docker_Single_User.md) |
| Docker multi-user + Postgres | [Profile_Docker_Multi_User_Postgres.md](./Profile_Docker_Multi_User_Postgres.md) |
| Local single-user (full details) | [Profile_Local_Single_User.md](./Profile_Local_Single_User.md) |
| Audio setup (CPU) | [First_Time_Audio_Setup_CPU.md](./First_Time_Audio_Setup_CPU.md) |
| Audio setup (GPU/Accelerated) | [First_Time_Audio_Setup_GPU_Accelerated.md](./First_Time_Audio_Setup_GPU_Accelerated.md) |
| Multi-user admin setup | [Multi-User_Postgres_Setup.md](../User_Guides/Server/Multi-User_Postgres_Setup.md) |
