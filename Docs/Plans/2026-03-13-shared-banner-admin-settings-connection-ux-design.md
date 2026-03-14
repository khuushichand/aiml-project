# Shared Banner And Admin Settings Connection UX Design

**Date:** 2026-03-13

## Goal

Correct the remaining shared banner and warning-only admin/settings surfaces so auth-required, setup-required, and unreachable-server states no longer collapse into generic offline messaging.

## Scope

- Modify `apps/packages/ui/src/components/Common/ConnectFeatureBanner.tsx`.
- Modify these local user-facing warning surfaces:
  - `apps/packages/ui/src/components/Option/KnowledgeQA/index.tsx`
  - `apps/packages/ui/src/components/Option/ModerationPlayground/ModerationPlaygroundShell.tsx`
  - `apps/packages/ui/src/components/Option/Settings/GuardianSettings.tsx`
  - `apps/packages/ui/src/components/Option/Settings/evaluations.tsx`
- Add focused regression coverage for the shared banner and the affected pages.

Out of scope:

- Notes, Writing Playground, Quick Ingest, and other true offline-capable flows
- Sidepanel chat and other mixed transport surfaces
- Refactors to internal query guards or queue semantics

## Current Problem

Several remaining pages still rely on either:

- `ConnectFeatureBanner`, which always renders a setup-oriented CTA even when the real problem is missing credentials or an unreachable server
- local inline warnings that say only "offline" or "connect to your server"

This still misclassifies:

- missing or invalid credentials
- incomplete first-run or URL setup
- configured but unreachable backends
- transient testing states

## Design

### Shared banner

Update `ConnectFeatureBanner` to read `useServerOnline()` and `useConnectionUxState()` itself.

Behavior:

- `!isOnline && uxState === "error_auth"` or `configuring_auth`
  - show built-in credentials guidance
  - primary action `/settings/tldw`
- `!isOnline && uxState === "unconfigured"` or `configuring_url`
  - show built-in setup guidance
  - primary action `/`
- `!isOnline && uxState === "error_unreachable"`
  - show built-in diagnostics guidance
  - primary action `/settings/health`
  - secondary action `/settings/tldw`
- `!isOnline && uxState === "testing"`
  - render nothing
- any other case
  - keep current caller-supplied title/description/examples and current CTA behavior

Caller-provided copy stays the generic fallback only. State-specific auth/setup/unreachable copy should come from the component itself so callers do not accidentally mislabel the problem.

This automatically improves:

- `apps/packages/ui/src/components/Option/Settings/general-settings.tsx`
- the offline Prompts entry in `apps/packages/ui/src/components/Option/Prompt/index.tsx`

### KnowledgeQA

Replace the centered offline panel in `KnowledgeQA/index.tsx` with state-aware handling:

- auth/setup -> targeted actions instead of retry loop
- unreachable -> preserve retry CTA and countdown
- testing/generic fallback -> keep current generic offline behavior

Do not change the RAG-capability branch.

### Warning-only settings/admin pages

For `ModerationPlaygroundShell`, `GuardianSettings`, and `evaluations.tsx`:

- keep their current page layouts
- replace the generic warning copy with state-aware auth/setup/unreachable messaging and actions
- suppress the warning entirely during `uxState === "testing"`

These pages should remain warning-only surfaces, not new hard gates.

## Testing

Create focused connection-state tests:

- `apps/packages/ui/src/components/Common/__tests__/ConnectFeatureBanner.connection.test.tsx`
- `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.connection.test.tsx`
- `apps/packages/ui/src/components/Option/ModerationPlayground/__tests__/ModerationPlaygroundShell.connection.test.tsx`
- `apps/packages/ui/src/components/Option/Settings/__tests__/GuardianSettings.connection.test.tsx`
- `apps/packages/ui/src/components/Option/Settings/__tests__/evaluations.connection.test.tsx`

The tests should assert:

- shared banner auth/setup/unreachable actions and `testing` suppression
- KnowledgeQA auth/setup replacement of the generic offline screen
- KnowledgeQA unreachable retry behavior preserved
- warning-only settings/admin pages show actionable auth/setup/unreachable copy without blocking the rest of the page
- warning-only settings/admin pages suppress the warning during `testing`

## Risks

- `ConnectFeatureBanner` is shared; the change must preserve current fallback behavior for callers outside this sweep.
- `KnowledgeQA` has retry timing and capability logic; the patch must stay ahead of RAG capability checks and not disturb the retry scheduler.
- The warning-only admin/settings pages should not be converted into empty-state screens or disable their existing non-connection content.
