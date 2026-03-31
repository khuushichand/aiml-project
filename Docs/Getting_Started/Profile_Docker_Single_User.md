# Docker Single-User Setup

Use this profile when you want a containerized single-user deployment with minimal host setup.

## Prerequisites

- Docker Engine
- Docker Compose
- Git

> **Windows users:** Use WSL2, Git Bash, or see the [No-Make Path](../../README.md#no-make-path-windows-friendly) in the main README.

## Install

```bash
git clone https://github.com/rmusser01/tldw_server.git
cd tldw_server
cp tldw_Server_API/Config_Files/.env.example tldw_Server_API/Config_Files/.env
```

Optionally edit `tldw_Server_API/Config_Files/.env` to set your own API key:

```bash
AUTH_MODE=single_user
SINGLE_USER_API_KEY=replace-with-strong-key
```

> **Note:** If you use `make quickstart`, the Docker entrypoint automatically detects placeholder keys (like `CHANGE_ME` or `replace-with-strong-key`) and generates a secure random key for you. You can retrieve it later with `make show-api-key`.

## Run

```bash
make quickstart

# Manual equivalent if you are not using make:
# docker compose --env-file tldw_Server_API/Config_Files/.env \
#   -f Dockerfiles/docker-compose.yml \
#   -f Dockerfiles/docker-compose.webui.yml up -d --build
```

The default Docker + WebUI quickstart keeps same-origin browser API requests through the WebUI proxy. Treat LAN/custom-host browser access as advanced configuration and leave that off unless you specifically need another device, hostname, or proxy in front of the browser.

By default this profile stores application data in Docker named volumes, not in the repo checkout:

- `app-data` backs `/app/Databases`
- `chroma-data` backs `/app/Databases/user_databases`
- `postgres_data` and `redis_data` back the bundled Postgres and Redis containers

Keep `tldw_Server_API/Config_Files/.env` with your backups, because it stores the startup auth mode and single-user API key that the quickstart uses.

`docker compose down` keeps the Docker named volumes. `docker compose down -v` deletes them and removes the persisted databases, user files, and vector storage.

If you prefer host-visible storage for manual backups or inspection, use `Dockerfiles/docker-compose.host-storage.yml` instead of the default compose file:

```bash
docker compose --env-file tldw_Server_API/Config_Files/.env \
  -f Dockerfiles/docker-compose.host-storage.yml \
  -f Dockerfiles/docker-compose.webui.yml up -d --build
```

That optional variant writes data under `docker-data/` at the repo root and preserves the default quickstart behavior for existing users.

## Verify

```bash
curl -sS http://127.0.0.1:8000/health
curl -sS http://127.0.0.1:8000/docs > /dev/null && echo "docs-ok"
curl -sS http://127.0.0.1:8000/api/v1/config/quickstart
curl -sS http://127.0.0.1:8080 > /dev/null && echo "webui-ok"
```

If you later need LAN/custom-host browser access as advanced configuration, switch to the root README WebUI guidance and use the advanced override pair: `NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE=advanced` plus `NEXT_PUBLIC_API_URL=...`.

## Optional Add-ons

- If speech is part of day-one setup, continue with [First-Time Audio Setup: CPU Systems](./First_Time_Audio_Setup_CPU.md) or [First-Time Audio Setup: GPU/Accelerated Systems](./First_Time_Audio_Setup_GPU_Accelerated.md) after this profile is running.

## Troubleshoot

- If containers do not start, check: `docker compose -f Dockerfiles/docker-compose.yml logs --tail=200`.
- If API is unavailable, verify no port conflict on `8000`.
- If auth errors appear, confirm `AUTH_MODE` and `SINGLE_USER_API_KEY` in `.env`.

## What to Do Next

1. **Open the WebUI** at http://localhost:8080 — the onboarding wizard will guide you through connecting to the server.
2. **Retrieve your API key** (for curl, extension, or non-WebUI access):
   ```bash
   make show-api-key
   # Or read it directly:
   grep SINGLE_USER_API_KEY tldw_Server_API/Config_Files/.env | cut -d= -f2-
   ```
3. **Configure an LLM provider** — add a provider API key to `tldw_Server_API/Config_Files/.env` and restart:
   ```bash
   echo 'OPENAI_API_KEY=sk-your-key-here' >> tldw_Server_API/Config_Files/.env
   docker compose -f Dockerfiles/docker-compose.yml -f Dockerfiles/docker-compose.webui.yml restart
   ```
4. **Try your first API call:**
   ```bash
   API_KEY=$(make show-api-key)
   curl http://localhost:8000/api/v1/chat/completions \
     -H "X-API-Key: $API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "Hello!"}]}'
   ```
5. **Set up speech** (optional) — follow the [CPU](./First_Time_Audio_Setup_CPU.md) or [GPU](./First_Time_Audio_Setup_GPU_Accelerated.md) audio guide.

### How the Default Setup Works

The Docker quickstart uses a **same-origin proxy**: the Next.js WebUI rewrites browser API requests through its own server to the backend at `http://app:8000`. This means:
- The WebUI works without entering an API key in the browser.
- Your browser talks to port 8080 (WebUI), not port 8000 (API) directly.
- You only need the API key for direct API access (curl, scripts, browser extension, or advanced mode).

To access the API from other devices on your LAN, see the advanced configuration in the main README.

### Guided Setup Wizard (Optional)

For a visual configuration wizard, edit `tldw_Server_API/Config_Files/config.txt` and set:
```ini
[Setup]
enable_first_time_setup = true
setup_completed = false
```
Then restart the containers and visit http://localhost:8000/setup (local access only by default).
