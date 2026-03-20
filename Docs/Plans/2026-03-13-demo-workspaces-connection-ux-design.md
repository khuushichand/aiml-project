# Demo Workspaces Connection UX Design

**Date:** 2026-03-13

## Goal

Correct the connection UX for the demo-enabled Quiz, Flashcards, and Media workspaces so demo preview remains available without masking the real auth/setup/unreachable state.

## Scope

- Modify:
  - `apps/packages/ui/src/components/Quiz/QuizWorkspace.tsx`
  - `apps/packages/ui/src/components/Flashcards/FlashcardsWorkspace.tsx`
  - `apps/packages/ui/src/routes/option-media-multi.tsx`
- Add or extend focused connection-state tests for those three surfaces.

Out of scope:

- shared demo-aware gate extraction
- routed/non-demo Prompt Studio work
- capability-state refactors
- changing the actual demo content or preview interactions

## Current Problem

Each of these pages currently branches on `!isOnline` first and then gives full precedence to `demoEnabled`. That preserves the preview, but it hides whether the real problem is:

- missing credentials
- first-run setup not completed
- unreachable server

When `demoEnabled` is false, the same pages still collapse those states into generic offline copy.

## Design

### State model

Add `useConnectionUxState()` to each page and treat connection state separately from `demoEnabled`.

#### Demo enabled

- Keep the existing demo preview intact.
- If `uxState` is `error_auth`, `configuring_auth`, `unconfigured`, `configuring_url`, or `error_unreachable`, prepend a small inline warning above the preview.
- Do not replace the preview with a full-screen empty state.
- If `uxState === "testing"`, show no warning and keep demo content unchanged.

#### Demo disabled

- Replace the current generic offline branch with state-aware guidance:
  - auth-required
  - setup-required
  - unreachable
- Keep the existing generic offline copy only as a fallback for uncategorized `!isOnline` cases.
- For `testing`, do not show auth/setup/unreachable guidance.

### Surface-specific actions

#### Quiz and Flashcards

Keep the existing local recovery model:

- primary CTA stays `Go to server card`
- use `scrollToServerCard(...)`
- keep retry only for unreachable or generic connection-failure states

This is more consistent with those pages than switching to settings navigation.

#### Media

Keep the existing direct-navigation model:

- setup/auth routes to `/settings/tldw`
- unreachable routes to `/settings/health` with a secondary settings action

There is no in-page server-card helper here, so direct navigation remains the pragmatic choice.

### UI primitives

- Quiz and Flashcards:
  - non-demo offline state can keep `ConnectionProblemBanner`
  - demo-mode warning should be a smaller inline warning strip or `Alert`, not `ConnectionProblemBanner`
- Media:
  - keep existing `FeatureEmptyState` shape for non-demo offline state
  - demo-mode warning should also be smaller than the full preview block

## Testing

### Quiz

Extend:

- `apps/packages/ui/src/components/Quiz/__tests__/QuizWorkspace.connection-state.test.tsx`

Add assertions that:

- demo preview still renders while auth/setup/unreachable warning is visible
- non-demo auth/setup/unreachable states show the correct guidance
- existing demo and capability tests stay green

### Flashcards

Create:

- `apps/packages/ui/src/components/Flashcards/__tests__/FlashcardsWorkspace.connection-state.test.tsx`

Cover:

- demo preview preserved with warning
- non-demo auth/setup/unreachable guidance

### Media

Create:

- `apps/packages/ui/src/routes/__tests__/option-media-multi.connection-state.test.tsx`

Cover:

- demo preview preserved with warning
- non-demo auth/setup/unreachable guidance
- keep the old route-wrapper test focused on route composition only

## Risks

- `ConnectionProblemBanner` is too large for demo mode, so reusing it above previews would effectively undo the demo-preserving design.
- `testing` has no existing dedicated loading shell in these pages, so it must be handled explicitly.
- Quiz already has a mature harness; changes there need to be kept small to avoid breaking unrelated demo-flow assertions.
