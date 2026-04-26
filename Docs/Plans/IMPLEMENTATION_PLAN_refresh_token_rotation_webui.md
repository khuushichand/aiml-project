# Implementation Plan: refresh_token_rotation_webui

## Stage 1: Reproduce Rotated Refresh Token Regression

**Goal**: Capture the client bug where refresh responses rotate the refresh token but the WebUI keeps the stale one.
**Success Criteria**: Focused tests fail because `TldwAuth.refreshToken()` and stream fallback do not persist returned `refresh_token` values.
**Tests**: `bunx vitest run src/services/__tests__/tldw-auth.refresh-rotation.test.ts src/services/__tests__/background-proxy.test.ts -t "persists rotated refresh token"`
**Status**: Complete

## Stage 2: Persist Rotated Refresh Tokens

**Goal**: Update both normal auth refresh and streaming refresh fallback to save rotated refresh tokens.
**Success Criteria**: Returned refresh tokens replace stale stored values and stream retry uses the refreshed auth state.
**Tests**: Existing and new targeted Vitest tests.
**Status**: Complete

## Stage 3: Verify And Secure

**Goal**: Re-run targeted test coverage and TypeScript validation after the auth-state changes.
**Success Criteria**: Targeted tests and the shared UI type-check pass.
**Tests**: `bunx vitest run src/services/__tests__/background-proxy.test.ts src/services/__tests__/tldw-auth.refresh-rotation.test.ts src/services/__tests__/tldw-auth.splash-event.test.ts` and `bunx tsc --noEmit -p apps/packages/ui/tsconfig.json`
**Status**: Complete
