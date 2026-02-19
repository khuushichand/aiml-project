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
**Status**: Complete

### Stage 1 Implementation Notes (2026-02-18)
- Added shared error taxonomy + mapping utility:
  - `shared/watchlists-error.ts` normalizes status/error payloads into contextual diagnosis + next-step guidance.
  - Handles network, timeout, auth/permission, rate-limit, not-found, and server classes with severity mapping.
- Wired tab-level contextual recovery banners with retry CTA:
  - `RunsTab` load failures now render an in-context `Alert` with retry action.
  - `JobsTab` load failures now render an in-context `Alert` with retry action.
  - `SourcesTab` load failures now render an in-context `Alert` with retry action.
- Localization support added for shared error copy under `watchlists.errors` keys.
- Verification coverage:
  - Unit: `shared/__tests__/watchlists-error.test.ts` (classification + payload parsing).
  - Component: `RunsTab.load-error-retry`, `JobsTab.load-error-retry`, `SourcesTab.load-error-retry`.

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
**Status**: Complete

### Stage 2 Implementation Notes (2026-02-18)
- Added run-failure classification and remediation wiring:
  - Extended `run-notifications.ts` with `classifyRunFailure` for auth/rate-limit/timeout/dns/tls/network/unknown classes.
  - Reused `getRunFailureHint` as the primary remediation guidance text for failed runs.
- Upgraded `RunDetailDrawer` failure UI:
  - Failed runs now show a remediation alert with action controls directly in run context.
  - Added safe recovery actions:
    - `Retry run` (re-triggers monitor run via `triggerWatchlistRun`).
    - `Edit monitor schedule` (deep-link to monitor editor via Jobs tab).
    - `Review source settings` for source/connectivity-related failure classes.
- Improved filter diagnostics:
  - Added filtered-item sample section when `filtered_sample` is present.
  - Added explanatory copy that ties sample items to filter tallies for tuning include/exclude rules.
- Verification coverage:
  - `RunDetailDrawer.source-column.test.tsx` now covers remediation actions, retry flow, and filtered sample diagnostics.
  - `run-notifications.test.ts` remains green with added classification support.
  - `apps/extension/tests/e2e/watchlists.spec.ts` includes `activity run-details remediation can retry a failed run` to validate failed-run diagnostics and in-context retry handoff to a follow-up run detail.

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
**Status**: Complete

### Stage 3 Implementation Notes (2026-02-18)
- Extended `SourcesBulkImport` with post-import recovery controls for partial failures:
  - Added `Retry failed only` action to re-run import against a generated OPML containing only retryable failed rows.
  - Added failed-entry exports:
    - `Export failed CSV`
    - `Export failed JSON`
- Added structured failure reason codes on failed rows:
  - `duplicate_existing`, `duplicate_file`, `missing_url`, `invalid_url`, `auth`, `timeout`, `network`, `import_error`.
  - Rendered reason-code tags in failed-results table for quick diagnosis.
- Duplicate-safe retry defaults:
  - Retry flow excludes non-retryable duplicate/invalid entries by default.
  - Retry action is disabled when only non-retryable failures remain.
- Verification coverage:
  - `SourcesBulkImport.preflight-commit.test.tsx` now covers:
    - retry-failed-only scope generation
    - duplicate-safe retry disable behavior
    - existing preflight + commit regression paths
  - `apps/extension/tests/e2e/watchlists.spec.ts` now includes `feeds OPML import supports retry failed only recovery flow` to validate end-to-end partial-failure recovery and retry scope isolation.

## Dependencies

- Error taxonomy should align with notification severity handling in H1.
- Retry and rerun actions must respect permissions and rate-limit controls from backend.
