# Deep Research Chat-Linked Runs Status Design

**Date:** 2026-03-08

## Goal

Show linked deep research runs in the originating chat thread without polluting the conversation transcript.

For v1, this should appear as a compact thread-level status surface above the message list, covering multiple linked runs from the same chat and linking back to the canonical `/research` console.

## User-Facing Outcome

For v1:

- chat threads with linked deep research runs show a stacked status block above the transcript
- one row is shown per linked run
- rows show a short query snippet, current state, and an `Open in Research` action
- multiple concurrent runs from the same thread are supported
- status stays outside the transcript and does not create assistant/user messages

## Non-Goals

This slice does not include:

- in-thread progress messages
- inline bundle rendering inside chat
- checkpoint approval or editing from chat
- research SSE inside the chat surface
- per-run dismissal or pinning state
- chat-wide research history beyond the linked runs for the current thread

## Constraints From The Current Codebase

The current code already provides:

- durable chat-to-research linkage via `research_chat_handoffs` in `tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py`
- chat-origin deep research launch through the playground/chat surface
- canonical run state via the research service and `research_sessions`
- the main chat UI in `apps/packages/ui/src/components/Option/Playground/PlaygroundChat.tsx`
- a stable per-thread server chat identifier (`serverChatId`) in the playground state

The current code does **not** provide:

- any chat-facing endpoint for linked research runs
- any chat UI element for linked research status
- any polling contract for thread-local research visibility

Those gaps define the shape of this design.

## Architecture

### 1. Source Of Truth

Keep the research domain as the source of truth.

Do not add a second chat-owned run-tracking table.

The linked-run status list should be derived from:

- `research_chat_handoffs`
- `research_sessions`

That keeps chat as a consumer of research state instead of creating a parallel status model.

### 2. Compact Chat-Facing Read Path

Add a chat-facing read endpoint:

- `GET /api/v1/chats/{chat_id}/research-runs`

This endpoint should:

- verify chat ownership exactly like other chat session endpoints
- load linked research runs for that `chat_id` and current user
- return a compact list, not full research session payloads
- return all nonterminal runs plus only the latest bounded terminal history

Recommended v1 bound:

- all nonterminal linked runs
- latest `10` terminal linked runs

Suggested response shape:

- `runs: list[ChatLinkedResearchRunResponse]`

Per run:

- `run_id`
- `query`
- `status`
- `phase`
- `control_state`
- `latest_checkpoint_id`
- `updated_at`

This endpoint should not return:

- bundle content
- artifacts
- checkpoint payloads
- trust data

### 3. Backend Query Shape

Add a narrow research-side query that returns linked runs for a chat.

Suggested layering:

- DB helper in `ResearchSessionsDB.py`
- service wrapper in `tldw_Server_API/app/core/Research/service.py`
- chat API endpoint in `character_chat_sessions.py`

The DB/helper contract should:

- scope by `owner_user_id`
- filter by `chat_id`
- join handoff rows to current research session state
- use `research_sessions.updated_at` as the authoritative ordering field
- return newest linked runs first by `research_sessions.updated_at DESC`
- bound terminal history server-side instead of sending the entire handoff history forever

The frontend can then group:

- nonterminal runs first
- terminal runs second

while preserving the backend order within each group.

### 4. Chat UI Surface

Render the status outside the transcript in `PlaygroundChat.tsx`.

Placement:

- above the existing message list
- below any thread-global empty/search scaffolding that belongs to the chat shell itself

This matters for empty threads: if a linked run exists before any normal assistant reply is present, the status block must still remain visible and not get buried under the empty-state layout.

Shape:

- stacked compact rows
- one row per linked run
- minimal labels and a direct `Open in Research` link

Each row should visually distinguish:

- running
- waiting for review
- paused/cancel requested
- completed
- failed/cancelled

Checkpoint-needed state should be inferred from the run phase:

- `awaiting_plan_review`
- `awaiting_source_review`
- `awaiting_outline_review`

### 5. Multiple Concurrent Runs

V1 must support multiple concurrent linked runs in the same chat.

Display rules:

- show all linked runs for the current thread
- group active and waiting runs ahead of terminal runs
- if many terminal runs exist, collapse older terminal rows behind a simple `Show more` affordance

There is no v1 limit of “one active run per chat”.

### 6. Polling Model

Use polling, not SSE, for the chat-linked status surface.

Behavior:

- no request when there is no `serverChatId`
- no request for temporary chats
- poll on a modest interval while the thread is open
- use a faster interval when any linked run is nonterminal
- slow the interval once all linked runs are terminal
- treat query failures as non-blocking and silent in v1

Recommended v1 behavior:

- `5s` while any run is nonterminal
- `30s` once all runs are terminal
- after a small number of consecutive query failures, silently back off polling instead of retrying forever at the same rate

Recommended v1 backoff:

- after `3` consecutive failures, switch to a slower retry like `60s`
- reset to the normal cadence on the next successful fetch

This keeps the feature simple and avoids creating a second real-time contract inside chat.

## API And Schema Changes

Add chat-specific response models in `tldw_Server_API/app/api/v1/schemas/chat_session_schemas.py`.

Suggested models:

- `ChatLinkedResearchRunResponse`
- `ChatLinkedResearchRunsResponse`

Do not reuse the full `ResearchRunResponse` or `ResearchRunListItemResponse` directly as the public chat contract. The chat endpoint should stay compact and chat-oriented, even if it is built from the same underlying fields.

Do not include a backend-authored `console_url` field in this contract. The client should build the `/research?run=<id>` link through the shared route helper so route policy stays frontend-owned.

## Frontend Integration Shape

Keep the frontend integration on the package-side chat surface, not only in `apps/tldw-frontend`.

Suggested frontend touches:

- `apps/packages/ui/src/services/tldw/TldwApiClient.ts`
  - add a lightweight `listChatResearchRuns(chatId)` method
- `apps/packages/ui/src/components/Option/Playground/PlaygroundChat.tsx`
  - fetch and render linked research rows
- `apps/packages/ui/src/routes/route-paths.ts`
  - reuse or extend the existing research run path helper
- small colocated helper/presenter if needed for readability

Do not add a transcript message renderer or mutate the chat message list to represent research progress.

The backend endpoint should also use a proper research-service dependency path. It must not instantiate the research DB ad hoc inside the endpoint without the normal per-user path resolution that `ResearchService` already encapsulates.

This v1 surface is scoped to the web playground/chat experience that can navigate to `/research`. If the shared package-side component is later used in a non-web host, that host can either reuse the same route helper semantics or hide the action until it has an equivalent research route.

## Testing Requirements

### Backend

- listing linked runs for a chat returns only the owner’s linked runs
- compact response shape excludes bundle/artifact/checkpoint payloads
- compact response shape is bounded to all nonterminal plus latest bounded terminal rows
- ordering is stable with mixed active and terminal runs
- chats without linked runs return an empty list
- multi-user endpoint tests prove a user cannot read another user’s linked runs through the chat endpoint

### Frontend

- stacked status rows render above the chat transcript
- stacked status rows still render in the right place for an otherwise empty thread
- multiple linked runs render distinctly
- waiting/completed/failed states are visually distinct
- `Open in Research` targets the correct run via the shared route helper
- polling updates the status rows without touching message history
- terminal overflow collapse works if implemented in this slice
- query failure does not block chat rendering and does not emit transcript pollution or toast noise
- consecutive query failures trigger silent polling backoff instead of fixed-rate retry forever

## Exit Condition

This slice is complete when:

- a chat thread can query all linked research runs through a compact owner-scoped endpoint
- the playground chat renders a stacked thread-level status block above the transcript
- multiple concurrent linked runs are supported
- chat users can see actionable research state without any additional transcript pollution
