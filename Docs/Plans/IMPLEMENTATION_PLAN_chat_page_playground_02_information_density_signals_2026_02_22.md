# Chat Page (Playground) Group 02 - Information Density and Missing Signals Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Surface high-value runtime signals (cost, context, provenance, status, variants, branches) while reducing noisy UI output.

**Architecture:** Centralize message/session diagnostics in a shared usage and provenance model, then expose concise, layered signals across message cards, composer context strip, and model/provider controls.

**Tech Stack:** React, TypeScript, chat state hooks, retrieval metadata payloads, Vitest integration tests.

---

## Scope

- Findings: `UX-006`, `UX-007`, `UX-008`, `UX-009`, `UX-010`, `UX-011`, `UX-012`
- Primary surfaces:
  - `apps/tldw-frontend/src/components/Option/Playground/CostEstimation.tsx`
  - `apps/tldw-frontend/src/components/Option/Playground/TokenProgressBar.tsx`
  - `apps/tldw-frontend/src/components/Common/Playground/Message.tsx`
  - `apps/tldw-frontend/src/components/Common/Playground/MessageSource.tsx`
  - `apps/tldw-frontend/src/components/Sidepanel/Chat/RagSearchBar.tsx`
  - `apps/tldw-frontend/src/components/Sidepanel/Chat/ConnectionStatusIndicator.tsx`

## Stage 1: Turn-Level and Session-Level Usage Signals
**Goal**: Show users what each turn cost and how close they are to context and budget limits.
**Success Criteria**:
- Each assistant message can reveal input/output tokens and estimated turn cost.
- Composer strip shows cumulative session tokens, cost, and remaining context budget.
- Token budget bar distinguishes safe, warning, and overflow thresholds.
**Tests**:
- Add unit tests for usage aggregation calculations.
- Add component tests for turn/session usage rendering and warning states.
**Status**: Complete

## Stage 2: Model Capability and Provider Health Transparency
**Goal**: Make model/provider selection informed and resilient.
**Success Criteria**:
- Model selector includes context window, tool/vision/streaming badges, and price hints.
- Provider health state (healthy/degraded/rate-limited) appears near active model.
- Degraded state surfaces actionable switch/fallback recommendations.
**Tests**:
- Add selector rendering tests for capability badges.
- Add integration tests for degraded/rate-limited status UX.
**Status**: Complete

## Stage 3: Retrieval Provenance and Citation Explainability
**Goal**: Make source-grounded answers auditable by users.
**Success Criteria**:
- Citation click opens "why this source" with score, retrieval strategy, and chunk metadata.
- Pinned source usage is visible per answer.
- RAG cards include relevance and selected-strategy metadata.
**Tests**:
- Add integration tests for citation drill-down and back navigation.
- Add tests for provenance metadata rendering from backend payloads.
**Status**: Complete

## Stage 4: Timeline State Signals (Variants, Branches, Conversation State)
**Goal**: Improve orientation in long or branched conversations.
**Success Criteria**:
- Variant controls show explicit count (for example `2 of 4`).
- Branch markers show fork point and branch depth.
- Conversation state chip (`In Progress`, `Resolved`, `Backlog`) is visible and editable.
**Tests**:
- Add tests for variant/branch badge rendering and updates.
- Add integration tests for conversation state transitions.
**Status**: Complete

## Stage 5: Error Signal Quality and Noise Reduction
**Goal**: Ensure failures are clear, recoverable, and not noisy.
**Success Criteria**:
- Provider/rate-limit/context-overflow errors include specific remediation actions.
- Non-actionable debug noise is hidden behind optional details toggles.
- Recovery cards preserve context and partial outputs where available.
**Tests**:
- Add integration tests for error-card action flows.
- Run focused regression suite for stream interruptions and overflow handling.
**Status**: Complete

## Dependencies

- Depends on Group 01 state bar and mode labeling contracts.
- Enables Group 03 recovery flow and Group 04 composer simplification.

## Exit Criteria

- Users can answer: "What mode/state am I in, what is this costing, why did this source appear, and what should I do if this fails?" without leaving the current view.

## Progress Notes (2026-02-22)

- Completed validation of usage accounting, provenance transparency, and error-recovery signals via focused test runs.
- Test evidence (33 tests passing total):
  - `bunx vitest run src/components/Option/Playground/__tests__/usage-metrics.test.ts src/components/Option/Playground/__tests__/ContextFootprintPanel.test.tsx src/components/Option/Playground/__tests__/ContextFootprintPanel.integration.test.tsx src/components/Common/Playground/__tests__/MessageSource.integration.test.tsx src/components/Sidepanel/Chat/__tests__/SourceFeedback.integration.test.tsx src/components/Sidepanel/Chat/__tests__/SourceFeedback.citation.integration.test.tsx src/components/Common/Playground/__tests__/routing-fallback-audit.test.ts src/components/Common/Playground/__tests__/Message.routing-fallback.integration.test.tsx src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts --reporter=dot`
  - `bunx vitest run src/components/Common/Playground/__tests__/MessageActionsBar.menuOptions.test.tsx src/components/Common/Playground/__tests__/Message.error-recovery.guard.test.ts src/components/Common/Playground/__tests__/Message.error-recovery.integration.test.tsx src/components/Common/Playground/__tests__/MessageSource.transparency.guard.test.ts --reporter=dot`
- Stage 2 completion evidence:
  - Added capability/price/context badges in selector hook and validated with `src/hooks/playground/__tests__/useModelSelector.capabilities.test.tsx`.
  - Added degraded provider recommendation signal coverage in `src/components/Option/Playground/__tests__/ComposerToolbar.test.tsx`.
- Stage 4 completion evidence:
  - Variant label now renders explicit `x of y` count, validated in `src/components/Common/Playground/__tests__/MessageActionsBar.menuOptions.test.tsx`.
  - Conversation state transition contract validated in `src/components/Common/__tests__/ConversationTab.generationOverride.test.tsx`.
- Consolidated closure run (2026-02-22): `10 files / 45 tests passed`.
