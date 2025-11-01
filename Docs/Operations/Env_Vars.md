# Environment Variables - tldw_server (v0.1)

This reference lists environment variables recognized by the server. Environment variables take precedence over values from `Config_Files/.env`, which in turn take precedence over `Config_Files/config.txt` (where supported).

Precedence (highest → lowest):
- Process environment variables
- `.env` (Pydantic / dotenv)
- `config.txt` (sections parsed by the app; not all settings support file overrides)

Note: Secrets should be set via environment or `.env`. `config.txt` is supported for convenience in dev; prefer env in production.

## Core Server
- `tldw_production`: Enable production guards (`true|false`). Masks API key in logs, hardens WebUI config, enforces DB/secret checks.
- `ENABLE_OPENAPI`: Show OpenAPI/Swagger UI when `true`. Defaults to hidden in production unless explicitly enabled.
- `ALLOWED_ORIGINS`: CORS allowlist. Comma-separated or JSON array.
- `TLDW_CONFIG_PATH`: Absolute path to the primary `config.txt`. When set, the parent directory is treated as the config root for auxiliary assets (e.g., `Synonyms/`).
- `TLDW_CONFIG_DIR`: Explicit directory containing `config.txt` and related config assets. Checked after `TLDW_CONFIG_PATH`.
- `ENABLE_SECURITY_HEADERS`: Enable security headers middleware (defaults to true in production).
- `UVICORN_WORKERS`: Uvicorn worker count (default 4 in Docker).
- `LOG_LEVEL`: Application log level (`DEBUG|INFO|WARNING|ERROR`).
- `MAGIC_FILE_PATH`: Path to `magic.mgc` for `python-magic` if needed.

## Testing & CI Controls
- `TEST_MODE`: Enables test-friendly behaviors (`true|1|yes`). Used across modules to:
  - Relax or bypass certain rate limiter keys (e.g., client IP) to avoid false positives in tests.
  - Prefer offline/test-safe code paths (e.g., RAG/Chunking avoid network downloads; health endpoints may expose additional diagnostics in tests).
- `DISABLE_NLTK_DOWNLOADS`: Prevent NLTK dataset downloads (`1|true|yes`).
  - RAG query features and Chunking modules will not attempt to download `punkt`, `wordnet`, or `stopwords` when this is set; they degrade gracefully to local fallbacks.
- `ALLOW_NLTK_DOWNLOADS`: Force-enable NLTK downloads even when running tests (`1|true|yes`).
  - Overrides `TEST_MODE`/`DISABLE_NLTK_DOWNLOADS`/pytest auto-detection to allow downloads for development scenarios that require full NLTK resources.

## RAG Module
- `tldw_production`: When `true`, RAG retrievers disable raw SQL fallbacks and require adapters (MediaDatabase/ChaChaNotesDB). Unified endpoints already pass adapters; direct pipeline usage must supply them.
- `RAG_LLM_RERANK_TIMEOUT_SEC`: Per-document LLM rerank timeout (seconds). Default `10`.
- `RAG_LLM_RERANK_TOTAL_BUDGET_SEC`: Total time budget for LLM reranking per query (seconds). Default `20`.
- `RAG_LLM_RERANK_MAX_DOCS`: Cap on number of documents scored by LLM reranker per query. Default `20`.
 - `RAG_TRANSFORMERS_RERANKER_MODEL`: Cross-encoder model id for fast reranking (stage 1). Default `BAAI/bge-reranker-v2-m3`.
 - `RAG_REWRITE_CACHE_PATH`: Optional path for query→rewrite cache JSONL (default `Databases/Rewrite_Cache/rewrite_cache.jsonl`).

### RAG Guardrails (Production Defaults)
- `RAG_GUARDRAILS_STRICT`: When `true`, enable strict guardrails in the unified pipeline (enables numeric fidelity and hard citations by default). Useful for non-prod environments where you still want strict behavior.
- `RAG_ENABLE_NUMERIC_FIDELITY`: Force-enable numeric fidelity verification of answers (overrides request default). Optional; typically implied by `RAG_GUARDRAILS_STRICT`.
- `RAG_REQUIRE_HARD_CITATIONS`: Force-enable per-sentence hard citations mapping (overrides request default). Optional; typically implied by `RAG_GUARDRAILS_STRICT`.
- `RAG_NUMERIC_FIDELITY_BEHAVIOR`: Default behavior when numeric values are not verified in sources: `continue` | `ask` | `decline` | `retry`. Default `ask` when strict mode is active.
 - `RAG_PAYLOAD_EXEMPLAR_SAMPLING`: Sampling rate (0..1) to record redacted payload exemplars when adaptive check fails (default `0.05`).
 - `RAG_PAYLOAD_EXEMPLAR_PATH`: Optional path for payload exemplars JSONL sink (default `Databases/observability/rag_payload_exemplars.jsonl`).
 - `RAG_PERSONALIZATION_HALF_LIFE_DAYS`: Half-life for decay of per-user priors (default `7`).
- `RAG_PERSONALIZATION_WEIGHT`: Additive weight applied to prior during boosting (default `0.1`).

### RAG Quality Evaluations (Nightly)
- `RAG_QUALITY_EVAL_ENABLED`: Enable nightly eval scheduler in-process (`true|false`, default `false`).
- `RAG_QUALITY_EVAL_INTERVAL_SEC`: Interval between eval runs in seconds (default `86400`).
- `RAG_QUALITY_EVAL_DATASET`: Path to JSONL eval dataset (default `Docs/Deployment/Monitoring/Evals/nightly_rag_eval.jsonl`).

### Embeddings A/B Persistence
- `EVALS_ABTEST_PERSISTENCE`: Backend for embeddings A/B test storage. Defaults to `sqlalchemy` (or `repo`) which enables the SQLAlchemy repository with typed models. Set to any other value (for example `legacy`) to fall back to the previous SQLite helper implementation. Only the SQLite deployment path honors this toggle; Postgres deployments always use the legacy adapter.

Notes:
- In production (`tldw_production=true`) or when `RAG_GUARDRAILS_STRICT=true`, the unified pipeline will default to enabling numeric fidelity and strict citations unless explicitly configured otherwise by the request.

### Two-Tier Reranking Calibration & Gating
- `RAG_RERANK_CALIB_BIAS`: Logistic calibration bias. Default `-1.5`.
- `RAG_RERANK_CALIB_W_ORIG`: Weight for original retrieval score. Default `0.8`.
- `RAG_RERANK_CALIB_W_CE`: Weight for cross-encoder score. Default `2.5`.
- `RAG_RERANK_CALIB_W_LLM`: Weight for LLM reranker score. Default `3.0`.
- `RAG_MIN_RELEVANCE_PROB`: Minimum calibrated probability to allow generation. Default `0.35`.
- `RAG_SENTINEL_MARGIN`: Required margin of (top_prob - sentinel_prob) to consider evidence strong enough. Default `0.10`.

### RAG Rollout Toggles (Structure, Planner, Cache)
- `RAG_ENABLE_STRUCTURE_INDEX`: Enable persisted document structure index (sections/paragraphs with char offsets) and retrieval metadata enrichment. Defaults to `true`. Config file key: `[RAG] enable_structure_index`.
- `RAG_STRICT_EXTRACTIVE`: Use strict extractive answer path in the standard pipeline (assemble only from retrieved spans). Defaults to `false`. Config key: `[RAG] strict_extractive`.
- `RAG_LOW_CONFIDENCE_BEHAVIOR`: Behavior when evidence is insufficient after guardrails (`continue` | `ask` | `decline`). Defaults to `continue`. Config key: `[RAG] low_confidence_behavior`.
- `RAG_AGENTIC_CACHE_BACKEND`: Agentic ephemeral cache backend (`memory` | `sqlite`). Defaults to `memory`. Config key: `[RAG] agentic_cache_backend`.
- `RAG_AGENTIC_CACHE_TTL_SEC`: TTL for agentic cache entries in seconds. Defaults to `600`. Config key: `[RAG] agentic_cache_ttl_sec`.

Notes:
- These env vars take precedence over `.env`, which takes precedence over `config.txt`. The loader now propagates `config.txt` defaults into process env when unset, so modules reading `os.getenv` will honor file settings by default.

### Ingest & Chunking
- `INGEST_ENABLE_DEDUP`: Enable near-duplicate removal at ingestion time (`true|false`, default `true`).
- `INGEST_DEDUP_THRESHOLD`: Jaccard similarity threshold for shingle-based dedupe (0-1, default `0.9`).
- Chunker adaptive controls are primarily request-level, but ingestion defaults set `adaptive=true` and `adaptive_overlap=true`.

### RAG Adaptive Post-Verification
- `RAG_ADAPTIVE_TIME_BUDGET_SEC`: Optional hard cap (seconds) for post-generation verification and repair. When unset or `0`, no cap is applied. Other knobs are request-level (`enable_post_verification`, `adaptive_max_retries`, `adaptive_unsupported_threshold`, `adaptive_max_claims`).
- `RAG_ADAPTIVE_ADVANCED_REWRITES`: Toggle advanced rewrite strategy (HyDE + multi-strategy + diversity) for the adaptive pass. `true|false` (default `true`). When `false`, the adaptive pass uses a simple single-query retrieval.

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

## Audio Jobs
- `AUDIO_JOBS_WORKER_ENABLED`: Enable the in-process Audio Jobs worker (`true|false`, default `false`). When true, the worker starts at app startup and polls the Jobs backend for the `audio` domain pipeline stages.
- `AUDIO_JOBS_OWNER_STRICT`: Enable owner-aware acquisition for fairness across users (`true|false`, default `false`). When enabled, the worker preferentially acquires jobs for owners under their concurrent-job caps.
- `AUDIO_QUOTA_USE_REDIS`: Use Redis for distributed audio concurrency tracking (`true|false`, default `true` when `REDIS_URL` is set). Falls back to in-process counters when disabled or unavailable.

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
- `SECURITY_ALERTS_ENABLED`: Enable AuthNZ security alert dispatching (`true|false`, default `false`).
- `SECURITY_ALERT_MIN_SEVERITY`: Minimum severity to deliver (`low|medium|high|critical`, default `high`).
- `SECURITY_ALERT_FILE_PATH`: JSONL file sink for security alerts (default `Databases/security_alerts.log`).
- `SECURITY_ALERT_WEBHOOK_URL`: Optional webhook endpoint for security alerts (e.g., Slack/PagerDuty).
- `SECURITY_ALERT_WEBHOOK_HEADERS`: JSON object of extra headers for webhook calls (e.g., auth tokens).
- `SECURITY_ALERT_EMAIL_TO`: Comma-separated recipient list for email alerts.
- `SECURITY_ALERT_EMAIL_FROM`: From address for email alerts (required when using SMTP).
- `SECURITY_ALERT_EMAIL_SUBJECT_PREFIX`: Subject prefix for alert emails (default `[AuthNZ]`).
- `SECURITY_ALERT_SMTP_HOST`: SMTP host for email delivery.
- `SECURITY_ALERT_SMTP_PORT`: SMTP port (default `587`).
- `SECURITY_ALERT_SMTP_STARTTLS`: Enable STARTTLS negotiation (`true|false`, default `true`).
- `SECURITY_ALERT_SMTP_USERNAME`: SMTP username (if authentication required).
- `SECURITY_ALERT_SMTP_PASSWORD`: SMTP password/secret.
- `SECURITY_ALERT_SMTP_TIMEOUT`: SMTP connection timeout in seconds (default `10`).
- `SECURITY_ALERT_FILE_MIN_SEVERITY`: Override the global severity threshold for the file sink; choose from `low|medium|high|critical`.
- `SECURITY_ALERT_WEBHOOK_MIN_SEVERITY`: Override the global severity threshold for the webhook sink.
- `SECURITY_ALERT_EMAIL_MIN_SEVERITY`: Override the global severity threshold for email delivery.
- `SECURITY_ALERT_BACKOFF_SECONDS`: Cooldown applied after a sink fails before retrying (default `30`).
- `SHOW_API_KEY_ON_STARTUP`: In single-user mode, show API key once at startup (`true|false`). Avoid in production.
- `REDIS_ENABLED`: Boolean hint used in logs/metrics reporting.

Config file support (optional):
- Section `[AuthNZ]` in `Config_Files/config.txt` can define: `auth_mode`, `database_url`, `jwt_secret_key`, `single_user_api_key`, `enable_registration`, `require_registration_code`, `rate_limit_enabled`, `rate_limit_per_minute`, `rate_limit_burst`, `access_token_expire_minutes`, `refresh_token_expire_days`, `redis_url`, plus security alert keys (`security_alerts_enabled`, `security_alert_min_severity`, `security_alert_file_path`, `security_alert_webhook_url`, `security_alert_webhook_headers`, `security_alert_email_to`, `security_alert_email_from`, `security_alert_email_subject_prefix`, `security_alert_smtp_host`, `security_alert_smtp_port`, `security_alert_smtp_starttls`, `security_alert_smtp_username`, `security_alert_smtp_password`, `security_alert_smtp_timeout`, `security_alert_file_min_severity`, `security_alert_webhook_min_severity`, `security_alert_email_min_severity`).

## Chat / WebUI
- `CHAT_SAVE_DEFAULT`: Persist new chats by default (`true|false`).
- `DEFAULT_CHAT_SAVE`: Legacy alias; same as above.

### Tokenizer (Chat Dictionaries & World Books)
- `TOKEN_ESTIMATOR_MODE`: `whitespace` (default) or `char_approx`
  - `whitespace` counts whitespace-separated tokens.
  - `char_approx` estimates by character length (≈ length/divisor).
- `TOKEN_CHAR_APPROX_DIVISOR`: Integer divisor for `char_approx` (default `4`).

Runtime overrides (non-persistent) are available via API:
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
- `PRIVILEGE_SNAPSHOT_RETENTION_DAYS`: Keep privilege snapshots at full granularity for this many days before weekly downsampling (default `90`).
- `PRIVILEGE_SNAPSHOT_WEEKLY_RETENTION_DAYS`: Retain the downsampled weekly snapshots for this many days before purging entirely (default `365`).
- `PRIVILEGE_MAP_CACHE_TTL_SECONDS`: TTL for cached privilege summaries in seconds (default `120`, floor `10`). Controls the in-process and distributed cache expiry.
- `PRIVILEGE_CACHE_BACKEND`: `memory` (default) keeps cache local to each worker; set to `redis` to enable distributed caching with pub/sub invalidation.
- `PRIVILEGE_CACHE_REDIS_URL`: Redis connection string used when `PRIVILEGE_CACHE_BACKEND=redis`. Falls back to `REDIS_URL` if unset.
- `PRIVILEGE_CACHE_NAMESPACE`: Optional namespace prefix for distributed cache keys/channels (default `privmap`).
- `PRIVILEGE_CACHE_SLIDING_TTL`: `1|true` (default) refreshes Redis TTL on reads; set to `0|false` to keep a fixed expiry.
- `PRIVILEGE_CACHE_GENERATION_SYNC_SECONDS`: Polling interval (seconds) for generation checks when Redis pub/sub is unavailable (default `2`).
- `DISABLE_LLM_USAGE_AGGREGATOR`: When `true`, skip starting the LLM usage background aggregator at startup (env-only override).

## LLM Pricing
- `PRICING_OVERRIDES`: JSON object to override model/provider pricing used to compute costs. Example:
  ``
  export PRICING_OVERRIDES='{"openai":{"gpt-4o":{"prompt":0.005,"completion":0.015}}}'
  ``
  File-based overrides are also supported at `tldw_Server_API/Config_Files/model_pricing.json`.

## Embeddings
- `EMBEDDINGS_DEDUPE_TTL_SECONDS`: Dedupe window for worker replay suppression. Defaults to `3600` seconds. Workers compute a stage-specific dedupe key (or use `dedupe_key`/`idempotency_key` if provided) and suppress processing if the same key was seen within this TTL.
- `TRUSTED_HF_REMOTE_CODE_MODELS`: Comma-separated allowlist patterns for models that require `trust_remote_code=True` (e.g., `NovaSearch/stella_en_400M_v5,BAAI/*bge*`).

### Backpressure & Quotas
- `EMB_BACKPRESSURE_MAX_DEPTH`: Maximum depth across core embeddings queues (`embeddings:chunking`, `embeddings:embedding`, `embeddings:storage`) before ingest/embeddings endpoints return HTTP 429 with `Retry-After`. Default: `25000`.
- `EMB_BACKPRESSURE_MAX_AGE_SECONDS`: Maximum age (seconds) of the oldest message across core embeddings queues before HTTP 429. Default: `300`.
- `EMBEDDINGS_TENANT_RPS`: Per-tenant requests per second limit for embeddings endpoints (multi-tenant mode only). `0` disables. Default: `0`.
- `INGEST_TENANT_RPS`: Per-tenant requests per second limit for ingestion endpoints (multi-tenant mode). Falls back to `EMBEDDINGS_TENANT_RPS` if unset. `0` disables. Default: `0`.
- `EMBEDDINGS_REDIS_URL`: Redis connection string for embeddings job manager queues (`embeddings:*`). Falls back to `REDIS_URL` and defaults to `redis://localhost:6379`.

### Priority Queues
- `EMBEDDINGS_PRIORITY_ENABLED`: Enable per-stage priority sub-queues with weighted fair consumption (`true|false`). Default: `false`.
- `EMBEDDINGS_PRIORITY_WEIGHTS`: Comma-separated weights for `high`, `normal`, `low` priority buckets used by workers when `EMBEDDINGS_PRIORITY_ENABLED=true`. Example: `high:5,normal:3,low:1` (default).

### Vector Store: pgvector
- `RAG.vector_store_type`: Set to `pgvector` to activate the pgvector adapter (default `chromadb`).
  - Important: For normal server operation, pgvector connection settings are sourced from `config.txt` and are not overridden by environment variables. Tests and helper scripts may still use env-only DSNs.
- Test/runtime variables (used by tests/scripts; not overriding server pgvector settings):
  - `PGVECTOR_HOST`: Postgres host (default `localhost`).
  - `PGVECTOR_PORT`: Postgres port (default `5432`).
  - `PGVECTOR_DATABASE`: Database name (default `postgres`).
  - `PGVECTOR_USER`: Username (default `postgres`).
  - `PGVECTOR_PASSWORD`: Password (no default).
  - `PGVECTOR_SSLMODE`: SSL mode (default `prefer`).
  - `PGVECTOR_DSN`: Optional DSN string.
  - `PGVECTOR_POOL_SIZE`: Optional connection pool size (default `5`).
  - `PGVECTOR_HNSW_EF_SEARCH`: Optional session `ef_search` for HNSW queries (default `64`).

Quick start (local dev):
- `docker-compose -f docker-compose.pg.yml up -d` to start Postgres with pgvector.
- Set `RAG.vector_store_type=pgvector` and either `PGVECTOR_DSN` or the discrete `PGVECTOR_*` vars.
- Vector Store API (`/api/v1/vector_stores`) and the embeddings storage worker will use pgvector when configured.

## LLM Provider Keys
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `COHERE_API_KEY`, `DEEPSEEK_API_KEY`, `GOOGLE_API_KEY`, `GROQ_API_KEY`, `HUGGINGFACE_API_KEY`, `MISTRAL_API_KEY`, `OPENROUTER_API_KEY`, `QWEN_API_KEY`
- Additional provider-specific variables as required by their APIs.

## MCP Unified
- `MCP_JWT_SECRET`: Secret used by the MCP server for issuing/verifying tokens.
- `MCP_API_KEY_SALT`: Salt used for API key hashing/derivation.
- `MCP_LOG_LEVEL`: MCP module log level (`DEBUG|INFO|WARNING|ERROR`).

## OCR - POINTS Reader (optional)
- `POINTS_MODE`: `sglang` or `transformers` (default: auto).
- `POINTS_SGLANG_URL`: SGLang chat/completions endpoint (e.g., `http://127.0.0.1:8081/v1/chat/completions`).
- `POINTS_SGLANG_MODEL`: Model name in SGLang server (e.g., `WePoints`).

## Scheduler
- `SCHEDULER_DATABASE_URL`: Database URL for the core task scheduler. Defaults to `sqlite:///PROJECT_ROOT/Databases/scheduler.db` (test mode uses a per-process temp file). Set this to place the scheduler DB alongside other DBs.
- `SCHEDULER_BASE_PATH`: Base path for the scheduler’s payload storage. Defaults to `PROJECT_ROOT/Databases/scheduler`.
- `WORKFLOWS_SCHEDULER_DATABASE_URL`: Optional override for the Workflows Scheduler (cron) persistence; if using SQLite and not set, it defaults to the per-user path under `USER_DB_BASE_DIR/<user_id>/workflows/workflows_scheduler.db`.
- `WORKFLOWS_SCHEDULER_RESCAN_SEC`: Interval (seconds) for the Workflows Scheduler to rescan all users for new/removed schedules. Default: `600`.
- `POINTS_MODEL_PATH`: HF model path when running locally (e.g., `tencent/POINTS-Reader`).
- `POINTS_PROMPT`: Optional prompt override.

## Notes
- Many subsystems also support file-based configuration under `Config_Files/` and module-specific YAML files (e.g., TTS provider config). Environment variables always take precedence when present.

## Telemetry & Observability

- OpenTelemetry service identity
  - `OTEL_SERVICE_NAME`: Logical service name (default `tldw_server`).
  - `OTEL_SERVICE_VERSION`: Service version string (default `1.0.0`).
  - `OTEL_SERVICE_NAMESPACE`: Namespace grouping (default `production`).
  - `DEPLOYMENT_ENV`: Deployment environment label (default `development`).

- Exporters and enablement
  - `ENABLE_METRICS`: Enable metrics pipeline (`true|false`, default `true`).
  - `ENABLE_TRACING`: Enable tracing pipeline (`true|false`, default `true`).
  - `ENABLE_OTEL_LOGGING`: Enable OTEL logging integration (`true|false`, default `false`).
  - `OTEL_METRICS_EXPORTER`: Comma list of metrics exporters (`prometheus,console` by default).
  - `OTEL_TRACES_EXPORTER`: Comma list of traces exporters (`console` by default).

- Prometheus (pull/endpoint exporter)
  - `PROMETHEUS_HOST`: Bind host for Prometheus exporter (default `0.0.0.0`).
  - `PROMETHEUS_PORT`: Bind port for Prometheus exporter (default `9090`).

- OTLP (push exporters for traces/metrics)
  - `OTEL_EXPORTER_OTLP_ENDPOINT`: e.g., `http://otel-collector:4317`.
  - `OTEL_EXPORTER_OTLP_PROTOCOL`: `grpc` or `http/protobuf` (default `grpc`).
  - `OTEL_EXPORTER_OTLP_HEADERS`: Optional headers (e.g., `authorization=Bearer <token>`).
  - `OTEL_EXPORTER_OTLP_INSECURE`: Allow insecure transport (`true|false`, default `true`).

Notes
- Metrics/OTEL wiring is initialized in the server; see `tldw_Server_API/app/core/Metrics/telemetry.py` for defaults.
- When `OTEL_METRICS_EXPORTER` includes `prometheus`, the server exposes a scrape endpoint consumed by Prometheus; the port/host are controlled by `PROMETHEUS_*` above.

### Quick Defaults

| Variable                        | Default             | Notes |
|---------------------------------|---------------------|-------|
| `OTEL_SERVICE_NAME`             | `tldw_server`       | Logical service name |
| `OTEL_SERVICE_VERSION`          | `1.0.0`             | Freeform version string |
| `OTEL_SERVICE_NAMESPACE`        | `production`        | Logical namespace/group |
| `DEPLOYMENT_ENV`                | `development`       | Environment label |
| `ENABLE_METRICS`                | `true`              | Enable metrics pipeline |
| `ENABLE_TRACING`                | `true`              | Enable tracing pipeline |
| `ENABLE_OTEL_LOGGING`           | `false`             | Enable OTEL logging integration |
| `OTEL_METRICS_EXPORTER`         | `prometheus,console`| Comma-separated exporters |
| `OTEL_TRACES_EXPORTER`          | `console`           | Comma-separated exporters |
| `PROMETHEUS_HOST`               | `0.0.0.0`           | Bind host for Prometheus exporter |
| `PROMETHEUS_PORT`               | `9090`              | Bind port for Prometheus exporter |
| `OTEL_EXPORTER_OTLP_ENDPOINT`   | (empty)             | e.g., `http://otel-collector:4317` |
| `OTEL_EXPORTER_OTLP_PROTOCOL`   | `grpc`              | `grpc` or `http/protobuf` |
| `OTEL_EXPORTER_OTLP_HEADERS`    | (empty)             | Optional headers string |
| `OTEL_EXPORTER_OTLP_INSECURE`   | `true`              | Allow insecure transport |

## Prometheus & Grafana (deployment)

- Grafana container (see compose service `grafana`)
  - `GF_SECURITY_ADMIN_USER`: Admin user (default `admin` in samples).
  - `GF_SECURITY_ADMIN_PASSWORD`: Admin password (default `admin` in samples; change in production).
  - `GF_AUTH_ANONYMOUS_ENABLED`: Enable anonymous access (`true|false`).
  - `GF_AUTH_ANONYMOUS_ORG_ROLE`: Role for anonymous users (e.g., `Viewer`).
  - `GF_PLUGINS_PREINSTALL`: Optional list of plugins to preinstall (preferred over deprecated `GF_INSTALL_PLUGINS`).

- Prometheus container
  - Configured via mounted `prometheus.yml`; see `tldw_Server_API/Config_Files/prometheus.yml` (sample provided).
  - No mandatory env vars by default; override scrape targets in the YAML.

Dashboards/Alerts/Annotations
- Dashboards are provisioned from `Docs/Deployment/Monitoring/` (mounted to `/var/lib/grafana/dashboards`).
- Alerts are provisioned from `Docs/Deployment/Monitoring/Alerts` (mounted to `/etc/grafana/provisioning/alerting`).
- A sample Prometheus-backed annotations source is provisioned from `Samples/Grafana/provisioning/annotations/deploys.yml`.
  - Push a metric like `tldw_deploy_info{version="vX.Y.Z",git_sha="..."} 1` at deploy time to see release markers.

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

## Watchlists Module
- `WATCHLIST_OUTPUT_DEFAULT_TTL_SECONDS`: Default retention (seconds) applied to persisted outputs. `0` keeps outputs indefinitely. Defaults to `0`.
- `WATCHLIST_OUTPUT_TEMP_TTL_SECONDS`: Retention (seconds) for temporary outputs (`temporary=true`). Defaults to `86400` (24h).
- `WATCHLIST_TEMPLATE_DIR`: Override directory for watchlist templates (defaults to `Config_Files/templates/watchlists`).
- `EMAIL_PROVIDER`: Delivery backend for NotificationsService (`mock`, `smtp`, ...). Defaults to `mock` for local setups.
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_USE_TLS`: SMTP settings consumed by NotificationsService when `EMAIL_PROVIDER=smtp`.


## Privilege Maps Snapshot Workflow
- `PRIVILEGE_METADATA_VALIDATE_ON_STARTUP`: Defaults to `1`. Set to `0` when running tests that inject a fake privilege service to bypass catalog validation.
- Snapshot guard: CI compares the live privilege route registry (collected at runtime) against `tldw_Server_API/tests/fixtures/privilege_route_registry_snapshot.json`. If the snapshot drifts, CI fails with guidance to rerun `python Helper_Scripts/update_privilege_registry_snapshot.py` and commit the refreshed file. Use this script whenever you intentionally add or modify FastAPI routes or privilege dependencies.
