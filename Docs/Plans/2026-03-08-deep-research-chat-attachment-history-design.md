# Deep Research Chat Attachment History Design

## Summary

Extend the persisted chat-side deep-research attachment model so each saved server-backed chat thread keeps:

- one active `deepResearchAttachment`
- up to three prior attachments in `deepResearchAttachmentHistory`

This history stays out of the transcript, restores automatically with the thread, and lets the user switch back to a previous research attachment immediately from the composer area.

## Goals

- Preserve quick switching between recent research runs without reopening `/research`.
- Keep the existing single-active attachment model intact.
- Reuse the existing chat settings persistence seam and bounded attachment shape.
- Ensure history is deduped, bounded, and restored per saved chat thread.

## Non-Goals

- No transcript insertion or hidden message persistence.
- No unlimited attachment archive.
- No per-history-item editing surface in v1.
- No multiple simultaneously active research attachments.

## Approaches Considered

### 1. Local-only history

Keep the last few attachments only in live client state.

Pros:

- minimal implementation

Cons:

- loses history on reload
- undermines the previous persisted-attachment slice

### 2. Persist bounded history in chat settings

Store active plus recent history in per-chat settings.

Pros:

- reuses existing backend and package-side settings seam
- matches thread-local ownership
- straightforward restore behavior

Cons:

- requires explicit history merge and dedupe rules

### 3. Dedicated attachment-history table

Create a separate backend store keyed by `chat_id`.

Pros:

- clean separation

Cons:

- too much schema/API work for a bounded list of 3

## Recommended Approach

Persist bounded history in chat settings.

The feature belongs to thread-local, out-of-band chat state. Chat settings already own that persistence boundary, and the new history entries can reuse the same bounded attachment shape as the current active attachment.

## Architecture

Persist:

- `deepResearchAttachment`
- `deepResearchAttachmentHistory`

Both live in per-chat settings for saved server-backed chats only.

### Behavior

#### Attach a new run

- if there is no active attachment, make the new one active
- set baseline to the new active attachment
- if there is a different active attachment:
  - move the old active attachment into history
  - dedupe by `run_id`
  - keep newest-first ordering
  - cap history to 3
  - set baseline to the new active attachment
- if the new run matches the current active `run_id`, replace the active attachment in place and do not churn history
- if the same `run_id` is already present in history, remove the stale history copy after promoting the new active snapshot

#### Edit the active attachment

- update only the active attachment
- do not create or reorder history entries

#### Remove the active attachment

- clear `deepResearchAttachment`
- leave `deepResearchAttachmentHistory` intact

#### Restore from history

- selecting a history entry immediately makes it the active attachment
- set baseline to the restored active attachment
- if there was a different active attachment, move that old active attachment back into history
- remove the restored entry from history
- dedupe and cap again

## Data Contract

Use the same bounded attachment shape for both active and history entries.

### Settings fields

- `deepResearchAttachment?: DeepResearchAttachment | null`
- `deepResearchAttachmentHistory?: DeepResearchAttachment[]`

### Rules

- max history length: 3
- dedupe by `run_id`
- newest first
- no unknown keys inside history entries
- history entries use the same bounded caps as the active attachment
- malformed entries are stripped during normalization

### Merge semantics

- active attachment merge uses `deepResearchAttachment.updatedAt`
- history merge uses per-entry `updatedAt`
- after merge, history is rebuilt as:
  - valid entries only
  - newest-first
  - deduped by `run_id`
  - excluding the current active attachment `run_id`
  - capped to 3
- these rules must exist in both:
  - backend conversation-settings merge logic
  - package-side `chat-settings` reconciliation logic
- the existing overall chat-settings byte cap still applies to the combined active-plus-history payload

## UI Shape

Expose history from the composer attachment surface.

### Active attachment present

Show a compact `Recent research` menu/dropdown near the attached-context chip when history exists.

Each history item shows:

- query snippet
- attached time

Selecting an item immediately activates it.

### No active attachment present

If history exists, still show a compact `Recent research` affordance near the composer so the user can reactivate one.

In practice, this means:

- `AttachedResearchContextChip` can own the active+history affordance when an active attachment exists
- `PlaygroundForm` needs the fallback affordance when there is no active attachment but history exists

This stays outside the transcript and outside the thread status stack.

## Error Handling

- malformed history entries: strip silently during normalization
- settings fetch/update failure: keep local active attachment behavior and degrade gracefully
- temporary/local chats: never persist history
- history restore failure: do not block chat input

## Testing

### Backend

- settings accept a valid bounded history list
- oversized history list is rejected or normalized according to the chosen write path
- malformed entries are rejected at the API boundary
- history round-trips through get/update
- repeated updates merge history by per-entry `updatedAt` instead of whole-object top-level `updatedAt`
- active/history merge respects per-entry `updatedAt`
- history dedupe excludes the active `run_id`

### Frontend

- attaching a new run pushes the previous active attachment into history
- editing the active attachment does not create history churn
- removing active attachment preserves history
- restoring from history immediately replaces the active attachment
- restore/switch persists correctly across saved chats and reloads
- temp chats never persist history

## Risks

- history merge logic becoming subtle when both sides changed
- active and history snapshots exceeding the chat-settings size cap
- confusing ordering if `updatedAt` and `attached_at` diverge
- accidental history churn on every active-attachment edit

## Mitigations

- keep history bounded and newest-first
- dedupe by `run_id` after every merge and state transition
- only create history entries on true attachment switches, not edits
- reuse one bounded attachment shape for both active and history
- keep the cap at 3 and fail cleanly when the overall chat-settings payload still exceeds the existing byte limit

## Out of Scope

- named/saved attachment presets
- search/filter over history
- more than 3 retained history entries
