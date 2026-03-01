# Chat Page (Playground) Group 05 - Compare Mode Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make compare mode intuitive from activation through winner selection and continuation.

**Architecture:** Define compare as an explicit contract (`same prompt -> N models -> evaluate -> continue`) and standardize model identity, output comparability, and post-selection continuation semantics.

**Tech Stack:** React, TypeScript, compare-mode store/hooks, message rendering pipeline, Vitest integration tests.

---

## Scope

- Findings: `UX-027`, `UX-028`, `UX-029`, `UX-030`
- Primary surfaces:
  - `apps/tldw-frontend/src/components/Option/Playground/CompareToggle.tsx`
  - `apps/tldw-frontend/src/components/Option/Playground/PlaygroundChat.tsx`
  - `apps/tldw-frontend/src/components/Common/Playground/Message.tsx`
  - `apps/tldw-frontend/src/hooks/chat/*compare*`

## Stage 1: Activation Contract and Preflight
**Goal**: Eliminate ambiguity before first compare send.
**Success Criteria**:
- Compare activation surfaces a short contract and selected-model count.
- Compare send path blocks invalid states (<2 models) with corrective guidance.
- Shared context scope (character/RAG/system) is shown pre-send.
**Tests**:
- Add activation and preflight guard tests.
- Add integration tests for invalid/valid compare send transitions.
**Status**: Complete

## Stage 2: Response Comparability and Identity
**Goal**: Support fair and comprehensible evaluation across models.
**Success Criteria**:
- Every response card clearly shows model/provider identity.
- Optional normalized preview mode reduces length bias.
- Optional diff view highlights material differences.
**Tests**:
- Add rendering tests for model identity labels.
- Add utility tests for normalization/diff logic.
**Status**: Complete

## Stage 3: Winner Selection and Continuation Contract
**Goal**: Make post-compare continuation deterministic.
**Success Criteria**:
- Winner action uses plain language (`Use as Main Response`).
- After selection, user chooses `Continue with Winner` or `Keep Comparing`.
- Continuation choice persists and is visible in timeline metadata.
**Tests**:
- Add state tests for continuation-mode persistence.
- Add integration tests for next-turn behavior under each continuation mode.
**Status**: Complete

## Stage 4: Cross-Mode Interoperability
**Goal**: Define compare interaction with character, RAG, and voice.
**Success Criteria**:
- UI explicitly states compare interoperability behavior before send.
- Unsupported combinations are blocked or downgraded with clear reason.
- Per-model follow-up composer inputs route correctly with no leakage.
**Tests**:
- Add integration tests for compare+character, compare+RAG, compare+voice.
- Add routing tests for per-model follow-up targeting.
**Status**: Complete

## Stage 5: Mobile and Accessibility Contracts
**Goal**: Ensure compare mode remains usable on constrained devices and assistive tech.
**Success Criteria**:
- Mobile compare uses stacked cards/tabs without silent feature loss.
- Screen readers can identify model clusters and winner state.
- Touch targets and focus order support rapid compare workflows.
**Tests**:
- Add mobile compare interaction tests.
- Add accessibility tests for compare announcements and focus management.
**Status**: Complete

## Dependencies

- Depends on Group 01 mode/state legibility and Group 04 composer hierarchy.
- Inputs from Group 02 model capability and cost metadata are required.

## Exit Criteria

- Users can reliably execute and close a compare cycle without uncertainty about what happens next.

## Progress Notes (2026-02-22)

- Validated compare lifecycle end-to-end via:
  - `CompareToggle.integration.test.tsx`
  - `compare-preflight.test.ts`
  - `compare-interoperability.test.ts`
  - `compare-normalized-preview.test.ts`
  - `compare-response-diff.test.ts`
  - `PlaygroundChat.compare-contract.guard.test.ts`
  - `PlaygroundChat.model-identity.guard.test.ts`
  - `PlaygroundChat.normalized-preview.guard.test.ts`
  - `PlaygroundChat.diff-preview.guard.test.ts`
  - `PlaygroundChat.winner-copy.guard.test.ts`
  - `PlaygroundChat.per-model-routing.integration.test.tsx`
