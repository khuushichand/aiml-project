# Implementation Plan: Characters Gap 04 - Query Dimensions UI Surface (2026-02-19)

## Issue Summary

Server-side query supports more dimensions (date ranges and last-used sorting) than are currently surfaced in characters UI controls.

## Stage 1: Align Query Capability Matrix
**Goal**: Map backend-supported query/sort parameters to intended UI controls.
**Success Criteria**:
- Capability matrix is documented for API params and UI fields.
- Unsupported/ambiguous combinations are explicitly excluded.
- Default query behavior is defined.
**Tests**:
- API-level tests for each planned query/sort dimension.
- Unit tests for query-state serializer defaults.
**Status**: Complete
**Update (2026-02-19)**:
- Confirmed UI-to-API mapping contract in manager query serialization:
  - Created range: `created_from` / `created_to`
  - Updated range: `updated_from` / `updated_to`
  - Last-used sort: UI `lastUsedAt` -> API `last_used_at`
- Added deterministic date-boundary serializer (`YYYY-MM-DD` -> ISO start/end-of-day UTC) for stable request payloads.
- Confirmed date-range filters force server-query mode even when legacy rollout flag is disabled, preventing client-side fallback from dropping server-only dimensions.

## Stage 2: Implement Missing Filters and Sort Controls
**Goal**: Expose date-range and last-used dimensions in characters UI.
**Success Criteria**:
- Created/updated date range controls map to server params.
- Sort controls include `last_used_at` where applicable.
- Query-state serialization includes all new fields consistently.
**Tests**:
- Frontend integration tests for UI control to request-param mapping.
- API integration tests for date-range plus sort interactions.
**Status**: Complete
**Update (2026-02-19)**:
- Added created/updated date filter controls in `Manager.tsx` (from/to for each range).
- Wired new controls through server query params and legacy page-query fallback request payloads.
- Added table sort column for `Last used` and mapped sort serialization to `sort_by=last_used_at`.
- Added manager integration coverage in `Manager.first-use.test.tsx` for:
  - date range -> query param serialization,
  - forced server query mode when rollout flag is disabled,
  - persisted last-used sort mapping.

## Stage 3: Reset/Bookmark/Share Query-State Reliability
**Goal**: Ensure new controls behave correctly with clear-filters and URL/query-state persistence.
**Success Criteria**:
- Clear-filters resets all newly added controls.
- URL/query-state hydration preserves selected filters and sorts.
- Empty-state and loading-state UX remains clear with new dimensions.
**Tests**:
- UI tests for clear/reset behavior.
- Integration tests for query-state round-trip serialization.
**Status**: In Progress
**Update (2026-02-19)**:
- Completed clear-filter reset behavior for created/updated date controls in both primary filter toolbar and filtered-empty-state reset action.
- Added test coverage verifying date filters reset and query params clear after reset.
- Remaining: URL/query-state hydration/bookmark round-trip for the new date and sort dimensions.
