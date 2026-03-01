# Writing Playground Extra-Body Compatibility Metadata Design

- Date: 2026-02-26
- Status: Approved
- Authors: Codex + user

## Context

We are porting Mikupad functionality into the writing playground stack and want to preserve compatibility with existing `chat/completions` clients.

Mikupad exposes many advanced generation controls (for example: `mirostat`, `typical_p`, `tfs_z`, `dry_*`, `xtc_*`, `banned_tokens`, `grammar`, `ignore_eos`). In `tldw_server2`, these are not broadly first-class top-level request fields in the capability registry. However, the server already supports provider-specific pass-through via `extra_body`.

The decision is to keep advanced controls in `extra_body` and enrich discovery metadata so UIs can safely render capability-aware controls without breaking current clients.

## Goals

1. Keep `extra_body` as the compatibility channel for advanced/non-standard sampler params.
2. Add explicit metadata so clients can discover known `extra_body` params per provider and model.
3. Ensure `supported` means effective runtime support for this deployment (not just static catalog presence).
4. Mirror this metadata on both:
   - `GET /api/v1/writing/capabilities`
   - `GET /api/v1/llm/providers`
5. Make only additive response changes.

## Non-Goals

1. No new required/validated top-level fields for these advanced params.
2. No behavior changes to `POST /api/v1/chat/completions` request validation.
3. No tokenizer architecture changes in this phase.
4. No server-side memory/author-note/world-info context assembly in this phase.

## Decision Summary

Implement a shared compatibility catalog plus a runtime-effectiveness resolver that evaluates provider/model support for this deployment (for example strict OpenAI-compatible filtering). Attach provider-default and model-level metadata to writing and provider listing endpoints.

This keeps runtime generation behavior unchanged while making advanced support discoverable for writing UI parity.

## Approaches Considered

### Option 1: Writing-only metadata

- Pros: Smallest blast radius.
- Cons: Other clients cannot discover the same metadata.

### Option 2: Runtime adapter introspection

- Pros: Lower manual upkeep in theory.
- Cons: Unstable API shape, brittle coupling to adapter internals.

### Option 3: Shared catalog + runtime evaluation mirrored on both endpoints (selected)

- Pros: Stable additive API contract, deployment-accurate `supported`, easy to test, reused across endpoints.
- Cons: Manual updates when provider support evolves.

## Detailed Design

### 1) Shared compatibility catalog module

Add a new module:

- `tldw_Server_API/app/core/LLM_Calls/extra_body_compat_catalog.py`

Responsibilities:

1. Normalize provider/model identity.
2. Return provider-default and model-level compatibility objects.
3. Evaluate deployment runtime constraints (for example `strict_openai_compat`) before setting `supported`.
4. Provide a safe fallback for unknown providers/models.

Proposed API:

- `get_provider_extra_body_compat(provider: str, *, runtime_context: dict[str, Any] | None = None) -> dict[str, Any]`
- `get_model_extra_body_compat(provider: str, model: str, *, runtime_context: dict[str, Any] | None = None) -> dict[str, Any]`
- `list_known_extra_body_params(provider: str, model: str | None = None) -> list[str]`

### 2) Metadata contract (additive)

Attach `extra_body_compat` with this shape:

```json
{
  "supported": true,
  "effective_reason": "supported in current deployment",
  "known_params": ["mirostat", "mirostat_tau", "mirostat_eta", "typical_p"],
  "param_groups": ["sampling", "penalties", "constraints"],
  "notes": "Provider-specific parameters should be sent under extra_body.",
  "example": {
    "extra_body": {
      "mirostat": 2,
      "mirostat_tau": 5,
      "mirostat_eta": 0.1
    }
  },
  "source": "catalog+runtime"
}
```

`supported` semantics: effective runtime support for this provider/model in the current deployment.

Fallback for unknown provider/model:

```json
{
  "supported": false,
  "effective_reason": "unsupported for deployment/runtime configuration",
  "known_params": [],
  "param_groups": [],
  "notes": "No extra_body compatibility metadata registered for this provider.",
  "example": {"extra_body": {}},
  "source": "catalog+runtime"
}
```

### 3) Writing capabilities endpoint changes

Update `tldw_Server_API/app/api/v1/endpoints/writing.py`:

1. For each provider in `providers[]`, include provider-default `extra_body_compat`.
2. For each provider in `providers[]`, include `model_extra_body_compat` keyed by model name.
3. For `requested` block:
   - include provider-default `extra_body_compat` when only provider is provided.
   - include model-specific `extra_body_compat` when provider+model are provided.
4. Compute runtime context per provider (for example strict OpenAI-compatible filtering flags) and feed it to resolver.

Update `tldw_Server_API/app/api/v1/schemas/writing_schemas.py`:

1. Add a typed model for `extra_body_compat`.
2. Add optional `model_extra_body_compat: dict[str, WritingExtraBodyCompat]` where model granularity is returned.
3. Add optional `extra_body_compat` field to:
   - `WritingProviderCapabilities`
   - `WritingRequestedCapabilities`

### 4) LLM providers endpoint mirror

Update `tldw_Server_API/app/api/v1/endpoints/llm_providers.py`:

1. For each provider object in `providers[]`, include provider-default `extra_body_compat`.
2. For each model entry in `models_info`, include model-level `extra_body_compat`.
3. Keep payload additive and backward-compatible.

### 5) Behavior invariants

No changes to these runtime paths:

1. `ChatCompletionRequest` top-level advanced field enforcement.
2. `capability_registry.validate_payload(...)` support list for top-level fields.
3. `merge_extra_body(...)` pass-through behavior.

## Known Mikupad-Aligned Params To Catalog

Initial known param set (provider-specific subsets, not universally supported):

- `dynatemp_range`
- `dynatemp_exponent`
- `repeat_penalty`
- `repeat_last_n`
- `ignore_eos`
- `mirostat`
- `mirostat_tau`
- `mirostat_eta`
- `typical_p`
- `min_p`
- `tfs_z`
- `xtc_threshold`
- `xtc_probability`
- `dry_multiplier`
- `dry_base`
- `dry_allowed_length`
- `dry_penalty_last_n`
- `dry_sequence_breakers`
- `banned_tokens`
- `grammar`
- `logit_bias`

## Error Handling

1. Catalog lookup must never fail endpoint responses.
2. Unknown provider/model returns default `supported=false` object.
3. If resolver logic throws unexpectedly, endpoints must still return a fallback metadata object (never omit the field).

## Test Plan

### Writing integration tests

Update `tests/Writing/test_writing_endpoint_integration.py` to verify:

1. `GET /api/v1/writing/capabilities` includes provider-default `extra_body_compat`.
2. `GET /api/v1/writing/capabilities` includes `model_extra_body_compat` map for provider models.
3. `requested` includes model-level `extra_body_compat` when provider+model are requested.
4. Unknown provider/model returns safe fallback shape.
5. Runtime strict-compat deployment flags set `supported=false` for non-standard param pass-through.

### LLM providers endpoint tests

Add or extend endpoint tests to verify:

1. `GET /api/v1/llm/providers` returns provider-default `extra_body_compat` per provider object.
2. `GET /api/v1/llm/providers` returns model-level `extra_body_compat` within `models_info`.
3. Shape is stable and additive.

### Regression confidence

1. Existing chat completion behavior remains unchanged.
2. Existing clients ignoring unknown fields continue to work.

## Rollout

1. Ship server metadata changes first.
2. Update writing playground UI to consume metadata and render controls conditionally.
3. Keep advanced request payloads in `extra_body` only.

## Risks And Mitigations

1. **Risk**: Metadata drift from real provider behavior.
   - **Mitigation**: Keep catalog conservative and apply runtime-effectiveness overlays before returning `supported`.
2. **Risk**: Client assumes metadata implies strict server validation support.
   - **Mitigation**: Include notes clarifying these are `extra_body` compatibility hints.

## Acceptance Criteria

1. Both endpoints expose mirrored provider-default and model-level `extra_body_compat` metadata.
2. `supported` is deployment-effective for the evaluated provider/model.
3. No new top-level chat param enforcement for advanced sampler fields.
4. Existing clients continue working without changes.
5. Tests cover model-level metadata, runtime-effective support, and unknown-provider/model fallback.
