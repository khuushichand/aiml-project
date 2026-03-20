# Persona And Companion Connection UX Design

**Date:** 2026-03-13

## Goal

Fix the remaining user-facing connection UX regressions in the persona and companion entry surfaces without widening the sweep into nested prompt or writing workflows.

## Problem Summary

The shared connection store now distinguishes setup-required, auth-required, unreachable, testing, and demo states. Two remaining entry surfaces still flatten those states into a boolean online check:

- `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- `apps/packages/ui/src/components/Option/Companion/CompanionPage.tsx`

Both currently render a generic offline or unavailable message whenever `useServerOnline()` is false. That misreports reachable-but-misconfigured states and gives users the wrong recovery path.

## Constraints

- Preserve existing surface-specific layout and framing.
- Do not force `WorkspaceConnectionGate` into surfaces where its `PageShell` and default navigation targets are the wrong fit.
- Keep capability checks local to each feature after the connection gate logic.
- Leave `option-media-multi` and nested prompt or writing guards for a later demo-aware pass.
- Do not move gating into `WorldBooksManager`, because `WorldBooksWorkspace` already owns the real workspace-level connection gate.

## Chosen Approach

Implement local connection-state mapping inside persona and companion, using `useConnectionUxState()` directly while preserving each surface’s existing shell.

### Why not use `WorkspaceConnectionGate` directly?

`WorkspaceConnectionGate` is appropriate for full-page workspace shells, but these two surfaces have different requirements:

- `sidepanel-persona` must preserve its sidepanel header and route root wrapper.
- `CompanionPage` serves both option and sidepanel surfaces and should not be forced into a generic page shell.
- `WorkspaceConnectionGate` currently hardcodes settings and diagnostics navigation targets that do not exactly match the current sidepanel persona entry behavior.

Using the shared hook with local rendering gives the same state accuracy without breaking surface-specific layout.

## UX Behavior

### Sidepanel Persona

Before persona capability or stream logic runs:

- `error_auth` or `configuring_auth`
  - show targeted credential guidance
  - keep route header and root shell
  - primary CTA routes to settings

- `unconfigured` or `configuring_url`
  - show setup guidance
  - route users to setup/settings based on `hasCompletedFirstRun`

- `error_unreachable`
  - show diagnostics-oriented offline guidance

- `testing`
  - show a lightweight loading state inside the existing route shell

- `demo_mode`, `connected_ok`, or `connected_degraded`
  - continue into existing persona/capability flow

### Companion Page

Before personalization capability checks and workspace data loading:

- auth/setup/unreachable/testing states render surface-appropriate guidance
- options and sidepanel surfaces keep their current framing
- connected and demo states continue into existing capabilities and loading logic

Capability-specific “Companion unavailable” behavior remains local and only renders after connection state allows the page to load.

## Data Flow

1. Surface reads `useConnectionUxState()`.
2. Surface selects a connection-state-specific early return while preserving its own layout shell.
3. If connection state is renderable, the component continues into feature-specific capability and data logic.
4. Existing unsupported states remain untouched.

This keeps connection gating accurate without changing deeper persona or companion behavior.

## Tests

Add or extend targeted tests for:

- `sidepanel-persona`
  - auth-required guidance
  - setup-required guidance
  - unreachable guidance remains distinct from auth/setup

- `CompanionPage`
  - auth-required guidance
  - setup-required guidance
  - unreachable guidance
  - connected path still reaches capability checks

If a dedicated companion test file does not exist, add a narrow focused test file for the connection-gating behavior only.

## Risks

- These surfaces may need router-aware test harness updates because the new guidance paths trigger navigation callbacks.
- `CompanionPage` is shared across two surfaces, so copy and CTA behavior must stay generic enough to work in both.
- Overreaching into nested workflow guards would raise the risk sharply; this pass explicitly avoids that.

## Out Of Scope

- `option-media-multi` demo/offline reconciliation
- nested `isOnline` action guards in Prompt or Writing Playground
- moving gating into `WorldBooksManager`
- broader refactoring of `WorkspaceConnectionGate`
