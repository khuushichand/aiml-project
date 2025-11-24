# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to Some kind of Versioning
    
## [Unreleased]

### Changed

### Removed

### Fixed



## [0.1.8] - 2025-11-22

### Added
- Auto-streaming for large audit exports exceeding configured threshold
- CSV streaming support for audit exports
- Model discovery for local LLM endpoints
- Audit event replay mechanism for failed exports
- Enhanced HTTP error handling for DNS resolution failures
- SuperSonicTTS support + setup script

### Changed
- Audio:
  - Replace Parakeet-specific transcriber/config usage with unified UnifiedStreamingTranscriber/UnifiedStreamingConfig; add _LegacyWebSocketAdapter to adapt legacy WS to unified handler; defer imports and update tests to use unified stubs.
- Audit:
  - Add config-driven auto-stream threshold, support streaming for json/jsonl/csv, force streaming when max_rows exceeds threshold; CSV streaming generator; non-stream export caps; API-key hashing; fallback JSONL queue with background replay task; tests for streaming and replay.
- LLM:
  - Add local model discovery (short timeouts, TTL cache, candidate endpoints), get_configured_providers_async and integrate async provider loading into startup and web UI config; provider payloads include is_configured and endpoint_only.
- TTS
  - WAV output now buffered and deferred until finalize with in-memory threshold and disk spill; StreamingAudioWriter.__init__ adds max_in_memory_bytes; tests validate spill and finalize behavior.
- Web Scraping
  - Use defusedxml, broaden sitemap parse error handling, add test-mode egress bypass, add conditional process_web_scraping_task import/export, and preserve HTTPException semantics in ingestion endpoint.
- Tests
  - Extensive test updates (unified WS stub, fake HTTP client for RSS, env snapshot/restore, admin override fixtures, watchlists full-app fixture, connectors pre-mounting); CI embedding cache key changed to a static key.

### Removed
- Hopes, Dreams.

### Deprecated
- Efficiency.

### Fixed
- Improved WebSocket disconnect handling
- Consistent error handling in session cleanup and web ingestion
- Better network error resilience with graceful fallbacks
- Add _is_dns_resolution_error detection and mark DNS resolution errors non-retriable (DNSResolutionError signal); tests verify DNS errors are not retried while other network errors follow retry policy.
- My life.


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
