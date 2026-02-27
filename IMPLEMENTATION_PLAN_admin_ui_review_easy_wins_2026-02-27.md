## Stage 1: Harden Admin Event Streaming Auth
**Goal**: Remove credential leakage via URL query params for admin event streaming while preserving stream behavior.
**Success Criteria**: Admin events stream no longer appends JWT/API keys to URL; stream still supports authenticated requests.
**Tests**: Add/extend `admin-ui/lib/admin-events` tests to assert no credential query params and event-frame parsing behavior.
**Status**: Complete

## Stage 2: Ensure Auth Mode Exclusivity
**Goal**: Prevent mixed auth state by clearing API key when password login succeeds and clearing JWT when API-key login succeeds.
**Success Criteria**: Outbound auth headers contain only the active auth mode after login transitions.
**Tests**: Extend `admin-ui/lib/auth.test.ts` with login-mode-switch coverage.
**Status**: Complete

## Stage 3: Fix ACP Sessions Filter Fetch Behavior
**Goal**: Stop automatic fetches on every filter keystroke; only fetch when user applies filters (plus initial load).
**Success Criteria**: Typing filter values does not trigger API calls until Apply is clicked.
**Tests**: Add `admin-ui/app/acp-sessions/__tests__/page.test.tsx` to verify fetch call count and apply flow.
**Status**: Complete

## Stage 4: Close Remaining Easy Wins
**Goal**: Resolve remaining review items (lint warnings and README port mismatch).
**Success Criteria**: Lint has no warnings in touched scope; README run URL matches scripts.
**Tests**: Run lint and relevant targeted tests.
**Status**: Complete
