# Knowledge QA Thread Lifecycle Design

## Context

Knowledge QA now has stronger loading and storage resilience, but thread lifecycle remains inconsistent in two user-facing flows:

1. `New Topic` promises a fresh session but currently leaves the prior query, answer, and sources visible while only creating a new thread id.
2. Deleting the currently active history item removes it from history, but the page can stay attached to the deleted thread id and stale results.

Users treat Knowledge QA as a primary page, so these transitions need to behave predictably and preserve resumability for prior threads.

## Goals

- Make `New Topic` start a visibly fresh session.
- Ensure deleting the active thread leaves the UI in a safe empty state.
- Preserve restore/resume behavior for all prior threads that were not deleted.
- Keep lifecycle rules in provider logic rather than duplicating them in UI components.

## Non-Goals

- Changing the semantics of ordinary search, follow-up, branching, or permalink restoration.
- Reworking the history sidebar UX beyond fixing stale-state behavior.
- Introducing new persistence formats or backend APIs.

## Options Considered

### 1. UI-only resets

Have `FollowUpInput` and `HistorySidebar` call existing low-level actions like `clearResults()` and `setQuery("")`.

Pros:
- Small diff.

Cons:
- Lifecycle semantics get split across components.
- Easy to regress when other entry points are added.
- Harder to test provider behavior directly.

### 2. Provider-owned lifecycle actions

Add explicit provider actions for starting a fresh topic and safely clearing the active session after delete.

Pros:
- Centralizes thread lifecycle semantics.
- Keeps components simple.
- Easiest to regression-test at provider level.

Cons:
- Slightly broader provider API change.

### 3. Broaden `createNewThread()` to always reset state

Pros:
- Minimal surface area.

Cons:
- Incorrect for existing call sites like search bootstrap and branch creation, where unconditional reset would be surprising or destructive.

## Decision

Use option 2.

## Design

### Provider actions

- Add a dedicated provider action for starting a fresh topic.
- This action will:
  - clear visible query/result/message/error state,
  - detach the current thread,
  - create/select a new empty thread using the existing thread creation path.

- Update history deletion logic so that after a successful delete:
  - the history entry is removed,
  - if the deleted conversation was the active thread, the active session is cleared to the same safe empty state.

### UI wiring

- `FollowUpInput` will call the new provider action instead of calling `createNewThread()` directly.
- History sidebar delete wiring can stay the same if provider deletion becomes state-safe.

### Resume semantics

- Starting a fresh topic does not delete prior threads.
- Existing threads remain available through history restore and permalink routes.
- Only explicitly deleted threads become non-restorable.

## Testing

- Provider test: starting a fresh topic clears prior visible state and selects a new empty thread.
- Provider test: deleting the active remote history item clears active session state after successful server delete.
- UI test: `New Topic` button invokes the new provider action rather than raw thread creation.
