# Config Files Overview

This document explains the purpose and usage of settings in `Config_Files/config.txt`.
It is the single source of truth for server/runtime configuration. Values are read
at startup by the backend and, for some modules, re-read on demand.

Conventions
- All keys belong to an INI section like `[Chunking]`.
- Booleans: `true|false` (case-insensitive). Integers/floats are unquoted.
- Paths are relative to the repo root unless noted.
- Secrets should be supplied via `.env` where indicated; do not commit secrets.

How to apply changes
- Edit `tldw_Server_API/Config_Files/config.txt` and restart the server.
- Some modules cache settings at import; prefer restart after edits.

---

## Diagnostics
- Admin network diagnostics endpoint: `GET /api/v1/admin/network-info`
  - Returns resolved client IP, proxy headers used, and access decisions for WebUI/Setup based on toggles and IP lists.
  - Requires admin role. Useful when configuring `trusted_proxies`, allow/deny lists, or remote toggles.

## [Setup]
- `enable_first_time_setup` (bool): Allow interactive/setup workflows on first run.
- `setup_completed` (bool): Marks setup completed to suppress guided flows.
- `allow_remote_setup_access` (bool): If true, allows setup API from non-localhost.
 - `setup_ip_allowlist` (csv): Optional IPs/CIDRs allowed to access `/setup` remotely.
   - Env override: `TLDW_SETUP_ALLOWLIST="203.0.113.0/24"`
 - `setup_ip_denylist` (csv): Optional IPs/CIDRs to explicitly block from `/setup`.
   - Env override: `TLDW_SETUP_DENYLIST="0.0.0.0/0"`

## [Server]
- `disable_cors` (bool): Disable CORS protections for development.
- `allow_remote_webui_access` (bool): Allow remote clients (non-localhost) to load `/webui`.
  - Security: Only enable on trusted networks and with proper auth. When enabled, run the server
    listening on a public interface (e.g., `uvicorn ... --host 0.0.0.0`).
  - Env override: set `TLDW_WEBUI_ALLOW_REMOTE=1` (or `WEBUI_ALLOW_REMOTE=1`).
 - `webui_ip_allowlist` (csv): Optional IPs/CIDRs allowed to access `/webui` remotely.
   - Examples: `192.168.1.0/24, 10.0.0.5, 2001:db8::/32`
   - Env override: `TLDW_WEBUI_ALLOWLIST="192.168.1.0/24,10.0.0.5"`
 - `webui_ip_denylist` (csv): Optional IPs/CIDRs to explicitly block from `/webui`.
   - Env override: `TLDW_WEBUI_DENYLIST="203.0.113.4,198.51.100.0/24"`
 - `trusted_proxies` (csv): Proxy IPs/CIDRs trusted for X-Forwarded-For/X-Real-IP processing.
   - If the socket peer is in this list, the server uses the leftmost X-Forwarded-For IP as the client.
   - Env override: `TLDW_TRUSTED_PROXIES="10.0.0.0/8,192.168.0.0/16,127.0.0.1"`

## [Processing]
- `processing_choice` (str): Hardware backend, e.g., `cuda|cpu` for ML pipelines.

## [Media-Processing]
- `max_audio_file_size_mb` (int): Max upload size for audio files.
- `max_pdf_file_size_mb` (int): Max upload size for PDFs.
- `max_video_file_size_mb` (int): Max upload size for videos.
- `max_epub_file_size_mb` (int): Max upload size for EPUB.
- `max_document_file_size_mb` (int): Max upload size for generic docs.
- `pdf_conversion_timeout_seconds` (int): Timeout for PDF conversion.
- `audio_processing_timeout_seconds` (int): Timeout for audio processing.
- `video_processing_timeout_seconds` (int): Timeout for video processing.
- `max_archive_internal_files` (int): Max files extracted from archives.
- `max_archive_uncompressed_size_mb` (int): Max total uncompressed archive size.
- `audio_transcription_buffer_size_mb` (int): Buffer budget for streaming STT.
- `uuid_generation_length` (int): Default short UUID length used in DBs/exports.
- `kept_video_max_files` (int): Retention: count of video temp files.
- `kept_video_max_storage_mb` (int): Retention: MB cap for video temp files.
- `kept_video_retention_hours` (int): Retention: age cap for video temp files.

## [Chat-Dictionaries]
- `enable_chat_dictionaries` (bool): Enable dictionary-based post-gen editing.
- `post_gen_replacement` (bool): Apply post generation replacement list.
- `post_gen_replacement_dict` (path): Markdown file with replacements.
- `chat_dictionary_chat_prompts` (path): Prompt dictionary for chat.
- `chat_dictionary_RAG_prompts` (path): Prompt dictionary for RAG.
- `strategy` (str): Application strategy, e.g., `character_lore_first`.
- `max_tokens` (int): Size cap for dictionary-injected content.
- `default_rag_prompt` (str): Name of default system prompt for RAG.

## [Chat-Module]
- `enable_provider_fallback` (bool): Allow fallback to alt provider on failure.
- `max_base64_image_size_mb` (int): Per-image Base64 size limit.
- `max_text_length_per_message` (int): Characters per user message.
- `max_messages_per_request` (int): Limit messages per API call.
- `max_images_per_request` (int): Max images per API call.
- `max_request_size_bytes` (int): Hard payload cap for requests.
- `streaming_idle_timeout_seconds` (int): Idle WS timeout for streaming.
- `streaming_heartbeat_interval_seconds` (int): Ping interval for streaming.
- `streaming_max_response_size_mb` (int): Max streamed response size.
- `chat_save_default` (bool): Default persistence for conversations.
- `conversation_creation_max_retries` (int)
- `db_transaction_max_retries` (int)
- `rate_limit_per_minute` (int): Global rate per client.
- `rate_limit_per_conversation_per_minute` (int): Per-conversation rate.
- `history_messages_limit` (int): History window size for context (1-500).
- `history_messages_order` (str): `asc|desc` ordering of loaded history.

## [Character-Chat]
- `CHARACTER_RATE_LIMIT_OPS` (int): Ops allowed per window.
- `CHARACTER_RATE_LIMIT_WINDOW` (int sec): Window size in seconds.
- `MAX_CHARACTERS_PER_USER` (int)
- `MAX_CHARACTER_IMPORT_SIZE_MB` (int)

## [Settings]
- `chunk_duration` (int sec): Media chunk duration for STT.
- `words_per_second` (int): Heuristic for text/audio timing.
- `save_character_chats` (bool)
- `save_rag_chats` (bool)
- `save_video_transcripts` (bool)

## [Auto-Save]
- `save_character_chats` (bool)
- `save_rag_chats` (bool)

## [Prompts]
- `prompt_sample` (str): Example prompt used in demos/tests.
- `video_summarize_prompt` (str): Default summarization prompt.

## [Database]
- `type` (str): `sqlite|postgres|...` DB backend selector.
- `sqlite_path` (path): Main media summary DB when `sqlite`.
- `sqlite_wal_mode` (bool)
- `sqlite_foreign_keys` (bool)
- `backup_path` (path): Backup/export directory.
- `pg_connection_string` (dsn): Single string alternative to fields below.
- `pg_host|pg_port|pg_database|pg_user|pg_password|pg_sslmode` (str): Postgres.
- `pg_pool_size|pg_max_overflow|pg_pool_timeout` (ints/floats): Pool tuning.
- `elasticsearch_host|elasticsearch_port` (str/int): If ES is used.
- `chroma_db_path` (path): ChromaDB path.
- `prompts_db_path|rag_qa_db_path|character_db_path` (path): Other DBs.

## [Chunking]
Global defaults:
- `chunking_method` (str): `words|sentences|paragraphs|tokens|...`.
- `chunk_max_size` (int): Default chunk size (units vary by method).
- `chunk_overlap` (int): Default overlap (units vary by method).
- `adaptive_chunking` (bool): Adaptive window scaling heuristics.
- `chunking_multi_level` (bool): Paragraph-aware multi-level chunking.
- `language` (str): Default language hint.

Operational controls:
- `max_streaming_flush_threshold_chars` (int): Upper bound on stream flush size; 0 disables.
- `json_single_metadata_reference` (bool): Emit one JSON metadata chunk and reference from others.
- `json_metadata_reference_key` (str): Reference field name in JSON chunks.
- `cache_copy_on_access` (bool): Deep-copy cached results (safety) vs direct store (performance).
- `verbose_logging` (bool): Raise chunk creation logs to INFO (otherwise DEBUG).
- `regex_timeout_seconds` (float): Cap regex execution time in `ebook_chapters`.
- `regex_disable_multiprocessing` (bool): Use thread-guarded regex only.
- `regex_simple_only` (bool): Restrict custom chapter regex to safe subset.
- `enable_contextual_retrieval` (bool): Include contextual elements in retrieval.
- `context_window_size` (int): Contextual window for retrieval.
- `include_parent_context` (bool)

Per-media defaults (override global):
For each type in `chunking_types` (`article|audio|book|document|mediawiki_article|mediawiki_dump|obsidian_note|podcast|text|video`) the following are available:
- `<type>_chunking_method` (str)
- `<type>_chunk_max_size` (int)
- `<type>_chunk_overlap` (int)
- `<type>_adaptive_chunking` (bool)
- `<type>_chunking_multi_level` (bool)
- `<type>_language` (str)

## [AuthNZ]
- `auth_mode` (str): `single_user|multi_user`.
- `database_url` (dsn): Auth DB URL; default uses SQLite file.
- `enable_registration` (bool)
- `require_registration_code` (bool)
- `rate_limit_enabled` (bool)
- `rate_limit_per_minute` (int)
- `rate_limit_burst` (int)
- `access_token_expire_minutes` (int)
- `refresh_token_expire_days` (int)

## [Embeddings]
- `embedding_provider` (str): `openai|huggingface|llama|...`.
- `embedding_model` (str): Model id.
- `onnx_model_path|model_dir` (path): Local model locations.
- `embedding_api_url` (url): Custom API endpoint.
- `chunk_size|overlap` (int): Chunking defaults for embeddings.
- `enable_contextual_chunking` (bool)
- `contextual_llm_model` (str)
- `context_window_size` (int|None)
- `context_strategy` (str)
- `context_token_budget` (int)

## [Claims]
- `ENABLE_INGESTION_CLAIMS` (bool): Extract claims during ingestion.
- `CLAIM_EXTRACTOR_MODE` (str): `heuristic|llm|...`.
- `CLAIMS_MAX_PER_CHUNK` (int)
- `CLAIMS_EMBED` (bool)
- `CLAIMS_EMBED_MODEL_ID` (str)
- `CLAIMS_LLM_PROVIDER|CLAIMS_LLM_MODEL` (str)
- `CLAIMS_LLM_TEMPERATURE` (float)
- `CLAIMS_REBUILD_ENABLED` (bool)
- `CLAIMS_REBUILD_INTERVAL_SEC` (int)
- `CLAIMS_REBUILD_POLICY` (str)
- `CLAIMS_STALE_DAYS` (int)
- `contextual_llm_model` (str): Claims pipeline LLM.
- `contextual_chunk_method` (str)
- `trusted_hf_remote_code_models` (csv)
- `max_models_in_memory` (int)
- `max_model_memory_gb` (int)
- `model_lru_ttl_seconds` (int)

## [RAG]
- `vector_store_type` (str): `chromadb|pgvector|...`.
- `pgvector_*` (dsn parts): Host/port/db/user/password/sslmode when used.
- `enable_parent_expansion` (bool) & `parent_expansion_size` (int)
- `include_sibling_chunks` (bool) & `sibling_window` (int)
- `include_parent_document` (bool) & `parent_max_tokens` (int)
- `default_llm_provider|default_llm_model` (str)
- `hyde_provider|hyde_model` (str): HyDE settings.
- `semantic_cache_enabled` (bool) & `cache_similarity_threshold` (float)
- `enable_reranking` (bool) & `rerank_top_k` (int)
- Rerankers: `llm_reranker_*`, `llama_reranker_*`, `transformers_reranker_model` (str)
- Feature flags (phased rollout):
  - `enable_structure_index` (bool)
  - `strict_extractive` (bool)
  - `require_hard_citations` (bool)
  - `low_confidence_behavior` (str): `continue|ask|decline`
  - `agentic_cache_backend` (str): `memory|sqlite`
  - `agentic_cache_ttl_sec` (int)

## [API] (Hosted providers)
For each provider, settings follow the pattern:
- `<provider>_model` (str), `<provider>_streaming` (bool), `<provider>_temperature` (float), `<provider>_top_p|min_p` (float), `<provider>_max_tokens` (int), `<provider>_api_timeout` (int sec), `<provider>_api_retry` (int), `<provider>_api_retry_delay` (int sec)
Providers present: `anthropic, cohere, deepseek, qwen, google, groq, huggingface, mistral, openai, openrouter` and two generic `custom_openai_api`, `custom_openai2_api` blocks.
- `model_for_summarization` (str): Preferred model for summarize endpoints.
- `default_api` (str): Default provider for chat.
- `default_api_for_tasks` (str): Default provider for batch/tools.

## [Local-API]
Local service backends (Kobold, LLaMA, Oobabooga, Tabby, vLLM, Ollama, Aphrodite). Each has similar knobs:
- `<engine>_api_IP` (url)
- `<engine>_model` (str, when applicable)
- `<engine>_streaming` (bool)
- `<engine>_temperature|top_p|min_p|top_k` (floats/ints)
- `<engine>_max_tokens` (int), `<engine>_api_timeout|_api_retry|_api_retry_delay`
Common: `max_tokens`, `local_api_timeout`, `local_api_retries`, `local_api_retry_delay`, `streaming`, `temperature`, `top_p`, `min_p`.

## [STT-Settings]
- `default_transcriber` (str): `faster-whisper|nemo-...|mlx`.
- `nemo_model_variant` (str), `nemo_device` (str), `nemo_cache_dir` (path)
- `nemo_chunk_duration|nemo_overlap_duration` (sec)
- `streaming_fallback_to_whisper` (bool)
- `mlx_chunk_duration|mlx_overlap_duration|buffered_chunk_duration|buffered_total_buffer` (sec)
- `buffered_merge_algo` (str): e.g., `lcs`.

## [external_providers]
- Reserved for plugging in external providers (YAML/INI sub-configs).

## [TTS-Settings]
General and provider-specific:
- `local_tts_device` (str): `cpu|cuda|auto`.
- `default_tts_provider` (str), `default_tts_voice` (str), `default_tts_speed` (float)
OpenAI TTS:
- `default_openai_tts_voice|_speed|_model|_output_format|_streaming`
ElevenLabs TTS (placeholders if not used):
- `default_eleven_tts_*` keys (voice/model/language/tunables)
Google/Edge (placeholders): `default_google_tts_*`, `edge_tts_voice`
AllTalk:
- `default_alltalk_tts_*`, `alltalk_api_ip`
Kokoro (local):
- `kokoro_model_path`, `default_kokoro_tts_*`
Custom OpenAI-compatible TTS:
- `default_custom_openai_*`
VibeVoice:
- `vibevoice_*` keys: variant/model/device/quantization/streaming params/paths

## [Search-Engines]
- `search_provider_default` (str)
- `search_language_query|results|analysis` (str)
- `search_default_max_queries` (int)
- `search_enable_subquery` (bool) & `search_enable_subquery_count_max` (int)
- `search_result_rerank` (bool)
- `search_result_max|search_result_max_per_query` (int)
- `search_result_blacklist` (json/array)
- `search_result_display_type` (str) & `search_result_display_metadata` (bool)
- `search_result_save_to_db` (bool)
- `search_result_analysis_tone` (str)
- Per-engine keys: API keys/IDs/region/language filters and router URLs.

## [Web-Scraper]
- `web_scraper_api_key|web_scraper_api_url` (str)
- `web_scraper_api_timeout|web_scraper_api_retry|web_scraper_api_retry_delay` (int)
- `web_scraper_retry_count` (int)
- `web_scraper_stealth_playwright` (bool)
  - Crawl flags (env overrides file):
    - `web_crawl_strategy` (str) → `WEB_CRAWL_STRATEGY` (default `default`)
    - `web_crawl_include_external` (bool) → `WEB_CRAWL_INCLUDE_EXTERNAL` (default `false`)
    - `web_crawl_score_threshold` (float) → `WEB_CRAWL_SCORE_THRESHOLD` (default `0.0`)
    - `web_crawl_max_pages` (int) → `WEB_CRAWL_MAX_PAGES` (default `100`)
    - `web_crawl_allowed_domains` (csv) → restrict crawl to specific domains (always includes base host when `include_external` is false)
    - `web_crawl_blocked_domains` (csv) → domains to exclude (subdomains included)
  - Scoring (env overrides file):
    - `web_crawl_enable_keyword_scorer` (bool) → `WEB_CRAWL_ENABLE_KEYWORD_SCORER` (default `false`)
    - `web_crawl_keywords` (csv) → `WEB_CRAWL_KEYWORDS` (e.g., `ai,ml,python`)
    - `web_crawl_enable_domain_map` (bool) → `WEB_CRAWL_ENABLE_DOMAIN_MAP` (default `false`)
    - `web_crawl_domain_map` (json or `domain:score` csv) → `WEB_CRAWL_DOMAIN_MAP`
      - Examples: `{"docs.python.org": 1.0, "github.com": 0.8}` or `docs.python.org:1.0,github.com:0.8`
  - Robots policy:
    - `web_scraper_respect_robots` (bool, default `true`): enforce robots.txt for egress-allowed hosts
      - Resolved per-domain with caching; missing robots.txt fails open.
  - Patterns:
    - Default excludes include common non-content paths (e.g., `/tag/`, `/category/`, `wp-content`, images/docs). These are applied internally.
    - Advanced pattern controls can be added via code (see `URLPatternFilter` in `app/core/Web_Scraping/filters.py`).

## [Logging]
- `log_level` (str): `DEBUG|INFO|WARN|ERROR`.
- `log_file` (path), `log_metrics_file` (path)
- `max_bytes` (int|null): log rotation size
- `backup_count` (int): rotated files kept

## [Moderation]
- `enabled` (bool)
- `input_enabled|output_enabled` (bool)
- `input_action|output_action` (str): `block|redact|warn`
- `redact_replacement` (str)
- `blocklist_file|user_overrides_file` (path)
- `per_user_overrides` (bool)
- `pii_enabled` (bool), `categories_enabled` (csv)
- `runtime_overrides_file` (path)

## [Redis]
- `redis_enabled` (bool)
- `redis_host|redis_port|redis_db` (str|int)
- `cache_ttl` (int): default TTL seconds for cached items

## [Web-Scraping]
- `stealth_wait_ms` (int): Delay to allow stealth page prep.

## [personalization]
- `enabled` (bool)
- `alpha|beta|gamma` (floats): Weighting for recommender signals.
- `recency_half_life_days` (int)

## [persona]
- `enabled` (bool)
- `default_persona` (str)
- `voice` (str), `stt` (str): Preferred voice/STT for persona.
- `max_tool_steps` (int)

## [persona.rbac]
- `allow_export` (bool)
- `allow_delete` (bool)

---

Notes
- Some keys are placeholders (`FIXME`); leave empty or set via `.env` when a provider requires credentials.
- When both provider-specific and global keys exist, provider-specific keys take precedence for that provider’s operations.
- For advanced tuning of chunking behavior, see `tldw_Server_API/app/core/Chunking/README.md`.

---

## API Route Toggles

Purpose: allow end users to run only stable API modules and let developers/operators selectively enable in-development endpoints. Route inclusion is evaluated at startup before routers are mounted.

Default behavior
- Stable-only mode is ON by default. A curated set of experimental routes is disabled unless explicitly enabled.
- You can override behavior per route or globally via `config.txt` or environment variables.

Configure in `config.txt`
- Section: `[API-Routes]`
- Keys:
  - `stable_only` (bool, default: true): When true, disables the experimental set unless explicitly enabled.
  - `disable` (csv): Route keys to always disable.
  - `enable` (csv): Route keys to force-enable (useful when `stable_only=true`).
  - `experimental_routes` (csv): Extend the curated experimental set with more route keys.

Environment overrides
- `ROUTES_STABLE_ONLY=true|false`
- `ROUTES_DISABLE="sandbox,connectors"`
- `ROUTES_ENABLE="workflows"`
- `ROUTES_EXPERIMENTAL="workflows,scheduler"`

Known route keys (not exhaustive)
`health, metrics, monitoring, moderation, audit, auth, auth-enhanced, users, privileges, admin, mcp-catalogs, media, audio, audio-jobs, audio-websocket, chat, characters, character-chat-sessions, character-messages, chunking, chunking-templates, outputs-templates, outputs, embeddings, vector-stores, connectors, claims, media-embeddings, items, reading, watchlists, subscriptions-deprecated, notes, prompts, reading-highlights, prompt-studio, rag-health, rag-unified, workflows, scheduler, research, paper-search, evaluations, ocr, vlm, benchmarks, setup, config, jobs, sync, tools, sandbox, flashcards, personalization, persona, mcp-unified, chatbooks, llm, llamacpp, web-scraping, webui`

Curated experimental set (gated by `stable_only=true` unless explicitly enabled)
`sandbox, connectors, workflows, scheduler, flashcards, personalization, persona, jobs, benchmarks`

Examples
- Run stable-only with workflows enabled:
  - `stable_only = true`
  - `enable = workflows`
- Disable web-scraping and connectors regardless of `stable_only`:
  - `disable = web-scraping, connectors`

Notes
- Control-plane endpoints are also gated:
  - `metrics` key: gates both `/metrics` (Prometheus text) and `/api/v1/metrics` (JSON).
  - `health` key: gates `/health`, `/ready`, and `/health/ready`, as well as health routers (`/healthz`, `/readyz`).
  - `webui` key: gates the WebUI static mount (`/webui`) and `/webui/config.json`.
  - `setup` key: gates the Setup UI (`/setup`) and the setup API routes; root (`/`) only redirects to `/setup` when this key is enabled and setup is required.
