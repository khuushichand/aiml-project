# Knowledge QA History Hydration Design

## Context

Knowledge QA persists history to `localStorage` and hydrates it on mount. The current effect order creates a destructive race:

- provider mounts with `searchHistory = []`,
- the persistence effect runs first and removes `knowledge_qa_history`,
- mount-time `loadSearchHistory()` then reads nothing and local history is lost.

This is user-visible because it can silently erase prior local sessions before the page finishes loading.

## Goal

- Preserve persisted local history across initial mount.
- Keep existing history persistence behavior after hydration is complete.

## Options Considered

### 1. Skip removal only on the first render

Pros:
- Small diff.

Cons:
- Brittle and order-dependent.
- Harder to reason about if history is reloaded manually later.

### 2. Recommended: gate persistence until history hydration completes

Pros:
- Matches the actual lifecycle boundary.
- Easy to test.
- Safe for both mount-time and manual `loadSearchHistory()` paths.

Cons:
- Adds one small hydration flag to provider state flow.

### 3. Reorder effects only

Pros:
- Minimal code motion.

Cons:
- Still fragile and dependent on hook ordering.
- Easier to regress later.

## Decision

Use option 2.

## Design

- Add a provider-local hydration flag that starts `false`.
- `loadSearchHistory()` will set the flag to `true` in a `finally` block so it flips even when storage or server history fetch fails.
- The history persistence effect will return early until hydration is complete.
- Once hydration is complete, the existing behavior remains:
  - empty history removes `knowledge_qa_history`,
  - non-empty history is persisted and trimmed as needed.

## Testing

- Add a provider test proving that history stored before mount is still present after initial hydration without manually calling `loadSearchHistory()`.
- Verify local storage remains intact after mount hydration completes.
