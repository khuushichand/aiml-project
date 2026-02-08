# Provider Registry Unification PRD

Status: Draft
Owner: Core Maintainers
Target Release: 0.2.x

## 1. Summary
Create a shared provider registry base so LLM, TTS, and STT provider registries reuse one implementation for adapter resolution, capability discovery, availability tracking, and default selection. This collapses duplicate registry logic while preserving domain-specific adapter interfaces.

## 2. Problem Statement
Provider registries are implemented independently with overlapping behavior:
- LLM adapter registry (lazy dotted-path resolution): `tldw_Server_API/app/core/LLM_Calls/adapter_registry.py`
- TTS adapter registry (lazy import, failure tracking, config injection): `tldw_Server_API/app/core/TTS/adapter_registry.py`
- STT provider registry (static adapter map + name normalization): `tldw_Server_API/app/core/Ingestion_Media_Processing/Audio/stt_provider_adapter.py`

Each registry maintains its own name normalization, adapter caching, and capability discovery. This duplication slows down new provider onboarding and increases drift risk.

## 3. Unifying Principle (Simplification Cascade)
All providers are adapters with capabilities; a single registry base should manage adapter lookup, caching, and availability for every domain. Domain-specific behavior belongs in adapters, not in bespoke registries.

**Expected deletions**: duplicate registry logic in LLM, TTS, and STT; multiple name-normalization helpers; redundant capability-listing paths.

## 4. Goals & Success Criteria
- One shared registry base in Infrastructure.
- Domain registries become thin wrappers that supply adapter classes and config.
- Consistent provider name normalization and availability semantics.
- Simplified capability listing and introspection endpoints.

Success metrics:
- LLM, TTS, and STT registries delegate to the shared base.
- New provider onboarding requires adapter-only changes (no registry edits beyond registration).

## 5. Non-Goals
- Changing adapter contracts (LLM/TTS/STT adapters keep their domain-specific interfaces).
- Reworking configuration precedence or adding new config files.
- Embeddings provider selection (explicitly out of scope for this PRD).

## 6. In Scope
- New shared registry base module in Infrastructure.
- Migration of LLM, TTS, and STT registries to the base.
- Unified capability listing contracts (per domain).

## 7. Out of Scope
- Provider-specific HTTP client changes.
- UI changes.

## 8. Functional Requirements
### 8.1 Shared Registry Base
Provide a `ProviderRegistryBase` with:
- Adapter registration via class, instance, or dotted-path string.
- Lazy adapter initialization with caching.
- Failure tracking with configurable retry backoff (for TTS parity).
- Provider availability status (`enabled`, `failed`, `disabled`, `unknown`).
- Consistent name normalization and alias mapping hooks.
- Capability discovery with error isolation (capability failure does not crash registry).

### 8.2 Domain-Specific Wrappers
- LLM registry remains responsible for `ChatProvider`-specific behavior.
- TTS registry remains responsible for TTS adapter config and voice capabilities.
- STT registry remains responsible for STT provider selection logic.
- Each wrapper supplies its own adapter base class and capability shape.

### 8.3 Configuration Integration
- Registries accept a config adapter callback so each domain can load settings from its existing config source.
- No changes to config precedence.

### 8.4 Capability Listing
- Each domain exposes a standard `list_capabilities()` method that returns:
  - provider name
  - availability
  - capability metadata

## 9. Design Overview
### 9.1 Location
- `tldw_Server_API/app/core/Infrastructure/provider_registry.py`

### 9.2 Base Types
- `ProviderStatus` enum (enabled/disabled/failed/unknown).
- `ProviderRegistryBase` with registration, normalization, caching, and status tracking.
- Optional `ProviderRegistryConfig` for retry/backoff settings.

### 9.3 Domain Integration
- LLM registry wraps `ProviderRegistryBase` and exposes `ChatProvider` adapters.
- TTS registry wraps `ProviderRegistryBase` and plugs in existing config defaults (auto-download, device, etc.).
- STT registry wraps `ProviderRegistryBase` and keeps model-to-provider resolution logic.

### 9.4 Related Work
- This PRD complements the LLM Adapter Registry Migration (`Docs/Product/LLM_Adapter_Registry_Migration_PRD.md`) by providing shared registry infrastructure, not changing the LLM adapter contract.

## 10. Migration Plan
### Phase 0: Base Registry Implementation
- Implement `ProviderRegistryBase` with caching, normalization, and failure tracking.

### Phase 1: LLM Registry Migration
- Rebuild LLM registry on top of the base without changing adapter behavior.

### Phase 2: TTS Registry Migration
- Move TTS registry to the base, preserving config loading and failure backoff semantics.

### Phase 3: STT Registry Migration
- Replace STT registry internals with the base while keeping model resolution.

### Phase 4: Cleanup
- Remove duplicate registry helpers and normalize provider naming across domains.

## 11. Risks & Mitigations
- Risk: Different capability formats across domains.
  - Mitigation: keep domain-specific capability shapes and only standardize metadata envelope.
- Risk: TTS failure backoff semantics change.
  - Mitigation: encode TTS backoff settings in the base config and add parity tests.

## 12. Testing Plan
- Unit tests for base registry adapter resolution and caching.
- Domain-specific tests to validate registry behavior parity.
- Capability listing tests for each domain.

## 13. Acceptance Criteria
- LLM, TTS, and STT registries are thin wrappers over the shared base.
- Provider naming is normalized consistently.
- Capability listing endpoints share a common envelope across domains.

## 14. Open Questions
- Should the base registry live under Infrastructure or a new Providers package?

## 15. Requirement-by-Requirement Implementation Checklist
Current assessment date: 2026-02-08
Current implementation status: Partially implemented (R1-R11 complete; R12-R15 still pending)

Use this as the execution tracker for this PRD. Mark each item complete only when code, tests, and API behavior are all verified.

| ID | Requirement (from this PRD) | Concrete Implementation Tasks | Target Files (create/update) | Tests (create/update) | Status |
| --- | --- | --- | --- | --- | --- |
| R1 | Shared `ProviderRegistryBase` exists in Infrastructure (Sections 8.1, 9.1) | Create shared base module with registry core, config object, and public API. | `tldw_Server_API/app/core/Infrastructure/provider_registry.py` (new), `tldw_Server_API/app/core/Infrastructure/__init__.py` | `tldw_Server_API/tests/Infrastructure/test_provider_registry_base.py` (new) | [x] |
| R2 | Registration supports class, instance, dotted-path string (Section 8.1) | Implement `register_adapter()` and resolver that accepts all 3 forms and validates adapter type via wrapper hook. | `tldw_Server_API/app/core/Infrastructure/provider_registry.py` | `tldw_Server_API/tests/Infrastructure/test_provider_registry_base.py` | [x] |
| R3 | Lazy initialization with caching (Section 8.1) | Implement lazy materialization and adapter instance cache with cache invalidation on re-register. | `tldw_Server_API/app/core/Infrastructure/provider_registry.py` | `tldw_Server_API/tests/Infrastructure/test_provider_registry_base.py` | [x] |
| R4 | Failure tracking + retry backoff parity (Section 8.1) | Implement failed-provider tracking, retry timestamps, configurable retry window, and "retry disabled" mode. | `tldw_Server_API/app/core/Infrastructure/provider_registry.py` | `tldw_Server_API/tests/Infrastructure/test_provider_registry_backoff.py` (new), `tldw_Server_API/tests/TTS/*` parity tests | [x] |
| R5 | Unified provider availability statuses (`enabled`, `failed`, `disabled`, `unknown`) (Section 8.1, 9.2) | Add shared `ProviderStatus` enum and conversion/mapping hooks for domain-specific states. | `tldw_Server_API/app/core/Infrastructure/provider_registry.py`, wrapper registries | `tldw_Server_API/tests/Infrastructure/test_provider_registry_status.py` (new) | [x] |
| R6 | Consistent provider normalization + alias mapping hooks (Section 8.1) | Implement canonical name normalization utility and alias table support in base; make wrappers register aliases. | `tldw_Server_API/app/core/Infrastructure/provider_registry.py`, `tldw_Server_API/app/core/LLM_Calls/adapter_registry.py`, `tldw_Server_API/app/core/TTS/adapter_registry.py`, `tldw_Server_API/app/core/Ingestion_Media_Processing/Audio/stt_provider_adapter.py` | `tldw_Server_API/tests/Infrastructure/test_provider_registry_normalization.py` (new), `tldw_Server_API/tests/Audio/test_stt_provider_adapter.py` | [x] |
| R7 | Capability discovery with error isolation (Section 8.1) | Implement protected capability fetch path where one provider failure does not fail global listing. | `tldw_Server_API/app/core/Infrastructure/provider_registry.py` | `tldw_Server_API/tests/Infrastructure/test_provider_registry_capabilities.py` (new) | [x] |
| R8 | LLM registry migrated to thin wrapper over base (Sections 8.2, 9.3, 10 Phase 1) | Refactor `ChatProviderRegistry` to delegate registration/lookup/capability listing/state to base while preserving `ChatProvider` behavior. | `tldw_Server_API/app/core/LLM_Calls/adapter_registry.py` | `tldw_Server_API/tests/LLM_Calls/test_adapter_registry_defaults.py`, `tldw_Server_API/tests/LLM_Calls/test_llm_providers.py` | [x] |
| R9 | TTS registry migrated to thin wrapper over base with existing config defaults/backoff semantics (Sections 8.2, 9.3, 10 Phase 2) | Refactor `TTSAdapterRegistry` to use base for registration/caching/status/backoff while keeping TTS config shaping/provider priority logic in wrapper. | `tldw_Server_API/app/core/TTS/adapter_registry.py`, `tldw_Server_API/app/core/TTS/tts_service_v2.py` | `tldw_Server_API/tests/TTS/test_tts_module.py`, `tldw_Server_API/tests/TTS/test_tts_adapters.py`, `tldw_Server_API/tests/TTS_NEW/unit/test_tts_service.py` | [x] |
| R10 | STT registry migrated to thin wrapper over base while keeping model-to-provider resolution logic (Sections 8.2, 9.3, 10 Phase 3) | Move adapter storage/lookup/capability listing/status tracking to base; keep `resolve_provider_for_model()` and default-provider logic in STT wrapper. | `tldw_Server_API/app/core/Ingestion_Media_Processing/Audio/stt_provider_adapter.py` | `tldw_Server_API/tests/Audio/test_stt_provider_adapter.py`, STT integration tests under `tldw_Server_API/tests/STT/` | [x] |
| R11 | Config integration via callback without precedence changes (Section 8.3) | Add config callback interface to base and wire per-domain callback implementations (LLM/TTS/STT) without changing existing precedence rules. | `tldw_Server_API/app/core/Infrastructure/provider_registry.py`, domain registries above | `tldw_Server_API/tests/Infrastructure/test_provider_registry_config_callback.py` (new), domain regression tests | [x] |
| R12 | Standard `list_capabilities()` envelope across domains (Section 8.4, Acceptance Criteria) | Define common envelope shape: `{provider, availability, capabilities}`; implement in each wrapper and keep domain capability payload in `capabilities`. | `tldw_Server_API/app/core/Infrastructure/provider_registry.py`, `tldw_Server_API/app/core/LLM_Calls/adapter_registry.py`, `tldw_Server_API/app/core/TTS/adapter_registry.py`, `tldw_Server_API/app/core/Ingestion_Media_Processing/Audio/stt_provider_adapter.py` | New/updated wrapper tests for capability envelope; endpoint tests listed below | [ ] |
| R13 | Endpoint parity with unified capability envelope (Goal/Acceptance impact) | Update endpoints that expose provider capabilities/health to consume standardized wrapper outputs without response regressions. | `tldw_Server_API/app/api/v1/endpoints/llm_providers.py`, `tldw_Server_API/app/api/v1/endpoints/audio/audio_health.py`, `tldw_Server_API/app/api/v1/endpoints/audio/audio_transcriptions.py` | Endpoint integration tests under `tldw_Server_API/tests/Chat_NEW/`, `tldw_Server_API/tests/TTS_NEW/integration/`, `tldw_Server_API/tests/STT/` | [ ] |
| R14 | Cleanup duplicate helpers and old normalization paths (Phase 4) | Remove superseded registry duplication, consolidate normalization helpers into base, and delete dead code paths. | Same registry modules and any extracted helper modules | Regression suite across LLM/TTS/STT before and after cleanup | [ ] |
| R15 | Testing plan complete (Section 12) and acceptance criteria met (Section 13) | Ensure base unit tests, wrapper parity tests, and capability listing tests all pass; verify acceptance criteria in PR summary. | Test suite + PR checklist | `python -m pytest -m "unit" -v` plus targeted integration tests for LLM/TTS/STT registries/endpoints | [ ] |

### Suggested Execution Order
1. Implement R1-R7 in shared base with dedicated unit tests.
2. Migrate LLM wrapper (R8), then TTS wrapper (R9), then STT wrapper (R10).
3. Wire config callbacks and standardized capability envelope (R11-R12).
4. Update capability-exposing endpoints and run integration tests (R13).
5. Remove duplicate helpers and complete parity/regression pass (R14-R15).

### R10 Execution Notes (2026-02-08)
- STT registry now delegates adapter registration, lookup, status, and capability envelope listing to `ProviderRegistryBase` while preserving STT-specific provider/model resolution and default provider logic.
- Added STT wrapper migration coverage in `tldw_Server_API/tests/Audio/test_stt_provider_registry_wrapper_migration.py`.
- Hardened `tldw_Server_API/tests/Audio/test_stt_provider_adapter.py` import helper for Python 3.9 by injecting explicit compatibility stubs for `core.exceptions` and `Audio_Transcription_Lib`, preventing heavy dependency imports during unit tests.
- Validation run completed successfully:
  - `python3 -m pytest -q tldw_Server_API/tests/Infrastructure/test_provider_registry_base.py tldw_Server_API/tests/Infrastructure/test_provider_registry_backoff.py tldw_Server_API/tests/Infrastructure/test_provider_registry_status.py tldw_Server_API/tests/Infrastructure/test_provider_registry_normalization.py tldw_Server_API/tests/Infrastructure/test_provider_registry_capabilities.py tldw_Server_API/tests/Infrastructure/test_provider_registry_async.py tldw_Server_API/tests/Audio/test_stt_provider_adapter.py tldw_Server_API/tests/Audio/test_stt_provider_registry_wrapper_migration.py`
  - Result: `65 passed`.

### R11 Execution Notes (2026-02-08)
- Added config callback support to shared registry base via `provider_enabled_callback`, including runtime callback updates with `set_provider_enabled_callback(...)`.
- Base registry availability checks now consult callback state (when provided) for `get_adapter`, `get_adapter_async`, `get_status`, and `list_providers`, while preserving legacy behavior when callback is unset or returns `None`.
- Wired per-domain callbacks:
  - LLM registry now reads explicit enable flags from config (`providers.<name>.enabled` or `<name>_enabled`) without affecting defaults when unset.
  - TTS registry now surfaces existing `is_provider_enabled(...)` and explicit `{provider}_enabled` logic through the shared callback path.
  - STT registry now wires the callback interface as an intentional no-op to preserve existing STT precedence.
- Added and updated tests:
  - New: `tldw_Server_API/tests/Infrastructure/test_provider_registry_config_callback.py`
  - Updated: `tldw_Server_API/tests/LLM_Calls/test_adapter_registry_wrapper_migration.py`
  - Updated: `tldw_Server_API/tests/TTS/test_tts_adapter_registry_wrapper_migration.py`
  - Updated: `tldw_Server_API/tests/Audio/test_stt_provider_registry_wrapper_migration.py`
- Validation run completed successfully:
  - `python3 -m pytest -q tldw_Server_API/tests/Infrastructure/test_provider_registry_base.py tldw_Server_API/tests/Infrastructure/test_provider_registry_backoff.py tldw_Server_API/tests/Infrastructure/test_provider_registry_status.py tldw_Server_API/tests/Infrastructure/test_provider_registry_normalization.py tldw_Server_API/tests/Infrastructure/test_provider_registry_capabilities.py tldw_Server_API/tests/Infrastructure/test_provider_registry_async.py tldw_Server_API/tests/Infrastructure/test_provider_registry_config_callback.py tldw_Server_API/tests/LLM_Calls/test_adapter_registry_wrapper_migration.py tldw_Server_API/tests/TTS/test_tts_adapter_registry_wrapper_migration.py tldw_Server_API/tests/Audio/test_stt_provider_adapter.py tldw_Server_API/tests/Audio/test_stt_provider_registry_wrapper_migration.py`
  - Result: `80 passed`.
