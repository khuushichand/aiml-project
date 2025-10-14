# Environment Variables – tldw_server (v0.1)

This reference lists environment variables recognized by the server. Environment variables take precedence over values from `Config_Files/.env`, which in turn take precedence over `Config_Files/config.txt` (where supported).

Precedence (highest → lowest):
- Process environment variables
- `.env` (Pydantic / dotenv)
- `config.txt` (sections parsed by the app; not all settings support file overrides)

Note: Secrets should be set via environment or `.env`. `config.txt` is supported for convenience in dev; prefer env in production.

For the full, frequently updated raw reference, see `Env_Vars.md` in the repository root.

## Core Server
- `tldw_production`: Enable production guards (`true|false`). Masks API key in logs, hardens WebUI config, enforces DB/secret checks.
- `ENABLE_OPENAPI`: Show OpenAPI/Swagger UI when `true`. Defaults to hidden in production unless explicitly enabled.
- `ALLOWED_ORIGINS`: CORS allowlist. Comma‑separated or JSON array.
- `ENABLE_SECURITY_HEADERS`: Enable security headers middleware (defaults to true in production).
- `UVICORN_WORKERS`: Uvicorn worker count (default 4 in Docker).
- `LOG_LEVEL`: Application log level (`DEBUG|INFO|WARNING|ERROR`).
- `MAGIC_FILE_PATH`: Path to `magic.mgc` for `python-magic` if needed.

## AuthNZ (Authentication)
- `AUTH_MODE`: `single_user` | `multi_user`.
- `DATABASE_URL`: AuthNZ database URL. For production multi-user, use Postgres.
- `SINGLE_USER_API_KEY`: API key for single-user mode (>=24 chars recommended).
- `JWT_SECRET_KEY`: JWT signing secret (>=32 chars). Required for `multi_user` in production.
- `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`.
- `REDIS_URL`: Optional Redis URL for sessions.
- `ENABLE_REGISTRATION`, `REQUIRE_REGISTRATION_CODE`.
- `SHOW_API_KEY_ON_STARTUP`: Avoid in production.

## Jobs Backend / Worker
- `JOBS_DB_URL`: Postgres DSN for Jobs backend; falls back to SQLite when unset.
- `JOBS_*`: Lease/renew/metrics settings (see repo `Env_Vars.md`).

## Chunking / RAG / Embeddings / MCP / TTS
Module-specific toggles exist; see the repo `Env_Vars.md` or the respective module docs for details.

