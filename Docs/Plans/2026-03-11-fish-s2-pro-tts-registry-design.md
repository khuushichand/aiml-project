# Fish Audio S2 Pro TTS Registry Design

Date: 2026-03-11
Status: Approved for planning
Scope: Design only, no implementation

## Overview

This document describes how to add Fish Audio S2 Pro support to the tldw TTS
registry without breaking the current adapter, voice-management, or auth
patterns.

The approved direction is:

- add one canonical provider: `fish_s2`
- support the upstream Fish HTTP server first
- keep a future local-runtime backend as an internal design target, but not a
  normal v1 deployment mode
- support Fish-style managed reference workflows from day one

Key upstream constraints confirmed during design:

- Fish ships a native HTTP server with `POST /v1/tts`
- managed references are handled via `/v1/references/add|list|delete`
- the native server supports `wav`, `pcm`, and `mp3` output for non-streaming
- native streaming is limited to `wav`
- S2 Pro is documented as SGLang-first; the Hugging Face model card does not
  expose hosted inference

Sources:

- https://github.com/fishaudio/fish-speech
- https://speech.fish.audio/server/
- https://huggingface.co/fishaudio/s2-pro
- https://github.com/sgl-project/sglang-omni/blob/main/sglang_omni/models/fishaudio_s2_pro/README.md

## Goals

- Add Fish Audio S2 Pro to the TTS registry as a first-class provider.
- Support generation through the existing `POST /api/v1/audio/speech` route.
- Support managed reference creation, listing, and deletion from day one.
- Reuse existing tldw voice storage and metadata where practical.
- Preserve user isolation when multiple tldw users share one Fish backend.
- Avoid claiming unsupported semantics such as non-WAV streaming.

## Non-Goals

- Implementing the in-process local runtime in v1.
- Supporting arbitrary remote-only Fish references with no local tldw record.
- Surfacing Fish managed references in the global `/api/v1/audio/voices/catalog`
  route in v1.
- Adding a new multi-speaker public request surface in v1.
- Adding raw ad hoc inline `extra_params.references` audio uploads in v1.

## Primary Decisions

### 1. Canonical Provider

Add a new provider enum and registry entry:

- provider key: `fish_s2`
- adapter class: `FishS2Adapter`

Model aliases should resolve to `fish_s2`, including at least:

- `fish_s2`
- `fish-s2`
- `fish-s2-pro`
- `s2-pro`
- `fishaudio/s2-pro`

### 2. Backend Shape

The public provider is always `fish_s2`. Internally, the adapter delegates to a
backend strategy:

- `FishS2NativeHttpBackend` in v1
- `FishS2LocalRuntimeBackend` as a future internal extension point

This keeps registry, fallback, metrics, and API routing stable while allowing a
later local runtime without changing the external provider contract.

### 3. Reference Identity

In v1, the user-facing Fish `reference_id` is the local tldw `voice_id`.

This is the most important design revision from review. It avoids creating a
second public namespace or a second persistence layer. The backend-specific Fish
reference ID becomes an internal implementation detail derived from:

- `user_id`
- `voice_id`

Example internal remote ID pattern:

- `tldw_u{user_id}_v{voice_id}`

The exact formatting can be finalized during implementation, but it must be
deterministic and collision-resistant.

### 4. Storage Reuse

Reuse existing voice metadata in `voice_manager` for Fish mappings.

Store Fish state under:

- `provider_artifacts["fish_s2"]`

Expected fields:

- `remote_reference_id`
- `reference_text`
- `backend`
- `created_remote`
- `updated_remote`
- optional health/sync metadata

No second logical-reference store should be introduced in v1.

## Architecture

### Adapter and Backend Components

Planned components:

- `tldw_Server_API/app/core/TTS/adapters/fish_s2_adapter.py`
- `tldw_Server_API/app/core/TTS/backends/fish_s2_base.py`
- `tldw_Server_API/app/core/TTS/backends/fish_s2_native_http.py`

The adapter is responsible for:

- capability reporting
- request validation delegation
- mapping `TTSRequest` into backend-native requests
- consistent exception mapping

The native HTTP backend is responsible for:

- `GET /v1/health`
- `POST /v1/tts`
- `POST /v1/references/add`
- `GET /v1/references/list`
- `DELETE /v1/references/delete`
- bearer auth header handling

### API Integration

Speech generation remains on the existing route:

- `POST /api/v1/audio/speech`

Fish managed reference routes are added under the audio namespace:

- `POST /api/v1/audio/providers/fish_s2/references`
- `GET /api/v1/audio/providers/fish_s2/references`
- `DELETE /api/v1/audio/providers/fish_s2/references/{reference_id}`

In v1, `reference_id` on these routes is the local `voice_id`.

## Request Mapping

### Speech Generation

Existing request fields map as follows:

- `input` -> Fish `text`
- `response_format` -> Fish `format`
- `stream` -> Fish `streaming`

Fish-specific request controls live in `extra_params`:

- `reference_id`
- `chunk_length`
- `normalize`
- `seed`
- `use_memory_cache`
- `top_p`
- `temperature`
- `repetition_penalty`

### Reference Selection Precedence

For `model=fish_s2`, v1 resolution order is:

1. `extra_params.reference_id`
2. `voice=custom:<voice_id>`
3. no managed reference

If `extra_params.reference_id` is present, it resolves to a local `voice_id`
owned by the current user, then loads the Fish provider artifact mapping from
that voice metadata.

If `voice=custom:<voice_id>` is present, the service resolves the stored voice
through `voice_manager`. If a Fish remote reference already exists for that
voice, reuse it. Otherwise, create the remote Fish reference on demand using the
stored audio and transcript, then persist the mapping.

### Optional Shorthand

`voice=fishref:<id>` may be accepted as compatibility sugar, but it is not the
primary documented contract. If implemented, `<id>` still resolves to the local
logical `reference_id` / `voice_id`, not the backend remote ID.

## Managed Reference Lifecycle

### Creation

`POST /api/v1/audio/providers/fish_s2/references` supports two modes:

1. Existing stored voice:
   - request supplies `voice_id`
   - optionally allows overriding `reference_text`

2. New upload:
   - request supplies audio file plus transcript and metadata
   - route first creates a local stored voice via existing `voice_manager`
   - then creates the remote Fish reference for that voice

This preserves one authoritative local record per managed reference.

### Listing

`GET /api/v1/audio/providers/fish_s2/references` should list current-user
managed references from local metadata, not from Fish’s global backend list.

This avoids cross-user leakage and keeps the local database authoritative.
Backend sync checks may be added as best-effort status indicators, but local
metadata remains the source of truth for listing.

### Deletion

`DELETE /api/v1/audio/providers/fish_s2/references/{reference_id}`:

- resolves `reference_id` as a local `voice_id`
- deletes the remote Fish reference if present
- removes `provider_artifacts["fish_s2"]`
- does not delete the local stored voice itself

If the user wants to remove the underlying uploaded voice, they should continue
to use the existing `/api/v1/audio/voices/{voice_id}` delete route.

## Voice Catalog Behavior

Fish managed references should not appear in:

- `GET /api/v1/audio/voices/catalog`

Reason:

- that route is currently capability-driven and not user-aware
- Fish managed references are user-scoped data, not provider-global presets

`fish_s2` may still appear in provider capabilities with:

- empty built-in voices
- voice cloning support enabled

## Validation

### Provider-Level Validation

V1 validation should be conservative and honest:

- `stream=true` requires `response_format=wav` for `fish_s2`
- `mp3` and `pcm` are allowed for non-streaming requests
- `lang_code` is not validated as a hard provider contract in v1 because the
  native Fish HTTP request does not take an explicit language field
- `target_sample_rate` is ignored unless a backend later supports it explicitly

Fish-specific sampling controls should be validated into upstream ranges:

- `chunk_length`: 100-300
- `top_p`: 0.1-1.0
- `temperature`: 0.1-1.0
- `repetition_penalty`: 0.9-2.0

### Reference Audio Validation

Fish reference audio should reuse the existing upload and storage pipeline
instead of bypassing it. Add a `fish_s2` entry to `voice_manager`
`PROVIDER_REQUIREMENTS` with conservative defaults.

Recommended v1 defaults:

- allowed formats: `.wav`, `.mp3`, `.flac`, `.ogg`, `.m4a`, `.opus`
- conversion target: `wav`
- sample rate target: `24000`
- transcript required
- initial duration envelope: 3-60s
- user guidance should recommend 10-30s as the high-quality target

Arbitrary raw inline `extra_params.references` payloads should be deferred from
v1. Supporting only:

- managed references via `reference_id`
- stored voices via `custom:<voice_id>`

keeps validation, quota enforcement, and user isolation much cleaner.

## Capability Reporting

`fish_s2` should report:

- `provider_name = "Fish Audio S2"`
- `supports_voice_cloning = true`
- `supports_streaming = true`
- `supported_formats = {wav, mp3, pcm}`
- `default_format = wav`

V1 should not advertise:

- provider-global preset voices
- `supports_multi_speaker = true`

unless a first-class supported request surface exists for those features.

## Auth and Route Policy

Do not introduce a new Fish-specific privilege scope family in v1.

Instead, mirror the policy posture of the existing voice-management routes:

- same token-scope mode as current audio voice endpoints
- same quota/counting category where appropriate

This avoids unnecessary privilege-catalog churn and reduces startup validation
risk while the provider is still new.

## Configuration

Add a `fish_s2` block to the TTS provider config:

```yaml
providers:
  fish_s2:
    enabled: false
    backend: "native_http"
    base_url: "http://127.0.0.1:8080"
    api_key: null
    timeout: 120
    verify_api_key_on_init: false
    model: "s2-pro"
    sample_rate: 24000
    max_text_length: 0
    extra_params:
      default_chunk_length: 200
      default_normalize: true
      default_use_memory_cache: "off"
```

Notes:

- `backend=local_runtime` remains an internal future shape, not a supported
  operator-facing mode in v1 docs
- health verification should prefer `/v1/health`
- bearer auth should be used when `api_key` is configured

## Error Handling

Map backend failures into existing TTS exceptions:

- 401/403 -> `TTSAuthenticationError`
- 400 -> `TTSValidationError`
- 404 managed reference missing -> validation/not-found provider error
- 429 -> `TTSRateLimitError`
- network failure -> `TTSNetworkError`
- timeout -> `TTSTimeoutError`
- unsupported local backend mode in v1 -> `TTSProviderInitializationError`

Managed reference routes should return user-shaped responses:

- 400 invalid transcript or payload
- 404 unknown current-user `reference_id`
- 409 duplicate or conflicting mapping
- 502/503 backend unavailable

## Testing Plan

### Unit Tests

- registry resolves `fish_s2` and its model aliases
- request mapping to Fish `/v1/tts`
- `reference_id` resolves through local `voice_id`
- `custom:<voice_id>` creates or reuses Fish provider artifacts correctly
- validation rejects `stream=true` with non-`wav`
- provider artifact persistence under `provider_artifacts["fish_s2"]`

### Integration Tests

- `/api/v1/audio/speech` with `model=fish_s2`
- add/list/delete Fish managed references
- create managed Fish reference from an existing stored voice
- create managed Fish reference from a fresh upload
- user A cannot list or delete user B’s Fish references
- deleting a Fish reference does not delete the underlying local stored voice

### Documentation

Add a Fish S2 setup guide that documents:

- starting the upstream Fish server
- configuring `fish_s2`
- WAV-only streaming on the native server backend
- creating and using managed references
- using `custom:<voice_id>` with Fish

## Summary

The approved v1 design is intentionally conservative:

- one provider: `fish_s2`
- one real backend: native Fish HTTP server
- one logical reference namespace: local `voice_id`
- one persistence path: existing `voice_manager` metadata

That keeps the design aligned with upstream Fish behavior while fitting the
current tldw TTS architecture, auth model, and user-isolated voice storage.
