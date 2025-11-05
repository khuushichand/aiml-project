# Config Normalization PRD (Targeted)

Status: Proposal ready for implementation
Owner: Core Maintainers
Target Release: 0.2.x

## 1. Summary
Normalize configuration across rate limiting, embeddings, and audio quota by introducing one typed settings object per domain. Replace ad-hoc env/config parsing with a Pydantic Settings façade layered over `tldw_Server_API/app/core/config.py`. Standardize testing via a single `TEST_MODE` switch and unified defaults while retaining backward compatibility for legacy keys.

## 2. Problem Statement
Multiple modules parse environment variables and `config.txt` independently with custom fallbacks and test overrides, creating drift and brittleness.
- Duplicated logic exists at:
  - `tldw_Server_API/app/core/Chat/rate_limiter.py:270`
  - `tldw_Server_API/app/core/Embeddings/rate_limiter.py:246`
  - `tldw_Server_API/app/core/Usage/audio_quota.py:281`
- A central adapter exists (`tldw_Server_API/app/core/config.py:1`) but is not the single source of truth.

Consequences: inconsistent precedence rules, scattered defaults, harder testing, and noisy diffs when adding new options.

## 3. Goals & Success Criteria
- One typed settings object per domain (RateLimits, Embeddings, AudioQuota, Common).
- Single precedence order everywhere: environment → config file → hardcoded defaults.
- Standardize test behavior with `TLDW_TEST_MODE=1` and domain‑specific test defaults.
- Backward compatibility for existing env names and config keys via aliases.
- Reduce code duplication and improve readability, validation, and startup diagnostics.

**Success Metrics**
- Reduced config-related test flakiness and fewer env mutations in tests.
- Removal of duplicated parsing blocks in the three target modules.
- Clear startup logs showing effective settings and sources (env/config/default).

## 4. Out of Scope (v1)
- Global refactor of all configuration domains (LLM providers, RAG, MCP, TTS globals).
- Changing default values beyond achieving current behavior parity (except test flag normalization).
- Introducing new external configuration stores or secret managers.

## 5. Personas & Use Cases
- Developer: Instantiates one settings object per domain; never re‑implements parsing.
- QA/CI: Sets `TLDW_TEST_MODE=1` and receives stable, test‑friendly defaults.
- Operator: Configures env or `config.txt` once and observes consistent behavior with clear startup logs.

## 6. Scope
### In Scope
- New settings façade package: `tldw_Server_API/app/core/settings/`
- Integration changes within:
  - `tldw_Server_API/app/core/Chat/rate_limiter.py`
  - `tldw_Server_API/app/core/Embeddings/rate_limiter.py`
  - `tldw_Server_API/app/core/Usage/audio_quota.py`
- Minimal adapter updates in `tldw_Server_API/app/core/config.py` to support lookups.

### Out of Scope (follow‑ups)
- LLM provider settings, RAG, MCP, TTS global settings.

## 7. Functional Requirements
- Common settings
  - `CommonSettings`: `test_mode` from `TLDW_TEST_MODE`, `environment` from `TLDW_ENV`.
- Rate limits
  - `RateLimitSettings`: `chat_rpm`, `chat_tpm`, `chat_burst`, `chat_concurrency`, `enabled`.
  - Preferred env keys: `TLDW_RATE_CHAT_RPM`, `TLDW_RATE_CHAT_TPM`, `TLDW_RATE_CHAT_BURST`, `TLDW_RATE_CHAT_CONCURRENCY`, `TLDW_RATE_ENABLED`.
  - Legacy aliases for any existing `TEST_*` and current names used in the code.
- Embeddings
  - `EmbeddingSettings`: `provider`, `model`, `rpm`, `max_batch`, `concurrency`, `dims`.
  - Env keys: `TLDW_EMB_PROVIDER`, `TLDW_EMB_MODEL`, `TLDW_EMB_RPM`, `TLDW_EMB_MAX_BATCH`, `TLDW_EMB_CONCURRENCY`, `TLDW_EMB_DIMS`.
- Audio quota
  - `AudioQuotaSettings`: `max_seconds_per_day`, `window_days`, `per_user`, `enabled`.
  - Env keys: `TLDW_AUDIO_QUOTA_SECONDS_DAILY`, `TLDW_AUDIO_QUOTA_WINDOW_DAYS`, `TLDW_AUDIO_QUOTA_PER_USER`, `TLDW_AUDIO_QUOTA_ENABLED`.
- Precedence
  - Environment → `config.py` adapter (reads `config.txt`) → hardcoded defaults.
- Validation
  - Reject invalid ranges (negative RPM/TPM, zero window); return clear errors.
- Test mode
  - If `test_mode` and a value is unspecified, apply current test‑friendly defaults per domain.
- Dependency Injection
  - FastAPI providers: `get_rate_limit_settings()`, `get_embedding_settings()`, `get_audio_quota_settings()`.
  - Optional constructor injection for unit tests to avoid env mutation.
- Observability
  - Log effective settings at startup (redacted secrets), including source markers `[env|config|default]`.

## 8. Non‑Functional Requirements
- Backward-compatible defaults; no material behavior changes for existing deployments.
- Minimal overhead; settings load once and are cached for reuse.
- Consistent error messages and Loguru logging.

## 9. Design Overview
- Package layout
  - `tldw_Server_API/app/core/settings/base.py` – shared mixins; source tagging; adapter to `config.py`.
  - `tldw_Server_API/app/core/settings/common.py` – `CommonSettings`.
  - `tldw_Server_API/app/core/settings/rate_limits.py` – `RateLimitSettings`.
  - `tldw_Server_API/app/core/settings/embeddings.py` – `EmbeddingSettings`.
  - `tldw_Server_API/app/core/settings/audio_quota.py` – `AudioQuotaSettings`.
- Façade behavior
  - Pydantic `BaseSettings` classes read env with aliases; fallback to a `config.py` adapter for `[RateLimits]`, `[Embeddings]`, `[Audio-Quota]` sections; otherwise defaults.
  - Merge logic applies precedence and captures source for logging.
- Dependency injection
  - Singleton instances resolved at app startup; overridable in tests via fixtures.

## 10. Data Model
- In-memory Pydantic models; no new DB schema.
- Helper: `ConfigSourceAdapter` for section/key access via `config.py`.
- Merge function to compute final effective settings per domain with per‑field source metadata.

## 11. APIs & Interfaces
- FastAPI dependency providers returning domain settings singletons.
- Optional (debug): authenticated endpoint to inspect effective config: `/api/v1/config/effective` (redacted).

## 12. Implementation Phases
1. Scaffold settings package and `config.py` adapter; add DI providers. Optional feature flag `TLDW_SETTINGS_V1=1`.
2. Integrate three target modules to consume settings via DI/constructor args; remove local parsing blocks.
3. Cleanup: delete dead code and finalize aliases; update docs/examples.

## 13. Migration & Rollout
- Default to new settings; retain legacy env names via field aliases.
- During soak, log effective values clearly; if needed, temporarily gate via `TLDW_SETTINGS_V1`.
- Later minor release removes deprecated env names and parsing remnants.

## 14. Risks & Mitigations
- Silent behavior drift from defaults → add parity tests; dual logging during rollout.
- Env name collisions → use `TLDW_*` namespace; keep explicit legacy aliases.
- Test brittleness from env reliance → prefer injected settings fixtures; minimize env mutation.

## 15. Dependencies & Assumptions
- Pydantic available in the project environment.
- `tldw_Server_API/app/core/config.py` remains the adapter for `config.txt`.
- Existing defaults in the three modules are the source of truth for parity.

## 16. Acceptance Criteria
- Target modules fetch all configuration via typed settings; no ad‑hoc env parsing remains.
- `TLDW_TEST_MODE=1` yields consistent test defaults across domains.
- Precedence (env → config → default) verified by tests.
- Startup logs show effective settings with sources; sensitive values redacted.
- Unit and integration tests pass with no behavioral regressions.

## 17. Testing Plan
- Unit tests (per settings class): precedence resolution, alias handling, validation errors, test‑mode defaults.
- Integration tests: ensure Chat limiter, Embeddings limiter, and Audio quota behavior is unchanged under representative env/config permutations.
- Fixtures: `settings_override` to inject domain instances in tests without env pollution.
- Coverage: include in `python -m pytest --cov=tldw_Server_API --cov-report=term-missing`.

## 18. Timeline (Estimate)
- Design + scaffolding: 0.5 day
- Implement settings + adapters: 0.5 day
- Integrate 3 modules and remove duplication: 0.5–1 day
- Tests + docs: 0.5–1 day
- Total: 2–3 days

## 19. Open Questions
- Enumerate all legacy env keys in use for alias mapping (audit required).
- Confirm test‑mode default semantics (unlimited vs large but finite rates) with QA.
- Need per‑provider embeddings rate limits now, or defer?
- Include an authenticated endpoint to expose effective config, or keep logs only?

## 20. References
- Central config adapter: `tldw_Server_API/app/core/config.py`
- Duplicated parsing locations:
  - `tldw_Server_API/app/core/Chat/rate_limiter.py:270`
  - `tldw_Server_API/app/core/Embeddings/rate_limiter.py:246`
  - `tldw_Server_API/app/core/Usage/audio_quota.py:281`
- Related design doc: `Docs/Design/Resource_Governor_PRD.md`
