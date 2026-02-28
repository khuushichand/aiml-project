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

## Verify

```bash
curl -sS http://127.0.0.1:8000/health
curl -sS http://127.0.0.1:8000/docs > /dev/null && echo "docs-ok"
curl -sS http://127.0.0.1:8000/api/v1/config/quickstart
```

## Troubleshoot

- If containers do not start, check: `docker compose -f Dockerfiles/docker-compose.yml logs --tail=200`.
- If API is unavailable, verify no port conflict on `8000`.
- If auth errors appear, confirm `AUTH_MODE` and `SINGLE_USER_API_KEY` in `.env`.
