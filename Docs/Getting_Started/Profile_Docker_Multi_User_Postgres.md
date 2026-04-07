# Docker Multi-User + Postgres Setup

Use this profile for team-style deployment with JWT auth mode and PostgreSQL backing services.

## Prerequisites

- Docker Engine
- Docker Compose
- Git

> **Windows users:** Use WSL2 or Git Bash. The `make` targets require a Unix-like shell.

## Install

```bash
git clone https://github.com/rmusser01/tldw_server.git
cd tldw_server
cp tldw_Server_API/Config_Files/.env.example tldw_Server_API/Config_Files/.env
```

Configure multi-user mode in `.env`:

```bash
AUTH_MODE=multi_user
```

Generate and set the required secrets (run each command, paste the output into `.env`):

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
# Paste output as: JWT_SECRET_KEY=<output>

python -c "import secrets; print(secrets.token_urlsafe(32))"
# Paste output as: MCP_JWT_SECRET=<output>

python -c "import secrets; print(secrets.token_urlsafe(32))"
# Paste output as: MCP_API_KEY_SALT=<output>
```

> **Note:** `JWT_SECRET_KEY` is for the main auth system. `MCP_JWT_SECRET` and `MCP_API_KEY_SALT` are for the MCP subsystem. All three must be unique values.

Set the Postgres connection URL (see Postgres Options below):

```bash
DATABASE_URL=postgresql://tldw_user:your_password@postgres:5432/tldw_users
```

### Postgres Options

**Option A: Use the bundled Postgres from docker-compose** (recommended for getting started):
The default `docker-compose.yml` includes a Postgres service. Set `DATABASE_URL` to point to it:
```bash
DATABASE_URL=postgresql://tldw_user:TestPassword123!@postgres:5432/tldw_users
```

**Option B: Use an external Postgres instance:**
Point `DATABASE_URL` to your existing database:
```bash
DATABASE_URL=postgresql://your_user:your_pass@your-host:5432/your_db
```
Ensure the database exists and the user has CREATE TABLE permissions.

For full variable details and hardening, see:
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
- If port 8000 is already in use, stop the conflicting process or change the host port mapping in docker-compose.

## What to Do Next

1. **Browse the API docs** at http://127.0.0.1:8000/docs
2. **Create the first admin user** — follow the multi-user setup guide at `Docs/User_Guides/Server/Multi-User_Postgres_Setup.md`
3. **Configure LLM providers** — add provider API keys to `.env` and restart containers
4. **Add the WebUI** — add the WebUI compose overlay:
   ```bash
   docker compose --env-file tldw_Server_API/Config_Files/.env \
     -f Dockerfiles/docker-compose.yml \
     -f Dockerfiles/docker-compose.webui.yml up -d --build
   ```
