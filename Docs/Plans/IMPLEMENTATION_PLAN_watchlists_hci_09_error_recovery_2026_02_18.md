# Implementation Plan: Watchlists H9 - Help Users Recognize, Diagnose, and Recover from Errors

## Scope

Route/components: all watchlists tabs error boundaries/toasts, `RunDetailDrawer`, `SourcesBulkImport`  
Finding IDs: `H9.1` through `H9.3`

## Finding Coverage

- Generic failure messages without diagnosis/remediation: `H9.1`
- Run errors lack context-specific next steps: `H9.2`
- OPML import failures cannot be selectively retried: `H9.3`

## Stage 1: Structured Error Messaging Baseline
**Goal**: Replace generic errors with actionable, contextual messages.
**Success Criteria**:
- Shared error mapper converts API/network errors into user-readable diagnosis + next step.
- Tab-level load failures include retry action and context (`source fetch`, `job fetch`, etc.).
- Error copy supports localization and severity levels.
**Tests**:
- Unit tests for error-code-to-message mapping.
- Component tests for retry CTA presence and behavior.
- Contract tests for expected error payload parsing.
**Status**: Not Started

## Stage 2: Run-Focused Remediation UX
**Goal**: Help users resolve failed runs without leaving run context.
**Success Criteria**:
- `RunDetailDrawer` shows remediation suggestions based on error class (auth, 403, timeout, parse failure).
- Filtered-item explanations use available fields (`filtered_sample`, filter tallies) where present.
- "Try again" actions are offered where safe (`rerun`, `test source`, `edit schedule` deep links).
**Tests**:
- Integration tests for remediation hint rendering by error type.
- Component tests for filtered-sample visibility and empty-state fallback.
- E2E test for failed run -> remediation action -> successful follow-up run.
**Status**: Not Started

## Stage 3: Import Recovery Controls
**Goal**: Allow targeted recovery from partial OPML import failures.
**Success Criteria**:
- Import result view supports "retry failed only" and CSV/JSON export of failed entries.
- Failed rows preserve reason codes to avoid blind retries.
- Recovery flow avoids duplicate successful imports by default.
**Tests**:
- Integration tests for retry-failed-only payload generation.
- Unit tests for dedupe logic in re-import path.
- E2E test for partial-failure import recovery workflow.
**Status**: Not Started

## Dependencies

- Error taxonomy should align with notification severity handling in H1.
- Retry and rerun actions must respect permissions and rate-limit controls from backend.
