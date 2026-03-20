# Deep Research Research-To-Chat Return Handoff Design

**Goal:** Add a clean `Back to Chat` return path from the web research console to the originating saved chat thread for research runs that were launched from chat.

**Status:** Approved design baseline for implementation planning.

## Summary

The current deep-research/chat integration is strongly one-way:

- chat can launch deep research
- chat can track linked runs
- chat can attach completed research back into the composer
- chat can hand users off into `/research` for checkpoint review

The missing loop is the return path. Once a user is in the research console, especially after reviewing a checkpoint, there is no clean way back to the exact originating chat thread.

This slice adds a run-level `Back to Chat` affordance in the web research console, but only for runs that still have a valid linked saved chat thread.

## Desired Behavior

For a research run that originated from chat and still has a valid linked chat:

- the research console shows `Back to Chat`
- clicking it navigates directly back to the exact linked chat thread

For a research run with no linked chat, or with stale/invalid linkage:

- the research console shows no `Back to Chat` affordance

This slice is navigation-only:

- no transcript writes
- no composer prefill
- no draft mutation
- no generic fallback to the chat landing screen

## Scope

Backend:

- `tldw_Server_API/app/api/v1/schemas/research_runs_schemas.py`
- `tldw_Server_API/app/api/v1/endpoints/research_runs.py`
- `tldw_Server_API/app/core/Research/service.py`
- `tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py`

Frontend:

- `apps/tldw-frontend/lib/api/researchRuns.ts`
- `apps/tldw-frontend/pages/research.tsx`
- route helpers in `apps/packages/ui/src/routes/route-paths.ts` if a new helper is needed

Tests:

- backend research run read API tests
- frontend research console tests around linked versus unlinked runs

## Architecture

This slice is not frontend-only. The current research run read model does not expose linked chat state, so the run read payload must be extended first.

The backend should expose a single optional field on the owned run read model:

- `chat_id?: string | null`

That field should be derived from the persisted research chat handoff linkage, but only returned when the linked chat is still valid for the owning user.

Frontend return flow:

- the research console reads `chat_id` from the run payload
- if `chat_id` exists, it renders `Back to Chat`
- clicking it navigates into the exact saved chat thread selection path

Important constraint:

- the return mechanism must be explicitly defined, not implied

If the current web chat screen uses `/chat` plus selected-thread bootstrap instead of a dedicated detail route, this slice should define a concrete helper for “open chat with serverChatId” instead of hardcoding ad hoc query strings in `research.tsx`.

## State Contract

The run read payload should add:

- `chat_id?: string | null`

Rules:

- `chat_id` is present only when:
  - the run originated from chat
  - the linked chat still exists
  - the linked chat is still owned/accessible by the requesting user
- `chat_id` is `null` or absent otherwise

The frontend must not infer chat linkage from:

- query params
- `from=chat`
- notification payloads
- historical handoff message metadata

This is a run read-model field, not a guessed frontend convention.

## Validity Rules

The persisted handoff table already stores `chat_id`, but that value is not sufficient by itself for the read model.

The read path should treat linkage as stale and return `chat_id = null` when:

- the linked chat no longer exists
- the linked chat is no longer owned/accessible for the requesting user

That prevents a stale `Back to Chat` affordance from being rendered for a dead or inaccessible thread.

## Navigation Contract

The design must define one explicit chat-thread return mechanism.

Recommended direction:

- add a route helper that builds the chat screen URL with enough information to reopen the saved server-backed thread

Examples of acceptable approaches:

- `/chat?server_chat_id=<id>`
- route state plus a stable `/chat` entry point, if that is already a supported web pattern

Unacceptable approach:

- linking only to `/chat` with no exact-thread selection path

This slice should pick one mechanism and reuse it consistently.

## UI Shape

Surface `Back to Chat` in the web research console header/action area for linked runs only.

Behavior:

- visible for valid linked runs
- hidden for unlinked or stale-linked runs
- same placement regardless of run status

Do not duplicate it in multiple console subsections in v1.

## Testing Scope

Backend tests should prove:

- linked run reads include `chat_id`
- unlinked run reads omit or null it
- stale/inaccessible linked chats are filtered to `chat_id = null`

Frontend tests should prove:

- `Back to Chat` renders only when the run payload includes a valid `chat_id`
- clicking it targets the exact chat-thread return path
- unlinked runs render no return affordance

## Out Of Scope

- no generic chat landing fallback
- no composer prefill or draft mutation
- no transcript writes
- no research-console to chat bidirectional transient state beyond navigation

## Risks

- exposing stale raw linkage instead of a validated read-model field
- inventing a one-off research-to-chat URL that diverges from how the web chat screen actually restores saved threads
- accidentally exposing `chat_id` on the wrong research payloads instead of the owned run read model only

## Implementation Notes

The current backend already persists chat linkage in `research_chat_handoffs`, and launch-time ownership is validated. The new work is about surfacing a safe, validated reverse link on reads and wiring the web console to a concrete chat-thread route helper.

That means the implementation should:

- keep validation backend-owned
- keep the frontend navigation helper explicit
- treat stale linkage as missing linkage
