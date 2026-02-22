# Chat Page (Playground) Group 03 - User Flows and Task Completion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove friction and dead ends across first-message, multi-turn, roleplay, compare, RAG, voice, branching, and export/share workflows.

**Architecture:** Harden each critical flow as an explicit state machine with visible transitions and recovery actions, then validate with integration and end-to-end flow tests.

**Tech Stack:** React, TypeScript, existing chat/voice/RAG hooks, modal workflows, Vitest + Playwright.

---

## Scope

- Findings: `UX-013`, `UX-014`, `UX-015`, `UX-016`, `UX-017`, `UX-018`, `UX-019`, `UX-020`
- Primary surfaces:
  - `apps/tldw-frontend/src/components/Option/Playground/PlaygroundEmpty.tsx`
  - `apps/tldw-frontend/src/components/Option/Playground/PlaygroundChat.tsx`
  - `apps/tldw-frontend/src/components/Common/Playground/MessageActionsBar.tsx`
  - `apps/tldw-frontend/src/components/Sidepanel/Chat/RagSearchBar.tsx`
  - `apps/tldw-frontend/src/components/Layouts/ChatHeader.tsx`

## Stage 1: First Message and Multi-Turn Baseline
**Goal**: Make initial send and iterative follow-up paths predictable and low-friction.
**Success Criteria**:
- Empty-state starter intents preconfigure relevant modes.
- Post-send focus and next-step affordances are consistent.
- Corrections and clarifications maintain clear state continuity.
**Tests**:
- Add integration tests for starter-card to first-response path.
- Add multi-turn tests for edit/regenerate/continue workflows.
**Status**: Complete

## Stage 2: Character and Compare Core Flow Hardening
**Goal**: Stabilize high-value advanced flow completion paths.
**Success Criteria**:
- Character selection -> greeting -> response loop is explicit and recoverable.
- Compare flow enforces model selection prerequisites before send.
- Canonical/winner continuation choices are explicit and persisted.
**Tests**:
- Add integration tests for character start and mid-chat persona updates.
- Add compare flow tests for preflight, result evaluation, and continuation.
**Status**: Complete

## Stage 3: RAG-Grounded Chat Completion Loop
**Goal**: Keep retrieval and citation verification in the natural conversation workflow.
**Success Criteria**:
- Users can pin sources, ask follow-up questions, and inspect citations without context loss.
- Citation interactions offer clear provenance and source jump controls.
- Pinned-source state persists across turns and branches.
**Tests**:
- Add integration tests for pin/search/ask/verify loop.
- Add tests for pinned-state persistence and restoration.
**Status**: Complete

## Stage 4: Voice and Branching Reliability
**Goal**: Ensure voice and branch exploration are first-class, not fragile add-ons.
**Success Criteria**:
- Voice mode shows recording/transcription/tts state clearly and supports typing handoff.
- Branch creation from any message has clear fork semantics.
- Returning to original branch is one action with visible branch context.
**Tests**:
- Add voice mode integration tests for mode switches and interruption handling.
- Add branching tests for fork, navigate, and return paths.
**Status**: Complete

## Stage 5: Error Recovery and Export/Share Completion
**Goal**: Prevent user work loss and unblock sharing workflows.
**Success Criteria**:
- Mid-stream failure preserves partial output and offers retry/switch/fallback actions.
- Export/share actions include status, completion feedback, and error remediation.
- Shared-link read-only view path is validated end-to-end.
**Tests**:
- Add stream failure simulation tests for retry/switch paths.
- Add end-to-end tests for export and shared-link open flows.
**Status**: Complete

## Dependencies

- Depends on Group 01 state visibility and Group 02 signal quality.
- Group 05 compare implementation details must align with this flow contract.

## Exit Criteria

- All critical flows can be completed without hidden prerequisites or unrecoverable dead ends.

## Progress Notes (2026-02-22)

- Validated first-message/multi-turn, compare contract, RAG search loops, and recovery/share flows through focused integration and guard suites.
- Included voice dictation cross-surface contract verification and fixed a brittle contract mismatch in `src/components/Sidepanel/Chat/form.tsx` (no behavior change; contract parity restored).
- Evidence command (passing): consolidated 42-file sweep including `Playground.search.integration`, `PlaygroundChat.search.integration`, `dictation.cross-surface.contract`, `Message.error-recovery.*`, and share-link integration tests.
- Stage 4 closure evidence:
  - Added explicit branch fork/return coverage in `src/components/Option/Playground/__tests__/ConversationBranching.integration.test.tsx`.
  - Added branch context badge coverage (fork point + depth + return action) in `src/components/Option/Playground/__tests__/Playground.search.integration.test.tsx`.
  - Consolidated closure run (2026-02-22): `10 files / 45 tests passed`.
