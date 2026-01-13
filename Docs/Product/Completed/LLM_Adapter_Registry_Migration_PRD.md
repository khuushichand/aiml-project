# LLM Adapter Registry Migration PRD

## Summary
Consolidate all LLM chat and summarization flows onto the adapter registry while preserving response-side extensions and enforcing strict request validation. The end state is one LLM call surface that validates payloads against a provider capability registry, with adapters responsible for auth/base URL resolution, streaming normalization, error mapping, and strict error/log redaction. Legacy LLM modules, dispatch tables, and shims are retired without constraining current or future integrations. `config.txt` remains the first-class configuration source.

## Goals
- One LLM call surface (adapter registry) for chat and summarization/analysis.
- Explicit support for OpenAI-compatible extensions via provider capability registry.
- Deterministic 400s for unsupported request parameters at the provider capability registry level (no silent drops or provider-side surprises for provider-level fields).
- Preserve response-side extensions in both streaming and non-streaming responses.
- Keep `config.txt` precedence and semantics unchanged.
- Remove legacy module naming and dispatch shims once parity is proven.
- Preserve streaming SSE semantics and existing error mapping behavior.
- Improve maintainability: fewer code paths, fewer test doubles, simpler provider onboarding.

## Non-Goals
- UI changes (no Admin UI or `tldw-frontend` work).
- Rewriting the RAG pipeline, chunking strategies, or ingestion workflows.
- Changing the response schema returned by public APIs.
- Switching the configuration system away from `config.txt`.
- Replacing Resource Governance or rate limit policies (existing guardrails stay as-is).
- Embeddings and other non-chat LLM surfaces (explicitly listed in the Phase 0 out-of-scope inventory).
- Free-form request passthrough of unknown parameters (unsupported fields must error).
- Model-level capability enforcement (provider-only validation; model-specific unsupported fields may still error at the provider).

## Users and Use Cases
- Backend maintainers: add/update providers by implementing one adapter.
- Integrators: send supported OpenAI-compatible fields and receive deterministic errors for unsupported params.
- Evaluations/RAG/Jobs/Services: call a single LLM interface without provider-specific branching.
- Test authors: patch adapters or `perform_chat_api_call` directly without relying on compatibility request shims.

## User Stories
- As an integrator, I can send supported OpenAI-compatible fields (e.g., `min_p`, `top_k`, `repetition_penalty`) and get a clear error if a field is unsupported.
- As a maintainer, I can add a provider by writing one adapter and registering it.
- As a service owner, I can request streaming or non-streaming behavior with identical semantics across providers.
- As a tester, I can stub a provider adapter without having to patch `http_client` factories or transport adapters directly.

## Problem Statement
LLM calls are fragmented across compatibility modules (`chat_calls.py`, `local_chat_calls.py`), summarization helpers, adapter call handlers, and provider-specific dispatch tables. This duplicates config parsing, error handling, and transport behaviors, while increasing the risk of extension-field regressions. The adapter registry exists but is not the exclusive entry point.

## Proposed Architecture
### Core Principles
- **Validated payloads**: validate request keys against a provider capability registry and reject unknown fields.
- **Adapter-only transport**: adapters perform auth/base URL resolution, streaming normalization, and error mapping.
- **Config-first**: provider config comes from `config.txt`, injected into adapters rather than re-parsed per module.
- **Single source of truth**: supported request fields and mappings live in the capability registry, not in callers.

### Adapter Contract (High-Level)
- Input: `{ provider, payload, api_key?, base_url?, extra_headers?, extra_body?, timeout?, stream? }`
- Behavior:
  - Merge `extra_body` into `payload` as additive-only (precedence: `payload` wins on key conflicts; `extra_body` is for provider-specific additive keys).
  - Merge `extra_headers` into headers (explicit headers win on key conflicts).
  - Validate merged payload keys against the provider capability registry; reject unsupported keys with a `Chat*Error` 400 including the unsupported key names.
  - Emit OpenAI-compatible response JSON (non-streaming) or SSE lines (streaming).
  - Map errors to `Chat*Error` types consistently.
  - Precedence:
    - **Auth/base URL/headers**: explicit call args (`api_key`, `base_url`, `extra_headers`) > BYOK resolved values > `config.txt` defaults.
    - **Request body**: `payload` > `extra_body` > adapter defaults (only for missing keys; never override caller input).

### Registry Behavior
- Registry resolves provider name -> adapter class.
- Registry does not enforce schemas; adapters validate via the capability registry.
- Callers choose provider and pass payload directly.

### Capability Registry
- **Location**: `tldw_Server_API/app/core/LLM_Calls/capability_registry.py` (tests in `tldw_Server_API/tests/LLM_Calls/capability_registry/`).
- **Scope**: defines the base OpenAI-compatible chat schema plus provider-specific extensions.
- **Structure**:
  - `base_fields`: allowlist of top-level request fields supported across providers.
  - `provider_extensions`: per-provider allowlist of extension fields.
  - `aliases`: per-provider mapping of public field names -> provider-specific field names.
  - `blocked_fields`: explicit denylist for unsafe or forbidden fields.
  - `schema_version`: bumped when the base schema changes.
- **Validation flow**:
  - Reject any field not in `base_fields` or provider `extensions`.
  - Reject any field in `blocked_fields` with a deterministic 400.
  - Apply `aliases` after validation; adapters send only provider-supported keys.
- **Update workflow**:
  - Adding a provider or field requires a capability registry update + tests.
  - No ad-hoc adapter allowlists; the registry is the single source of truth.
  - Registry changes require updating the supported field docs and fixtures.
- **Runtime**: registry is read-only at runtime; `config.txt` selects providers but does not alter supported fields.
- **Validation scope**: provider-level only; model-specific capability enforcement is out-of-scope for this migration.

### Capability Registry Launch Checklist (from legacy handler inventory + strict mode tests)
**Alias mappings to capture**
- [x] global aliases: `temp` -> `temperature`; `streaming` -> `stream`; `topp`/`maxp` -> `top_p`; `topk` -> `top_k`; `minp` -> `min_p`; `system_prompt` -> `system_message`; `user_identifier` -> `user`.
- [x] google: `max_output_tokens` -> `max_tokens`; `stop_sequences` -> `stop`; `candidate_count` -> `n`.
- [x] huggingface: `max_new_tokens` -> `max_tokens`.
- [x] anthropic/cohere: `stop_sequences` -> `stop`.

**Blocked fields to define at launch**
- [x] cohere: block `tool_choice` (legacy handler does not accept it).
- [x] google: block `tool_choice` until adapter/capability support is explicit.
- [x] local providers in `strict_openai_compat`: drop non-OpenAI keys (at minimum `top_k`, `min_p`).

## Functional Requirements
### Adapter Payload Validation
- Adapters must validate the merged payload against the provider capability registry.
- Unsupported fields return a deterministic 400 `Chat*Error` listing unsupported keys.
- Blocked fields return a deterministic 400 `Chat*Error` with the blocked key names.
- Supported extension fields are explicitly declared per provider (no implicit passthrough).
- Field translation is adapter-only and defined in the capability registry; adapters send only provider-supported keys.

### Nested Validation Policy (Selected: Option A)
The capability registry only validates top-level keys today. Adopt shallow shape checks for known nested fields and pass through unknown nested shapes:
- Enforce types/required keys for: `tools[]`, `response_format`, `logit_bias`, `json_schema` (if present).
- Reject invalid types with deterministic 400s; keep nested contents otherwise unvalidated.
- Tests: fixtures that assert valid/invalid shapes per field and provider.

### Response Pass-Through
- Adapters must preserve unknown fields in non-streaming responses (provider-specific extensions are returned unchanged).
- Streaming adapters must preserve extra fields in `data:` JSON chunks; normalization may add fields but must not drop provider fields.
- Redaction applies to logs/error messages only; response payloads are not modified for redaction.
- Non-OpenAI providers attach their original payload under `provider_response` in non-streaming responses and SSE chunks.

### Config and Secrets
- `config.txt` remains the primary source of provider settings and defaults.
- Adapter initialization accepts injected config derived from `config.txt` (no per-module config parsing).
- BYOK (per-user key resolution) remains supported and overrides config defaults.
- Caller-provided `api_key`/`base_url`/`extra_headers` override BYOK and config defaults.

### Base URL Override Policy (Selected: Option A)
Base URL overrides are allowed only for trusted callers (internal services/admin) and only when `config.txt` enables it per provider.
- SSRF protections required: scheme allowlist, block link-local/metadata IPs, DNS re-resolution, and explicit port allowlist.
- Tests: allow/deny fixtures for trusted/untrusted callers and blocked network targets.
- Config: set `byok_allowed_base_url_providers` in `Config_Files/config.txt` to allow per-provider overrides.

### Streaming Semantics
- Streaming responses must remain SSE formatted with `data:` lines and `[DONE]`.
- For providers without native SSE, adapters convert streaming output to the same SSE format.
- Streaming fallback behavior remains backward compatible with existing endpoints.
- Streaming chunks must follow OpenAI-compatible chat completion schemas (e.g., `choices[].delta` or `choices[].message`) and preserve any provider-specific fields in each chunk.
- Chunk ordering must match provider output; `finish_reason` appears only on terminal chunks, and `[DONE]` is emitted after the final chunk.

### Error Mapping
- Errors must map to existing `Chat*Error` types.
- Error messages should avoid leaking secrets or internal URLs (existing sanitization rules preserved).

### Backward Compatibility and Deprecation
- Legacy entry points remain temporarily as thin wrappers around the adapter registry.
- Deprecation notices are logged once per process for compatibility entry point usage.
- Complete migration means no production code path depends on legacy module names or compatibility shims.

## In-Scope Migration Targets
Primary modules to consolidate after parity:
- `tldw_Server_API/app/core/LLM_Calls/chat_calls.py`
- `tldw_Server_API/app/core/LLM_Calls/local_chat_calls.py`
- `tldw_Server_API/app/core/Chat/provider_config.py` (deprecated stub; dispatch tables removed)
- `tldw_Server_API/app/core/LLM_Calls/Summarization_General_Lib.py`
- `tldw_Server_API/app/core/LLM_Calls/Local_Summarization_Lib.py`

Call sites to converge on the registry:
- Services (`tldw_Server_API/app/services/*`)
- RAG pipeline (`tldw_Server_API/app/core/RAG/*`)
- Evaluations (`tldw_Server_API/app/core/Evaluations/*`)
- Web search/scraping (`tldw_Server_API/app/core/WebSearch/*`, `tldw_Server_API/app/core/Web_Scraping/*`)
- Ingestion modules that call summarization (`tldw_Server_API/app/core/Ingestion_Media_Processing/*`)

## Out-of-Scope Inventory (Phase 0 Output)
- Embeddings API (`/api/v1/embeddings`) and related adapter paths.
- Other non-chat LLM endpoints not listed in In-Scope Migration Targets (to be enumerated in Phase 0).

## Migration Plan (Phased)
### Phase 0: PRD Sign-Off + Inventory
- Confirm provider list and extension-field requirements.
- Inventory all LLM call sites and current request payload shapes.
- Document explicit out-of-scope surfaces (e.g., embeddings or other non-chat endpoints) in this PRD.
- Inventory legacy `provider_config.py` consumers and define a replacement surface (registry + config loader or compatibility facade).
- Define capability registry entries per provider (`base_fields`, extensions, aliases, blocked fields).
- Define a parity gate (golden tests + fixtures) and a feature flag/rollback plan for registry cutover.

### Phase 1: Adapter Contract + Validation
- Define/implement adapter payload merge semantics.
- Update existing adapters to validate payloads against the capability registry.
- Add unit tests that verify extension allowlists and validation end-to-end.
- Stand up the `provider_config.py` replacement or compatibility facade used by remaining call sites.
- Implement base_url override gating and SSRF checks; add test fixtures for `trusted_caller_context`, `untrusted_caller_context`, `base_url_allowed`, `base_url_invalid_scheme`, `base_url_blocked_link_local`, `base_url_blocked_metadata`, `base_url_blocked_private_ip`, `base_url_dns_rebind`.

### Phase 2: Summarization/Analysis Collapse
- Convert `Summarization_General_Lib.analyze` into a prompt-builder that calls adapters.
- Move default prompts to `Config_Files/Prompts` and load via `prompt_loader`.
- Remove provider-specific summarization functions after parity.

### Phase 3: Compatibility Entry Points as Thin Wrappers
- Route legacy chat functions to adapters without filtering or param maps.
- Remove `provider_config` dispatch tables and route compatibility wrappers through `chat_service.perform_chat_api_call`.
- Migrate remaining call sites to registry directly.

### Phase 4: Rename Legacy Modules
- Keep `chat_calls.py`/`local_chat_calls.py` as compatibility wrappers and remove legacy param maps.
- Update docs and tests to reference the registry interface and compatibility module paths.

## Success Criteria
- 100% LLM calls route through adapter registry in production code paths.
- No loss of documented extension fields (verified by tests); unsupported fields return deterministic errors.
- Response-side extension fields preserved in streaming and non-streaming flows.
- Legacy modules removed without regression in public API behavior.
- Reduced maintenance surface (measurable decrease in LLM-related modules/files).

## Observability
- Metrics: provider request counts, latency histograms, streaming durations.
- Logs: allowlist only (provider name, model if present, request ids, status, latency). Never log payloads, headers, or unknown fields.
- Error metrics keyed by provider and error class.
- Validation metrics: counts of rejected requests by provider (no parameter names in logs).

## Testing
- Unit tests: adapter validation, error mapping, streaming normalization.
- Integration tests: representative endpoints using custom extension fields.
- Regression tests: legacy payloads produce identical outputs pre/post migration.
- Response extension tests: provider-specific response fields preserved in JSON and SSE chunks.
- Streaming contract tests: canonical SSE fixtures covering `choices[].delta` and terminal `[DONE]`.
- Validation tests: unsupported/blocked request fields produce deterministic 400s with key names.

## Risks and Mitigations
- **Extension field loss**: enforce capability registry tests and payload merge policies.
- **Provider-specific quirks**: encode in adapters only; no caller-side branching.
- **Test brittleness**: standardize adapter-level test fixtures instead of request shims.
- **Capability registry drift**: add provider conformance tests and keep registry in a single module.
- **Client regressions from stricter validation**: inventory extension usage and document unsupported fields early.

## Compatibility Shims (Launch)
**Removed (Stage 5)**
- `tldw_Server_API/app/core/Chat/Chat_Functions.py`: removed after call-site migrations to `chat_orchestrator`/`chat_service`.
- `tldw_Server_API/app/core/LLM_Calls/adapter_calls.py`: removed after compatibility wrappers were migrated to `chat_service.perform_chat_api_call`.

**Removal timeline**
- Completed in Stage 5; no runtime toggle remains.

**Rollback plan (Phase 4)**
- No runtime toggle once the cutover is complete; rollback requires deploying the previous release.

**Can remove early (internal call sites)**
- `tldw_Server_API/app/core/Prompt_Management/prompt_studio/prompt_generator.py`: direct `chat_with_openai` usage.
- `tldw_Server_API/app/core/Prompt_Management/prompt_studio/prompt_improver.py`: direct `chat_with_openai` usage.
- `tldw_Server_API/app/core/RAG/rag_service/generation.py`: direct `chat_with_*` providers.
- `tldw_Server_API/app/core/Evaluations/wordbench_runner.py`: direct `chat_with_*` usage.
- `tldw_Server_API/app/core/Workflows/adapters.py`: direct `chat_with_openai_async` usage.

## Open Questions
- None (resolved: nested validation Option A; base URL override Option A).

## Implementation Plan
## Stage 1: Capability Registry Foundation
**Goal**: Implement the capability registry module and baseline schema definitions.
**Success Criteria**: `capability_registry.py` exists with `base_fields`, per-provider extensions, aliases, blocked fields, and schema versioning; docs updated to reference the registry.
**Tests**: Unit tests for registry structure loading and validation behavior.
**Status**: Complete

## Stage 2: Adapter Validation Integration
**Goal**: Enforce request validation and deterministic 400s across adapters.
**Success Criteria**: All registry-backed adapters reject unsupported/blocked keys before provider calls; error mapping remains consistent; response extensions preserved.
**Tests**: Adapter validation tests; integration tests that assert 400s on unsupported fields; response extension preservation tests; base_url override SSRF tests with fixtures `trusted_caller_context`, `untrusted_caller_context`, `base_url_allowed`, `base_url_invalid_scheme`, `base_url_blocked_link_local`, `base_url_blocked_metadata`, `base_url_blocked_private_ip`, `base_url_dns_rebind`.
**Status**: Complete

## Stage 3: Summarization and Call Site Migration
**Goal**: Route summarization/analysis and core call sites through validated adapters.
**Success Criteria**: Summarization uses the registry path; RAG/evals/services call the registry without legacy shims.
**Tests**: Regression tests comparing pre/post outputs; streaming contract fixtures still pass.
**Status**: Complete

## Stage 4: Compatibility Wrapper Cutover
**Goal**: Convert legacy entry points to thin wrappers and remove feature-flag routing.
**Success Criteria**: Legacy modules call registry only; parity gate tests pass; rollback plan documented (release rollback); compatibility shims deprecated with a published removal timeline.
**Tests**: Golden parity fixtures; legacy entry point integration tests.
**Status**: Complete

## Stage 5: Legacy Module Removal and Cleanup
**Goal**: Remove legacy module naming and finalize docs/tests.
**Success Criteria**: Legacy module names removed after deprecation window; docs updated; all tests green; no production path depends on deleted code.
**Tests**: Full test suite with unit/integration coverage for adapter registry and validation.
**Status**: Complete
