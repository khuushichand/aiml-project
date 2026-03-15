# Review Entry Pages Connection UX Design

**Date:** 2026-03-13

## Goal

Correct the top-level connection gates in `apps/packages/ui/src/components/Review/ViewMediaPage.tsx`, `apps/packages/ui/src/components/Review/MediaTrashPage.tsx`, and `apps/packages/ui/src/components/Review/ReviewPage.tsx` so auth-required, setup-required, and unreachable-server states no longer collapse into generic offline messaging.

## Scope

- Modify only the three current Review entry pages.
- Keep their existing capability, loading, and content flows intact.
- Add focused regression coverage for connection-state rendering and navigation.

Out of scope:

- `apps/packages/ui/src/components/Review/ViewMediaPage-Old.tsx`
- Query-enabling refactors below the top-level gates
- Changes to shared connection hooks or `WorkspaceConnectionGate`
- Capability-unavailable UX for servers that genuinely lack Media support

## Current Problem

These Review entry pages still gate on `useServerOnline()` alone:

- `ViewMediaPage` and `MediaTrashPage` show a generic offline `FeatureEmptyState`
- `ReviewPage` shows either a demo preview or `ConnectionProblemBanner`, but both use generic "not connected" copy

That drops richer connection store state on the floor:

- missing or broken credentials
- setup still incomplete
- backend unreachable after configuration
- transient connection testing

The result is the same misleading UX pattern already fixed in Collections, Persona, Companion, Prompt Studio, and the demo-enabled workspaces.

## Design

### State handling

Add `useConnectionUxState()` to all three pages and branch before the current generic offline paths:

- `error_auth` and `configuring_auth`
  - show credentials guidance
  - primary action goes to `/settings/tldw`
- `unconfigured` and `configuring_url`
  - show setup guidance
  - primary action goes to `/`
- `error_unreachable`
  - show unreachable-server guidance
  - primary action goes to `/settings/health`
  - secondary or retry action stays available where the page already supports it
- `testing`
  - do not show auth/setup/unreachable guidance
  - fall through to existing loading/capability behavior
- any other `!online` case
  - keep the current generic offline fallback

### Page-specific recovery

#### `ViewMediaPage` and `MediaTrashPage`

Keep the centered `FeatureEmptyState` short-circuit pattern. Replace the generic offline copy with state-aware titles, descriptions, and actions:

- credentials -> `/settings/tldw`
- setup -> `/`
- unreachable -> `/settings/health` plus retry
- generic fallback -> current offline copy

Do not add a demo preview here.

#### `ReviewPage`

Keep the existing split:

- demo mode preserves the preview scaffold
- non-demo mode preserves `ConnectionProblemBanner`

Update both branches to use state-aware copy and actions driven by `useConnectionUxState()`.

One important exception: when `forceOffline` is `true`, keep the current generic offline behavior. `forceOffline` is an explicit local override and should not be reinterpreted as auth/setup trouble.

## Testing

Create three focused test files:

- `apps/packages/ui/src/components/Review/__tests__/ViewMediaPage.connection.test.tsx`
- `apps/packages/ui/src/components/Review/__tests__/MediaTrashPage.connection.test.tsx`
- `apps/packages/ui/src/components/Review/__tests__/ReviewPage.connection.test.tsx`

The harnesses should mock only:

- `useServerOnline`
- `useConnectionUxState`
- `useServerCapabilities`
- `useDemoMode`
- `useNavigate`
- `useConnectionActions` where retry is asserted

Required assertions:

- auth-required state shows credentials guidance and routes to `/settings/tldw`
- setup-required state shows setup guidance and routes to `/`
- unreachable state shows diagnostics guidance and can retry
- `ReviewPage` keeps demo preview plus state-aware guidance when demo mode is enabled
- `ReviewPage forceOffline` stays on the generic offline path
- `testing` does not render the new auth/setup/unreachable messaging

## Risks

- `ReviewPage` is large, so the patch must stay at the top-level gate and avoid downstream query behavior changes.
- `ViewMediaPage` and `MediaTrashPage` depend on capability checks immediately after the offline gate; the new state-aware guard must preserve that ordering.
- Existing heavy Review suites should remain untouched unless the new connection tests expose an actual conflict.
