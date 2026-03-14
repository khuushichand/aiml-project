# Persona Setup Live Unavailable Autoconnect Design

**Date:** 2026-03-14

## Goal

When assistant setup reaches `Test and finish`, the live test is unavailable, and the user chooses `Open Live Session to fix this`, the route should detour into `Live Session` and immediately start the normal connection flow without requiring an extra click.

## Problem

The previous slice made `live_unavailable` detour-capable, but the user still has to click `Connect` again after landing in `Live Session`. That is unnecessary friction because the only thing blocking them is the missing live connection, and the route already has a single authoritative `connect()` path.

## Constraints

- Reuse the existing `connect()` callback and connection lifecycle exactly.
- Do not add a second websocket/session creation path.
- Only auto-connect for `live_unavailable`, not `live_failure`.
- Do not auto-send any message or auto-complete setup on connect alone.
- Preserve the current manual `Return to setup` detour behavior.

## Recommended Approach

Patch only the route recovery handler in `sidepanel-persona.tsx` so the `live_unavailable` detour activates the existing `connect()` flow immediately after switching to `Live Session`.

## Architecture

### 1. Route-Only Recovery Branch

The current setup live-recovery path already calls:

```ts
handleRecoverSetupInLiveSession({
  source,
  text
})
```

That handler should branch by source:

- `live_failure`
  - keep current behavior
  - activate the live detour
  - switch to `activeTab = "live"`
- `live_unavailable`
  - activate the live detour
  - switch to `activeTab = "live"`
  - immediately call `void connect()`

### 2. Idempotent Guard

Auto-connect should only happen when:

```ts
context.source === "live_unavailable" &&
!connected &&
!connecting
```

This prevents duplicate websocket/session creation if:

- the route is already connected
- a connect attempt is already in progress

### 3. No New UI Surface

No component changes are required in this slice.

The existing setup live detour banner remains:

- `Finish this live test, then return to setup.`
- `Return to setup`

The `SetupTestAndFinishStep` button copy also remains unchanged:

- `Open Live Session to fix this`

## UX Behavior

### Before

1. Setup shows `live_unavailable`
2. User clicks `Open Live Session to fix this`
3. Route detours into `Live Session`
4. User must click `Connect`

### After

1. Setup shows `live_unavailable`
2. User clicks `Open Live Session to fix this`
3. Route detours into `Live Session`
4. Route immediately starts `connect()`
5. User can continue from the real Live surface once connected

This does not auto-send any setup test message. The user still explicitly drives the live attempt from there.

## Edge Cases

- If `connect()` is already in progress, just detour into Live and let the existing connection state finish naturally.
- If the route is already connected, detour into Live without calling `connect()` again.
- If auto-connect fails, keep the detour active and let the user retry or return manually.
- Reset/rerun setup behavior stays unchanged because the previous slice already clears the live detour state.

## Testing Strategy

### Route

`sidepanel-persona.test.tsx`

- `live_unavailable` detour auto-creates the websocket/session without an extra click
- `live_failure` detour does not auto-connect again
- if already connected, `live_unavailable` detour does not create a second websocket

## Out Of Scope

- Backend changes
- New live-session copy
- Auto-sending a setup live retry after auto-connect
