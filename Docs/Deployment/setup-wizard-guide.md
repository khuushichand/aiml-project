# Setup Wizard Guide

## Overview

The tldw_server setup wizard runs automatically on first launch when no admin account exists. It walks you through creating the initial admin user and confirming essential settings.

**URL:** `http://localhost:8000/setup`

The server redirects to this page if setup has not been completed. Once an admin account is created, the wizard is disabled and the endpoint returns 404.

## Prerequisites

Before starting the server for the first time, ensure:

1. **Python environment** is set up: `pip install -e .`
2. **FFmpeg** is installed (required for audio/video processing)
3. **Environment file** exists: copy the example and edit it:
   ```bash
   cp tldw_Server_API/Config_Files/.env.example tldw_Server_API/Config_Files/.env
   ```

### Required Environment Variables

Set these in `.env` before first run:

| Variable | Purpose | Example |
|----------|---------|---------|
| `AUTH_MODE` | Authentication mode | `single_user` or `multi_user` |
| `SINGLE_USER_API_KEY` | API key (single-user mode only) | Any strong random string |
| `SECRET_KEY` | JWT signing key (multi-user mode) | `openssl rand -hex 32` |
| `DATABASE_URL` | AuthNZ database location | `sqlite:///./Databases/users.db` |

### Optional Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `CORS_ORIGINS` | Allowed CORS origins | `*` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |

## What the Wizard Does

1. **Checks for existing admin** -- if one exists, the wizard is skipped
2. **Presents a form** to create the first admin account (username, email, password)
3. **Initializes the AuthNZ database** schema if not already present
4. **Creates the admin user** with full privileges
5. **Redirects to the API docs** (`/docs`) on success

## Running the Wizard

```bash
# Start the server
python -m uvicorn tldw_Server_API.app.main:app --host 0.0.0.0 --port 8000

# Open in browser
open http://localhost:8000/setup
```

In Docker, the wizard is available at the same path on whatever port you mapped.

## Post-Setup Configuration

After the admin account is created, configure the remaining settings.

### LLM Providers

Edit `tldw_Server_API/Config_Files/config.txt` or set environment variables:

**OpenAI:**
```
[API_Keys]
openai_api_key = sk-...
```
Or: `export OPENAI_API_KEY=sk-...`

**Anthropic:**
```
[API_Keys]
anthropic_api_key = sk-ant-...
```
Or: `export ANTHROPIC_API_KEY=sk-ant-...`

**Local LLMs (Ollama, llama.cpp, etc.):**
```
[Local-API]
local_llm_api_ip = http://localhost:11434
```

No API key is needed for most local providers. Set the base URL to wherever the model server listens.

### Embedding Providers

Configure in `config.txt` under `[Embeddings]`:
```
embedding_provider = openai
embedding_model = text-embedding-3-small
```

Or use a local provider:
```
embedding_provider = local
embedding_model = all-MiniLM-L6-v2
```

### Storage

Default database paths work out of the box. To use PostgreSQL for AuthNZ:
```
DATABASE_URL=postgresql://user:pass@localhost:5432/tldw_auth
```

See `Docs/Deployment/Postgres_Migration_Guide.md` for full migration steps.

### SMTP (Optional)

For password reset emails in multi-user mode, configure SMTP in `.env`:
```
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=noreply@example.com
SMTP_PASSWORD=...
SMTP_FROM=noreply@example.com
```

## Quick Verification

After setup, confirm the server is working:

```bash
# Health check
curl http://localhost:8000/api/v1/health

# List providers (single-user mode)
curl -H "X-API-Key: YOUR_KEY" http://localhost:8000/api/v1/llm/providers

# Interactive API docs
open http://localhost:8000/docs
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Setup page not appearing | Check if admin already exists; check `AUTH_MODE` is set |
| "Database locked" on setup | Stop other processes accessing the DB; ensure write permissions on `Databases/` |
| Can't reach `/setup` in Docker | Verify port mapping in `docker-compose.yml` |
| Setup completes but can't log in | In single-user mode, use `X-API-Key` header; in multi-user mode, use `/api/v1/auth/login` |
