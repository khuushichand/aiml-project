# Docker Multi-User + Postgres Setup

Use this profile for team-style deployment with JWT auth mode and PostgreSQL backing services.

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

Configure multi-user mode and Postgres connection in `.env`:

```bash
AUTH_MODE=multi_user
DATABASE_URL=postgresql://<user>:<password>@<host>:5432/<db_name>
```

For full variable details and hardening, follow:
- `Docs/User_Guides/Server/Multi-User_Postgres_Setup.md`
- `Docs/Deployment/First_Time_Production_Setup.md`

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

## Optional Add-ons

- If speech is part of day-one setup, continue with [First-Time Audio Setup: CPU Systems](./First_Time_Audio_Setup_CPU.md) or [First-Time Audio Setup: GPU/Accelerated Systems](./First_Time_Audio_Setup_GPU_Accelerated.md) after this profile is running.

## Troubleshoot

- If startup fails, verify `DATABASE_URL` points to reachable Postgres.
- Confirm Postgres credentials and network access from containers.
- Check logs: `docker compose -f Dockerfiles/docker-compose.yml logs --tail=200`.
