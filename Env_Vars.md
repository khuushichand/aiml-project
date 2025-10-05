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
