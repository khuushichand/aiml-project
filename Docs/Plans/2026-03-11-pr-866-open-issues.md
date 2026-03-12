# PR 866 Open Issues Implementation Plan

## Stage 1: Reproduce And Lock The CI Regression
**Goal**: Capture the failing `UX Smoke Gate` condition in an automated regression test.
**Success Criteria**: A test demonstrates that the connection store ignores a persisted first-run flag when `chrome.storage.local` exists but does not contain the key.
**Tests**: `apps/packages/ui/src/store/__tests__/connection.test.ts`
**Status**: Complete

## Stage 2: Fix Persistent Flag Fallback
**Goal**: Make the connection store fall back to `localStorage` when `chrome.storage.local` is available but missing the requested flag.
**Success Criteria**: The first-run completion flag is restored correctly in the smoke runtime and no existing connection-store behaviors regress.
**Tests**: `apps/packages/ui/src/store/__tests__/connection.test.ts`
**Status**: Complete

## Stage 3: Verify And Close Review Threads
**Goal**: Re-run the targeted verification suite and close the remaining already-satisfied PR review threads.
**Success Criteria**: Targeted tests pass, Bandit is run for touched scope, and the three unresolved Gemini threads are resolved on GitHub.
**Tests**: `apps/packages/ui/src/store/__tests__/connection.test.ts`, existing PR-866 targeted Vitest tests
**Status**: Complete
