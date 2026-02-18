# Implementation Plan: Knowledge QA - Error Handling and Edge Cases

## Scope

Components: `apps/packages/ui/src/components/Option/KnowledgeQA/index.tsx`, `KnowledgeQAProvider.tsx`, `ExportDialog.tsx`, online/capability status hooks, local storage persistence helpers
Finding IDs: `10.1` through `10.10`

## Finding Coverage

- Improve server-offline and capability messaging: `10.1`, `10.2`
- Add persistence transparency and fallback status: `10.3`, `10.4`, `10.5`
- Harden storage/no-result/long-answer behavior: `10.7`, `10.8`, `10.9`
- Improve export failure communication while preserving strong delete-retry pattern: `10.6`, `10.10`

## Stage 1: Connection and Capability Recovery UX
**Goal**: Turn static error screens into actionable recovery flows.
**Success Criteria**:
- Offline state includes manual retry and timed auto-retry indicator (`10.1`).
- RAG-not-available state provides concrete setup guidance and docs link (`10.2`).
- Retry behavior is bounded and does not spam network calls.
**Tests**:
- Integration tests for retry button and countdown polling behavior.
- Component tests for capability-state guidance copy and link presence.
- Unit tests for retry scheduler/backoff helpers.
**Status**: Complete

## Stage 2: Persistence-Failure Transparency and Local-Mode Signaling
**Goal**: Inform users when data is not being persisted without over-alerting.
**Success Criteria**:
- Local-thread fallback displays subtle offline/not-synced indicator (`10.3`).
- First persistence failure for chat message shows non-blocking warning (`10.4`).
- RAG context persistence failure handling is reviewed and documented as metadata-only path (`10.5`).
**Tests**:
- Provider tests for fallback thread creation and status-flag propagation.
- Integration tests for one-time warning toast/banner behavior.
- Unit tests ensuring warning dedupe (first-failure only).
**Status**: Complete

## Stage 3: State Robustness for Storage and Empty Results
**Goal**: Prevent silent failures and ambiguous blank UI outcomes.
**Success Criteria**:
- localStorage writes are wrapped with quota handling and trimming strategy (`10.7`).
- Empty-result searches render explicit no-results guidance (`10.9`).
- Long answers have controlled default viewport with expand affordance (`10.8`).
**Tests**:
- Unit tests simulating `QuotaExceededError` and trim/retry path.
- Integration tests for no-results state copy and suggestions.
- Component tests for answer max-height + expand/collapse behavior.
**Status**: Complete

## Stage 4: Export/Error Messaging Consistency and Recovery Patterns
**Goal**: Standardize user-visible error reporting across actions.
**Success Criteria**:
- Chatbook export failures surface user-visible errors with actionable retry (`10.10`).
- Existing strong history delete failure + retry toast pattern is preserved (`10.6`).
- Error taxonomy is shared across export and query actions where feasible.
**Tests**:
- Integration tests for export failure toast and retry outcomes.
- Regression tests preserving delete failure retry action behavior.
- Unit tests for shared error-message mapping utility.
**Status**: Complete

## Dependencies

- Export failure handling should be implemented jointly with Export and Sharing plan stage work (`7.7`).
