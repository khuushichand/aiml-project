# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to Some kind of Versioning
    
## [Unreleased]

### Changed
- Modularized `/api/v1/media` endpoints into `tldw_Server_API.app.api.v1.endpoints.media.*` while keeping response shapes and status codes backward compatible. The legacy monolith `_legacy_media.py` now acts as a compatibility shim that forwards to core helpers and modular routers.
- Added `TLDW_DISABLE_LEGACY_MEDIA` flag to allow running the server in a legacy-free media mode where `/api/v1/media` behavior is owned entirely by the modular endpoints and core ingestion/persistence helpers.
- NeuTTS TTS provider is now shipped disabled by default and must be explicitly re-enabled via `tldw_Server_API/app/core/TTS/tts_providers_config.yaml` (`enabled: true`) and a service restart. Disabled providers are filtered by the provider manager via `is_provider_enabled()`, so legacy configs that reference NeuTTS will be ignored until you opt in again.

### Removed
- Deleted unused legacy-only helpers from `_legacy_media.py` (`parse_advanced_query`, `_claims_extraction_enabled`, `_resolve_claims_parameters`, `_prepare_claims_chunks`, `_single_pdf_worker`) after auditing that no modular endpoints, core ingestion helpers, or tests import them directly.
- Retired legacy-only implementations `_legacy_media._process_batch_media` and `_legacy_media._add_media_impl`; these names now resolve to thin shims that delegate to core ingestion/persistence helpers and the modular `/api/v1/media` endpoints.
- Removed the remaining `_process_batch_media` / `_add_media_impl` aliases from `_legacy_media.py`; callers must use core persistence helpers and modular endpoints.

### Deprecated
- Character Chat legacy completion endpoint `POST /api/v1/chats/{chat_id}/complete` is deprecated.
  - The request body is no longer supported. Non-empty bodies now return `422 Unprocessable Entity`.
  - The route is marked `deprecated` in the OpenAPI schema and returns deprecation headers (`Deprecation: true`, `Sunset`, `Link` to successor endpoint).
  - Successor endpoints:
    - `POST /api/v1/chats/{chat_id}/complete-v2` for execution (with optional persistence/streaming).
    - `POST /api/v1/chats/{chat_id}/completions` to prepare messages for `/api/v1/chat/completions`.

### Fixed
- Kokoro double output bug.

### Notes for Operators
- If clients still post bodies to the legacy endpoint, they will start receiving `422` after this change. Migrate clients to the successor endpoints above.
- If you previously used NeuTTS, search your configuration (for example `config.txt`, environment variables, or overrides) for `neutts` / `neutts-air`, update references as needed, then set `enabled: true` for the NeuTTS entry in `tldw_Server_API/app/core/TTS/tts_providers_config.yaml` and restart the server to restore NeuTTS behavior.


## [0.1.6] - 2025-11-14
### Fixed 
- HTTP-redirect loop
- test bugs

### Added
- Option for HTTP redirect adherence in media ingestion endpoints added in config.txt


## [0.1.5] - 2025-11-13
### Fixed 
- Ollama API system_prompt
- Other stuff

### Added
- Updated WebUI
- Added PRD/initial work for cli installer/setup wizard
  - Auto-title notes
- Notes Graph CRUD
- Documentation/PRDs
- (From Gemini) New Chatbook Tools: Implemented a suite of new tools for Chatbooks, including sandboxed template variables for dynamic content in chat dictionary replacements, user-invoked slash commands (e.g., /time, /weather) for pre-LLM context enrichment, and a comprehensive dictionary validation tool (CLI and API) to lint schemas, regexes, and template syntax.


## [0.1.4] - 2025-11-9
### Fixed 
- Numpy requirement in base install
- Default API now respected via config/not just ENV var.
- Too many issues to count.

### Added
- Unified requests module
- Added Resource governance module
- Moved all streaming requests to a unified pipeline (will need to revisit)
- WebUI CSP-related stuff
- Available models loaded/checked from `model_pricing.json`
- Rewrote TTS install/setup scripts (all TTS modules are likely currently broken)


## [0.1.3.0] - 2025-X
### Fixed 
- Bugfixes
- 

## [0.1.2.0] - 2025-X
### Fixed 
- Bugfixes


## [0.1.1.0] - 2025-X
### Features
- Version 0.1
### Fixed 
- Use of gradio
