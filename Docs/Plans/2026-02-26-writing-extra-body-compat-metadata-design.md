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
2. Add explicit metadata so clients can discover known `extra_body` params per provider.
3. Mirror this metadata on both:
   - `GET /api/v1/writing/capabilities`
   - `GET /api/v1/llm/providers`
4. Make only additive response changes.

## Non-Goals

1. No new required/validated top-level fields for these advanced params.
2. No behavior changes to `POST /api/v1/chat/completions` request validation.
3. No tokenizer architecture changes in this phase.
4. No server-side memory/author-note/world-info context assembly in this phase.

## Decision Summary

Implement a shared provider compatibility catalog that declares known `extra_body` parameters and associated metadata, then attach this metadata to writing and provider listing endpoints.

This keeps runtime generation behavior unchanged while making advanced support discoverable for writing UI parity.

## Approaches Considered

### Option 1: Writing-only metadata

- Pros: Smallest blast radius.
- Cons: Other clients cannot discover the same metadata.

### Option 2: Runtime adapter introspection

- Pros: Lower manual upkeep in theory.
- Cons: Unstable API shape, brittle coupling to adapter internals.

### Option 3: Shared static catalog mirrored on both endpoints (selected)

- Pros: Stable additive API contract, quick to ship, easy to test, reused across endpoints.
- Cons: Manual updates when provider support evolves.

## Detailed Design

### 1) Shared compatibility catalog module

Add a new module:

- `tldw_Server_API/app/core/LLM_Calls/extra_body_compat_catalog.py`

Responsibilities:

1. Normalize provider name (lowercase + trim).
2. Return a stable compatibility object for a provider.
3. Provide a safe fallback for unknown providers.

Proposed API:

- `get_extra_body_compat(provider: str) -> dict[str, Any]`
- `list_known_extra_body_params(provider: str) -> list[str]`

### 2) Metadata contract (additive)

Attach `extra_body_compat` with this shape:

```json
{
  "supported": true,
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
  "source": "catalog"
}
```

Fallback for unknown provider:

```json
{
  "supported": false,
  "known_params": [],
  "param_groups": [],
  "notes": "No extra_body compatibility metadata registered for this provider.",
  "example": {"extra_body": {}},
  "source": "catalog"
}
```

### 3) Writing capabilities endpoint changes

Update `tldw_Server_API/app/api/v1/endpoints/writing.py`:

1. For each provider in `providers[]`, include `extra_body_compat` from catalog.
2. For `requested` block (when provider/model query params are used), include provider-specific `extra_body_compat`.

Update `tldw_Server_API/app/api/v1/schemas/writing_schemas.py`:

1. Add a typed model for `extra_body_compat`.
2. Add optional `extra_body_compat` field to:
   - `WritingProviderCapabilities`
   - `WritingRequestedCapabilities`

### 4) LLM providers endpoint mirror

Update `tldw_Server_API/app/api/v1/endpoints/llm_providers.py`:

1. For each provider object in `providers[]`, include `extra_body_compat` using the same catalog.
2. Keep payload additive and backward-compatible.

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

## Error Handling

1. Catalog lookup must never fail endpoint responses.
2. Unknown provider returns default `supported=false` object.
3. If catalog logic throws unexpectedly, endpoint should degrade gracefully by omitting/using fallback metadata rather than failing the request.

## Test Plan

### Writing integration tests

Update `tests/Writing/test_writing_endpoint_integration.py` to verify:

1. `GET /api/v1/writing/capabilities` includes `extra_body_compat` for providers.
2. `requested` includes `extra_body_compat` when provider is requested.
3. Unknown provider returns safe fallback shape.

### LLM providers endpoint tests

Add or extend endpoint tests to verify:

1. `GET /api/v1/llm/providers` returns `extra_body_compat` per provider object.
2. Shape is stable and additive.

### Regression confidence

1. Existing chat completion behavior remains unchanged.
2. Existing clients ignoring unknown fields continue to work.

## Rollout

1. Ship server metadata changes first.
2. Update writing playground UI to consume metadata and render controls conditionally.
3. Keep advanced request payloads in `extra_body` only.

## Risks And Mitigations

1. **Risk**: Metadata drift from real provider behavior.
   - **Mitigation**: Keep catalog conservative; document params as "known/compat" not guaranteed.
2. **Risk**: Client assumes metadata implies strict server validation support.
   - **Mitigation**: Include notes clarifying these are `extra_body` compatibility hints.

## Acceptance Criteria

1. Both endpoints expose mirrored `extra_body_compat` metadata.
2. No new top-level chat param enforcement for advanced sampler fields.
3. Existing clients continue working without changes.
4. Tests cover new metadata fields and unknown-provider fallback.
