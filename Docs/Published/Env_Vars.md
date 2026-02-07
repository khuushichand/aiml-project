# Environment Variables - tldw_server (v0.1)

This reference lists environment variables recognized by the server. Environment variables take precedence over values from `Config_Files/.env`, which in turn take precedence over `Config_Files/config.txt` (where supported).

Precedence (highest → lowest):
- Process environment variables
- `.env` (Pydantic / dotenv)
- `config.txt` (sections parsed by the app; not all settings support file overrides)

Note: Secrets should be set via environment or `.env`. `config.txt` is supported for convenience in dev; prefer env in production.

For the full, frequently updated raw reference (auto-generated), see `Env_Vars.md` in the repository root.

Config file support (selected):
- Section `[Image-Generation]` in `Config_Files/config.txt` can define: `default_backend`, `enabled_backends`, `max_width`, `max_height`, `max_pixels`, `max_steps`, `max_prompt_length`, `inline_max_bytes`, `sd_cpp_binary_path`, `sd_cpp_diffusion_model_path`, `sd_cpp_model_path`, `sd_cpp_llm_path`, `sd_cpp_vae_path`, `sd_cpp_lora_paths`, `sd_cpp_allowed_extra_params`, `sd_cpp_default_steps`, `sd_cpp_default_cfg_scale`, `sd_cpp_default_sampler`, `sd_cpp_device`, `sd_cpp_timeout_seconds`.

## Core Server
- `tldw_production`: Enable production guards (`true|false`). Masks API key in logs and enforces DB/secret checks.
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

Setup Access Guard (remote access controls)
- `TLDW_SETUP_ALLOW_REMOTE`: Temporarily allow remote access to the Setup UI (`/setup`). Only use on trusted networks.
- `TLDW_SETUP_ALLOWLIST`: Comma-separated IPs/CIDRs allowed to access `/setup`.
- `TLDW_SETUP_DENYLIST`: Comma-separated IPs/CIDRs denied from `/setup`.
- `TLDW_TRUSTED_PROXIES`: Comma-separated proxy IPs/CIDRs trusted for X-Forwarded-For/X-Real-IP.

Setup CSP (Content Security Policy)
- `TLDW_SETUP_NO_EVAL`: When set, controls whether `'unsafe-eval'` is allowed for `/setup` scripts.
  - Precedence: if present, its truthiness decides the policy.
  - Truthy values (case-insensitive): `1`, `true`, `yes`, `on`, `y` → DISABLE eval (no `'unsafe-eval'`).
  - Falsy values (e.g., `0`, `false`) → ENABLE eval.
  - If unset: default is allow eval.

## AuthNZ (Authentication)
- `AUTH_MODE`: `single_user` | `multi_user`.
- `DATABASE_URL`: AuthNZ database URL. For production multi-user, use Postgres.
- `SINGLE_USER_API_KEY`: API key for single-user mode (>=24 chars recommended).
- `JWT_SECRET_KEY`: JWT signing secret (>=32 chars). Required for `multi_user` in production.
- `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`.
- `REDIS_URL`: Optional Redis URL for sessions.
- `ENABLE_REGISTRATION`, `REQUIRE_REGISTRATION_CODE`.
- `BYOK_ENABLED`: Enable per-user BYOK keys (ignored in single_user mode).
- `BYOK_ALLOWED_PROVIDERS`: Optional comma-separated allowlist of providers eligible for BYOK.
- `BYOK_ALLOWED_BASE_URL_PROVIDERS`: Optional comma-separated allowlist for BYOK `base_url` overrides.
- `BYOK_ENCRYPTION_KEY`: Base64-encoded 32-byte key for BYOK secret encryption (AES-GCM).
- `BYOK_LAST_USED_THROTTLE_SECONDS`: Throttle runtime updates to BYOK `last_used_at` (seconds, default `300`).
- `BYOK_SECONDARY_ENCRYPTION_KEY`: Secondary BYOK encryption key for dual-read during rotations.
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
- `TLDW_WORKERS_SIDECAR_MODE`: When true, skip in-process Jobs workers so you can run them as sidecars (`true|false`, default `false`).
- `MEDIA_INGEST_JOBS_WORKER_ENABLED`: Start the in-process media ingest jobs worker on app startup (`true|false`, default follows route policy for `media`).
- `FILES_JOBS_WORKER_ENABLED`: Start the in-process file artifacts jobs worker on app startup (`true|false`, default follows route policy for `files`); otherwise run `python -m tldw_Server_API.app.core.File_Artifacts.jobs_worker`.
- `PROMPT_STUDIO_JOBS_WORKER_ENABLED`: Start the in-process Prompt Studio jobs worker on app startup (`true|false`, default follows route policy for `prompt-studio`).
- `PRIVILEGE_SNAPSHOT_WORKER_ENABLED`: Start the in-process privilege snapshot jobs worker on app startup (`true|false`, default follows route policy for `privileges`).
- `EMBEDDINGS_JOBS_QUEUE`: Queue for embeddings stage jobs (default `default`).
- `EMBEDDINGS_ROOT_JOBS_QUEUE`: Queue for embeddings root jobs (default `low` when stage queue is not `low`).
- `EMBEDDINGS_JOBS_WORKER_ID`: Worker identifier for embeddings jobs (default `embeddings-jobs-<pid>`).
- `EMBEDDINGS_JOBS_EXPOSE_PROGRESS`: Include progress fields in public embeddings jobs responses (`true|false`, default `false`).

## Data Tables
- `DATA_TABLES_JOBS_WORKER_ENABLED`: Start the in-process data tables jobs worker on app startup (`true|false`, default follows route policy for `data-tables`).
- `DATA_TABLES_JOBS_QUEUE`: Queue for data table generation jobs (default `default`).
- `DATA_TABLES_JOBS_WORKER_ID`: Worker identifier for data tables jobs (default `data-tables-jobs-<pid>`).
- `DATA_TABLES_JOBS_LEASE_SECONDS`: Lease duration for data tables jobs (default `60`).
- `DATA_TABLES_JOBS_RENEW_JITTER_SECONDS`: Lease renew jitter in seconds (default `5`).
- `DATA_TABLES_JOBS_RENEW_THRESHOLD_SECONDS`: Renew threshold in seconds (default `10`).
- `DATA_TABLES_JOBS_BACKOFF_BASE_SECONDS`: Base retry backoff in seconds (default `2`).
- `DATA_TABLES_JOBS_BACKOFF_MAX_SECONDS`: Max retry backoff in seconds (default `30`).
- `DATA_TABLES_JOBS_RETRY_BACKOFF_SECONDS`: Backoff for retryable errors (default `10`).
- `DATA_TABLES_DEFAULT_MAX_ROWS`: Default max rows per table when request omits `max_rows` (default `200`).
- `DATA_TABLES_MAX_ROWS`: Hard cap on generated rows per table (default `2000`).
- `DATA_TABLES_MAX_SOURCE_CHARS`: Per-source character cap used when building prompts (default `12000`).
- `DATA_TABLES_MAX_TOTAL_SOURCE_CHARS`: Aggregate character cap across all sources (default `60000`).
- `DATA_TABLES_MAX_SNAPSHOT_CHARS`: Per-chunk snapshot text cap for rag_query sources (default `8000`).
- `DATA_TABLES_MAX_PROMPT_CHARS`: Total prompt size cap (default `24000`).
- `DATA_TABLES_CHAT_BATCH_SIZE`: Batch size when loading chat messages (default `250`).
- `DATA_TABLES_CHAT_MAX_MESSAGES`: Maximum chat messages loaded per source (default `1500`).
- `DATA_TABLES_LLM_MAX_TOKENS`: LLM response token budget for table generation (default `2000`).
- `DATA_TABLES_LLM_TEMPERATURE`: LLM temperature for table generation (default `0.2`).

## Chat
- `CHAT_STREAM_INCLUDE_METADATA`: Include `tldw_*` IDs in chat SSE streaming chunks (`true|false`, default `true`). Set `false` for strict OpenAI streaming compatibility.

## Chatbooks
- `CHATBOOKS_JOBS_BACKEND`: Core-only; overrides are ignored (kept for compatibility).
- `CHATBOOKS_CORE_WORKER_ENABLED`: Enable shared Chatbooks worker when backend=core (default `true`).
- `CHATBOOKS_SIGNED_URLS`: Require HMAC-signed download URLs (`true|false`, default `false`).
- `CHATBOOKS_SIGNING_SECRET`: Secret key used for download URL signing (required when signed URLs are enabled).
- `CHATBOOKS_ENFORCE_EXPIRY`: Enforce job `expires_at` on download (`true|false`, default `true`).
- `CHATBOOKS_URL_TTL_SECONDS`: Default expiry TTL for generated download links (default `86400`).
- `CHATBOOKS_EXPORT_RETENTION_DEFAULT_HOURS`: Retention window for completed exports before expiry (default `24`).
- `CHATBOOKS_CLEANUP_INTERVAL_SEC`: Scheduled cleanup cadence in seconds (set `0` to disable scheduling).
- `CHATBOOKS_EVAL_EXPORT_MAX_ROWS`: Max rows exported per evaluation run (default `200`).
- `CHATBOOKS_BINARY_LIMITS_MB`: JSON map of content type to max bundled size in MB (for example, `{"media": 0, "conversations": 10, "generated_docs": 25}`).
- `CHATBOOKS_IMPORT_DICT_STRICT`: When true, skip dictionaries with fatal validation errors instead of importing with warnings.

## Audio Quotas & Workers
- `AUDIO_JOBS_WORKER_ENABLED`: Start the in-process Audio Jobs worker on app startup (`true|false`, default follows route policy for `audio-jobs`).
- `AUDIO_JOBS_OWNER_STRICT`: Enable owner-aware acquisition heuristic for fair scheduling (`true|false`).
- `AUDIO_QUOTA_USE_REDIS`: Store active streams/jobs counters in Redis for multi-instance fairness. Defaults to true when `REDIS_URL` is set.
- `REDIS_URL`: Redis connection string (e.g., `redis://localhost:6379`).

Audio Chat (non-streaming)
- `AUDIO_CHAT_MAX_BYTES`: Max input audio size (bytes) for `/api/v1/audio/chat` (default `20MB`). Requests exceeding this return HTTP 413 before STT runs.
- `AUDIO_CHAT_MAX_DURATION_SEC`: Max input duration (seconds) for `/api/v1/audio/chat` (default `120`). Requests exceeding this return HTTP 400 before STT runs.
- `AUDIO_CHAT_ENABLE_ACTIONS`: Enable action/tool execution for `/api/v1/audio/chat` (default disabled). When true, `metadata.action` or `llm_config.extra_params.action` hints are routed to MCP modules via `execute_tool`; results are returned in `action_result` and persisted as a `tool` message.

Streaming Audio / TTS
- `AUDIO_WS_QUOTA_CLOSE_1008`: When set, close WebSocket quota/rate-limit violations with code `1008` (default `4003`) for streaming audio routes.
- `AUDIO_WS_COMPAT_ERROR_TYPE`: When `1` (default), include legacy `error_type` alias in Audio WS error payloads alongside canonical `code`; set `0` to disable alias during client migration.
- `TTS_PHONEME_OVERRIDES_PATH`: Optional YAML/JSON file with phoneme overrides (defaults to `Config_Files/tts_phonemes.yaml|yml|json`).
- `KOKORO_ENABLE_PHONEME_OVERRIDES`: Toggle Kokoro phoneme override application (`true|false`, default `true`).
- `TTS_HISTORY_ENABLED`: Enable per-user TTS history (`true|false`, default `true`).
- `TTS_HISTORY_STORE_TEXT`: Store full text in history (`true|false`, default `true`).
- `TTS_HISTORY_STORE_FAILED`: Store failed TTS attempts (`true|false`, default `true`).
- `TTS_HISTORY_HASH_KEY`: Secret key for HMAC hashing of TTS input text (required for hashing).
- `TTS_HISTORY_RETENTION_DAYS`: Age-based purge window in days (default `90`, set `0` to disable).
- `TTS_HISTORY_MAX_ROWS_PER_USER`: Max rows retained per user (default `10000`, set `0` to disable).
- `TTS_HISTORY_PURGE_INTERVAL_HOURS`: Purge cadence in hours (default `24`).

Queues
- CPU stages use `queue=default`.
- GPU transcription uses dedicated `queue=transcribe` (see GPU worker container stub).

## Chunking / RAG / Embeddings / MCP / TTS
Module-specific toggles exist; see the repo `Env_Vars.md` or the respective module docs for details.
Notable: `ALLOW_ZERO_EMBEDDINGS_MEDIA_TYPES` lets media-embeddings jobs succeed with zero vectors for media types like `audio,video`.

RAG precomputed spans (late-interaction index)
- `RAG_PRECOMPUTED_SPANS_MAX_VECTORS_PER_CORPUS`: Cap on stored span vectors per corpus (default `200000`).
- `RAG_PRECOMPUTED_SPANS_MAX_MB_PER_CORPUS`: Cap on precomputed span storage per corpus in MB (default `512`).
- `RAG_PRECOMPUTED_SPANS_RETENTION_DAYS`: Retention window for precomputed spans before GC (default `30`).

Monitoring & Telemetry
- `METRICS_ENABLED`: Enable text metrics endpoints.
- `METRICS_RING_BUFFER_MAXLEN_OR_UNBOUNDED`: Rolling metrics sample window size (default `10000`). Set `0` or a negative value for an unbounded buffer.
- OpenTelemetry export is controlled via standard `OTEL_*` environment variables (e.g., `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME`, `OTEL_TRACES_EXPORTER`). See the Deployment/Monitoring docs.

## Workflows (Auth & Scheduler)
- `WORKFLOWS_DEFAULT_BEARER_TOKEN`: Default Authorization bearer token used by Workflows steps when not explicitly provided in headers.
- `WORKFLOWS_DEFAULT_API_KEY`: Default `X-API-KEY` used by Workflows steps when bearer is not provided.
- `WORKFLOWS_VALIDATE_DEFAULT_AUTH`: `true|false` - optionally validate the default token once per run against `/api/v1/workflows/auth/check`.
- `WORKFLOWS_INTERNAL_BASE_URL`: Base URL for validation requests; defaults to `http://127.0.0.1:8000`.
- `WORKFLOWS_MINT_VIRTUAL_KEYS`: `true|false` - when enabled, the scheduler mints a short-lived scoped JWT (`scope=workflows`) per scheduled run and injects it as `secrets.jwt`.
- `WORKFLOWS_VIRTUAL_KEY_TTL_MIN`: TTL (minutes) for per-run tokens; default `15`.

## Workflows (File Access)
- `WORKFLOWS_FILE_BASE_DIR`: Base directory for workflow `file://` access. Relative paths resolve from the project root; defaults to the per-user base dir under `USER_DB_BASE_DIR` (with a `Databases/` fallback).
- `WORKFLOWS_ALLOW_UNSAFE_FILE_ACCESS`: `true|false` - allow workflow file access outside the per-user base dir, but only under allowlisted base directories (default `false`).
- `WORKFLOWS_FILE_ALLOWLIST`: Comma-separated list of allowed base directories for unsafe file access; relative paths resolve from the project root.
- `WORKFLOWS_FILE_ALLOWLIST_<TENANT>`: Optional per-tenant override (uppercase, `-` replaced by `_`); when set, it replaces the global allowlist for that tenant.

## Health Probes (CI smoke)
- The smoke lifecycle script probes health endpoints in this order: `/healthz`, `/api/v1/healthz`, `/health`, `/api/v1/health`, `/ready`, `/api/v1/health/ready`.
- Success criteria: HTTP `200` on any endpoint, or HTTP `206` on `/api/v1/health` (aggregate “degraded” still indicates the server is up).
- Timeout can be adjusted with `SMOKE_STARTUP_TIMEOUT_SECONDS` (default `120`).
