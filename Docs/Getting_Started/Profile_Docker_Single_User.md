# Docker Single-User Setup

Use this profile when you want a containerized single-user deployment with minimal host setup.

## Prerequisites

- Docker Engine
- Docker Compose
- Git

## Install

```bash
git clone https://github.com/rmusser01/tldw_server.git
cd tldw_server
cp tldw_Server_API/Config_Files/.env.example tldw_Server_API/Config_Files/.env
```

Set a single-user API key in `tldw_Server_API/Config_Files/.env`:

```bash
AUTH_MODE=single_user
SINGLE_USER_API_KEY=replace-with-strong-key
```

## Run

```bash
docker compose --env-file tldw_Server_API/Config_Files/.env -f Dockerfiles/docker-compose.yml up -d --build
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
docker compose --env-file tldw_Server_API/Config_Files/.env -f Dockerfiles/docker-compose.host-storage.yml up -d --build
```

That optional variant writes data under `docker-data/` at the repo root and preserves the default quickstart behavior for existing users.

## Verify

```bash
curl -sS http://127.0.0.1:8000/health
curl -sS http://127.0.0.1:8000/docs > /dev/null && echo "docs-ok"
curl -sS http://127.0.0.1:8000/api/v1/config/quickstart
```

If you later need LAN/custom-host browser access as advanced configuration, switch to the root README WebUI guidance and use the advanced override pair: `NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE=advanced` plus `NEXT_PUBLIC_API_URL=...`.

## Optional Add-ons

- If speech is part of day-one setup, continue with [First-Time Audio Setup: CPU Systems](./First_Time_Audio_Setup_CPU.md) or [First-Time Audio Setup: GPU/Accelerated Systems](./First_Time_Audio_Setup_GPU_Accelerated.md) after this profile is running.

## Troubleshoot

- If containers do not start, check: `docker compose -f Dockerfiles/docker-compose.yml logs --tail=200`.
- If API is unavailable, verify no port conflict on `8000`.
- If auth errors appear, confirm `AUTH_MODE` and `SINGLE_USER_API_KEY` in `.env`.
