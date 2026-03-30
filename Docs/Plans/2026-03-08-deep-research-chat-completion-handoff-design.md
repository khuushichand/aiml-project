# Deep Research Chat Completion Handoff Design

**Date:** 2026-03-08

## Goal

When a deep research run is launched from chat and later completes, deliver a concise linked completion message back into the originating chat thread.

If that originating chat is no longer available or writable, fall back to a durable user notification and surface that notification as a global toast through the normal notifications stream.

## User-Facing Outcome

For v1:

- the chat thread gets one concise completion message with a direct run link when delivery succeeds
- no report text, citations, or bundle body are inlined into chat
- if chat delivery is impossible, the user gets one durable notification with a link back to the completed research run
- that fallback notification can toast anywhere in the app, not only on `/notifications`

## Non-Goals

This slice does not include:

- inline bundle rendering inside chat
- special chat rendering for research bundle sections
- automatic chat insertion for failed or cancelled research runs
- per-run custom message templates
- using `limits_json` or `provider_overrides_json` as a generic place to hide chat linkage

## Constraints From The Current Codebase

The current code already provides:

- a clear terminal completion point in `tldw_Server_API/app/core/Research/jobs.py`
- durable research session persistence in `tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py`
- plain backend chat message creation in `tldw_Server_API/app/api/v1/endpoints/character_messages.py`
- durable notifications plus replayable notification SSE in `tldw_Server_API/app/api/v1/endpoints/notifications.py`

The current code does **not** provide:

- any persisted chat linkage on research sessions
- global notification toasts outside the `/notifications` page
- metadata-on-create for chat messages

Those gaps define the shape of this design.

## Architecture

### 1. First-Class Handoff Record

Add a dedicated `research_chat_handoffs` table in the research DB, not a JSON blob in session metadata.

Suggested fields:

- `session_id TEXT PRIMARY KEY`
- `owner_user_id TEXT NOT NULL`
- `chat_id TEXT NOT NULL`
- `launch_message_id TEXT NULL`
- `handoff_status TEXT NOT NULL`
  - `pending`
  - `chat_inserted`
  - `notification_only`
  - `failed`
- `delivered_chat_message_id TEXT NULL`
- `delivered_notification_id INTEGER NULL`
- `last_error TEXT NULL`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`
- `delivered_at TEXT NULL`

Indexes:

- `(owner_user_id, session_id)`
- `(owner_user_id, chat_id, handoff_status)`

This table is the source of truth for handoff state and idempotency. It avoids scanning arbitrary JSON and avoids overloading the main `research_sessions` row with delivery bookkeeping.

### 2. Launch Contract

Extend the research create contract with an optional `chat_handoff` object:

- `chat_id: str`
- `launch_message_id: str | None`

Rules:

- only chat-origin launches set this object
- ordinary `/research` launches leave it absent
- the backend stores the handoff row at session creation time

For the existing chat launch flow through `/research`, the chat launch helper should carry `chat_id` as a transient launch param and the research console should:

- include that chat linkage in the create request
- strip the transient launch params after autorun so refresh does not repeat launch or leak chat linkage in the URL

### 3. Completion Bridge

After `bundle.json` is written and the research run transitions to `completed`, invoke a best-effort completion bridge.

The bridge must:

1. load the `research_chat_handoffs` row for the session
2. no-op if there is no handoff row
3. no-op if `handoff_status` is already terminal for this delivery
4. attempt chat delivery first
5. fall back to notification delivery only when chat delivery is impossible
6. never fail the research run itself

This bridge should be backend-owned and triggered from the research completion path, not from SSE or the client.

### 4. Chat Delivery Primitive

Use the plain backend chat message creation path, not the streamed completion persist endpoint.

Meaning:

- do **not** use `/{chat_id}/completions/persist`
- use the equivalent of `POST /chats/{chat_id}/messages` semantics
- if implemented internally, call the same underlying DB/service path that plain chat message create uses

For v1, keep the inserted message as plain content with a direct run URL. Do not require metadata-on-create.

If a structured run link is desired later, that can be a second metadata write using `set_message_metadata_extra(...)`, but that is not required for the initial slice.

### 5. Notification Fallback

If chat delivery fails because the chat is missing, deleted, inaccessible, or otherwise invalid, create a normal user notification with:

- `kind = "deep_research_completed"`
- `severity = "info"`
- `title = "Deep research completed"`
- `message = <concise query-based summary>`
- `link_url = /research?run=<session_id>`
- `link_type = "deep_research_run"`
- `link_id = <session_id>`
- `dedupe_key = deep_research_completed:<session_id>`

This fallback reuses the existing notifications system instead of inventing a research-only toast channel.

### 6. Global Toast Requirement

The current app only toasts notification events on `/notifications`. That is not enough for the required fallback behavior.

To satisfy the “global toast if the thread is no longer active/available” requirement, add an app-level notification stream bridge mounted from `apps/tldw-frontend/components/AppProviders.tsx`.

That bridge should:

- subscribe once to the notifications SSE stream
- show toasts through the existing `ToastProvider`
- coexist with the notifications inbox page without producing duplicate toasts

To avoid duplication:

- move notification-toast responsibility out of `pages/notifications.tsx` and into the shared app-level bridge, or
- explicitly disable page-level toast emission when the global bridge is active

The notifications page can still keep list refresh/live inbox behavior, but it should no longer own the only toast subscription.

## Message Contract

The inserted chat message should be concise and link-oriented.

Suggested shape:

- `Deep research finished for "<query>".`
- `Open the full report: /research?run=<session_id>`

Optional canonical counters are allowed only if cheap and stable, for example:

- section count
- source count

Do not inline:

- report markdown
- claims
- citations
- source excerpts

The fallback notification should mirror this same concise contract.

## Idempotency And Failure Semantics

Delivery must be idempotent under worker retries.

Rules:

- `research_chat_handoffs.session_id` is unique
- if `delivered_chat_message_id` is already set, do not insert another chat message
- if `delivered_notification_id` is already set, do not emit another notification
- bridge retries can advance `pending -> chat_inserted`, `pending -> notification_only`, or `pending -> failed`
- bridge failures do not change the research run status away from `completed`

Recommended behavior:

- persist `last_error` for observability
- only create fallback notification on chat-unavailable cases, not on arbitrary transient exceptions
- transient delivery exceptions should remain retryable while preserving dedupe

## Ownership And Safety

All chat and notification writes must stay owner-scoped.

Requirements:

- only the research run owner’s handoff row may be read
- only the owner’s chat may receive the inserted message
- only the owner’s notifications DB may receive the fallback notification
- if ownership checks fail, treat delivery as failed and do not fall back across users

## Testing Requirements

### Backend

- creating a research run with chat linkage stores a handoff row
- completing a linked run inserts exactly one assistant message into the origin chat
- deleting or invalidating the chat falls back to exactly one notification
- duplicate completion handling does not double-insert chat messages or notifications
- bridge failures do not fail or roll back the completed research run
- owner scoping is enforced for both chat and notifications

### Frontend

- the chat launch helper can carry transient chat linkage into `/research`
- the research page strips transient chat linkage after autorun
- the global notification bridge mounted from `AppProviders` shows a toast for incoming notification events
- the notifications page no longer duplicates those toasts

## Exit Condition

This slice is complete when:

- chat-launched deep research runs create a durable chat handoff link
- completed runs insert one concise linked message into the originating chat when possible
- otherwise they create one deduped notification linked back to the run
- the notification fallback can toast anywhere in the app through the shared notifications subscriber
