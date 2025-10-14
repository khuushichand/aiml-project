# Environment Variables – tldw_server (v0.1)

This reference lists environment variables recognized by the server. Environment variables take precedence over values from `Config_Files/.env`, which in turn take precedence over `Config_Files/config.txt` (where supported).

Precedence (highest → lowest):
- Process environment variables
- `.env` (Pydantic / dotenv)
- `config.txt` (sections parsed by the app; not all settings support file overrides)

Note: Secrets should be set via environment or `.env`. `config.txt` is supported for convenience in dev; prefer env in production.

## Core Server
- `tldw_production`: Enable production guards (`true|false`). Masks API key in logs, hardens WebUI config, enforces DB/secret checks.
- `ENABLE_OPENAPI`: Show OpenAPI/Swagger UI when `true`. Defaults to hidden in production unless explicitly enabled.
- `ALLOWED_ORIGINS`: CORS allowlist. Comma‑separated or JSON array.
- `ENABLE_SECURITY_HEADERS`: Enable security headers middleware (defaults to true in production).
- `UVICORN_WORKERS`: Uvicorn worker count (default 4 in Docker).
- `LOG_LEVEL`: Application log level (`DEBUG|INFO|WARNING|ERROR`).
- `MAGIC_FILE_PATH`: Path to `magic.mgc` for `python-magic` if needed.

## Testing & CI Controls
- `TEST_MODE`: Enables test-friendly behaviors (`true|1|yes`). Used across modules to:
  - Relax or bypass certain rate limiter keys (e.g., client IP) to avoid false positives in tests.
  - Skip heavy startup hooks when combined with `DISABLE_HEAVY_STARTUP` (see below).
  - Prefer offline/test-safe code paths (e.g., RAG/Chunking avoid network downloads; health endpoints may expose additional diagnostics in tests).
- `DISABLE_HEAVY_STARTUP`: Skip unrelated heavy startup work (`1|true|yes`).
  - Skips MCP server, TTS initialization, chat workers, and other background loops in tests/CI.
  - Also mentioned in README with additional context.
- `DISABLE_NLTK_DOWNLOADS`: Prevent NLTK dataset downloads (`1|true|yes`).
  - RAG query features and Chunking modules will not attempt to download `punkt`, `wordnet`, or `stopwords` when this is set; they degrade gracefully to local fallbacks.
- `ALLOW_NLTK_DOWNLOADS`: Force-enable NLTK downloads even when running tests (`1|true|yes`).
  - Overrides `TEST_MODE`/`DISABLE_NLTK_DOWNLOADS`/pytest auto-detection to allow downloads for development scenarios that require full NLTK resources.

### Chunking (regex safety and templates)
- `CHUNKING_REGEX_TIMEOUT`: Float seconds to cap regex execution for chapter/section detection and template boundaries. Default: `2`. Values <= 0 disable. On timeout, strategies fall back to safe paths.
- `CHUNKING_DISABLE_MP`: Disable process-based isolation for regex (default: disabled, i.e., no MP). Set `0|false|no` to enable optional MP fallback; note platform constraints.
- `CHUNKING_REGEX_SIMPLE_ONLY`: When `1|true|yes`, only a safe regex subset is allowed for custom boundary patterns. Unsafe constructs are rejected during validation.
- `CHUNKING_TEMPLATES_FALLBACK_ENABLED`: When `0|false|no`, disallow the in-process fallback store for chunking templates. Endpoints will return `500` with a hint if DB methods are missing. Default: enabled for dev/test.

### Security Health (Audit Thresholds)
- `AUDIT_SEC_CRITICAL_HIGH_RISK_MIN`: Minimum count of high-risk security events in the last 24h to mark status as `at_risk` and risk level `critical`. Default: `1`.
- `AUDIT_SEC_ELEVATED_FAILURE_MIN`: Minimum count of failure events in the last 24h to mark status `elevated` and risk level `high`. Default: `50`.

### Test Suite Toggles
- `TLDW_TEST_POSTGRES_REQUIRED`: Require Postgres-backed AuthNZ tests; when unset and Postgres is unavailable, tests auto-skip.
- `RUN_MCP_TESTS`: Enable MCP unified tests (defaults to skipped). Set to `1|true|yes` to run.
- `RUN_MOCK_OPENAI`: Enable Mock OpenAI server tests (defaults to skipped). Set to `1|true|yes` to run.

## Jobs Backend / Worker
- `JOBS_DB_URL`: PostgreSQL DSN for the core Jobs backend (e.g., `postgresql://user:pass@host:5432/jobs`). When unset, SQLite is used (Databases/jobs.db).
- `JOBS_LEASE_SECONDS`: Default lease granted when acquiring a job (default `60`).
- `JOBS_LEASE_RENEW_SECONDS`: Renewal cadence while a worker processes a job (default `30`).
- `JOBS_LEASE_RENEW_JITTER_SECONDS`: Jitter (seconds) applied to renewals to avoid herd behavior (default `5`).
- `JOBS_LEASE_MAX_SECONDS`: Cap for acquire/renew lease seconds (default `3600`).
- `CHATBOOKS_CORE_WORKER_ENABLED`: Enable shared Chatbooks worker when backend=core (default `true`).

Pytest markers
- `-m jobs`: Run all core Jobs tests (SQLite + PG-gated).
- `-m pg_jobs`: Run Postgres-only Jobs tests (requires JOBS_DB_URL and psycopg).
- `-m pg_jobs_stress`: Run heavier multi-process concurrency tests for PG (opt-in only).
  - Also set `RUN_PG_JOBS_STRESS=1` to enable these tests during runs.

## AuthNZ (Authentication)
- `AUTH_MODE`: `single_user` | `multi_user`.
- `DATABASE_URL`: AuthNZ database URL. For production multi-user, use Postgres (e.g., `postgresql://user:pass@host:5432/db`). SQLite supported for dev.
- `SINGLE_USER_API_KEY`: API key for single-user mode (>=24 chars recommended in production).
- `JWT_SECRET_KEY`: JWT signing secret (>=32 chars). Required for `multi_user` in production.
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Access token lifetime (default 30).
- `REFRESH_TOKEN_EXPIRE_DAYS`: Refresh token lifetime (default 7).
- `REDIS_URL`: Optional Redis URL for sessions (`redis://` or `rediss://`).
- `ENABLE_REGISTRATION`: Enable user registration (`true|false`).
- `REQUIRE_REGISTRATION_CODE`: Require code to register (`true|false`).
- `RATE_LIMIT_ENABLED`: Auth endpoints rate limit toggle (`true|false`).
- `RATE_LIMIT_PER_MINUTE`: Requests per minute (default 60).
- `RATE_LIMIT_BURST`: Burst size (default 10).
- `SHOW_API_KEY_ON_STARTUP`: In single-user mode, show API key once at startup (`true|false`). Avoid in production.
- `REDIS_ENABLED`: Boolean hint used in logs/metrics reporting.

Config file support (optional):
- Section `[AuthNZ]` in `Config_Files/config.txt` can define: `auth_mode`, `database_url`, `jwt_secret_key`, `single_user_api_key`, `enable_registration`, `require_registration_code`, `rate_limit_enabled`, `rate_limit_per_minute`, `rate_limit_burst`, `access_token_expire_minutes`, `refresh_token_expire_days`, `redis_url`.

## Chat / WebUI
- `CHAT_SAVE_DEFAULT`: Persist new chats by default (`true|false`).
- `DEFAULT_CHAT_SAVE`: Legacy alias; same as above.

### Tokenizer (Chat Dictionaries & World Books)
- `TOKEN_ESTIMATOR_MODE`: `whitespace` (default) or `char_approx`
  - `whitespace` counts whitespace‑separated tokens.
  - `char_approx` estimates by character length (≈ length/divisor).
- `TOKEN_CHAR_APPROX_DIVISOR`: Integer divisor for `char_approx` (default `4`).

Runtime overrides (non‑persistent) are available via API:
- `GET /api/v1/config/tokenizer` → read current mode/divisor
- `PUT /api/v1/config/tokenizer` → update mode/divisor in memory

## Usage Logging & Aggregators
- `USAGE_LOG_ENABLED`: Enable lightweight HTTP usage logging middleware (`true|false`, default `false`).
- `USAGE_LOG_EXCLUDE_PREFIXES`: JSON array of path prefixes to skip (default includes `/docs`, `/metrics`, `/static`, `/webui`). Example: `USAGE_LOG_EXCLUDE_PREFIXES='["/docs","/metrics"]'`.
- `USAGE_AGGREGATOR_INTERVAL_MINUTES`: Background aggregation cadence for `usage_daily` (default `60`).
- `USAGE_LOG_RETENTION_DAYS`: Retain `usage_log` rows for this many days; daily job prunes older rows (default `180`).
- `USAGE_LOG_DISABLE_META`: When `true`, do not store IP/User-Agent in `usage_log.meta` (stores `{}`) regardless of `PII_REDACT_LOGS`.
- `DISABLE_USAGE_AGGREGATOR`: When `true`, skip starting the HTTP usage background aggregator at startup (env-only override).

- `LLM_USAGE_ENABLED`: Enable per-request LLM usage logging (`true|false`, default `true`). Can also be set via env and respected by the tracker.
- `LLM_USAGE_AGGREGATOR_ENABLED`: Enable background aggregation of `llm_usage_log` into `llm_usage_daily` (`true|false`, default `true`).
- `LLM_USAGE_AGGREGATOR_INTERVAL_MINUTES`: Background LLM aggregation cadence in minutes (default `60`).
- `LLM_USAGE_LOG_RETENTION_DAYS`: Retain `llm_usage_log` rows for this many days; daily job prunes older rows (default `180`).
- `DISABLE_LLM_USAGE_AGGREGATOR`: When `true`, skip starting the LLM usage background aggregator at startup (env-only override).

## LLM Pricing
- `PRICING_OVERRIDES`: JSON object to override model/provider pricing used to compute costs. Example:
  ``
  export PRICING_OVERRIDES='{"openai":{"gpt-4o":{"prompt":0.005,"completion":0.015}}}'
  ``
  File-based overrides are also supported at `tldw_Server_API/Config_Files/model_pricing.json`.

## Embeddings
- `TRUSTED_HF_REMOTE_CODE_MODELS`: Comma‑separated allowlist patterns for models that require `trust_remote_code=True` (e.g., `NovaSearch/stella_en_400M_v5,BAAI/*bge*`).

## LLM Provider Keys
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `COHERE_API_KEY`, `DEEPSEEK_API_KEY`, `GOOGLE_API_KEY`, `GROQ_API_KEY`, `HUGGINGFACE_API_KEY`, `MISTRAL_API_KEY`, `OPENROUTER_API_KEY`, `QWEN_API_KEY`
- Additional provider‑specific variables as required by their APIs.

## MCP Unified
- `MCP_JWT_SECRET`: Secret used by the MCP server for issuing/verifying tokens.
- `MCP_API_KEY_SALT`: Salt used for API key hashing/derivation.
- `MCP_LOG_LEVEL`: MCP module log level (`DEBUG|INFO|WARNING|ERROR`).

## OCR – POINTS Reader (optional)
- `POINTS_MODE`: `sglang` or `transformers` (default: auto).
- `POINTS_SGLANG_URL`: SGLang chat/completions endpoint (e.g., `http://127.0.0.1:8081/v1/chat/completions`).
- `POINTS_SGLANG_MODEL`: Model name in SGLang server (e.g., `WePoints`).
- `POINTS_MODEL_PATH`: HF model path when running locally (e.g., `tencent/POINTS-Reader`).
- `POINTS_PROMPT`: Optional prompt override.

## Notes
- Many subsystems also support file‑based configuration under `Config_Files/` and module‑specific YAML files (e.g., TTS provider config). Environment variables always take precedence when present.

## Monitoring & Alerts
- Topic Monitoring (watchlists and alerting):
  - `MONITORING_WATCHLISTS_FILE`: JSON file with watchlists (default `tldw_Server_API/Config_Files/monitoring_watchlists.json`).
  - `MONITORING_ALERTS_DB`: SQLite DB path for topic alerts (default `Databases/monitoring_alerts.db`).
  - `TOPIC_MONITOR_MAX_SCAN_CHARS`: Max characters scanned per text (default `200000`).
  - `TOPIC_MONITOR_DEDUP_SECONDS`: Deduplication window to avoid repeated alerts for same (user,watchlist,pattern,source) (default `300`).

- Notifications (scaffold; local-first with optional external hooks):
  - `MONITORING_NOTIFY_ENABLED`: Enable notification output (`true|false`, default `false`).
  - `MONITORING_NOTIFY_MIN_SEVERITY`: Minimum severity to notify (`info|warning|critical`, default `critical`).
  - `MONITORING_NOTIFY_FILE`: JSONL file sink for notifications (default `Databases/monitoring_notifications.log`).
  - `MONITORING_NOTIFY_WEBHOOK_URL`: Optional HTTP webhook URL (best-effort, async, retries).
  - `MONITORING_NOTIFY_EMAIL_TO`: Optional email recipient (comma not supported; one address).
  - `MONITORING_NOTIFY_EMAIL_FROM`: Sender email address (defaults to SMTP user if unset).
  - `MONITORING_NOTIFY_SMTP_HOST`: SMTP server host (required for email).
  - `MONITORING_NOTIFY_SMTP_PORT`: SMTP port (default `587`).
  - `MONITORING_NOTIFY_SMTP_STARTTLS`: Enable STARTTLS (`true|false`, default `true`).
  - `MONITORING_NOTIFY_SMTP_USER`: SMTP auth username (optional if server allows anon relay; not recommended).
  - `MONITORING_NOTIFY_SMTP_PASSWORD`: SMTP auth password.

Notes:
- Monitoring alerts do not block or modify content; they create reviewable signals for admins.
- Webhook/email delivery is best-effort and runs in background threads with small timeouts and retries.
