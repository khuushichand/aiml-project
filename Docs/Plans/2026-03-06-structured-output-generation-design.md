# Structured Output Generation Design

Date: 2026-03-06  
Status: Approved  
Scope: `chat/completions` + claims/RAG internal structured generation paths

## 1. Summary

Add first-class structured output generation with strict server-side validation across:

- OpenAI-compatible chat endpoint (`/api/v1/chat/completions`)
- Claims extraction and related internal structured-output consumers

The design centralizes negotiation, parsing, schema validation, fallback, and retry behavior so chat and claims do not drift.

## 2. User-Approved Decisions

1. Scope includes both chat and claims/RAG internals.
2. If provider does not support `json_schema`, downgrade to `json_object` and still enforce schema validation server-side.
3. Server must enforce schema validation before returning success.
4. Streaming remains allowed and must emit a final validated structured result event before stream completion.

## 3. Current State

### 3.1 Existing Capabilities

- `structured_output.py` provides robust JSON candidate parsing (`lenient`/`strict`) and shape normalization utilities.
- `capability_registry.py` already validates `response_format` payloads including `json_schema` shape.
- Many adapters pass `response_format` through to providers.
- Claims module already has partial response-format negotiation logic in `Claims_Extraction/output_parser.py`.

### 3.2 Gaps

- Chat request schema currently limits `response_format.type` to `text|json_object`.
- No shared structured-generation orchestrator for negotiation + retry + validation.
- No final structured stream event contract in chat streaming.
- Duplicate/fragmented structured output handling across features.

## 4. Goals and Non-Goals

### 4.1 Goals

- Unified structured generation behavior across chat and claims.
- Deterministic server-side schema enforcement.
- Streaming compatibility with a machine-readable final structured event.
- Provider capability-aware fallback and bounded retries.
- Backward compatibility for existing text/non-structured usage.

### 4.2 Non-Goals

- Rewriting all provider adapters to expose perfect capability metadata in this phase.
- Changing moderation, auth, or rate-limit policies.
- Introducing a new endpoint family; changes remain inside existing contracts.

## 5. Proposed Architecture (Recommended)

Introduce a shared orchestrator module:

`tldw_Server_API/app/core/LLM_Calls/structured_generation.py`

Responsibilities:

1. Validate structured request intent (schema presence/shape).
2. Negotiate request mode:
   - preferred: `json_schema`
   - fallback: `json_object` when schema mode unsupported
3. Execute structured call attempts (initial + bounded retries).
4. Parse and normalize model output via existing `structured_output.py`.
5. Validate parsed payload against JSON Schema (`jsonschema`).
6. Return typed result metadata for response encoding/telemetry.

### 5.1 Key Types

- `StructuredGenerationRequest`
  - `provider`, `model`, `messages`, `requested_response_format`, `schema_name`, `json_schema`, `stream`, `max_retries`
- `StructuredGenerationResult`
  - `validated_payload`, `mode_used`, `fallback_used`, `attempts`, `parse_mode`
- `StructuredGenerationError` (taxonomy)
  - `structured_output_capability_error`
  - `structured_output_no_payload`
  - `structured_output_parse_error`
  - `structured_output_schema_error`

### 5.2 Reused Components

- `parse_structured_output`, `extract_items` from existing `structured_output.py`
- `capability_registry.get_allowed_fields()` for baseline field availability
- Existing adapter registry/capabilities for optional format-type detection

## 6. API and Schema Changes

### 6.1 Chat Request Schema

Update chat request schemas to support `response_format.type = "json_schema"` with nested `json_schema` object:

- `name` (required for schema mode)
- `schema` (JSON Schema object, required for schema mode)
- optional `strict` passthrough if needed

Maintain support for existing:

- `{"type":"text"}`
- `{"type":"json_object"}`

### 6.2 Response Surface

Non-stream:

- On success: existing completion payload plus structured metadata extensions (tldw-prefixed metadata field).
- On structured failure after retries: HTTP 400 with structured error code + retry/fallback context.

Stream:

- Preserve existing delta flow.
- Emit final event before stream end:
  - `event: structured_result` with validated payload and metadata.
- On validation failure:
  - `event: structured_error` with code/context.
- Continue emitting stream terminal markers for compatibility (`stream_end`, `[DONE]`).

## 7. Detailed Data Flow

### 7.1 Non-Streaming Chat

1. Request parsed and validated by Pydantic.
2. If structured mode requested, invoke orchestrator.
3. Orchestrator negotiates `json_schema` or `json_object`.
4. LLM call runs.
5. Parse + schema validate response content.
6. Success returns validated structured payload metadata.
7. Failure after retries returns structured 400 error.

### 7.2 Streaming Chat

1. Stream deltas as today.
2. Accumulate full assistant text in stream handler.
3. At finalize stage (`save_callback`), invoke parse + schema validation.
4. Emit `structured_result` or `structured_error` event.
5. Emit standard terminal events and `[DONE]`.

### 7.3 Claims / RAG Internals

1. Replace local response-format selection in claims output parser paths with orchestrator negotiation utility.
2. Keep claims domain wrappers for domain-specific naming/errors, but delegate parse+validate+retry engine to shared orchestration.
3. Preserve existing outputs expected by claims engine and ingestion paths.

## 8. Error Handling and Retry Policy

## 8.1 Negotiation Rules

- Malformed requested schema -> immediate 400.
- Provider lacks `response_format` support -> structured 400.
- Provider supports `response_format` but not `json_schema` -> downgrade to `json_object`.

### 8.2 Retry Rules

- Retries apply on parse/schema failures only.
- Default retries: 2 additional attempts.
- Retry prompt reinforces strict JSON/schema requirements.
- Capture attempt-level diagnostics (without leaking sensitive content).

### 8.3 Terminal Failure Behavior

Non-stream:

- HTTP 400, structured detail body:
  - `code`, `message`, `attempts`, `mode_used`, `fallback_used`.

Stream:

- `structured_error` event with same machine-readable fields.
- Stream still terminates with standard completion markers.

## 9. Testing Strategy

### 9.1 Unit

- Chat schema accepts/rejects `json_schema` variants correctly.
- Orchestrator negotiation matrix:
  - schema supported
  - schema unsupported but json_object supported
  - response_format blocked
- Retry and terminal error code behavior.

### 9.2 Integration

- `/chat/completions` non-stream structured success/failure flows.
- Streaming structured success emits `structured_result`.
- Streaming structured failure emits `structured_error` and `[DONE]`.

### 9.3 Regression

- Existing `json_object` and text flows unchanged.
- Existing claims extraction tests continue passing with shared orchestration path.

## 10. Observability and Metrics

Add metrics (counter-style):

- `structured_output_requests_total`
- `structured_output_validation_failures_total`
- `structured_output_fallback_total`
- `structured_output_retry_total`

Add structured logs with:

- provider/model
- requested vs effective response format
- attempt count
- terminal error code

No raw schema-sensitive payload logging.

## 11. Rollout Plan

Phase 1:

- Feature-flag enforcement (default enabled in tests, configurable in runtime):
  - `CHAT_STRUCTURED_OUTPUT_ENFORCED`

Phase 2:

- Enable by default in broader environments once metrics show stable validation pass rates.

Rollback:

- Disable enforcement flag to revert to current behavior for structured mode requests while preserving endpoint availability.

## 12. Risks and Mitigations

1. Provider inconsistency in JSON mode output.
   - Mitigation: bounded retries + strict parser/validator + fallback mode.
2. Streaming consumers unprepared for new event names.
   - Mitigation: additive events only; existing deltas and `[DONE]` unchanged.
3. Drift between chat and claims semantics.
   - Mitigation: single orchestrator reused by both surfaces.

## 13. Implementation Entry Points

Expected touch points:

- `tldw_Server_API/app/api/v1/schemas/chat_request_schemas.py`
- `tldw_Server_API/app/core/LLM_Calls/structured_generation.py` (new)
- `tldw_Server_API/app/core/Chat/chat_service.py`
- `tldw_Server_API/app/core/Chat/streaming_utils.py` (event emission wiring)
- `tldw_Server_API/app/core/Claims_Extraction/output_parser.py`
- Targeted tests under:
  - `tldw_Server_API/tests/Chat/`
  - `tldw_Server_API/tests/LLM_Calls/`
  - `tldw_Server_API/tests/Claims/`

## 14. Acceptance Criteria

1. Chat schema accepts `json_schema` response_format.
2. Structured requests are validated server-side before success response.
3. Provider schema-mode unsupported path downgrades to json_object and still validates schema.
4. Streaming emits a final structured result/error event and remains backward compatible.
5. Claims internal structured generation uses the shared orchestration path.
6. New tests cover negotiation, retries, and terminal failure contracts.
