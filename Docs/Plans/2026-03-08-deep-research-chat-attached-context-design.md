# Deep Research Chat-Attached Context Design

**Date:** 2026-03-08

## Goal

Let users explicitly attach a completed deep research run to the active chat session as bounded working context for follow-up prompts, without polluting the transcript and without persisting that context to the thread in v1.

## User-Facing Outcome

For v1:

- completed research runs in chat expose a `Use in Chat` action
- clicking `Use in Chat` fetches the completed bundle and attaches a bounded research context snapshot to the active chat UI state
- the attached context remains active until the user removes it or replaces it with another research run
- attached context is shown as a persistent composer-area chip/banner, outside the transcript
- subsequent chat requests include the attached research context as a bounded side-channel payload
- attached context is not saved to the chat thread and does not become a transcript message

## Non-Goals

This slice does not include:

- automatic attachment on completion
- transcript messages for research progress or context
- persistence of attached context across page reloads
- multiple simultaneous attached research contexts
- attaching full `report_markdown`, full source inventories, or raw artifacts
- chat-side checkpoint approval or editing
- durable thread-level research attachments in the database

## Constraints From The Current Codebase

The current code already provides:

- completed deep research bundles via the research run APIs and `bundle.json`
- chat-origin research linkage and completion handoff
- linked research run status rows above the transcript
- a frontend `ChatCompletionRequest` type in `apps/packages/ui/src/services/tldw/TldwApiClient.ts`
- a backend `ChatCompletionRequest` model in `tldw_Server_API/app/api/v1/schemas/chat_request_schemas.py`
- message metadata sidecars for chat messages when requested with `include_metadata`

The current code does **not** provide:

- a chat-side attached research context state model
- any `research_context` field on the chat completion request
- a composer UI surface for active research context
- a structured marker on completion handoff messages for rendering a `Use in Chat` action

Those gaps define the shape of this design.

## Architecture

### 1. Session-Scoped Attached Context

Keep the initial implementation entirely session-scoped on the chat surface.

The source of truth for the attached research context is the live chat UI state, not the research database and not the chat thread.

That means:

- attaching context is an explicit client action
- the attached snapshot lives only in the current chat session
- reloads clear it in v1
- replacing the attached run overwrites the current context instead of stacking multiple contexts

This preserves the clean boundary the user asked for: useful follow-up context without turning research state into transcript clutter or durable hidden thread state.

### 2. Bounded Research Context Contract

The chat-attached context should be a bounded projection derived from the canonical research bundle, not the raw bundle itself.

Suggested client-side shape:

- `run_id`
- `query`
- `attached_at`
- `question`
- `outline`
- `key_claims`
- `unresolved_questions`
- `verification_summary`
- `source_trust_summary`
- `research_url`

Field constraints:

- `key_claims` is capped to a small number of canonical claims, such as `5-10`
- `unresolved_questions` is capped to a small list
- `source_trust_summary` is aggregate-only and does not include full `source_inventory`
- `report_markdown` is excluded
- full `claims`, `contradictions`, `source_inventory`, and raw artifacts are excluded

This keeps the attached context useful for follow-up reasoning while staying below the threshold where it becomes a second full report payload.

### 3. Attach Surfaces

Expose `Use in Chat` in two places:

- completed linked research run rows in the thread-local status stack
- the final completion handoff assistant message when present in the thread

The linked-run row is the primary v1 surface because it already has a structured run reference.

For the completion handoff message, add a small hidden metadata marker when the handoff is written so the chat UI can render `Use in Chat` without parsing message text. Suggested metadata extra:

- `deep_research_completion`
  - `run_id`
  - `query`
  - `kind: "completion_handoff"`

This keeps the visible completion message concise while giving the frontend a stable hook for the action.

### 4. Composer Surface

Render one persistent attached-context chip or banner near the composer, outside the transcript.

It should show:

- a short `Deep Research attached` label
- a query snippet
- `Open in Research`
- `Remove`

Behavior:

- it stays active until removed
- attaching a different run replaces the current chip contents
- it is clearly framed as active input context, not message history

This placement matches the user’s requirement that research updates and context not pollute the conversation itself.

### 5. Request Path

Extend the chat completion request contract with an explicit optional `research_context` payload.

Frontend:

- add `research_context` to the package-side `ChatCompletionRequest` interface
- when context is attached, include the bounded snapshot on every send
- when no context is attached, omit the field entirely

Backend:

- add a typed `ResearchChatContext` model to `chat_request_schemas.py`
- add an optional `research_context` field to `ChatCompletionRequest`
- carry it through the existing `/api/v1/chat/completions` request assembly path

Server-side chat assembly should convert that payload into a bounded context block for the model, clearly separated from transcript messages.

It should not be:

- stored as a user message
- appended as an assistant message
- silently persisted to the conversation

This preserves the distinction between user-authored transcript and model-side working context.

### 6. Context Lifetime

Attached research context remains active until the user removes it or replaces it.

It is not one-shot.

That means:

- the next prompt uses it
- later prompts also use it
- the user has to explicitly remove or replace it to stop including it

This matches the approved multi-turn follow-up model and makes the composer chip meaningful.

### 7. Failure Behavior

Failures should stay local and non-transcript.

If `Use in Chat` cannot fetch or derive a valid completed bundle:

- show a local UI error near the action or composer area
- do not attach anything
- do not emit a transcript message
- do not create a toast unless the existing local pattern already does so for action failures

If a run was attached successfully and later cannot be reloaded:

- continue using the already-attached in-memory snapshot for the live session
- do not silently drop the context

This keeps the feature predictable and avoids surprising users with disappearing context.

## API And Schema Changes

### Backend

In `tldw_Server_API/app/api/v1/schemas/chat_request_schemas.py`:

- add `ResearchChatContext` and any nested helper models needed for the bounded payload
- add optional `research_context: ResearchChatContext | None` to `ChatCompletionRequest`

In the chat completion pipeline:

- thread `research_context` through the request assembly/orchestration path
- inject a bounded context block into model-facing prompt assembly
- keep transcript messages unchanged

### Frontend

In `apps/packages/ui/src/services/tldw/TldwApiClient.ts`:

- extend `ChatCompletionRequest` with optional `research_context`
- add a typed representation of the attached research context

In the chat message read path:

- fetch metadata for completion handoff messages when needed so the message action can be rendered from `metadata_extra`

## UI Integration Shape

Primary v1 UI touches:

- `ResearchRunStatusStack`
  - add `Use in Chat` for completed runs
- chat completion handoff message rendering
  - add `Use in Chat` when the message metadata indicates a deep research completion handoff
- chat composer area
  - add the active attached-context chip/banner
- send path in the playground form/chat stack
  - include `research_context` on outbound requests when attached

This is enough to close the product loop:

- launch research from chat
- watch status outside the transcript
- get completion handoff
- explicitly attach completed research to the next prompts

## Testing

Backend tests should cover:

- `ChatCompletionRequest` accepts the new optional `research_context` field
- prompt assembly includes the bounded research context block
- transcript messages are unchanged when `research_context` is present
- omission of `research_context` preserves current behavior
- completion handoff messages persist the hidden metadata marker

Frontend tests should cover:

- `Use in Chat` renders for completed linked runs
- `Use in Chat` renders on completion handoff messages when metadata is present
- attaching context derives the bounded snapshot from the completed bundle
- the composer chip stays active across sends
- attaching a second run replaces the first
- removing the chip stops outbound `research_context`
- failed bundle fetch does not attach context and does not pollute the transcript

## Risks

- token bloat if the bounded subset grows without explicit caps
- UI confusion if the composer chip does not clearly communicate that the context is temporary and removable
- request-shape drift between frontend `ChatCompletionRequest` and backend `ChatCompletionRequest`
- over-coupling the completion handoff action to free-text message content instead of stable metadata

## Recommended Guardrails

- keep the attached subset capped and canonical
- keep only one attached research context active at a time in v1
- prefer hidden metadata markers over content parsing for the completion-message action
- do not persist attached context across reloads in this slice

