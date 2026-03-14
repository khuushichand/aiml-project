# Persona Setup Live Recovery Detour Design

**Date:** 2026-03-14

## Goal

When assistant setup reaches `Test and finish` and the live test fails because the live session is unavailable or the send attempt fails, let the user detour into the real `Live Session` tab, recover there, and then resume setup without losing the setup flow.

## Problem

The setup test step already distinguishes `live_unavailable` and `live_failure`, but the current UX only shows text guidance. That is weaker than the recovery flow users now get for `dry_run_no_match`, because the only real place to fix live issues is the actual `Live Session` surface that owns connection state, session banners, and runtime status.

## Constraints

- Setup must remain persona-scoped and `in_progress` until the user explicitly finishes.
- The detour must reuse the existing `Live Session` tab and route-owned session logic.
- Auto-return must only trigger for the specific setup live test response the route is already awaiting.
- Manual return must not leave a stale awaited-live-response state behind.
- This slice should stay frontend-only.

## Recommended Approach

Add a route-owned `setupLiveDetour` state that temporarily suppresses the setup overlay and opens the `Live Session` tab. While active, the route shows a small setup recovery banner in Live and auto-returns to the setup test step after the awaited setup live response succeeds. The user can also return manually before success.

## Architecture

### 1. Route-Owned Setup Live Detour

Add route state in `sidepanel-persona.tsx`:

```ts
type SetupLiveDetourState = {
  source: "live_unavailable" | "live_failure"
  lastText: string
}
```

This is independent from:

- `setupCommandDetour`
- `setupTestOutcome`
- `setupWizardAwaitingLiveResponseRef`

The route also keeps a small `setupLiveReturnNote: string | null` so the test step can explain why the user is back in setup after a detour.

### 2. Setup Gating Escape Hatch

The setup overlay remains the default while `personaSetupWizard.isSetupRequired` is true, except when either of these route-owned detours is active:

- `setupCommandDetour`
- `setupLiveDetour`

When `setupLiveDetour` is active, the route renders the normal tab surface and switches to `Live Session` so the user sees the real session controls and status panels.

### 3. Outcome-Specific Recovery Actions In The Test Step

`SetupTestAndFinishStep` gets one optional callback:

```ts
onRecoverInLiveSession?: (context: {
  source: "live_unavailable" | "live_failure"
  text: string
}) => void
```

The test step renders:

- `Open Live Session to fix this` for `live_unavailable`
- `Try again in Live Session` for `live_failure`

For `live_failure`, the callback should receive the failed text attempt. For `live_unavailable`, it should receive the last known setup live text if available, otherwise an empty string.

### 4. Auto-Return On Successful Setup Live Response

The route already uses `setupWizardAwaitingLiveResponseRef` plus the next assistant response to recognize a successful setup live test. That same path should be extended:

- if `setupLiveDetour` is active
- and the route consumes the awaited setup live response successfully

then:

- clear `setupLiveDetour`
- restore the setup overlay at `test`
- keep `setupTestOutcome = { kind: "live_success", ... }`
- set `setupLiveReturnNote = "Live session responded. Finish setup when you're ready."`

This auto-return should consume the awaited setup response exactly once.

### 5. Manual Return Before Success

The live detour banner adds a single action:

- `Return to setup`

Clicking it should:

- clear `setupLiveDetour`
- clear `setupWizardAwaitingLiveResponseRef.current`
- restore the setup overlay at `test`
- keep the setup incomplete
- set a neutral note:
  - `Live session is still available if you want to retry.`

Manual return must not allow a later unrelated assistant message to bounce the user back unexpectedly.

## UX Behavior

### Test Step

For live failure states:

- `live_unavailable`
  - explanation stays visible
  - action: `Open Live Session to fix this`
- `live_failure`
  - explanation stays visible
  - action: `Try again in Live Session`

### Live Session During Detour

The Live tab shows a compact recovery banner above the normal controls:

- `Finish this live test, then return to setup.`
- action: `Return to setup`

No duplicate connection or send controls are added there. The normal Live session UI remains the real recovery surface.

### Return To Setup

On auto-return after success:

- `SetupTestAndFinishStep` shows:
  - `Live session responded. Finish setup when you're ready.`
- `setupTestOutcome` remains `live_success`
- the user can immediately click `Finish with live session`

On manual return before success:

- the test step shows:
  - `Live session is still available if you want to retry.`
- no completion affordance is unlocked

## Edge Cases

- If the user disconnects while the live detour is active, keep the detour active until they either reconnect successfully or return to setup manually.
- If the user resets or reruns setup while the live detour is active, clear:
  - `setupLiveDetour`
  - `setupLiveReturnNote`
  - `setupWizardAwaitingLiveResponseRef`
- Existing non-setup live usage must stay unchanged. The detour logic only runs when setup is required and the detour is active.
- Auto-return must never trigger from unrelated later assistant messages once the detour has been cleared manually.

## Testing Strategy

### Component

`SetupTestAndFinishStep.test.tsx`

- `live_unavailable` renders `Open Live Session to fix this`
- `live_failure` renders `Try again in Live Session`

### Route

`sidepanel-persona.test.tsx`

- clicking live recovery hides the setup overlay and opens the `Live Session` tab
- active detour shows `Return to setup`
- a successful awaited setup live response auto-returns to setup with `live_success`
- manual `Return to setup` works before success and does not unlock finish
- reset/rerun clears the detour

## Out Of Scope

- Backend websocket changes
- New live-session transport behavior
- Auto-sending a setup live retry from the detour banner
