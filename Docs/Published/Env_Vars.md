# Environment Variables - tldw_server (v0.1)

This reference lists environment variables recognized by the server. Environment variables take precedence over values from `Config_Files/.env`, which in turn take precedence over `Config_Files/config.txt` (where supported).

Precedence (highest → lowest):
- Process environment variables
- `.env` (Pydantic / dotenv)
- `config.txt` (sections parsed by the app; not all settings support file overrides)

Note: Secrets should be set via environment or `.env`. `config.txt` is supported for convenience in dev; prefer env in production.

For the full, frequently updated raw reference (auto-generated), see `Env_Vars.md` in the repository root.

## Core Server
- `tldw_production`: Enable production guards (`true|false`). Masks API key in logs, hardens WebUI config, enforces DB/secret checks.
- `ENABLE_OPENAPI`: Show OpenAPI/Swagger UI when `true`. Defaults to hidden in production unless explicitly enabled.
- `ALLOWED_ORIGINS`: CORS allowlist. Comma-separated or JSON array.
- `TLDW_CONFIG_PATH`: Absolute path to the primary `config.txt`. The parent directory becomes the config root for auxiliary assets (e.g., `Synonyms/`).
- `TLDW_CONFIG_DIR`: Explicit directory containing `config.txt` and related config assets. Checked after `TLDW_CONFIG_PATH`.
- `ENABLE_SECURITY_HEADERS`: Enable security headers middleware (defaults to true in production).
- `UVICORN_WORKERS`: Uvicorn worker count (default 4 in Docker).
- `LOG_LEVEL`: Application log level (`DEBUG|INFO|WARNING|ERROR`).
- `MAGIC_FILE_PATH`: Path to `magic.mgc` for `python-magic` if needed.

Startup Fast/Deferred Mode (CI/test-friendly)
- `DEFER_HEAVY_STARTUP`: When `true`, defers non-critical initialization to a background task after the app starts serving requests. This reduces time-to-health for smoke checks. Deferred work includes MCP Unified init, Chat Provider Manager, Chat Request Queue + Rate Limiter, TTS service, chunking templates, and the optional embeddings dimension check. Implied when `TEST_MODE=true` or `DISABLE_HEAVY_STARTUP=1`.
- `DISABLE_HEAVY_STARTUP`: Back-compat flag used in CI; treated the same as `DEFER_HEAVY_STARTUP` by the server.

Logging & OpenAPI URLs
- `LOG_JSON` / `ENABLE_JSON_LOGS`: Enable structured JSON logs (`true|false`).
- `LOG_STREAM`: Log sink (`stderr|stdout`).
- `LOG_COLOR`: Force color in logs even when not a TTY (`1|0`). Also respects `FORCE_COLOR` / `PY_COLORS`.
- `OPENAPI_SERVER_BASE_URL`: Base URL for the API server used in OpenAPI server URLs (defaults to `http://127.0.0.1:8000`).
- `OPENAPI_EXTERNAL_DOCS_BASE_URL`: Absolute base used for externalDocs links in the OpenAPI spec.

WebUI Access Guard (remote access controls)
- `TLDW_WEBUI_ALLOW_REMOTE` (or `WEBUI_ALLOW_REMOTE`): Temporarily allow remote access to the legacy WebUI (`/webui`). Only use on trusted networks.
- `TLDW_WEBUI_ALLOWLIST`: Comma-separated IPs/CIDRs allowed to access `/webui`.
- `TLDW_WEBUI_DENYLIST`: Comma-separated IPs/CIDRs denied from `/webui`.
- `TLDW_TRUSTED_PROXIES`: Comma-separated proxy IPs/CIDRs trusted for X-Forwarded-For/X-Real-IP.

## AuthNZ (Authentication)
- `AUTH_MODE`: `single_user` | `multi_user`.
- `DATABASE_URL`: AuthNZ database URL. For production multi-user, use Postgres.
- `SINGLE_USER_API_KEY`: API key for single-user mode (>=24 chars recommended).
- `JWT_SECRET_KEY`: JWT signing secret (>=32 chars). Required for `multi_user` in production.
- `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`.
- `REDIS_URL`: Optional Redis URL for sessions.
- `ENABLE_REGISTRATION`, `REQUIRE_REGISTRATION_CODE`.
- `SHOW_API_KEY_ON_STARTUP`: Avoid in production.

Egress & Outbound Policy (global + Workflows)
- `EGRESS_ALLOWLIST`, `EGRESS_DENYLIST`: Global DNS allow/deny lists for outbound requests.
- `WORKFLOWS_EGRESS_PROFILE`: `strict|permissive|custom` profile for Workflows egress.
- `WORKFLOWS_EGRESS_ALLOWLIST`, `WORKFLOWS_EGRESS_DENYLIST`: Workflows DNS allow/deny lists; support per-tenant suffix `_TENANT`.
- `WORKFLOWS_EGRESS_BLOCK_PRIVATE`: Block RFC1918 and reserved ranges (`true|false`).
- `WORKFLOWS_EGRESS_ALLOWED_PORTS`: Comma-separated list of allowed ports (default `80,443`).

## Jobs Backend / Worker
- `JOBS_DB_URL`: Postgres DSN for Jobs backend; falls back to SQLite when unset.
- `JOBS_*`: Lease/renew/metrics settings (see repo `Env_Vars.md`).
  - Common toggles include `JOBS_WEBHOOKS_*`, `JOBS_INTEGRITY_SWEEP_*`, `JOBS_METRICS_*`.

## Audio Quotas & Workers
- `AUDIO_JOBS_WORKER_ENABLED`: Start the in-process Audio Jobs worker on app startup (`true|false`).
- `AUDIO_JOBS_OWNER_STRICT`: Enable owner-aware acquisition heuristic for fair scheduling (`true|false`).
- `AUDIO_QUOTA_USE_REDIS`: Store active streams/jobs counters in Redis for multi-instance fairness. Defaults to true when `REDIS_URL` is set.
- `REDIS_URL`: Redis connection string (e.g., `redis://localhost:6379`).

Queues
- CPU stages use `queue=default`.
- GPU transcription uses dedicated `queue=transcribe` (see GPU worker container stub).

## Chunking / RAG / Embeddings / MCP / TTS
Module-specific toggles exist; see the repo `Env_Vars.md` or the respective module docs for details.

Monitoring & Telemetry
- `METRICS_ENABLED`: Enable text metrics endpoints.
- OpenTelemetry export is controlled via standard `OTEL_*` environment variables (e.g., `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME`, `OTEL_TRACES_EXPORTER`). See the Deployment/Monitoring docs.

## Workflows (Auth & Scheduler)
- `WORKFLOWS_DEFAULT_BEARER_TOKEN`: Default Authorization bearer token used by Workflows steps when not explicitly provided in headers.
- `WORKFLOWS_DEFAULT_API_KEY`: Default `X-API-KEY` used by Workflows steps when bearer is not provided.
- `WORKFLOWS_VALIDATE_DEFAULT_AUTH`: `true|false` - optionally validate the default token once per run against `/api/v1/workflows/auth/check`.
- `WORKFLOWS_INTERNAL_BASE_URL`: Base URL for validation requests; defaults to `http://127.0.0.1:8000`.
- `WORKFLOWS_MINT_VIRTUAL_KEYS`: `true|false` - when enabled, the scheduler mints a short-lived scoped JWT (`scope=workflows`) per scheduled run and injects it as `secrets.jwt`.
- `WORKFLOWS_VIRTUAL_KEY_TTL_MIN`: TTL (minutes) for per-run tokens; default `15`.

## Health Probes (CI smoke)
- The smoke lifecycle script probes health endpoints in this order: `/healthz`, `/api/v1/healthz`, `/health`, `/api/v1/health`, `/ready`, `/api/v1/health/ready`.
- Success criteria: HTTP `200` on any endpoint, or HTTP `206` on `/api/v1/health` (aggregate “degraded” still indicates the server is up).
- Timeout can be adjusted with `SMOKE_STARTUP_TIMEOUT_SECONDS` (default `120`).
