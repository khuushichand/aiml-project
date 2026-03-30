# Deep Research Chat Pin-From-History Design

## Summary

Extend the saved-chat deep-research attachment management surface so users can pin a recent history entry directly, without making it active first.

This keeps the existing model intact:

- one active `deepResearchAttachment`
- one durable `deepResearchPinnedAttachment`
- up to three recent entries in `deepResearchAttachmentHistory`

The new action is purely a composer-surface affordance. It updates the pinned slot, leaves the active slot alone, and preserves recent-history ordering except for normal duplicate removal.

## Goals

- Let users pin a recent deep-research attachment without restoring it as active.
- Keep the action outside the transcript and within the existing composer attachment surface.
- Reuse the current active/pinned/history settings model and pure transition helpers.
- Preserve the distinction between “what chat uses now” and “what the thread should remember as its default.”

## Non-Goals

- No schema changes.
- No backend endpoint changes beyond regression coverage if needed.
- No modal or picker UI.
- No automatic activation when pinning.
- No history reordering beyond existing dedupe rules.

## Approaches Considered

### 1. Direct pin action on recent-history entries

Add a `Pin` control next to each recent-history item in the composer attachment surface.

Pros:

- smallest change
- matches the existing bounded history UI
- keeps active vs pinned behavior explicit

Cons:

- adds one more small action to an already dense chip/fallback surface

### 2. Separate pinned-picker UI

Let users open a small picker and choose a recent item to pin.

Pros:

- cleaner individual history rows

Cons:

- unnecessary UI surface for a maximum history size of 3

### 3. Auto-pin on restore-from-history

Whenever a history item is restored to active, optionally pin it too.

Pros:

- fewer visible controls

Cons:

- implicit and surprising
- collapses the distinction between active and pinned

## Recommended Approach

Add direct `Pin` actions to recent-history entries.

This reuses the existing data model and pure helper path, avoids schema churn, and makes pinning useful without introducing new state concepts. The user can still click a history item to make it active, but `Pin` becomes a separate, explicit action that affects only the pinned slot.

## Architecture

### Current model

The thread already persists:

- `deepResearchAttachment`
- `deepResearchPinnedAttachment`
- `deepResearchAttachmentHistory`

The new slice does not change those fields.

### New behavior

#### Pin a history item

- copy that history entry into `deepResearchPinnedAttachment`
- keep `deepResearchAttachment` unchanged
- keep history ordering unchanged
- after normalization, remove any duplicate history copy matching the pinned `run_id`

#### Unpin a history-aligned pinned item

- clear only `deepResearchPinnedAttachment`
- keep active and history unchanged

#### Restore from history

- unchanged from the current behavior
- clicking the history item itself still makes it active immediately

#### Restore pinned

- unchanged from the current behavior
- clicking the pinned item still makes it active immediately

### Implementation seam

Reuse the existing pure transition helper in:

- [research-chat-context.ts](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/research-chat-context.ts)

Specifically:

- `pinAttachedResearchContext({ nextPinned })`

The UI should call that helper rather than inventing a second local mutation path.

## UI Contract

### Active attachment chip present

Within the existing `Recent research` section:

- clicking the history item keeps its current “make active” behavior
- add a separate `Pin` button beside each recent-history item

If a recent item already matches the pinned slot:

- show `Pinned` or `Unpin` rather than `Pin`
- do not make it active automatically

### No active attachment, history fallback present

Within the fallback composer surface:

- each recent-history item also gets a `Pin` action
- the existing item click still restores that history entry as active

### Important interaction rules

- `Pin` must not bubble into the history item’s restore handler
- pinning does not reorder recent history
- pinning does not modify the active slot
- duplicate display guards remain in place when active, pinned, and history share a `run_id`

## Data Contract

No schema changes are required.

Persisted settings remain:

- `deepResearchAttachment?: DeepResearchAttachment | null`
- `deepResearchPinnedAttachment?: DeepResearchAttachment | null`
- `deepResearchAttachmentHistory?: DeepResearchAttachment[]`

Normalization and merge rules remain unchanged:

- active slot precedence first
- pinned slot precedence second
- history deduped after active and pinned
- history max length remains 3

## Error Handling

- pin action failure should not block chat use
- persistence remains best-effort for the UI path
- if a pin/unpin update fails, local state can still update, consistent with the current attachment management behavior
- event bubbling bugs must be prevented so `Pin` does not also activate the history item

## Testing

### Frontend

- pinning a history item does not change the active attachment
- pinning a history item persists the pinned slot
- history order stays unchanged except for dedupe against the pinned `run_id`
- active and pinned duplicate display guards still hold
- fallback recent-history surface supports direct pinning too

### Backend

- only add a regression test if needed; the persistence model itself does not change

## Risks

- accidental event bubbling causing `Pin` to also restore the history item
- UI density if pin and restore controls are not clearly separated
- duplicate render if normalization and UI guards drift apart

## Success Criteria

- users can pin a recent history entry directly from the composer surface
- pinning does not activate the item
- no schema changes are needed
- recent history remains bounded and stable
