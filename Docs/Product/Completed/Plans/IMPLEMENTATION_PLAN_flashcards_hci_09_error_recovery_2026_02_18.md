# Implementation Plan: Flashcards H9 - Help Users Recognize, Diagnose, and Recover from Errors

## Scope

Route/components: `tabs/ManageTab.tsx`, `tabs/ReviewTab.tsx`, flashcard mutation handlers, API error mapping utilities  
Finding IDs: `H9-1` through `H9-2`

## Finding Coverage

- Optimistic lock/version conflict errors are generic and non-actionable: `H9-1`
- Review submit failures provide no guided retry path: `H9-2`

## Stage 1: Error Taxonomy and User-Facing Messaging
**Goal**: Translate low-level API failures into clear recovery instructions.
**Success Criteria**:
- Version conflict errors map to explicit message: "Card changed elsewhere. Reload and retry."
- Network, validation, and server failures each produce distinct UI guidance and action labels.
- Error surfaces include stable error codes for telemetry/debugging.
**Tests**:
- Unit tests for API error-to-UI message mapping.
- Component tests for conflict/error banner rendering in review and cards contexts.
- Regression tests for fallback unknown-error handling.
**Status**: Complete

**Implementation Notes (2026-02-18)**:
- Added a shared flashcards error taxonomy mapper with stable error codes:
  - `FLASHCARDS_VERSION_CONFLICT`
  - `FLASHCARDS_NETWORK`
  - `FLASHCARDS_VALIDATION`
  - `FLASHCARDS_NOT_FOUND`
  - `FLASHCARDS_SERVER`
  - `FLASHCARDS_UNKNOWN`
- New utility:
  - `apps/packages/ui/src/components/Flashcards/utils/error-taxonomy.ts`
  - Includes HTTP status extraction, conflict/network/validation/server classification, and standardized message formatting with code suffix.
- Wired Review/Cards mutation error surfaces to taxonomy-based messages:
  - `ReviewTab.tsx` (`review submit`, `edit save`, `delete`, `reset scheduling`)
  - `ManageTab.tsx` (`move`, `edit save`, `delete`, `reset scheduling`)
- Added debug-friendly structured console warnings with `{ code, status, operation, raw }` payload for taxonomy outcomes.

**Validation Completed**:
- Unit mapping coverage:
  - `apps/packages/ui/src/components/Flashcards/utils/__tests__/error-taxonomy.test.ts`
- Review surface conflict messaging coverage:
  - `apps/packages/ui/src/components/Flashcards/tabs/__tests__/ReviewTab.create-cta.test.tsx`
- Cards surface conflict messaging coverage:
  - `apps/packages/ui/src/components/Flashcards/tabs/__tests__/ManageTab.undo-stage3.test.tsx`
- Flashcards regression sweep:
  - `src/components/Flashcards/**/__tests__/*.test.tsx`
  - `src/utils/__tests__/flashcards-shortcut-hint-telemetry.test.ts`

## Stage 2: Built-In Retry and Reconciliation Flows
**Goal**: Let users recover without redoing multi-step actions.
**Success Criteria**:
- Review mutation failure surface includes retry action with idempotent safeguards.
- Version conflict flow offers reload current card data and resubmit path.
- Failed mutations preserve user input/state where possible.
**Tests**:
- Integration tests for retry-after-network-failure behavior.
- Mutation tests for optimistic lock conflict resolution path.
- E2E tests for review failure -> retry success and conflict -> reload -> retry.
**Status**: Complete

**Implementation Notes (2026-02-18)**:
- Added inline review failure recovery surface in `ReviewTab`:
  - actionable retry alert (`flashcards-review-retry-alert`)
  - explicit retry CTA (`flashcards-review-retry-button`)
  - conflict/not-found reload CTA (`flashcards-review-reload-button`)
- Added idempotent retry safeguards for review submits:
  - retry payload binds to specific `cardUuid`
  - retry reuses the captured `answerTimeMs` from the failed attempt
  - retry path aborts when queue/card context changed before resubmit
- Added review-side reconciliation flow:
  - reload action triggers `reviewQuery.refetch()` + `dueCountsQuery.refetch()`
  - failure state updates to “latest data loaded” and allows immediate retry.
- Added cards-side conflict reconciliation in `ManageTab` edit flow:
  - on version conflict during save, editor auto-loads latest card data via `getFlashcard`
  - user receives explicit “reloaded latest data; review and save again” guidance.
- Preserved user state during failures:
  - review failures keep answer/rating context visible
  - edit drawer remains open with refreshed data on conflict.

**Validation Completed**:
- `apps/packages/ui/src/components/Flashcards/tabs/__tests__/ReviewTab.create-cta.test.tsx`
  - conflict error shows retry/reload recovery surface
  - reload action refetches review + due counts
  - retry-after-network-failure succeeds with preserved `answerTimeMs`
- `apps/packages/ui/src/components/Flashcards/tabs/__tests__/ManageTab.undo-stage3.test.tsx`
  - version conflict in edit save triggers reload-latest reconciliation warning path
- Regression sweep:
  - `src/components/Flashcards/**/__tests__/*.test.tsx`
  - `src/components/Flashcards/utils/__tests__/error-taxonomy.test.ts`
  - `src/utils/__tests__/flashcards-shortcut-hint-telemetry.test.ts`

## Stage 3: Recovery Observability and QA Hardening
**Goal**: Verify recovery UX works under real failure conditions and remains stable.
**Success Criteria**:
- Error/retry metrics captured for flashcard mutations (rate, reason, success-after-retry).
- Automated fault-injection test cases cover offline, timeout, and conflict scenarios.
- Release checklist includes mandatory recovery-path validation for flashcards changes.
**Tests**:
- Fault-injection integration tests for each failure class.
- Telemetry unit tests for event emission on failure/retry/recovery.
- QA scenario tests for desktop and mobile interaction parity.
**Status**: Complete

**Implementation Notes (2026-02-18)**:
- Added flashcards recovery telemetry state + tracker:
  - `apps/packages/ui/src/utils/flashcards-error-recovery-telemetry.ts`
  - tracks failure, retry-requested, retry-succeeded, and reload-recovery signals.
- Wired telemetry emission into live recovery paths:
  - `ReviewTab.tsx`
    - failure events for mutation errors
    - retry requested/succeeded events
    - reload-recovery events
  - `ManageTab.tsx`
    - failure events for mutation errors
    - reload-recovery events on edit conflict reconciliation.
- Expanded fault-injection coverage:
  - network and conflict recovery behavior in review/cards component tests
  - timeout-style error classification in taxonomy tests.
- Added a release/QA checklist for mandatory recovery validation:
  - `Docs/Product/Completed/Plans/IMPLEMENTATION_PLAN_flashcards_hci_09_error_recovery_2026_02_18.md`

**Validation Completed**:
- Telemetry state unit tests:
  - `apps/packages/ui/src/utils/__tests__/flashcards-error-recovery-telemetry.test.ts`
- Recovery flow component tests:
  - `apps/packages/ui/src/components/Flashcards/tabs/__tests__/ReviewTab.create-cta.test.tsx`
  - `apps/packages/ui/src/components/Flashcards/tabs/__tests__/ManageTab.undo-stage3.test.tsx`
- Timeout fault-injection mapping:
  - `apps/packages/ui/src/components/Flashcards/utils/__tests__/error-taxonomy.test.ts`
- Full flashcards regression:
  - `src/components/Flashcards/**/__tests__/*.test.tsx`
  - `src/utils/__tests__/flashcards-shortcut-hint-telemetry.test.ts`
  - `src/utils/__tests__/flashcards-error-recovery-telemetry.test.ts`

## Dependencies

- Stage 1 depends on structured backend error payloads (conflict identifiers/codes).
- Stage 2 retry UX should reuse existing mutation patterns from other app modules where possible.
- Stage 3 instrumentation should feed H1 analytics for health/status visibility.
