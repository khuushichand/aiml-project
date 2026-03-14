# Prompt Studio Playground Connection UX Design

**Date:** 2026-03-13

## Goal

Correct the top-level connection gate in `apps/packages/ui/src/components/Option/PromptStudio/PromptStudioPlaygroundPage.tsx` so auth-required, setup-required, and unreachable-server states do not collapse into the current generic offline warning.

## Scope

- Modify only `PromptStudioPlaygroundPage`.
- Keep the page's existing loading, capability, and content logic intact.
- Add focused regression coverage for connection-state rendering and navigation.

Out of scope:

- Routed Prompt Studio entry points under `/prompts?tab=studio` and `/settings/prompt-studio`
- React Query query-enabling refactors
- Shared gate extraction or `WorkspaceConnectionGate` adoption

## Current Problem

`PromptStudioPlaygroundPage` reads `useServerOnline()` and immediately renders a single offline `Alert` when `online === false`. That drops richer connection store state on the floor:

- missing or broken credentials
- first-run or URL setup still incomplete
- reachable configuration state while health checks are still running
- server URL present but backend unreachable

This matches the earlier Collections, Persona, and Companion regressions.

## Design

### State handling

Add `useConnectionUxState()` to the page and branch before the existing generic offline guard:

- `error_auth` and `configuring_auth`
  - show credentials guidance
  - action goes to `/settings/tldw`
- `unconfigured` and `configuring_url`
  - show setup guidance
  - action goes to `/` for first-run users, otherwise `/settings/tldw`
- `error_unreachable`
  - show diagnostics guidance
  - primary action goes to `/settings/health`
  - secondary action goes to `/settings/tldw`
- `testing`
  - do not show an error state
  - fall through to the existing loading/skeleton behavior
- any other `!online` case
  - keep the current generic offline warning as fallback

### UI pattern

Stay inside the page's existing Ant Design `Alert` pattern instead of introducing `FeatureEmptyState` or `WorkspaceConnectionGate`. This keeps the patch visually local and low-risk for an unrouted component.

### Navigation

Treat this page as options-only:

- `/settings/tldw`
- `/settings/health`
- `/`

No shell-aware branching is needed.

## Testing

Create a new focused test file:

- `apps/packages/ui/src/components/Option/PromptStudio/__tests__/PromptStudioPlaygroundPage.connection.test.tsx`

The harness should:

- wrap the component in `QueryClientProvider`
- mock `useServerOnline`
- mock `useConnectionUxState`
- mock Prompt Studio service calls so React Query can mount cleanly
- mock `useNavigate`

Required assertions:

- auth-required state shows credentials copy and routes to `/settings/tldw`
- setup-required state shows setup copy and routes to `/`
- unreachable state shows diagnostics copy and routes to `/settings/health`
- `testing` does not render the connection alert and falls through to the existing loading state

## Risks

- The component is currently unrouted, so this fix improves dormant or internal usage rather than a primary user path.
- Because queries are declared before the render branches, the test harness needs minimal React Query setup to avoid false failures.
- No attempt should be made to align the routed Prompt Studio surfaces in the same patch.
