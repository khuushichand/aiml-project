# PRD: Chat Endpoint Final Split (chat.py)

- Title: Chat Endpoint Final Split
- Owner: Server API Team
- Status: Draft
- Target Version: v0.2.x
- Last Updated: 2026-02-08

## Summary

`chat.py` remains a large mixed-concern module despite prior extractions (`chat_dictionaries.py`, `chat_documents.py`). This PRD defines the final split plan so completion orchestration, persistence helpers, command injection, audit handling, and analytics/conversation routes are separated with stable compatibility shims.

## Current State (Repo Evidence)

- Main file: `tldw_Server_API/app/api/v1/endpoints/chat.py` (~3967 lines).
- Existing helper modules already split:
  - `tldw_Server_API/app/api/v1/endpoints/chat_dictionaries.py`
  - `tldw_Server_API/app/api/v1/endpoints/chat_documents.py`
- Large endpoint remains:
  - `create_chat_completion` starts around line ~1290 and spans most of the file.
- Persistence helpers still in endpoint module:
  - `_process_content_for_db_sync`
  - `_save_message_turn_to_db`
- Compatibility shim still required by tests:
  - `is_authentication_required()` in `chat.py`

## Problem Statement

`chat.py` currently mixes HTTP routing, request validation, moderation, slash-command parsing/injection, queueing logic, provider selection, audit logging, DB sync/persistence, and analytics routes. This concentration makes behavior hard to change safely and difficult to unit test in isolation.

## Goals

- Keep all current Chat API paths and response shapes unchanged.
- Extract completion orchestration into dedicated service modules.
- Move persistence and content normalization out of endpoint file.
- Isolate slash-command parsing/injection and moderation side-effects.
- Preserve stable test patch points, including `is_authentication_required`.

## Non-Goals

- No API contract changes.
- No provider behavior redesign.
- No new chat features.
- No schema/database migrations as part of this refactor.

## Scope

### In Scope

- Internal refactor of:
  - `tldw_Server_API/app/api/v1/endpoints/chat.py`
  - `tldw_Server_API/app/core/Chat/*`
- Route module reorganization for chat completions vs conversation/analytics endpoints.

### Out of Scope

- `chat_dictionaries.py` and `chat_documents.py` feature changes.
- Non-chat endpoints.

## Target Architecture

### Endpoint Layout (Target)

- Keep `chat.py` as compatibility shim + router aggregator.
- Introduce split endpoint modules under `endpoints/chat/` (or equivalent package):
  - `chat_completions.py`
  - `chat_conversations.py`
  - `chat_analytics.py`
  - `chat_rag_context.py`
  - `chat_queue.py`

### Core Chat Services (Target)

- `core/Chat/completion_service.py`
  - provider/model resolution orchestration
  - queue integration
  - streaming/non-streaming execution dispatch
- `core/Chat/persistence.py`
  - `_process_content_for_db_sync`
  - `_save_message_turn_to_db`
  - related message metadata normalization helpers
- `core/Chat/commands.py`
  - slash command parse/dispatch
  - command injection modes (`system`, `preface`, `replace`)
- `core/Chat/audit.py`
  - chat audit event composition and dispatch wrappers

## Compatibility Requirements

- Preserve all existing routes under `/api/v1/chat/*`.
- Preserve all response fields and status codes.
- Preserve compatibility shim:
  - `is_authentication_required` remains importable and monkeypatchable from `chat.py`.
- Maintain existing dependency patterns (AuthNZ, rate limits, permissions).

## Migration Plan

### Phase 1: Extract Persistence Helpers

- Move content processing and message save helpers from endpoint to `core/Chat/persistence.py`.
- Keep wrappers in `chat.py` that delegate to extracted functions.

### Phase 2: Extract Command and Moderation Injection Flow

- Move slash-command parsing/injection logic into `core/Chat/commands.py`.
- Keep endpoint orchestration call signatures unchanged.

### Phase 3: Extract Completion Orchestration

- Move core completion flow from `create_chat_completion` into `core/Chat/completion_service.py`.
- `create_chat_completion` becomes a thin translation layer (request -> service -> response).

### Phase 4: Route Module Split

- Move non-completion routes (conversations, analytics, rag context, queue status) into dedicated endpoint modules.
- Keep `chat.py` as compatibility entrypoint that includes subrouters and re-exports required shims.

## Testing Strategy

- Keep all current chat endpoint tests passing.
- Add targeted unit tests for extracted services:
  - persistence normalization
  - command injection modes and moderation outcomes
  - completion orchestration branches (streaming and non-streaming)
- Add shim compatibility tests for imports patched in legacy tests.
- Ensure queue and audit behaviors remain unchanged in integration tests.

## Risks and Mitigations

- Risk: completion flow regressions due to intertwined side effects.
  - Mitigation: extract in small vertical slices with parity tests after each slice.
- Risk: test breakage from moved helper symbols.
  - Mitigation: retain wrapper functions in `chat.py` until all tests are migrated.
- Risk: hidden coupling with core chat modules.
  - Mitigation: define explicit service interfaces and avoid back-imports from endpoint layer.

## Success Metrics

- `chat.py` reduced from ~3967 lines to a thin compatibility layer.
- Completion orchestration moved into testable core services.
- Existing chat tests stay green.
- No observed response/protocol regressions for chat clients.

## Acceptance Criteria

- `create_chat_completion` endpoint behavior is unchanged for clients.
- Persistence helpers are no longer implemented inline in `chat.py`.
- Slash command and audit logic are extracted to dedicated modules/services.
- Compatibility shim symbols remain stable during and after migration.
