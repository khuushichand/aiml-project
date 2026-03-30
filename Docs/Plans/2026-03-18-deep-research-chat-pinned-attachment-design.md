# Deep Research Chat Pinned Attachment Design

## Summary

Extend the saved-chat deep-research attachment model so each saved server-backed chat thread can keep:

- one active `deepResearchAttachment`
- one durable `deepResearchPinnedAttachment`
- up to three prior attachments in `deepResearchAttachmentHistory`

The pinned attachment acts as the thread's default research context. It restores automatically when the thread opens and there is no active attachment, but it stays separate from the active slot and normal recent-history churn.

## Goals

- Preserve one durable default research attachment per saved chat thread.
- Keep pinning outside the transcript and within existing chat attachment management.
- Reuse the existing bounded attachment shape, chat settings seam, and restore flow.
- Avoid normal history rotation pushing an important research run out of the thread context model.

## Non-Goals

- No multiple pinned attachments.
- No pin ordering or favorites collection.
- No `/research`-page pin controls in this slice.
- No transcript persistence or hidden message injection.

## Approaches Considered

### 1. Separate pinned slot in chat settings

Store `deepResearchPinnedAttachment` alongside the existing active and history fields.

Pros:

- clear semantics
- simple restore precedence
- minimal schema/API change

Cons:

- requires explicit dedupe across three slots instead of two

### 2. Pinned flag on history entries

Keep a single history list and mark one entry as pinned.

Pros:

- less top-level schema churn

Cons:

- awkward precedence rules
- active/history/pinned responsibilities blur quickly

### 3. Dedicated pinned-attachment backend record

Create a separate server-side persistence object.

Pros:

- clean domain separation

Cons:

- too much new API/schema work for one bounded slot

## Recommended Approach

Persist a separate `deepResearchPinnedAttachment` field in chat settings.

This matches the existing thread-local ownership model, keeps pinning orthogonal to active/history switching, and makes restore behavior easy to explain: active first, pinned second, history after that.

## Architecture

Persist:

- `deepResearchAttachment`
- `deepResearchPinnedAttachment`
- `deepResearchAttachmentHistory`

All three live in per-chat settings for saved server-backed chats only.

### Behavior

#### Pin the active attachment

- copy the current active attachment into `deepResearchPinnedAttachment`
- do not change the active attachment
- remove the pinned `run_id` from history after normalization

#### Pin a history item

- copy the selected history entry into `deepResearchPinnedAttachment`
- do not force it active
- keep the current active attachment unchanged
- remove the pinned `run_id` from history after normalization

#### Unpin

- clear `deepResearchPinnedAttachment`
- leave active attachment and history untouched

#### Attach a new run

- active attachment behavior remains unchanged
- if the new active `run_id` matches the pinned `run_id`, keep both valid
- if the old active attachment is moved into history and matches the pinned `run_id`, drop the duplicate history copy

#### Edit the active attachment

- update only the active attachment
- do not mutate the pinned slot automatically
- pinned remains the last explicitly pinned snapshot

#### Remove the active attachment

- clear `deepResearchAttachment`
- leave pinned and history intact

#### Restore from history

- selecting a history item immediately makes it active
- if the restored `run_id` matches the pinned slot, both remain valid
- remove the restored entry from history
- if there was a different active attachment, move it into history unless it duplicates the pinned slot
- reapply dedupe and cap rules

#### Thread restore

- when a saved chat thread opens:
  - restore `deepResearchAttachment` if present
  - otherwise restore `deepResearchPinnedAttachment` if present
  - then restore history
- active restoration remains authoritative for what chat uses on the next send
- whenever pinned is restored into active, reset the active/baseline attachment snapshot to that restored pinned value so preview/debug reset behavior stays coherent

## Data Contract

Use the same bounded attachment shape for active, pinned, and history entries.

### Settings fields

- `deepResearchAttachment?: DeepResearchAttachment | null`
- `deepResearchPinnedAttachment?: DeepResearchAttachment | null`
- `deepResearchAttachmentHistory?: DeepResearchAttachment[]`

### Validation rules

- no unknown keys in active, pinned, or history entries
- pinned uses the same caps and required identity fields as active/history
- history length stays capped at 3
- malformed pinned/history entries are stripped during normalization

### Dedupe and precedence rules

Normalize by `run_id` with slot precedence:

1. active
2. pinned
3. history

Effects:

- if active and pinned share the same `run_id`, keep both slots valid
- history must not contain an entry whose `run_id` matches the active or pinned slot
- history remains newest-first after dedupe

### Merge semantics

- active merge uses `deepResearchAttachment.updatedAt`
- pinned merge uses `deepResearchPinnedAttachment.updatedAt`
- history merge uses per-entry `updatedAt`
- backend and package-side settings reconciliation must use the same slot precedence and dedupe rules
- the existing overall chat-settings byte cap still applies to active + pinned + history combined

## UI Shape

Expose pinning in the composer attachment management surface.

### Active attachment present

`AttachedResearchContextChip` shows:

- current active attachment
- `Pin` or `Unpin` action
- `Recent research` affordance when history exists

If a pinned slot exists, show a compact `Pinned research` section above `Recent research`.

If the pinned `run_id` matches the current active attachment:

- keep the pinned slot valid in settings
- do not render a duplicate pinned row in the composer UI
- the active chip can instead expose `Pinned` / `Unpin` state directly

### No active attachment present

If a pinned slot exists, show a composer-level `Pinned research` affordance so the user can immediately reactivate it.

If only history exists, continue showing the existing `Recent research` affordance.

### Interaction rules

- clicking the pinned item makes it active immediately
- pinning a history item does not force it active
- pin and recent-history affordances remain outside the transcript and status stack

## Error Handling

- malformed pinned/history entries: strip silently during normalization
- settings fetch/update failure: keep local active behavior and degrade gracefully
- temp/local chats: never persist pin state
- pin/unpin failure: do not block composer usage

## Testing

### Backend

- valid pinned attachment round-trips through chat settings
- malformed pinned attachment is rejected at the API boundary
- pinned merge respects its own `updatedAt`
- dedupe across active, pinned, and history excludes duplicate history entries
- active/pinned/history combined payload still respects the existing settings size limit

### Frontend

- pinning the active attachment persists the pinned slot
- unpin clears only the pinned slot
- pinning a history entry does not corrupt active/history order
- no-active thread state restores pinned as active by default
- switching chats restores the correct active/pinned/history trio
- temp chats never persist pinned state

## Risks

- subtle merge behavior when active and pinned evolve independently across devices
- duplicate display if active/pinned/history dedupe drifts between backend and frontend
- stale pinned snapshot confusing users if they edit active attachment later
- combined settings payload approaching the existing byte cap

## Mitigations

- keep one shared bounded attachment shape
- keep slot precedence explicit and identical on backend/frontend
- treat pinning as explicit snapshot capture, not a live alias of the active slot
- keep history capped at 3 and fail cleanly when settings size limits are exceeded

## Out of Scope

- multiple pins
- pinned ordering
- search/filter over recent or pinned attachments
