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
