# Knowledge QA Reliability Design

## Goal

Fix four user-facing reliability problems on the Knowledge QA page:

1. `Cmd/Ctrl+K` clears page state too broadly.
2. Thread loads can fail into a blank state.
3. Deep-link and shared-link hydration does not retry correctly after a transient failure.
4. Source-list filter persistence is not resilient to `localStorage` failures.

## Current Problems

### Global shortcut ownership

`SearchBar.tsx` installs page-global `window` handlers for `/` and `Cmd/Ctrl+K`. The `/` shortcut already avoids firing inside `input` and `textarea`, but `Cmd/Ctrl+K` always clears Knowledge QA state and refocuses the search box. This can discard visible search/thread state while the user is interacting with history filters, settings, or export UI.

### Thread load failure state

`KnowledgeQAProvider.selectThread()` eagerly sets `currentThreadId`, then fetches messages. If the fetch fails, it clears messages and results but does not surface a dedicated error or preserve the previous visible conversation. The page can therefore land in an empty state after a transient server problem.

### Route hydration retry

`KnowledgeQAContent` uses `routeHydratedThreadRef` and `routeHydratedShareRef` as one-shot guards. Those refs are updated before `selectThread()` / `selectSharedThread()` complete. If loading fails once, remaining on the same `/knowledge/thread/:id` or `/knowledge/shared/:token` route does not trigger another load attempt.

### Storage resilience mismatch

Most of Knowledge QA wraps storage access defensively, but `SourceList.tsx` reads and writes `window.localStorage` directly when hydrating and persisting filter state. In restricted browsing contexts, that can break source rendering or filter persistence behavior.

## Design

### 1. Narrow shortcut activation

Keep the search shortcuts in `SearchBar.tsx`, but only let them run when the active target is outside editable controls and outside modal/dialog content. The intended behavior is:

- `/` focuses the search box only from non-editable page context.
- `Cmd/Ctrl+K` starts a new Knowledge QA search only from non-editable, non-dialog page context.

This keeps the shortcut discoverability while preventing destructive clears during modal and control interaction.

### 2. Make thread loading transactional

Treat thread selection as a transactional load:

- Attempt the remote load first.
- Only commit the new thread as the active visible thread once messages have been loaded and normalized successfully.
- On failure, preserve the previous visible state and set a visible error message.

This avoids blanking the page on transient failures and gives users recovery context.

### 3. Make route hydration retry-aware

Route hydration should track whether the current route token/thread has successfully loaded, not merely whether it has been attempted. The route guards should therefore:

- reset when the route changes,
- allow reattempts after a failed load on the same route,
- stop retrying only after a successful load for the current token/thread.

This preserves direct-link usability for both normal and shared Knowledge QA routes.

### 4. Harden SourceList storage access

Wrap SourceList filter storage read/write in safe helpers with `try/catch`, defaulting back to in-memory defaults when storage is unavailable. This should match the rest of Knowledge QA’s defensive storage behavior and prevent the source pane from crashing in restricted environments.

## Testing Strategy

Add focused tests first:

- `SearchBar.behavior.test.tsx`
  - `Cmd/Ctrl+K` does not clear state when focus is inside another editable control.
- `KnowledgeQAProvider.history.test.tsx`
  - failed `selectThread()` preserves existing visible state and surfaces an error.
- `KnowledgeQA.golden-layout.test.tsx`
  - same-route `/knowledge/thread/:id` and `/knowledge/shared/:token` hydration retries after a failed first attempt.
- `SourceList.behavior.test.tsx`
  - storage failures during filter hydrate/persist do not break rendering.

After the failing tests are verified, patch the minimal implementation paths and rerun the focused suites plus the broader Knowledge QA suites already in use.
