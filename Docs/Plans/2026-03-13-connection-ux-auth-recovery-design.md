# Connection UX Auth Recovery Design

**Date:** 2026-03-13

## Goal

Fix three related connection UX regressions in the shared UI package:

1. Sidepanel auth recovery writes to a legacy storage key and does not repair requests.
2. Collections collapses auth-required and setup-required states into a generic offline message.
3. Opening onboarding/setup mutates global connection state destructively instead of resuming the current setup state.

## Problem Summary

The connection stack now distinguishes setup, auth, unreachable, and degraded states in the shared connection store. Some consumers still flatten that richer state into a boolean or mutate it too aggressively:

- `ConnectionBanner` writes API keys to `tldwApiKey`, but requests read auth from `tldwConfig`.
- `CollectionsPlaygroundPage` uses `useServerOnline()` and cannot tell auth-required from offline.
- `beginOnboarding()` currently both enters the onboarding UX and clears persisted first-run progress.

This creates a set of bugs where a user can be told setup succeeded, or that the server is offline, even though the real problem is missing credentials or an unnecessarily reset onboarding flow.

## Chosen Approach

Use the broader pragmatic refactor:

1. Split onboarding entry from onboarding reset.
2. Make `tldwConfig` the only writable connection auth source.
3. Update connection-sensitive UI surfaces to consume richer connection UX state instead of a single online boolean when rendering guidance or blocking access.

## Architecture

### Connection Store

Introduce two distinct actions:

- `enterOnboarding()`
  - Non-destructive.
  - Preserves persisted first-run completion.
  - Preserves existing `serverUrl`.
  - Derives the next step from current config and connection state.

- `restartOnboarding()`
  - Destructive and explicit.
  - Clears persisted first-run completion.
  - Forces the flow back to `configStep: "url"`.

This removes the current overload where simply opening onboarding acts like a reset.

### Auth Persistence

The request layer already reads `tldwConfig` on every request. All UI auth-repair flows should write through the same config path:

- sidepanel quick-fix for single-user auth updates `tldwConfig.apiKey`
- connection re-check runs after the write

The legacy `tldwApiKey` key should no longer be used for request repair.

### Consumer Guidance

User-facing surfaces that block access or explain failures should use `useConnectionUxState()` or equivalent derived state:

- auth/setup needed -> show targeted guidance and CTA
- unreachable -> show offline guidance
- connected/degraded -> render feature as normal

For this pass, the priority consumers are:

- `CollectionsPlaygroundPage`
- sidepanel connection banner/empty-state entry points
- onboarding entry routes

## Data Flow

### Sidepanel Auth Repair

1. User sees `error_auth` in sidepanel banner.
2. User enters API key.
3. Banner updates `tldwConfig` via shared config APIs.
4. Connection store runs `checkOnce()`.
5. Request layer now reads the updated API key from `tldwConfig`.
6. Banner and blocked surfaces recover based on shared connection state.

### Collections Gating

1. Collections reads `uxState` from the connection store.
2. It chooses one of:
   - auth/setup empty state with CTA
   - unreachable/offline empty state
   - full Collections tabs
3. The page no longer mislabels auth-required as server-offline.

### Onboarding Entry

1. Setup route or onboarding shell calls `enterOnboarding()`.
2. Connection store exposes the correct resumable `configStep`.
3. Explicit restart actions call `restartOnboarding()` instead.

## Error Handling

- Sidepanel inline API key entry remains single-user only.
- Multi-user auth repair continues to route users to Settings/login.
- Collections should surface actionable setup/auth copy, not a generic offline message, when the server is reachable.
- Restarting onboarding remains available from Settings, but that reset becomes explicit.

## Tests

Add regression coverage for:

1. Connection store onboarding behavior:
   - resumable onboarding preserves first-run state and advances to `auth` when URL exists but auth is missing
   - restart onboarding resets first-run and returns to `url`

2. Sidepanel auth repair:
   - saving an API key updates shared config and triggers a re-check
   - legacy `tldwApiKey` storage is not used

3. Collections UX:
   - auth-required state renders auth/setup guidance
   - unreachable state renders offline guidance

## Risks

- Changing onboarding entry behavior affects both WebUI and extension root routes.
- Some other consumers still use `useServerOnline()`; this pass should update only the blocking/guidance surfaces in scope, not every consumer in the repo.
- If tests rely on mocked `useServerOnline()` for these surfaces, they may need to be adjusted to richer connection state mocks.

## Out of Scope

- Replacing `useServerOnline()` across the entire app.
- Reworking multi-user login flows.
- Broader connection diagnostics UI cleanup.
