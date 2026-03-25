# Chat TTS Voice Gating Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the chat "Read aloud" gating so `ttsProvider=tldw` uses the selected model's built-in provider voice catalog before treating tldw TTS as unavailable.

**Architecture:** Keep the fix local to the shared `useTldwAudioStatus` hook by teaching it to infer the active tldw provider from an optional selected model and to check the provider voice catalog first, then fall back to custom uploaded voices. Update the chat call sites to pass the selected `tldwTtsModel`, and lock the behavior in with targeted hook tests.

**Tech Stack:** React, TanStack Query, Vitest, Testing Library

---

## Stage 1: Reproduce The Bug
**Goal:** Capture the broken chat voice-availability behavior in an automated test.
**Success Criteria:** A new hook test fails on the current implementation because catalog voices are ignored when custom voices are empty.
**Tests:** `bunx vitest run apps/packages/ui/src/hooks/__tests__/useTldwAudioStatus.test.tsx`
**Status:** Complete

### Task 1: Add the failing regression test

**Files:**
- Modify: `apps/packages/ui/src/hooks/__tests__/useTldwAudioStatus.test.tsx`

- [x] Add a test covering `requireVoices: true` with a Kitten model, empty custom voices, and non-empty provider catalog.
- [x] Run `bunx vitest run src/hooks/__tests__/useTldwAudioStatus.test.tsx` from `apps/packages/ui`.
- [x] Confirm the new test fails for the expected reason.

## Stage 2: Implement The Hook Fix
**Goal:** Make chat voice availability depend on the selected tldw model's provider catalog, with a custom-voice fallback.
**Success Criteria:** The hook returns `voicesAvailable=true` when catalog voices exist for the inferred provider, and existing health behavior remains unchanged.
**Tests:** `bunx vitest run apps/packages/ui/src/hooks/__tests__/useTldwAudioStatus.test.tsx`
**Status:** Complete

### Task 2: Update the hook and chat call sites

**Files:**
- Modify: `apps/packages/ui/src/hooks/useTldwAudioStatus.tsx`
- Modify: `apps/packages/ui/src/components/Common/Playground/Message.tsx`
- Modify: `apps/packages/ui/src/components/Common/Playground/useMessageState.ts`

- [x] Add an optional `tldwTtsModel` input to `useTldwAudioStatus`.
- [x] Infer the active tldw provider and query `/api/v1/audio/voices/catalog?provider=...` before falling back to `/api/v1/audio/voices`.
- [x] Pass the stored `tldwTtsModel` through the chat message call sites.
- [x] Re-run the hook test file and confirm it passes.

## Stage 3: Verify Integration Safety
**Goal:** Confirm the targeted chat regression is fixed without breaking nearby message behavior.
**Success Criteria:** Targeted message tests still pass and security verification is recorded for the touched paths.
**Tests:** `bunx vitest run apps/packages/ui/src/components/Common/Playground/__tests__/Message.error-recovery.integration.test.tsx`
**Status:** Complete

### Task 3: Run focused verification

**Files:**
- Verify: `apps/packages/ui/src/components/Common/Playground/__tests__/Message.error-recovery.integration.test.tsx`
- Verify: `apps/packages/ui/src/hooks/__tests__/useTldwAudioStatus.test.tsx`
- Verify: `apps/packages/ui/src/hooks/useTldwAudioStatus.tsx`
- Verify: `apps/packages/ui/src/components/Common/Playground/Message.tsx`
- Verify: `apps/packages/ui/src/components/Common/Playground/useMessageState.ts`

- [x] Run the focused Vitest suites for the hook and message integration.
- [x] Run Bandit on the touched UI paths from the project virtualenv and review the results.
- [x] Update this plan status to complete when verification is done.

Notes:
- `Message.error-recovery.integration.test.tsx` passed after the change.
- `Message.routing-fallback.integration.test.tsx` still fails on the existing workspace-scope save assertion and was left untouched.
- Bandit produced no findings, but it cannot parse `.ts`/`.tsx` files and reported AST syntax errors for the touched UI files.

## Stage 4: Remove Capability False Negatives
**Goal:** Prevent stale or missing `hasTts` capability data from greying out chat when the selected tldw provider's voice catalog is reachable.
**Success Criteria:** `useTldwAudioStatus` keeps TTS in an `unknown` state instead of `unavailable` when catalog voices confirm provider reachability, even if `hasTts` is false.
**Tests:** `bunx vitest run src/hooks/__tests__/useTldwAudioStatus.test.tsx src/components/Common/Playground/__tests__/Message.error-recovery.integration.test.tsx`
**Status:** Complete

### Task 4: Fail open on real voice availability

**Files:**
- Modify: `apps/packages/ui/src/hooks/useTldwAudioStatus.tsx`
- Modify: `apps/packages/ui/src/hooks/__tests__/useTldwAudioStatus.test.tsx`

- [x] Add a failing regression for `hasTts=false` with reachable catalog voices for the selected tldw model.
- [x] Let voice probing run even when capability detection says TTS is unavailable.
- [x] Treat confirmed voices as stronger evidence than stale capability data for chat gating.
- [x] Re-run the focused hook and message tests and confirm they pass.
